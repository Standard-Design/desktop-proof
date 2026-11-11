import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (ArrayObject, ContentStream, DecodedStreamObject,
                          DictionaryObject, NameObject, NumberObject)

from desktop_proof import convert, normalize, resource_fingerprint


def stream(data):
    obj = DecodedStreamObject()
    obj.set_data(data)
    return obj


class ProofTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="proof test's ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def fixture(self, content=b'0 0 0 1 k 10 10 20 20 re f', nested=False):
        writer = PdfWriter()
        page = writer.add_blank_page(100, 100)
        resources = DictionaryObject()
        page[NameObject('/Resources')] = resources
        image = stream(b'\x00\x20\x80')
        image.update({NameObject('/Type'): NameObject('/XObject'),
                      NameObject('/Subtype'): NameObject('/Image'),
                      NameObject('/Width'): NumberObject(1), NameObject('/Height'): NumberObject(1),
                      NameObject('/BitsPerComponent'): NumberObject(8),
                      NameObject('/ColorSpace'): NameObject('/DeviceRGB')})
        xobjects = DictionaryObject({NameObject('/Im0'): writer._add_object(image)})
        resources[NameObject('/XObject')] = xobjects
        if nested:
            form = stream(content)
            form.update({NameObject('/Type'): NameObject('/XObject'),
                         NameObject('/Subtype'): NameObject('/Form'),
                         NameObject('/BBox'): ArrayObject([NumberObject(x) for x in [0, 0, 100, 100]]),
                         NameObject('/Resources'): DictionaryObject()})
            xobjects[NameObject('/Fm0')] = writer._add_object(form)
            content = b'q /Fm0 Do Q q /Fm0 Do Q'
        page[NameObject('/Contents')] = writer._add_object(stream(content + b' q /Im0 Do Q'))
        path = self.root / 'source.pdf'
        writer.write(path)
        return path

    def test_exact_black_only_and_images_preserved(self):
        source = self.fixture(b'0 0 0 1 k 0 0 0 RG 0 0 0 0.1 k 0.004 0.004 0.004 rg 1 0 0 rg')
        original = source.read_bytes()
        target = self.root / 'proof.pdf'
        result = convert(source, target)
        self.assertEqual(result['converted'], 2)
        before, after = PdfReader(source), PdfReader(target)
        self.assertEqual(resource_fingerprint(before.pages[0]['/Resources']), resource_fingerprint(after.pages[0]['/Resources']))
        operations = ContentStream(after.pages[0].get_contents(), after).operations
        self.assertEqual(operations[0], ([0], b'g'))
        self.assertEqual(operations[1], ([0], b'G'))
        self.assertEqual(operations[2][1], b'k')
        self.assertEqual(source.read_bytes(), original)

    def test_shared_form(self):
        target = self.root / 'proof.pdf'
        result = convert(self.fixture(nested=True), target)
        self.assertEqual(result['converted'], 1)
        r = PdfReader(target)
        form = r.pages[0]['/Resources']['/XObject']['/Fm0']
        self.assertEqual(ContentStream(form, r).operations[0], ([0], b'g'))

    def test_later_sc_restores_original_space_and_stack(self):
        writer = PdfWriter()
        parsed, count = normalize(ContentStream(stream(b'0 0 0 1 k q 1 0 0 rg Q 0 1 0 0 sc'), writer))
        self.assertEqual(count, 1)
        self.assertEqual(parsed.operations[-2], ([NameObject('/DeviceCMYK')], b'cs'))
        self.assertEqual(parsed.operations[-1][1], b'sc')

    def test_refuses_inherited_form_color(self):
        source = self.fixture(b'0 0 0 1 sc', nested=True)
        with self.assertRaisesRegex(ValueError, 'inherited'):
            convert(source, self.root / 'proof.pdf')

    def test_failed_conversion_preserves_existing_target(self):
        source = self.fixture(b'Q')
        target = self.root / 'proof.pdf'
        target.write_bytes(b'previous proof')
        with self.assertRaisesRegex(ValueError, 'Unbalanced'):
            convert(source, target, replace=True)
        self.assertEqual(target.read_bytes(), b'previous proof')

    def test_requires_explicit_replace(self):
        source = self.fixture()
        target = self.root / 'proof.pdf'
        convert(source, target)
        with self.assertRaises(FileExistsError):
            convert(source, target)
        self.assertEqual(convert(source, target, replace=True)['converted'], 1)

    def test_source_cannot_be_overwritten(self):
        source = self.fixture()
        before = source.read_bytes()
        with self.assertRaisesRegex(ValueError, 'different'):
            convert(source, source, replace=True)
        self.assertEqual(source.read_bytes(), before)

    def test_no_conversion_for_existing_gray(self):
        self.assertEqual(convert(self.fixture(b'0 g'), self.root / 'proof.pdf')['converted'], 0)


if __name__ == '__main__':
    unittest.main()
