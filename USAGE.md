# Usage Guide

## Setup

**Prerequisites:** Python 3.10+, [uv](https://docs.astral.sh/uv/getting-started/installation/)

```bash
uv sync
cp .env.example .env
# Set GOOGLE_API_KEY in .env
```

---

## Step 1 — Convert PDFs to Markdown

Drop PDFs into `input/` then run:

```bash
uv run pdf2md
```

Or specify folders explicitly:

```bash
uv run pdf2md --input path/to/pdfs --output path/to/output
```

Failed PDFs land in `retry/` with `_error.log` files. The extractor runs a three-step fallback chain:

1. **Docling** — primary extractor, handles most readable PDFs
2. **PyMuPDF** — fallback when Docling output is sparse
3. **OCR (Tesseract via PyMuPDF)** — fallback for image-only / scanned PDFs with no text layer

Tesseract must be installed for OCR support:
```bash
brew install tesseract tesseract-lang
```

If Tesseract is unavailable and all else fails, the sparse Docling result is used as a last resort rather than failing completely.

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--input` | `input/` | Folder containing PDFs |
| `--output` | `output/` | Destination for `.md` files |
| `--retry` | `retry/` | Folder for failed PDFs |
| `--concurrency` | from `.env` | Max parallel PDFs |

---

## Step 2 — Review in the demo viewer

```bash
uv run uvicorn demo.server:app --reload
```

Open **http://localhost:8000** (use `--port 8001` if 8000 is busy).

The viewer shows three tabs per document:
- **Rendered** — formatted markdown preview
- **Diff** — line-by-line comparison against a reference file (if one exists)
- **Raw MD** — source markdown (access code: `pdf2md2026`)

### Where demo files live

The demo server serves files from two locations:

| What | Folder | URL path |
|------|--------|----------|
| Source PDFs | `attachments/` (repo root) | `/attachments/<filename>` |
| Converted markdown | `demo/data/` | `/data/<filename>` |

### Adding a document to the demo viewer

**1. Convert the PDF** — output directly into `demo/data/`:

```bash
# Convert all PDFs in demo/attachments/ at once
uv run pdf2md --input demo/attachments --output demo/data

# Or convert a single file from anywhere and copy PDF manually
uv run pdf2md --input path/to/file.pdf --output demo/data
cp path/to/file.pdf attachments/
```

If the PDF is image-only (scanned, no text layer), both Docling and PyMuPDF will fail. The file will land in `retry/` with an `_error.log`. These need an OCR pre-processing step before conversion.

**2. Register it in `demo/index.html`** — two places:

In the `<select>` dropdown (around line 341):
```html
<option value="mykey">My Document.pdf</option>
```

In the `DOCS` JavaScript object (around line 456):
```js
mykey: {
  label: 'My Document.pdf',
  pdf:   'attachments/My Document.pdf',
  md:    'data/My Document.md',
  // ref and refNote are optional — used by the Diff tab
},
```1

**3. Reload the browser** — hard refresh (Cmd+Shift+R) to bypass cache.

You can also upload any PDF directly from the brower for a live conversion.

---

## Step 3 — Export to TMX / CSV for translation

Convert markdown files to TMX 1.4 or CSV format for use in CAT tools (SDL Trados, memoQ, Wordfast, etc.):

```bash
# Single file — both formats
uv run pdf2export --input output/myfile.md --src-lang de-DE --tgt-lang en-GB

# Entire folder — TMX only
uv run pdf2export --input output/ --output exports/ --format tmx --src-lang de-DE --tgt-lang en-GB
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--input` | required | A `.md` file or folder of `.md` files |
| `--output` | same as `--input` | Destination folder |
| `--format` | `both` | `tmx`, `csv`, or `both` |
| `--src-lang` | `de-DE` | Source language BCP 47 code |
| `--tgt-lang` | `en-GB` | Target language BCP 47 code |

**Segmentation rules:**
- Each paragraph → one segment
- Each heading → one segment (hash prefix stripped)
- Each table row → one segment (cells joined with ` | `)
- YAML front matter and HTML comments are skipped
- Inline markdown syntax (`**bold**`, `*italic*`, etc.) is stripped to plain text

**TMX output format** (1.4, source populated, target empty):

```xml
<tu tuid="1">
  <tuv xml:lang="de-DE"><seg>Diagnose: Serologie: 0 Rh positiv</seg></tuv>
  <tuv xml:lang="en-GB"><seg></seg></tuv>
</tu>
```

**CSV output format:**

```
"id","de-DE","en-GB"
"1","Diagnose: Serologie: 0 Rh positiv",""
```

---

## Configuration (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | — | Google AI Studio API key (required for pdf2md) |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model |
| `MAX_CONCURRENT_PDFS` | `5` | PDFs in parallel |
| `MAX_CONCURRENT_PAGES` | `10` | Pages sent to Gemini in parallel |

---

## Step 4 — Extract structured data (CSV / XLSX)

```bash
# Single PDF → JSON artifacts + CSV + XLSX
uv run pdf2excel --input input/report.pdf --output output/

# Folder of PDFs, 4 parallel workers
uv run pdf2excel --input input/ --output output/ --workers 4

# Phase 1 only (extraction → JSON artifacts, no XLSX yet)
uv run pdf2extract --input input/ --intermediate intermediate/

# Explicit file list
uv run pdf2excel --files a.pdf b.pdf c.pdf --output output/
```

Output per run:
```
output/
  batch_results.xlsx      ← main workbook (Summary, Table_NNN, Warnings sheets)
  batch_report.json       ← counts, timings, extraction methods
  failed_files.json       ← any PDFs that errored
  csv/<stem>/
    <stem>__table_001.csv ← one per detected table
    <stem>__fields.csv    ← key-value pairs extracted from text
    <stem>__pages.csv     ← page text fallback (when no tables found)
    <stem>__warnings.csv  ← extraction warnings

intermediate/
  <stem>.extracted_document.json  ← raw IR (resume/retry)
  <stem>.structured_record.json   ← field/line-item record
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--input` | required | PDF file or folder (mutually exclusive with `--files`) |
| `--files` | — | Explicit list of PDF paths |
| `--output` | `output/` | Output folder |
| `--intermediate` | `intermediate/` | JSON artifact folder |
| `--workers` | `2` | Parallel extraction workers |
| `--force` | off | Re-extract even if artifacts exist |
| `--template` | — | Optional `.xlsx` template to append rows into |

Schemas for field extraction live in `schemas/` (`generic_invoice.json`, `logistics_load.json`). Schema-guided LLM extraction is P2 — current extraction is heuristic (key-value text patterns + raw table capture).

---

## Project structure

```
src/pdf_to_markdown/
  cli.py              ← pdf2md entry point
  export_cli.py       ← pdf2export entry point (TMX/CSV translation export)
  extract_cli.py      ← pdf2extract entry point (Phase 1 only)
  excel_cli.py        ← pdf2excel entry point (full pipeline)
  config.py           ← loads .env settings
  extractor.py        ← Docling → PyMuPDF fallback
  llm.py              ← async Gemini client
  assembler.py        ← merges page fragments
  validator.py        ← heading hierarchy check
  pipeline.py         ← async batch orchestrator
  exporter.py         ← markdown segmenter, TMX/CSV writers (translation)
  structured/
    models.py         ← ExtractedDocument, ExtractedTable, StructuredRecord IR
    extract_document.py ← PDF → IR (raw tables + text blocks)
    csv_writer.py     ← IR → CSV files
    xlsx_writer.py    ← IR → XLSX workbook
    batch_runner.py   ← two-phase parallel extraction + sequential XLSX write

demo/
  server.py           ← FastAPI demo server
  index.html          ← viewer UI
  data/               ← pre-converted .md files for the viewer
  attachments/        ← source PDFs served by the viewer

schemas/
  generic_invoice.json
  logistics_load.json
```
