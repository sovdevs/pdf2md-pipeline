# PDF-to-Excel / CSV Extension Spec for Claude

## Goal

Extend the existing PDF-to-Markdown application so it can also export structured CSV and Excel files from PDFs.

This should build on the existing PDF parsing/OCR/Gemini layout-handling pipeline rather than creating a separate project.

The target Upwork-style use case is:

> Automated PDF-to-Excel extraction system for readable PDFs, scanned PDFs, multiple layouts, bulk processing, high accuracy, and error handling.

The current system already covers several major parts:

- PDF parsing
- multiple PDF layouts using Gemini-assisted extraction
- scanned PDF / OCR support
- directory-based batch processing
- Markdown output
- structured downstream export concepts

The missing extension is mainly:

- PDF → CSV
- PDF → XLSX
- better structured table/field extraction layer
- optional multi-file upload / explicit file-list processing
- improved bulk processing status and error reporting

A second related reference project is `confidoc`, which already demonstrates:

- single PDF job workflow
- entity/anonymization review
- extraction review
- export to CSV
- staged document processing

This extension should remain in the original PDF-to-Markdown app, because it is a generic document conversion/export capability, not a confidential-document workflow.

---

## Product Framing

The existing app should evolve from:

```text
PDF → Markdown
```

into:

```text
PDF → Markdown / CSV / Excel
```

More specifically:

```text
PDF
→ readable/OCR extraction
→ Gemini-assisted layout interpretation where needed
→ normalized intermediate representation
→ Markdown export
→ CSV export
→ XLSX export
→ error report
```

Markdown remains useful as an inspection/debug/review format, but CSV/XLSX are the business-facing deliverables.

---

## Important Scope Boundary

Do not try to build a full logistics-specific extraction product yet.

For now, implement a general export layer capable of:

1. extracting tables where tables exist
2. extracting key-value fields where identifiable
3. exporting page-level text/sections when no structured table exists
4. writing clean CSV/XLSX outputs
5. reporting uncertain or failed extraction cases

Later, logistics-specific schemas can be added as profiles, for example:

- invoice number
- load number
- BOL number
- carrier
- shipper
- consignee
- pickup date
- delivery date
- origin
- destination
- miles
- rate
- fuel surcharge
- accessorial charges
- total amount

But do not hard-code trucking assumptions in the first version.

---

## Proposed Architecture

Add a new export module, for example:

```text
app/
  pipeline/
    pdf_to_markdown.py        # existing
    pdf_to_csv.py             # new
    pdf_to_excel.py           # new
    structured_extract.py     # new shared intermediate model
    table_extract.py          # optional helper
    field_extract.py          # optional helper
    validation.py             # new checks/errors/confidence
  exporters/
    csv_exporter.py
    excel_exporter.py
  batch/
    runner.py                 # extend existing batch flow
```

If the existing app has a different structure, adapt the names, but keep the separation:

- extraction
- structure detection
- validation
- export
- batch orchestration

---

## Intermediate Representation

Before exporting CSV/XLSX, create a structured intermediate result.

Suggested model:

```python
class ExtractedDocument:
    source_file: str
    pages: list[ExtractedPage]
    tables: list[ExtractedTable]
    fields: dict[str, ExtractedField]
    warnings: list[ExtractionWarning]
    errors: list[ExtractionError]

class ExtractedTable:
    page_number: int
    title: str | None
    columns: list[str]
    rows: list[dict[str, str]]
    confidence: float | None
    extraction_method: str  # pdfplumber | OCR | Gemini | fallback

class ExtractedField:
    name: str
    value: str
    page_number: int | None
    confidence: float | None
    extraction_method: str
```

This allows multiple export targets without duplicating extraction logic.

---

## Export Modes

Implement at least three export modes.

### 1. Tables Mode

Best for invoices, statements, logistics documents, reports with line items.

Output:

```text
output/<stem>.csv
output/<stem>.xlsx
```

Excel should contain:

- one sheet per detected table, or
- one combined `tables` sheet if simpler

Also include a `metadata` sheet with:

- source filename
- number of pages
- extraction method
- warnings
- errors
- timestamp

---

### 2. Fields Mode

Best for key-value documents.

Output columns:

```text
field_name,value,page,confidence,extraction_method
```

Excel sheet:

```text
fields
```

---

### 3. Full Structured Mode

Best general fallback.

Excel workbook should contain:

```text
metadata
fields
tables
pages
warnings
errors
```

This is probably the best default for the Upwork demo because it shows robustness.

---

## CSV Output

CSV export should support:

- one CSV per table
- one combined CSV for all rows where possible
- fallback CSV with page/section/text columns if no table is found

Suggested outputs:

```text
output/csv/<stem>__table_001.csv
output/csv/<stem>__table_002.csv
output/csv/<stem>__fields.csv
output/csv/<stem>__pages.csv
output/csv/<stem>__warnings.csv
```

---

## Excel Output

Use `openpyxl` or `xlsxwriter`.

Suggested workbook sheets:

```text
metadata
fields
table_001
table_002
pages
warnings
errors
```

Basic formatting:

- bold header row
- frozen first row
- auto-width columns where feasible
- warning/error sheet included even if empty
- no merged cells unless necessary

Keep the output practical and business-friendly, not visually complex.

---

## Bulk Processing

The current app reads from a directory. That is already acceptable for many batch-processing jobs.

