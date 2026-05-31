# KIA — Feeding Knowledge (ingestion guide)

KIA learns in two ways:
- **Knowledge base (RAG)** — instant, reliable for FACTS. Ask via `/brain <question>` in chat.
- **Weights (fine-tune)** — periodic, for STYLE/skill. See PHASE3_TRAINING_PLAN.md.

For facts (TPA records, papers, screenshots) always prefer RAG ingestion below.
Server-side content-hash dedup means re-running any ingester skips already-learned content.

## In chat (quick, ad-hoc)
- `/learn <text>`  — teach KIA pasted text (indexes now + queues for next fine-tune)
- `/brain <question>` — answer using KIA's knowledge base (hybrid keyword+vector retrieval)

## Structured data — CSV / Excel  (one clean record per row)
```
python scripts/ingest_structured.py "C:\data\tpa_database.csv"
python scripts/ingest_structured.py "C:\data\book.xlsx" --sheet Sheet1 --group 5
```
Needs `pip install openpyxl` for .xlsx. Each row becomes "Col: val | Col: val" so KIA can
answer about specific fields (address, email, specialty, ...).

## Documents — PDF / text / markdown / abstracts
```
python scripts/ingest_docs.py C:\papers --to-rag            # ground for recall (recommended)
python scripts/ingest_docs.py C:\papers --to-train \
  --teacher-url https://ollama.com/v1 --teacher-model gpt-oss:120b --teacher-key $env:TEACHER_KEY
```
Needs `pip install pypdf`.

## Images / scans / screenshots — OCR
Runs Tesseract locally, sends extracted text to KIA.
```
# 1) Install Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
# 2) pip install pytesseract pillow pdf2image    (pdf2image+Poppler only for image-only PDFs)
python scripts/ingest_images.py C:\scans
python scripts/ingest_images.py C:\scans\table.png --tesseract "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

## Codebase
```
python scripts/index_codebase.py C:\dev --reindex
```

## Multi-teacher distillation (training data from other models)
```
python scripts/distill_multiteacher.py            # curated teachers.json
python scripts/distill_multiteacher.py --auto     # one best model per domain
python scripts/distill_multiteacher.py --dedupe-only
```

## Maintenance
- Clear the whole knowledge base (start fresh):  POST /api/v1/knowledge/clear
- Retrieval is HYBRID (keyword + vector) so exact names (a company, a class) match well.
- Honest split: RAG = facts (instant, accurate); fine-tune = voice/skill (periodic, GPU).

<!-- ci: revalidate after lint fixes -->
