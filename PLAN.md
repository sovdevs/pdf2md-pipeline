Ok # PLAN.md — PDF to Markdown Batch Pipeline

## Architecture overview

```
input/          ← drop PDFs here (or pass --input flag)
output/         ← one .md per PDF written here
retry/          ← PDFs or pages that failed are dumped here with error logs
src/
  pdf_to_markdown/
    __init__.py
    cli.py          ← argparse entry point
    config.py       ← loads .env (GEMINI_API_KEY, concurrency limits)
    extractor.py    ← Docling → PyMuPDF fallback, returns List[PageText]
    llm.py          ← async Gemini 2.0 Flash client, one call per page
    assembler.py    ← merges LLM page outputs into final YAML + Markdown
    validator.py    ← checks heading hierarchy, required front matter fields
    pipeline.py     ← orchestrates async batch over all PDFs
pyproject.toml
.env              ← GEMINI_API_KEY=... (never committed)
.env.example      ← template (committed)
```

**Flow per PDF:**
1. Extract text page-by-page (Docling, fallback PyMuPDF)
2. Send each page to Gemini 2.0 Flash async → structured Markdown fragment
3. Assemble fragments → YAML front matter + full .md body
4. Validate heading hierarchy; fix trivial skips automatically
5. Write to `output/<stem>.md`
6. On any unrecoverable error: copy source PDF + error log to `retry/`

---

## TODO list

### Phase 1 — Project scaffold

- [ ] **1.1** `uv init pdf-to-markdown` inside the project root; confirm `pyproject.toml` is created with `requires-python = ">=3.10"`
- [ ] **1.2** Add dependencies via `uv add`:
  - `docling`
  - `pymupdf`
  - `google-generativeai>=0.8`
  - `python-dotenv`
  - `pyyaml`
  - `aiofiles`
  - `tenacity`  ← for retry logic on Gemini calls
- [ ] **1.3** Add dev dependencies: `uv add --dev pytest ruff`
- [ ] **1.4** Create `src/pdf_to_markdown/` package with empty `__init__.py`
- [ ] **1.5** Create `.env.example`:
  ```
  GEMINI_API_KEY=your_key_here
  GEMINI_MODEL=gemini-2.0-flash
  MAX_CONCURRENT_PDFS=5
  MAX_CONCURRENT_PAGES=10
  ```
- [ ] **1.6** Add `.env` and `output/` and `retry/` to `.gitignore`
- [ ] **1.7** Create `input/`, `output/`, `retry/` folders (add `.gitkeep` to each)

---

### Phase 2 — Config loader (`config.py`)

- [ ] **2.1** Create `src/pdf_to_markdown/config.py`
- [ ] **2.2** Use `python-dotenv` (`load_dotenv()`) to load `.env` at import time
- [ ] **2.3** Expose a `Settings` dataclass (or simple module-level constants):
  - `GEMINI_API_KEY: str` — raise `ValueError` if missing
  - `GEMINI_MODEL: str = "gemini-2.0-flash"`
  - `MAX_CONCURRENT_PDFS: int = 5`
  - `MAX_CONCURRENT_PAGES: int = 10`
  - `INPUT_DIR: Path = Path("input")`
  - `OUTPUT_DIR: Path = Path("output")`
  - `RETRY_DIR: Path = Path("retry")`

---

### Phase 3 — PDF extractor (`extractor.py`)

- [ ] **3.1** Create `src/pdf_to_markdown/extractor.py`
- [ ] **3.2** Define dataclass `PageText(page_number: int, text: str, extraction_method: str)`
- [ ] **3.3** Implement `extract_with_docling(pdf_path: Path) -> list[PageText]`:
  - Use `docling.document_converter.DocumentConverter`
  - Convert PDF; iterate pages; store `.export_to_markdown()` or raw text per page
  - Tag `extraction_method = "docling"`
- [ ] **3.4** Implement `extract_with_pymupdf(pdf_path: Path) -> list[PageText]`:
  - Use `fitz.open(pdf_path)`; iterate pages; call `page.get_text("text")`
  - Tag `extraction_method = "pymupdf"`