However, for the job description, it would be useful to support both:

### Existing Mode

```bash
uv run pdf2excel --input-dir data/input --output-dir data/output
```

### New Explicit File List Mode

```bash
uv run pdf2excel --files file1.pdf file2.pdf file3.pdf --output-dir data/output
```

### Optional Manifest Mode

```bash
uv run pdf2excel --manifest batch_jobs.csv --output-dir data/output
```

Where `batch_jobs.csv` might contain:

```csv
file_path,profile,notes
/path/to/doc1.pdf,generic,
/path/to/doc2.pdf,invoice,
```

---

## Parallel Processing

Add controlled parallel processing, but keep it conservative.

Suggested CLI argument:

```bash
--workers 4
```

Implementation:

- use `concurrent.futures.ProcessPoolExecutor` or `ThreadPoolExecutor` depending on current architecture
- default workers should be 1 or 2
- avoid too much parallelism when Gemini/API calls are used
- preserve per-file error isolation

Each file should produce its own result object:

```text
success
failed
partial_success
```

A single bad PDF must not stop the whole batch.

---

## Batch Summary Report

Every batch run should create:

```text
batch_summary.csv
batch_summary.json
```

Suggested fields:

```text
filename
status
pages
tables_found
fields_found
warnings_count
errors_count
output_xlsx
output_csv_dir
processing_seconds
extraction_methods_used
```

This is important for client confidence.

---

## Error Handling

Do not silently produce bad Excel.

The system should report:

- unreadable PDF
- OCR failure
- no tables detected
- low confidence extraction
- Gemini parsing failure
- empty output
- malformed table rows
- inconsistent column counts

Errors should appear in:

1. terminal logs
2. batch summary
3. Excel `errors` sheet
4. JSON sidecar if available

Suggested sidecar:

```text
output/<stem>__extraction_report.json
```

---

## Gemini Usage

Gemini should be used as a layout/table interpretation fallback, not as the only parser.

Recommended order:

```text
1. Try deterministic PDF table/text extraction
2. Try OCR if scanned or low text coverage
3. Use Gemini for tricky layouts/tables
4. Validate result
5. Export
```

This keeps costs and latency under control.

---

## CLI Commands

Add commands such as:

```bash
uv run pdf2csv --input data/input/sample.pdf --output data/output
uv run pdf2excel --input data/input/sample.pdf --output data/output
uv run pdf2excel --input-dir data/input --output-dir data/output --workers 4
uv run pdf2excel --files a.pdf b.pdf c.pdf --output-dir data/output --workers 2
```

Optional:

```bash
uv run pdf2structured --input data/input/sample.pdf --output data/output --formats md,csv,xlsx,json
```

If the app already has one main CLI command, extend it with:

```bash
--format md
--format csv
--format xlsx
--format all
```

or:

```bash
--export md,csv,xlsx
```

---

## API / UI Considerations

If the app has a FastAPI or web interface, add:

- upload multiple PDFs
- select export format: Markdown / CSV / Excel / All
- show batch progress
- allow download of XLSX
- allow download of ZIP containing CSVs and reports
- show warnings/errors per file

This is nice to have, not required for first CLI implementation.

---

## Tests / Acceptance Criteria

### Single PDF

- readable PDF exports to XLSX
- scanned PDF exports to XLSX via OCR
- PDF with table exports table rows correctly
- PDF with no table still exports page text fallback
- warnings/errors are captured

### CSV

- table CSV is created
- fields CSV is created where fields exist
- pages CSV fallback is created where no tables exist

### Excel

- workbook opens in Excel/LibreOffice
- metadata sheet exists
- warnings/errors sheets exist
- table sheets have headers
- empty or failed files do not create misleading clean outputs

### Batch

- input directory processing works
- explicit file list processing works
- one failed PDF does not stop the batch
- batch_summary.csv is created
- workers argument works or safely falls back to serial mode

### Gemini / OCR

- scanned PDFs route through OCR
- tricky layouts can use Gemini fallback
- extraction method is recorded in metadata

---

## Development Priority

### Priority 1 — CSV/XLSX export from existing extracted Markdown/structured data

Do this first. It gives the fastest portfolio-relevant result.

### Priority 2 — Structured intermediate representation

Needed to avoid messy direct conversion logic.

### Priority 3 — Batch file-list mode and summary report

Directory input already exists, but explicit file-list mode better matches client expectations.

### Priority 4 — Parallel processing

Useful but not critical. Add only after reliable serial batch processing works.

### Priority 5 — Logistics-specific extraction profile

Only after generic export is working.

---

## What Not To Do Yet

Do not build:

- a full logistics SaaS product
- a complex database-backed job system unless already present
- too many hard-coded trucking fields
- a full review UI unless needed
- perfect automatic extraction claims

The immediate goal is a credible, working PDF-to-CSV/XLSX extension that demonstrates:

- readable PDF support
- scanned PDF/OCR support
- multiple layouts
- clean Excel output
- bulk processing
- error handling

---

## Portfolio / Proposal Positioning

Once implemented, describe it like this:

> I have an existing PDF processing pipeline that handles readable and scanned PDFs, OCR, Gemini-assisted layout handling, batch processing, Markdown output, and structured exports. I recently extended it with CSV/XLSX export, per-file error reports, and batch summaries, which makes it directly applicable to PDF-to-Excel extraction workflows such as invoices, logistics documents, and operational reports.

