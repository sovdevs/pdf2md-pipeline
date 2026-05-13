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

Failed PDFs land in `retry/` with `_error.log` files. The extractor uses Docling first and falls back to PyMuPDF if output is suspiciously sparse.

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

Pre-loaded documents can be added by copying PDFs to `attachments/`, markdown files to `demo/data/`, and adding an entry to the `DOCS` object and `<select>` in `demo/index.html`.

You can also upload any PDF directly from the browser for a live conversion.

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

## Project structure

```
src/pdf_to_markdown/
  cli.py           ← pdf2md entry point
  export_cli.py    ← pdf2export entry point
  config.py        ← loads .env settings
  extractor.py     ← Docling → PyMuPDF fallback
  llm.py           ← async Gemini client
  assembler.py     ← merges page fragments
  validator.py     ← heading hierarchy check
  pipeline.py      ← async batch orchestrator
  exporter.py      ← markdown segmenter, TMX/CSV writers

demo/
  server.py        ← FastAPI demo server
  index.html       ← viewer UI
  data/            ← pre-converted .md files for the viewer
  attachments/     ← source PDFs served by the viewer
```
