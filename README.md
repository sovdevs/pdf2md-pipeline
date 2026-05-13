# SDEP — Structured Document Extraction Pipeline

Converts PDFs into clean Markdown, structured CSV/XLSX, and TMX/CSV translation exports. Handles readable, scanned/OCR, and multi-layout documents with Gemini-assisted extraction.

**Tech stack:** Python 3.12 · Docling (PDF extraction) · PyMuPDF (fallback) · Gemini 2.0 Flash (structure detection) · uv

---

## Setup

**Prerequisites:** Python 3.10+, [uv](https://docs.astral.sh/uv/getting-started/installation/)

```bash
# 1. Install dependencies
uv sync

# 2. Configure API key
cp .env.example .env
# Edit .env and set GOOGLE_API_KEY=<your Google AI Studio key>
```

Your key needs billing enabled — get one at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

---

## Usage

```bash
# Drop PDFs into input/ then run:
uv run pdf2md

# Or specify folders explicitly:
uv run pdf2md --input path/to/pdfs --output path/to/output

# Adjust parallelism (default: 5 PDFs, 10 pages in parallel):
uv run pdf2md --concurrency 3
```

---

## Output

| Folder | Contents |
|--------|----------|
| `output/` | One `.md` per PDF — YAML front matter + structured Markdown |
| `retry/` | PDFs that failed + `_error.log` files for diagnosis |

Each output file follows this structure:

```markdown
---
titolo: NORME TECNICHE DI ATTUAZIONE ...
comune: MARIANO COMENSE (CO)
tipo: Piano delle Regole
anno: 2023
---

# Document title

## TITOLO I - ...

### ART. 1 - ...

#### 1.1 - ...
```

---

## Configuration (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | — | Google AI Studio API key (required) |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model to use |
| `MAX_CONCURRENT_PDFS` | `5` | PDFs processed in parallel |
| `MAX_CONCURRENT_PAGES` | `10` | Pages sent to Gemini in parallel |

---

## Project structure

```
src/pdf_to_markdown/
  cli.py         ← entry point (argparse)
  config.py      ← loads .env settings
  extractor.py   ← Docling → PyMuPDF fallback
  llm.py         ← async Gemini client, per-page calls
  assembler.py   ← merges page fragments into one .md
  validator.py   ← heading hierarchy check + auto-fix
  pipeline.py    ← async batch orchestrator
```

---

## Running tests

```bash
uv run pytest tests/ -v
```

Tests in `tests/test_extractor.py` run against the sample PDFs in `samples/` (no API key needed).
The LLM test in `tests/test_llm.py` requires a valid API key.
