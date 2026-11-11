"""Produce a desktop-printing PDF with explicit pure black in DeviceGray.

No image decoding/re-encoding or global color conversion. This is a proofing
utility, not a PDF/X production converter. Requires pypdf >= 5.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import tempfile

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream, DecodedStreamObject, NameObject, NumberObject


def normalize(stream, inherited=False):
    """Track original color spaces so later sc/SC operators keep their meaning."""
    spaces = [NameObject('/DeviceGray'), NameObject('/DeviceGray')]
    changed = [False, False]
    stack, result = [], []
    established = [not inherited, not inherited]
    count = 0
    direct = {b'k': (0, '/DeviceCMYK', [0, 0, 0, 1]),
              b'K': (1, '/DeviceCMYK', [0, 0, 0, 1]),
              b'rg': (0, '/DeviceRGB', [0, 0, 0]),
              b'RG': (1, '/DeviceRGB', [0, 0, 0])}
    for args, op in stream.operations:
        if op == b'q':
            stack.append((spaces[:], changed[:], established[:]))
        elif op == b'Q':
            if not stack:
                raise ValueError('Unbalanced PDF graphics state; proof was not written.')
            spaces, changed, established = stack.pop()
        elif op in direct:
            channel, space, black = direct[op]
            spaces[channel] = NameObject(space)
            established[channel] = True
            changed[channel] = list(args) == black
            if changed[channel]:
                args, op = [NumberObject(0)], b'G' if channel else b'g'
                count += 1
        elif op in (b'g', b'G', b'cs', b'CS'):
            channel = int(op in (b'G', b'CS'))
            spaces[channel] = args[0] if op in (b'cs', b'CS') else NameObject('/DeviceGray')
            established[channel] = True
            changed[channel] = False
        elif op in (b'sc', b'SC', b'scn', b'SCN'):
            channel = int(op in (b'SC', b'SCN'))
            if not established[channel]:
                raise ValueError('Placed PDF uses an inherited color space; inspect before conversion.')
            if changed[channel]:
                result.append(([spaces[channel]], b'CS' if channel else b'cs'))
                changed[channel] = False
        result.append((args, op))
    if stack:
        raise ValueError('Unbalanced PDF graphics state; proof was not written.')
    stream.operations = result
    return stream, count


def resource_fingerprint(value, active=None):
    """Compare resource data, allowing only Form content bytes to change."""
    active = set() if active is None else active
    obj = value.get_object() if hasattr(value, 'get_object') else value
    if isinstance(obj, dict):
        if id(obj) in active:
            return 'cycle'
        active.add(id(obj))
        form = obj.get('/Subtype') == '/Form'
        ignored = {'/Length'} | ({'/Filter', '/DecodeParms'} if form else set())
        result = {str(k): resource_fingerprint(v, active) for k, v in obj.items()
                  if str(k) not in ignored}
        if hasattr(obj, '_data') and not form:
            result['encoded_stream_sha256'] = hashlib.sha256(obj._data).hexdigest()
        active.remove(id(obj))
        return result
    if isinstance(obj, list):
        return [resource_fingerprint(v, active) for v in obj]
    if isinstance(obj, (int, float)):
        return float(obj)
    return str(obj)


def file_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def convert(source, target, replace=False):
    source, target = Path(source).resolve(), Path(target).resolve()
    if source == target:
        raise ValueError('Input and output must be different files.')
    initial_target = file_digest(target)
    if initial_target is not None and not replace:
        raise FileExistsError('The proof already exists; explicit replacement is required.')
    original_digest = file_digest(source)
    reader = PdfReader(source)
    if reader.is_encrypted:
        raise ValueError('Export without PDF security, then try again.')
    if reader.trailer['/Root'].get('/AcroForm'):
        raise ValueError('Interactive forms are not supported by this proof exporter.')
    writer = PdfWriter(clone_from=reader)
    converted = 0
    visited = set()

    def check_resources(resources):
        # Default color-space overrides change the meaning of direct operators.
        cs = resources.get('/ColorSpace', {})
        if any(k in cs for k in ('/DefaultCMYK', '/DefaultRGB', '/DefaultGray')):
            raise ValueError('PDF uses default color-space overrides; inspect before conversion.')

    def forms(resources):
        nonlocal converted
        check_resources(resources)
        for key, ref in list(resources.get('/XObject', {}).items()):
            obj = ref.get_object()
            if obj.get('/Subtype') != '/Form' or id(obj) in visited:
                continue
            visited.add(id(obj))
            nested = obj.get('/Resources', resources)
            forms(nested)
            stream, count = normalize(ContentStream(obj, writer), inherited=True)
            if count:
                replacement = DecodedStreamObject()
                replacement.update({k: v for k, v in obj.items()
                                    if str(k) not in ('/Length', '/Filter', '/DecodeParms')})
                replacement.set_data(stream.get_data())
                # Keep shared references to this Form pointing to the same object.
                writer._objects[ref.idnum - 1] = replacement
                replacement.indirect_reference = ref
                visited.add(id(replacement))
                converted += count

    for page in writer.pages:
        forms(page['/Resources'])
        stream, count = normalize(ContentStream(page.get_contents(), writer))
        if count:
            page.replace_contents(stream)
            converted += count

    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix='.desktop-proof-', suffix='.pdf', dir=target.parent)
    os.close(fd)
    temp = Path(temp_name)
    try:
        writer.write(temp)
        check = PdfReader(temp)
        if len(check.pages) != len(reader.pages):
            raise ValueError('Page-count verification failed.')
        for old, new in zip(reader.pages, check.pages):
            if resource_fingerprint(old['/Resources']) != resource_fingerprint(new['/Resources']):
                raise ValueError('Image/font/profile resource verification failed.')
            for box in ('/MediaBox', '/CropBox', '/TrimBox', '/BleedBox', '/ArtBox', '/Rotate'):
                if old.get(box) != new.get(box):
                    raise ValueError('Page geometry verification failed.')
            if old.extract_text() != new.extract_text():
                raise ValueError('Text verification failed.')
        if resource_fingerprint(reader.trailer['/Root'].get('/OutputIntents', [])) != resource_fingerprint(check.trailer['/Root'].get('/OutputIntents', [])):
            raise ValueError('Output-profile verification failed.')
        if file_digest(source) != original_digest:
            raise ValueError('Source PDF changed during conversion; retry the export.')
        if file_digest(target) != initial_target:
            raise ValueError('Destination changed during conversion; existing file was preserved.')
        if initial_target is None:
            # Exclusive publication: do not overwrite a file created concurrently.
            os.link(temp, target)
            temp.unlink()
        else:
            os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    return {'pages': len(reader.pages), 'converted': converted, 'output': str(target)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('target', type=Path)
    parser.add_argument('--replace', action='store_true')
    args = parser.parse_args()
    try:
        result = convert(args.source, args.target, args.replace)
        print(f"Created {result['pages']}-page desktop proof. "
              f"Converted {result['converted']} pure-black color instructions.")
        if not result['converted']:
            print('No explicit RGB/CMYK pure black found. It may already be grayscale, '
                  'or the export may have converted it. Check Output > No Color Conversion.')
    except Exception as exc:
        parser.exit(1, f'Desktop proof failed: {exc}\n')


if __name__ == '__main__':
    main()
