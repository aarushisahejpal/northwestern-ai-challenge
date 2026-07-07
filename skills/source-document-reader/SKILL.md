---
name: source-document-reader
description: Turn an external primary-source PDF (court filing, SEC complaint, agency letter, contract) into searchable, page-anchored text a claim can cite. Uses render-to-image OCR that survives the broken embedded fonts common in e-filing systems (PACER/ECF and many state portals), where ordinary text extraction returns glyph-index garbage. For OUTSIDE-source documents only — the LDA/press corpus already ships as clean, citable text and must never be routed through this. Consumed by finding-verifier (re-deriving a claim that rests on an external document) and available to outside-context-scan (reading a fetched primary source during a landscape check).
---

# Source Document Reader

Converts an external PDF into paginated, greppable text plus a stable citation key, so a
claim that depends on a document *outside* this project's corpus is as reproducible as one
that rests on an internal record. This is the outward-facing counterpart to the corpus's
`show_record.py`: `show_record.py` resolves an internal citation key to a raw record; this
skill turns an outside document into a citable key in the first place.

**Scope guard.** Only for external primary sources. The Senate/House LDA and congressional
press corpora already carry clean text + a raw-record pointer on every row — they are cited
via `show_record.py` and must never be OCR'd. If you're reaching for this skill against a
corpus record, stop: you want `skills/lda-corpus-loader`.

## Why render-to-image instead of text extraction

Some e-filing systems embed fonts with no ToUnicode CMap. `pypdf`, `pdfminer`, and poppler
all "extract" glyph indices from those PDFs, not characters — you get plausible-looking
mojibake that silently corrupts a quote. `scripts/ocr_pdf.py` renders each page to a raster
image with PyMuPDF and OCRs the *pixels* with Tesseract, sidestepping the font layer
entirely. This is why it works on court filings where `pdfplumber` produces garbage; it is
also slower (~1s+/page), so it's a verification tool, not a bulk pipeline.

## Setup

The OCR engine (Tesseract) is a native binary installed at the OS level — pip cannot install
it. Install it once, then the Python wrappers.

```
# 1. Tesseract engine
Windows : winget install --id UB-Mannheim.TesseractOCR
macOS   : brew install tesseract
Linux   : apt-get install tesseract-ocr

# 2. Python wrappers (pinned in requirements.txt; verified on Python 3.12)
pip install pymupdf==1.28.0 pytesseract==0.3.13 pillow==12.3.0
```

If Tesseract isn't on PATH (common on Windows), pass `--tesseract-cmd` (see below). The
script is self-contained — it has no dependency on the rest of this repo, so it drops into
any project that needs to read PDFs.

## Usage

```bash
# OCR a document to page-separated text
python skills/source-document-reader/scripts/ocr_pdf.py \
    --pdf data/SEC_comp26458.pdf --out data/SEC_comp26458.ocr.txt

# Quick keyword check without writing a file
python skills/source-document-reader/scripts/ocr_pdf.py \
    --pdf data/SEC_comp26458.pdf --grep Innovairrs

# Tesseract not on PATH, and a noisy scan that wants higher resolution
python skills/source-document-reader/scripts/ocr_pdf.py --pdf scan.pdf --out scan.ocr.txt \
    --dpi 300 --tesseract-cmd "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

Flags: `--pdf` (required) · `--out` (write page-separated text) · `--grep` (case-insensitive
search after OCR) · `--dpi` (default 200; raise to 300+ for small type or old scans) ·
`--tesseract-cmd` (path to `tesseract` if not on PATH). Output pages are delimited with
`===== PAGE n =====`, which is what makes page-anchored citation keys stable.

## Citation convention for external documents

This project cites internal records by a stable key resolvable through `show_record.py`;
external documents need the same discipline so a reader can independently re-derive the
claim from the same source. For any outside PDF a locked claim depends on:

1. **Slug + pin.** Give the document a stable `source-slug` (short, lowercase, e.g.
   `sec-v-innovairrs-2026-complaint`). Record its provenance in a one-line sidecar committed
   next to the finding: retrieval URL, retrieved date, and the `sha256` of the source PDF.
   The PDF itself lives in gitignored `data/` (like the raw corpus); the pin is what makes
   the citation reproducible without committing the binary.
2. **OCR to a committed text file.** Run `ocr_pdf.py --out <source-slug>.ocr.txt` and commit
   that `.ocr.txt` (it's small text, and it's the artifact the citation actually points at).
   Keep the `===== PAGE n =====` separators intact.
3. **Cite page-anchored.** The citation key is `<source-slug>:p<N>` — e.g.
   `sec-v-innovairrs-2026-complaint:p12`. It names the document and the exact page, mirroring
   the internal `src_file:src_line` form.
4. **Quote, don't paraphrase, and confirm the pixels.** Because OCR is imperfect, an
   external-source claim quotes the exact OCR'd line, and a human confirms that line against
   the rendered page image before the finding locks. This is the verdict step `finding-verifier`
   already runs for internal claims — the same ladder (`verified | attribution error |
   overstated | fabricated`), applied to an outside document.

The effect: an external-source citation is auditable end to end — slug → provenance pin →
committed OCR text → page → confirmed quote — with the same rigor as an internal one, and
without ever committing a copyrighted or bulky source PDF.

## Batching a corpus

`ocr_pdf.py` reads one PDF at a time — right for verifying a single cited document. To read a
*corpus* of PDFs (e.g. a docket of court filings) rather than spot-check one, wrap it in a
loop that walks a directory, skips files already OCR'd (Tesseract is slow), and emits both a
per-file `.ocr.txt` and a combined index. That batch wrapper belongs here, alongside the
single-document script — not in any consumer skill.