- [ ] **3.5** Implement `extract_pages(pdf_path: Path) -> list[PageText]`:
  - Try Docling; if it raises any exception, log warning and fall back to PyMuPDF
  - If both fail, raise `ExtractionError` (custom exception defined in this file)
- [ ] **3.6** Write unit test `tests/test_extractor.py` using one of the sample PDFs in `attachments/`; assert `len(pages) > 0` and `pages[0].text` is non-empty

---

### Phase 4 — Gemini LLM client (`llm.py`)

- [ ] **4.1** Create `src/pdf_to_markdown/llm.py`
- [ ] **4.2** Initialise async Gemini client at module level using `GEMINI_API_KEY` from config
- [ ] **4.3** Define the **system prompt** (string constant `SYSTEM_PROMPT`) that instructs Gemini to:
  - Return only valid Markdown (no prose explanation)
  - Map document structure to `#` / `##` / `###` / `####` correctly
  - Preserve Italian legal text verbatim — no paraphrasing
  - Remove page headers/footers and page numbers that repeat on every page
  - Fix glued words (missing spaces) from OCR artefacts
  - Output YAML front matter block ONLY on page 1 (fields: `titolo`, `comune`, `tipo`, `anno`)
  - If page content is unreadable, output `<!-- UNREADABLE: page N -->`
- [ ] **4.4** Define `PAGE_PROMPT_TEMPLATE: str` — the per-page user message:
  ```
  Page {page_number} of {total_pages}. Raw extracted text follows. Return only the Markdown for this page.

  ---
  {raw_text}
  ---
  ```
- [ ] **4.5** Implement `async def process_page(page: PageText, total_pages: int) -> str`:
  - Call Gemini async API with `SYSTEM_PROMPT` + `PAGE_PROMPT_TEMPLATE`
  - Use `tenacity.retry` with exponential backoff (3 retries, wait 2–30 s) to handle rate-limit errors
  - Return the model's text response stripped of any markdown code fences it may have added
- [ ] **4.6** Write a smoke test `tests/test_llm.py` that calls `process_page` on a single short synthetic page and asserts the result starts with `#` or `##` or contains a heading

---

### Phase 5 — Markdown assembler (`assembler.py`)

- [ ] **5.1** Create `src/pdf_to_markdown/assembler.py`
- [ ] **5.2** Implement `extract_front_matter(page1_md: str) -> tuple[dict, str]`:
  - Parse YAML block between first `---` and second `---`
  - Return `(metadata_dict, body_without_frontmatter)`
  - If no YAML found, return `({}, page1_md)` — validation will catch it later
- [ ] **5.3** Implement `assemble(pages_md: list[str], source_filename: str) -> str`:
  - Extract front matter from `pages_md[0]`
  - Concatenate remaining page bodies with a single blank line separator
  - Ensure exactly one `# Title` line appears (the one from page 1 front matter or the first `#` heading found)
  - Return full document string: `---\n{yaml}\n---\n{body}`
- [ ] **5.4** Ensure YAML serialisation uses `allow_unicode=True` so Italian characters are preserved

---

### Phase 6 — Heading validator (`validator.py`)

- [ ] **6.1** Create `src/pdf_to_markdown/validator.py`
- [ ] **6.2** Implement `validate_front_matter(metadata: dict) -> list[str]`:
  - Return list of error strings for any missing required fields: `titolo`, `comune`, `tipo`, `anno`
- [ ] **6.3** Implement `validate_heading_hierarchy(markdown_text: str) -> list[str]`:
  - Parse all heading lines; detect level skips (e.g. `#` → `###` without `##`)
  - Return list of warning strings with line numbers
- [ ] **6.4** Implement `fix_heading_skips(markdown_text: str) -> str`:
  - Auto-correct level skips by inserting a placeholder heading at the missing level
  - Example: `#` followed by `###` → insert `## (section continued)` between them
  - Only fix gaps of 1 level; log a warning for larger gaps and leave them for manual review
- [ ] **6.5** Implement `validate_document(markdown_text: str) -> tuple[str, list[str]]`:
  - Returns `(fixed_markdown, warnings_list)`
  - Calls front matter + hierarchy validation and the auto-fix

---

### Phase 7 — Pipeline orchestrator (`pipeline.py`)

