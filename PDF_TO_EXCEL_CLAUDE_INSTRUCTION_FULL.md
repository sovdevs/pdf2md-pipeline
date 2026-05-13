# Claude Instruction — Extend PDF-to-Markdown App with PDF-to-CSV/XLSX Extraction

## Goal

Extend the existing PDF-to-Markdown application so it can also support commercial PDF-to-CSV/XLSX extraction workflows.

The target use case is not just dumping Markdown into Excel. The target use case is:

```text
multiple PDFs
→ readable/OCR extraction
→ Markdown/intermediate representation
→ schema-guided field extraction
→ validated structured JSON
→ one combined Excel workbook using a template
```

This should support jobs such as logistics/trucking document extraction, invoices, bills of lading, delivery notes, medical documents, and other structured/semi-structured PDFs.

The existing PDF-to-Markdown pipeline already handles:

- readable PDFs
- scanned PDFs / OCR
- multiple layouts through Gemini
- Markdown output
- batch directory-based processing

The missing extension is:

- structured CSV/XLSX export
- schema-based field extraction
- Excel template population
- better batch handling for multiple PDF uploads/files
- intermediate JSON artifacts for retry/resume/debugging

---

# Answers to Implementation Questions

## 1. P1 vs P2 Sequencing — build IR upfront?

Yes. Build a minimal intermediate representation upfront.

Do not build CSV/XLSX exporters directly from loose Markdown strings if that will cause a refactor later.

The exporters should target a minimal `ExtractedDocument` model from day one, even if some fields are initially stubbed.

Suggested minimal models:

```python
class ExtractedDocument:
    source_file: str
    document_id: str
    pages: list[ExtractedPage]
    tables: list[ExtractedTable]
    text_blocks: list[TextBlock]
    structured_records: list[StructuredRecord]
    warnings: list[ExtractionWarning]
    extraction_method: str
```

```python
class ExtractedTable:
    table_id: str
    page_number: int | None
    rows: list[list[str]]
    columns: list[str] | None
    confidence: float | None
    source: str  # pymupdf, gemini, markdown_import, manual
    notes: list[str]
```

```python
class StructuredRecord:
    document_id: str
    source_file: str
    document_type: str
    fields: dict
    line_items: list[dict]
    confidence: float | None
    warnings: list[str]
```

The important thing is not to over-engineer the IR. Keep it small, but make CSV/XLSX depend on it.

---

## 2. Table Source — parse Markdown tables or capture raw tables?

Prefer tapping the extractor earlier and capturing raw table objects before they become Markdown.

Primary path:

```text
PDF
→ extractor.py
→ raw table objects / text blocks
→ ExtractedDocument IR
→ Markdown / CSV / XLSX
```

Parsing Markdown tables back out of `.md` files is acceptable as a fallback/import mode, not the main extraction path.

Fallback path:

```text
existing Markdown
→ parse Markdown tables
→ ExtractedDocument IR
→ CSV/XLSX
```

Use PyMuPDF `find_tables()` first, since it already exists in the project.

`pdfplumber` was illustrative, not mandatory. Do not add it unless PyMuPDF proves insufficient for real sample PDFs.

---

## 3. Naming Collision — existing exporter.py

Yes, keep the new structured CSV/XLSX export logic separate from the existing translation exporter.

The current `exporter.py` is for translation-segment exports / TMX-style workflows.

The new structured CSV/XLSX output is different and should not be mixed into that file.

Suggested module layout:

```text
app/pipeline/structured/
  __init__.py
  models.py
  extract_tables.py
  extract_fields.py
  markdown_table_import.py
  schema.py
  validation.py
  csv_writer.py
  xlsx_writer.py
  batch_runner.py
  template_writer.py
```

Alternative names are fine, but keep translation export and structured business-data export separate.

---

## 4. Gemini Prompt Mode — Markdown only or structured JSON?

Add a structured Gemini mode.

Do not rely only on Markdown table parsing for difficult layouts.

Keep the existing Markdown mode unchanged, but add something like:

```text
--output-format markdown
--output-format structured
--output-format all
```

For structured mode, Gemini should return validated JSON matching the extraction schema / `StructuredRecord`.

Important rules:

- Gemini structured output should be optional or fallback-capable, not the only extraction path.
- First try deterministic extraction using PyMuPDF / existing parser.
- If tables are missing, messy, low-confidence, or the target fields are not easily extracted deterministically, use Gemini structured extraction.
- Save the raw Gemini JSON response for debugging.
- Validate JSON before writing CSV/XLSX.
- If validation fails, write an error/warning record instead of silently producing bad Excel.

Preferred architecture:

```text
PDF
→ deterministic extraction
→ ExtractedDocument IR
→ optional Gemini structured repair/enrichment
→ validated StructuredRecord
→ Markdown export
→ CSV export
→ XLSX export
→ warnings/errors report
```

---

# Important Clarification: Not PDF Text Dump to Excel

The system should NOT simply dump Markdown into arbitrary Excel columns.

