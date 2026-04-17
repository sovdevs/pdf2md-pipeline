# IMPLEMENTATION.md

Design decisions, discoveries, and non-obvious facts from the actual build. Does not repeat SPEC.md or PLAN.md.

---

## Gemini SDK

**Use `google-genai`, not `google-generativeai`.** The older `google-generativeai` package is fully deprecated and receives no updates. The replacement is `google-genai>=1.0`. Import path: `from google import genai`.

**API key naming.** Google's own tooling uses `GOOGLE_API_KEY`; some docs say `GEMINI_API_KEY`. Both are the same key from AI Studio. Config loads `GOOGLE_API_KEY` first, falls back to `GEMINI_API_KEY`, and skips any value equal to `"your_key_here"` (placeholder guard).

**Billing is required.** The free tier for `gemini-2.0-flash` has `limit: 0` — it returns HTTP 429 immediately with no free quota. The key must be linked to a GCP project with billing enabled. Cost is ~$0.075 per 1M input tokens; a single 100-page document costs well under $0.10.

**Retry policy.** `tenacity` retries on transient server errors but explicitly does NOT retry 429 (`RESOURCE_EXHAUSTED`) — retrying a quota error wastes time and gives a misleading wait.

**Gemini wraps YAML in code fences.** Even when instructed not to, the model frequently returns the front matter block as ` ```yaml ... ``` ` instead of bare `--- ... ---`. The `_strip_code_fences()` function in `llm.py` converts this automatically with a regex substitution.

---

## PDF Extraction

**Docling page iteration.** Docling's `DocumentConverter` returns a `DoclingDocument` with a `.pages` dict and an `.iterate_items()` method. Text is collected by matching `item.prov[].page_no` to the target page number. Empty pages are skipped; a page with no text raises `ExtractionError` which triggers PyMuPDF fallback.

**Docling deprecation warning.** Docling emits a `DeprecationWarning` about `generate_table_images` on every run. This is internal to the library and harmless — do not suppress it, as it may become load-bearing in a future version.

---

## Prompt Engineering

**Year extraction is hard.** The cover page of the test document contains no year — it first appears on page 9 inside a table of contents entry `"PGRA 2022-2023"`. Two-layer approach:
1. Prompt instructs Gemini to find standalone years not embedded in law citations (e.g. ignore `L.R. 12/2005`, `D.Lgs. n.42/2004`).
2. `assembler.py` fallback scans the full assembled document with regex `(?<!/)\b(20[12]\d)\b(?!/)` — the negative lookbehind/lookahead excludes years preceded or followed by `/`.

**Table of contents pages need explicit instruction.** Without a specific rule, Gemini formats TOC entries as `### headings` and preserves page numbers. The prompt must explicitly say: format as `- list items`, omit page numbers and dot leaders entirely.

**Boilerplate removal needs explicit examples.** Generic "remove repeated headers" is insufficient. The prompt lists specific content types to remove: standalone page numbers, municipality name/title repeating on every page, copyright/authorship notices (keywords: `copyright`, `vietato`, `autori`, `estensori`).

**Heading skip auto-fix.** The validator inserts `## (continued)` or `### (continued)` placeholders for level-1 skips (e.g. `##` → `####`). Skips larger than 1 level are logged as warnings and left for manual review — auto-fixing them risks misrepresenting document structure.

---

## Project / Package Setup

**`src` layout requires editable install for pytest.** With `src/pdf_to_markdown/` layout, `pytest` cannot find the package unless it is installed. Run `uv pip install -e .` once after setup; subsequent `uv run pytest` calls work correctly. This is already handled by `uv sync` in normal workflows.

**`pyproject.toml` hatch config is required** for the `src` layout to be recognised by the build backend:
```toml
[tool.hatch.build.targets.wheel]
packages = ["src/pdf_to_markdown"]
```

---

## Demo Interface

**`marked.js` hits a recursion limit on large documents.** The NTA document produces ~450KB / 4,650 lines of Markdown. Passing it to `marked.parse()` in one call causes a stack overflow ("Too much recursion") in all tested browsers. Fix: split the body into ~60-line chunks at heading boundaries before rendering, with a per-chunk `try/catch` that falls back to `<pre>` plain text.

**Server detection via `/api/health`.** The upload button is hidden by default. On page load, the demo fetches `/api/health` with a 1.5-second timeout. If the FastAPI server responds, `window.DEMO_SERVER_AVAILABLE` is set and the button appears. This means the same `index.html` works on Netlify (static, no upload) and locally (full upload).

**Netlify publish config.** `netlify.toml` sets `publish = "demo"` so the repo root is the build source but only `demo/` is published. The `attachments/` PDFs are served from `../attachments/` relative to `demo/index.html`, which resolves correctly on Netlify.

**FastAPI mounts order matters.** The `/attachments` static mount must be registered before the root `/` static mount; FastAPI evaluates mounts in registration order and the root mount would otherwise swallow `/attachments` requests.

---

## Known Limitations (v1)

| Issue | Notes |
|-------|-------|
| `anno` from cover page | Year reliably found only if it appears in body text; regex fallback uses most-frequent year across the document |
| TOC page numbers in list items | Prompt strips dot leaders but page numbers sometimes survive at end of list entries |
| Large parallel batches untested | Semaphore concurrency controls are in place; real-world rate limits at scale (20–50 docs) depend on API tier |
| Scanned / image-only PDFs | Docling runs OCR via `ocrmac` on macOS; quality on low-resolution scans is not validated |
