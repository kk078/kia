#!/usr/bin/env python3
"""OCR-ingest images (and image-only PDFs) into KIA's knowledge base.

Runs Tesseract OCR locally on each image, then sends the extracted text to KIA's
/knowledge/ingest (server-side content-hash dedup applies). Good for screenshots,
scanned documents, photos of tables, etc.

Setup (Windows):
  1) Install Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki
     (default path C:\\Program Files\\Tesseract-OCR\\tesseract.exe)
  2) pip install pytesseract pillow pdf2image
     For image-only PDFs you also need Poppler: https://github.com/oschwartz10612/poppler-windows
Usage (PowerShell):
  python scripts/ingest_images.py C:\\scans
  python scripts/ingest_images.py C:\\scans\\one.png
  python scripts/ingest_images.py C:\\scans --tesseract "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.request

API = "http://localhost:8000"
IMG_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp"}


def ocr_image(path: str) -> str:
    import pytesseract
    from PIL import Image

    with Image.open(path) as img:
        rgb = img.convert("RGB") if img.mode != "RGB" else img
        return pytesseract.image_to_string(rgb).strip()


def ocr_pdf(path: str) -> str:
    """OCR an image-only PDF by rasterizing pages (needs pdf2image + Poppler)."""
    import pytesseract
    try:
        from pdf2image import convert_from_path
    except ImportError:
        raise SystemExit("For PDF OCR install:  pip install pdf2image  (and Poppler)")
    pages = convert_from_path(path)
    out = []
    for pg in pages:
        rgb = pg.convert("RGB")
        out.append(pytesseract.image_to_string(rgb).strip())
    return "\n\n".join(out)


def post(api: str, content: str, source: str) -> int:
    body = json.dumps({"content": content, "source": source}).encode()
    req = urllib.request.Request(api.rstrip("/") + "/api/v1/knowledge/ingest",
                                 data=body, headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=600) as r:
        return len(json.loads(r.read().decode()).get("chunk_ids", []))


def collect(target: str) -> list[str]:
    if os.path.isfile(target):
        return [target]
    files = []
    for dp, _, names in os.walk(target):
        for n in names:
            ext = os.path.splitext(n)[1].lower()
            if ext in IMG_EXT or ext == ".pdf":
                files.append(os.path.join(dp, n))
    return files


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="image/PDF file or a folder of them")
    ap.add_argument("--api", default=API)
    ap.add_argument("--tesseract", default="", help="path to tesseract.exe if not on PATH")
    args = ap.parse_args()

    if args.tesseract:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = args.tesseract

    files = collect(args.target)
    print(f"Found {len(files)} image/PDF files")
    indexed = skipped = empty = failed = 0
    for full in files:
        rel = os.path.basename(full)
        ext = os.path.splitext(full)[1].lower()
        try:
            text = ocr_pdf(full) if ext == ".pdf" else ocr_image(full)
        except SystemExit:
            raise
        except Exception as e:
            print(f"  !! {rel}: {e}")
            failed += 1
            continue
        if not text.strip():
            print(f"  (no text found) {rel}")
            empty += 1
            continue
        try:
            n = post(args.api, f"OCR text from image {rel}:\n{text}", f"ocr:{rel}")
            if n:
                indexed += 1
                print(f"  + {rel}  ({len(text)} chars, {n} chunks)")
            else:
                skipped += 1
                print(f"  = {rel}  (duplicate-skipped)")
        except Exception as e:
            print(f"  !! post {rel}: {e}")
            failed += 1

    print(f"\nDone. indexed={indexed} duplicate_skipped={skipped} empty={empty} failed={failed}")
    print("Ask KIA about it in chat with:  /brain <your question>")


if __name__ == "__main__":
    main()