- [ ] **7.1** Create `src/pdf_to_markdown/pipeline.py`
- [ ] **7.2** Implement `async def process_pdf(pdf_path: Path) -> Path | None`:
  - Extract pages → call LLM per page (async, limited by `asyncio.Semaphore(MAX_CONCURRENT_PAGES)`)
  - Assemble → validate → write to `OUTPUT_DIR / (pdf_path.stem + ".md")`
  - On `ExtractionError` or unhandled exception:
    - Copy original PDF to `RETRY_DIR/`
    - Write `RETRY_DIR/<stem>_error.log` with traceback
    - Return `None`
  - Return output path on success
- [ ] **7.3** Implement `async def run_batch(pdf_paths: list[Path]) -> dict`:
  - Use `asyncio.Semaphore(MAX_CONCURRENT_PDFS)` to cap parallel PDF processing
  - Gather all `process_pdf` tasks
  - Return `{"success": [...], "failed": [...]}` summary dict
- [ ] **7.4** Print a progress line per PDF: `[OK] filename.pdf → output/filename.md` or `[FAIL] filename.pdf → retry/`

---

### Phase 8 — CLI entry point (`cli.py`)

- [ ] **8.1** Create `src/pdf_to_markdown/cli.py`
- [ ] **8.2** Use `argparse` with arguments:
  - `--input` (default: `input/`) — folder of PDFs
  - `--output` (default: `output/`) — destination for .md files
  - `--retry` (default: `retry/`) — destination for failed items
  - `--concurrency` (default: from config) — override `MAX_CONCURRENT_PDFS`
- [ ] **8.3** Collect all `*.pdf` files from `--input`; exit with message if none found
- [ ] **8.4** Call `asyncio.run(run_batch(pdf_paths))`
- [ ] **8.5** Print final summary: total processed, success count, fail count
- [ ] **8.6** Register `pdf2md` as a script entry point in `pyproject.toml`:
  ```toml
  [project.scripts]
  pdf2md = "pdf_to_markdown.cli:main"
  ```
  Then run with `uv run pdf2md --input input/ --output output/`

---

### Phase 9 — End-to-end test

- [ ] **9.1** Copy `attachments/NTA_PdR_PdS_Parte prima.pdf` into `input/`
- [ ] **9.2** Run `uv run pdf2md --input input/ --output output/`
- [ ] **9.3** Open `output/NTA_PdR_PdS_Parte prima.md` and manually check:
  - YAML front matter present with all 4 required fields
  - First `#` heading matches document title
  - Heading levels follow `#` → `##` → `###` → `####` without skips
  - No page numbers appearing as headings
  - No repeated header/footer boilerplate
  - Italian characters render correctly (UTF-8)
- [ ] **9.4** Also run on `attachments/tabella-oneri-e-costo-2026 (2).pdf`; verify the pipe tables look correct
- [ ] **9.5** Fix any prompt issues found in 9.3–9.4 by adjusting `SYSTEM_PROMPT` in `llm.py`

---

### Phase 10 — Polish and delivery

- [ ] **10.1** Run `uv run ruff check src/ --fix` and resolve any lint errors
- [ ] **10.2** Confirm `.env` is not tracked by git; add to `.gitignore` if missing
- [ ] **10.3** Write a brief `README.md`:
  - Prerequisites: Python 3.10+, uv
  - Setup: `uv sync`, copy `.env.example` to `.env` and add key
  - Usage: `uv run pdf2md --input input/`
  - Output structure: `output/`, `retry/`
- [ ] **10.4** Final acceptance run on a batch of at least 3 PDFs; confirm 90%+ heading accuracy

---

## Key decisions recorded

| Decision | Choice | Reason |
|----------|--------|--------|
| PDF extractor | Docling → PyMuPDF fallback | Docling handles tables better; PyMuPDF is the safe fallback |
| LLM | Gemini 2.0 Flash (async) | Cost-efficient for batch; async native support |
| Chunking | Page-by-page | Avoids context limit; easier to isolate failures |
| Parallelism | `asyncio` + `Semaphore` | Gemini SDK supports async; semaphores prevent rate-limit hammering |
| Failed files | `retry/` folder + error log | Non-destructive; allows manual reprocessing |
| Images | Not in scope | No images present in reference examples |