The commercial requirement is usually:

```text
PDF documents
→ specific business fields
→ clean rows/columns in Excel
```

For example, in a trucking/logistics job, likely fields include:

```text
file_name
document_type
invoice_number
load_number
bol_number
carrier
shipper
consignee
pickup_date
delivery_date
origin
destination
miles
rate
fuel_surcharge
accessorial_charges
total_amount
confidence
review_status
```

Tables or repeating records should go into a second sheet, for example:

```text
file_name
document_id
load_number
line_item_description
quantity
unit_price
amount
```

So we need a schema/template layer.

---

# Extraction Schema Layer

Add support for schema-guided extraction.

A schema defines:

- document type
- target fields
- field descriptions
- required/optional fields
- expected data types
- validation rules
- target Excel sheet/column/cell mappings
- repeating tables / line items

Example schema:

```json
{
  "document_type": "logistics_invoice",
  "fields": [
    {
      "name": "invoice_number",
      "type": "string",
      "required": true,
      "description": "Invoice number shown on the document"
    },
    {
      "name": "load_number",
      "type": "string",
      "required": false
    },
    {
      "name": "pickup_date",
      "type": "date",
      "required": false
    },
    {
      "name": "delivery_date",
      "type": "date",
      "required": false
    },
    {
      "name": "carrier",
      "type": "string",
      "required": false
    },
    {
      "name": "total_amount",
      "type": "currency",
      "required": true
    }
  ],
  "line_items": [
    {
      "name": "description",
      "type": "string"
    },
    {
      "name": "amount",
      "type": "currency"
    }
  ],
  "sheets": {
    "summary": "Summary",
    "line_items": "LineItems",
    "warnings": "Warnings",
    "raw_preview": "RawTextPreview"
  }
}
```

The LLM should use this schema to extract JSON.

Python should validate the JSON and write it to Excel.

---

# LLM Role vs Python Role

The LLM should not build the Excel file directly.

Correct separation:

```text
LLM extracts structured data.
Python builds CSV/XLSX.
```

Flow:

```text
PDF
→ Markdown/OCR text
→ LLM receives Markdown + extraction schema
→ LLM returns structured JSON
→ Python validates JSON
→ Python writes CSV/XLSX using template
```

Example LLM output:

```json
{
  "document_type": "logistics_invoice",
  "invoice_number": "INV-10293",
  "load_number": "LD-8821",
  "carrier": "ABC Trucking",
  "pickup_date": "2025-04-12",
  "delivery_date": "2025-04-13",
  "origin": "Dallas, TX",
  "destination": "Memphis, TN",
  "total_amount": 1840.50,
  "line_items": [
    {
      "description": "Fuel surcharge",
      "amount": 120.00
    }
  ],
  "warnings": []
}
```

---

# Excel Template Support

Assume many PDFs and one Excel template.

The Excel template should define the workbook shape, not one separate workbook per PDF.

Typical output workbook:

```text
batch_results.xlsx
  Summary        one row per PDF
  LineItems      many rows per PDF if tables/charges exist
  Warnings       missing fields, failed validations, low confidence
  RawPreview     optional source preview/debug sheet
```

If the client provides an Excel template, map fields into that template.

If no template is provided, generate a default workbook with the sheets above.

Example mapping config:

```json
{
  "summary_sheet": "Summary",
  "summary_start_row": 2,
  "summary_columns": {
    "file_name": "A",
    "document_type": "B",
    "invoice_number": "C",
    "load_number": "D",
    "carrier": "E",
    "pickup_date": "F",
    "delivery_date": "G",
    "origin": "H",
    "destination": "I",
    "total_amount": "J",
    "confidence": "K",
    "review_status": "L"
  },
  "line_items_sheet": "LineItems",
  "line_items_start_row": 2,
  "line_item_columns": {
    "file_name": "A",
    "document_id": "B",
    "load_number": "C",
    "description": "D",
    "quantity": "E",
    "unit_price": "F",
    "amount": "G"
  },
  "warnings_sheet": "Warnings",
  "warnings_start_row": 2
}
```

Use `openpyxl` or `xlsxwriter`. If writing into an existing template, `openpyxl` is likely the better first choice.

---

# Batch Processing

Current state: the app reads from a directory.

That is acceptable for CLI/batch workflows, but the new version should support a more explicit batch job abstraction.

The batch workflow should support:

- directory input
- explicit list of PDF paths
- uploaded multi-file batch
- retry/resume from intermediate artifacts
- partial failure handling

Important rule:

Do not let multiple workers write to the same Excel file concurrently.

Recommended two-phase batch architecture:

## Phase 1 — Parallel PDF Processing

Each PDF is processed independently.

For each PDF, write intermediate artifacts:

```text
intermediate/
  file_a.md
  file_a.extracted_document.json
  file_a.structured_record.json
  file_a.warnings.json

  file_b.md
  file_b.extracted_document.json
  file_b.structured_record.json
  file_b.warnings.json
```

