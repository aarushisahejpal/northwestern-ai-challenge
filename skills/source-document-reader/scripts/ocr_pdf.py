#!/usr/bin/env python3
"""OCR an external primary-source PDF (e.g. a court filing) to searchable text.

For outside-data verification only — the LDA/press corpus never needs this
(every corpus record already carries clean text + a raw-record pointer).
Some external PDFs (certain e-filing systems) embed fonts with no
ToUnicode CMap: pypdf/pdfminer/poppler all extract glyph-index garbage from
them, not text. Rendering each page to an image and OCR'ing the pixels
sidesteps that entirely.

Requires the Tesseract OCR engine on PATH (or set --tesseract-cmd):
  Windows : winget install --id UB-Mannheim.TesseractOCR
  macOS   : brew install tesseract
  Linux   : apt-get install tesseract-ocr

Usage:
  python ocr_pdf.py --pdf data/SEC_comp26458.pdf --out data/SEC_comp26458.ocr.txt
  python ocr_pdf.py --pdf data/SEC_comp26458.pdf --grep Innovairrs
"""

import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def ocr_pdf(pdf_path, dpi, tesseract_cmd):
    import fitz
    import pytesseract

    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc, 1):
        pix = page.get_pixmap(dpi=dpi)
        img_bytes = pix.tobytes("png")
        import io

        from PIL import Image

        img = Image.open(io.BytesIO(img_bytes))
        text = pytesseract.image_to_string(img)
        pages.append(text)
        print(f"  OCR'd page {i}/{doc.page_count}", file=sys.stderr)
    return pages


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf", required=True, type=Path)
    ap.add_argument("--out", type=Path, help="write paginated OCR text here")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--grep", help="case-insensitive keyword to search for after OCR'ing")
    ap.add_argument("--tesseract-cmd", help="path to tesseract.exe if not on PATH")
    args = ap.parse_args()

    if not args.pdf.exists():
        sys.exit(f"not found: {args.pdf}")

    pages = ocr_pdf(args.pdf, args.dpi, args.tesseract_cmd)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            for i, text in enumerate(pages, 1):
                f.write(f"\n===== PAGE {i} =====\n{text}")
        print(f"wrote {args.out} ({len(pages)} pages)")

    if args.grep:
        pat = re.compile(re.escape(args.grep), re.IGNORECASE)
        hits = 0
        for i, text in enumerate(pages, 1):
            for line in text.splitlines():
                if pat.search(line):
                    print(f"p{i}: {line.strip()}")
                    hits += 1
        print(f"\n{hits} line(s) matched {args.grep!r} across {len(pages)} pages")


if __name__ == "__main__":
    main()
