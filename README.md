# Export Desktop Proof

An independent macOS InDesign script for the Preview/Xerox workflow tested on
the VersaLink C7000. It exports a PDF and turns explicit pure CMYK/RGB black in
page content and nested PDF Form graphics into DeviceGray black. Photographic
image data, profiles, gray tints and nonblack colors are preserved.

## Use

1. In InDesign, open Window > Utilities > Scripts.
2. Under User, run **Export Desktop Proof** instead of File > Export.
3. Choose a destination (default name: `Document-Desktop-Proof.pdf`).
4. In the normal PDF export dialog, choose your page range and other settings.
   Start with **High Quality Print**, **Output > No Color Conversion**. Export
   one PDF, not separate files per page. Leave **View PDF after Exporting** off:
   that would open the intermediate PDF before conversion, not the final proof.
5. After export and verification, Finder opens with the finished PDF selected.
   Open it in Preview and print with your usual color settings. Normal success
   goes straight to Finder; warnings still appear when needed.

File > Export remains unchanged. The script does not edit or save the INDD,
outline text, rasterize pages, change the printer, or run a background service.
Unsaved documents can be exported. Cancellation produces no final proof.
An existing output requires confirmation; processing and verification finish
before replacement. On failure, the intermediate export is retained for diagnosis.

Use the resulting PDF for desktop proofs. It is not a substitute for the
production PDF required by a commercial printer, and PDF/X conformance is not
revalidated after conversion. The original document and normal export workflow
remain available.

## Scope and limitations

Only exact `0 0 0 1 k/K` and `0 0 0 rg/RG` instructions are converted. This does
not force gray text, rich black, spot/ICCBased black, patterns or raster images
to black. Existing DeviceGray black is retained. Explicit black in placed PDF
Form XObjects is supported. Opacity and overprinting are retained; transparent
black remains transparent. Shadings and annotation appearances are not rewritten.
Default color-space overrides and interactive forms are rejected for inspection.
Use No Color Conversion to avoid converting native InDesign black into rich black.

The helper verifies page boxes, text extraction, page resource dictionaries,
encoded image bytes, font streams and profiles before publishing. PDF numeric
serialization can round coordinates below one millionth of a point. A physical
print is still the acceptance check for a new printer/document combination.

## Installation and dependencies

Requires macOS, InDesign ExtendScript/AppleScript, and Python 3.10 or newer.
This is a standalone repository with its own Python environment; it does not
depend on the math project. From this repository's directory, set it up with:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

The script finds `.venv/bin/python` alongside its own source files. Recreate
the environment if you move or clone this repository to a different location.

A Scripts Panel launcher should use `$.evalFile(File("/absolute/path/to/Export Desktop Proof.jsx"));`
with `#target indesign`. Update the launcher's absolute path if you move the
repository. The launcher can be removed to uninstall the command.

For an existing PDF, the same helper can run independently:

```sh
.venv/bin/python desktop_proof.py input.pdf proof.pdf
```

Add `--replace` only to intentionally replace an existing proof. Source and
destination must differ. Run automated checks with:

```sh
.venv/bin/python -m unittest discover -s . -p 'test_*.py'
```