This phase can run in parallel with a configurable worker count.

Suggested config:

```text
--workers 4
--llm-concurrency 2
--continue-on-error
```

## Phase 2 — Single Excel Writer

After all JSON records are produced, load the Excel template once and append all records sequentially.

```text
structured_record.json files
→ single Excel writer
→ batch_results.xlsx
```

Never write to the XLSX file from multiple workers.

This avoids file corruption and makes failures easier to debug.

---

# Batch Output

For a batch of PDFs, produce:

```text
output/
  batch_results.xlsx
  batch_results.csv
  batch_report.json
  failed_files.json
  warnings.csv
```

Where:

- `batch_results.xlsx` is the main client-facing result
- `batch_results.csv` may contain the Summary sheet equivalent
- `batch_report.json` records counts, failures, confidence, and timings
- `failed_files.json` records which PDFs failed and why
- `warnings.csv` gives reviewable quality issues

---

# Suggested CLI

Add or extend CLI commands such as:

```bash
uv run pdf2md --input input/ --output output/ --output-format markdown
```

```bash
uv run pdf2extract --input input/ --schema schemas/logistics_invoice.json --output output/intermediate/
```

```bash
uv run pdf2excel --input input/ --schema schemas/logistics_invoice.json --template templates/logistics_template.xlsx --output output/batch_results.xlsx --workers 4
```

Or one combined command:

```bash
uv run pdf2excel \
  --input input/ \
  --schema schemas/logistics_invoice.json \
  --template templates/logistics_template.xlsx \
  --output output/batch_results.xlsx \
  --workers 4 \
  --llm-concurrency 2
```

Exact command names can follow the current project style.

---

# Implementation Priorities

## Priority 1 — Minimal IR + Structured Export Foundation

Implement:

- `ExtractedDocument`
- `ExtractedTable`
- `StructuredRecord`
- JSON serialization/deserialization
- deterministic table capture from extractor
- basic CSV/XLSX writer from structured records

Acceptance:

- one PDF can produce `.md`
- one PDF can produce `.extracted_document.json`
- one PDF can produce `.structured_record.json`
- one PDF can produce CSV/XLSX output

---

## Priority 2 — Schema-Based Field Extraction

Implement:

- schema loader
- schema validation
- LLM prompt for extracting fields from Markdown into JSON
- JSON validation
- warnings for missing required fields

Acceptance:

- schema defines columns/fields
- LLM returns structured JSON
- invalid/missing fields are reported
- no bad data is silently written

---

## Priority 3 — Excel Template Writer

Implement:

- template mapping config
- append one row per PDF to Summary sheet
- append repeated line items to LineItems sheet
- append warnings/errors to Warnings sheet
- generate default workbook if no template is provided

Acceptance:

- multiple PDF records write into one workbook
- line items go to separate sheet
- warnings are visible
- workbook opens correctly in Excel/LibreOffice

---

## Priority 4 — Batch Processing

Implement:

- explicit batch job handling
- directory input and list-of-files input
- parallel PDF processing
- rate-limited LLM calls
- sequential Excel writing
- retry/resume based on intermediate JSON artifacts

Acceptance:

- failed PDF does not kill entire batch
- successful PDFs still appear in workbook
- failures appear in Warnings/failed_files
- rerun skips already completed JSON artifacts unless forced

---

## Priority 5 — Gemini Structured Repair/Fallback

Implement:

- `--output-format structured`
- Gemini prompt for structured JSON
- raw Gemini response logging
- validation before export
- optional fallback when deterministic extraction confidence is low

Acceptance:

- Gemini can extract schema fields from Markdown
- Gemini can improve table extraction for difficult layouts
- raw response is saved for debugging
- invalid JSON does not corrupt final Excel

---

# Non-Goals for First Version

Do not build a full spreadsheet editor.

Do not build a complicated review UI yet unless already easy to adapt from existing UI.

Do not try to solve every document layout generically.

Do not promise perfect extraction without a representative PDF sample set.

Do not let LLM output directly modify Excel files.

---

# Strong Proposal Positioning

This extension lets us honestly say:

```text
I already have a working PDF extraction pipeline for readable PDFs, scanned PDFs/OCR, and multiple layouts.
For this job I would extend it into a schema-based PDF-to-Excel system:
PDF → Markdown/OCR → structured JSON extraction → validation → Excel template population.
This avoids simply dumping raw text into Excel and gives the client clean, reviewable business data.
```

Second reference project:

```text
My Confidoc project also shows a related single-PDF workflow with anonymization/entity extraction review and CSV export. That is relevant where confidential documents need human-in-the-loop validation before export.
```

---

# Final Architecture

```text
Multiple PDFs
→ batch runner
→ per-PDF Markdown/OCR extraction
→ ExtractedDocument IR
→ schema-guided field extraction
→ validated StructuredRecord JSON
→ per-PDF warnings/errors
→ single Excel template writer
→ batch_results.xlsx
```

This is the architecture to implement.
