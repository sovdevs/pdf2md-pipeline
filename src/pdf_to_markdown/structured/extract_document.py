"""Extract an ExtractedDocument IR from a PDF.

Separate from extract_pages() — captures raw table objects before they
become markdown strings, enabling structured CSV/XLSX export.

Extraction order:
  1. PyMuPDF find_tables() for all pages (deterministic, fast)
  2. Text blocks outside table bounding boxes per page
  3. Docling full-doc text as fallback for pages with no PyMuPDF text

The existing markdown pipeline (extract_pages) is unchanged.
"""

import logging
import uuid
from pathlib import Path

from pdf_to_markdown.extractor import ExtractionError
from pdf_to_markdown.structured.models import (
    ExtractedDocument,
    ExtractedPage,
    ExtractedTable,
    ExtractionWarning,
    StructuredRecord,
    TextBlock,
)

logger = logging.getLogger(__name__)

_KV_SEPARATORS = (":", "=", "—", "-")


def _is_header_row(row: list[str]) -> bool:
    """Heuristic: a row is a header if it has short non-numeric cells."""
    if not row:
        return False
    non_empty = [c for c in row if c.strip()]
    if not non_empty:
        return False
    numeric = sum(1 for c in non_empty if c.replace(".", "").replace(",", "").replace("-", "").isdigit())
    return numeric < len(non_empty) / 2


def _raw_to_extracted_table(tab, page_number: int) -> ExtractedTable | None:
    rows_raw = tab.extract()
    if not rows_raw:
        return None

    str_rows = [[str(c).strip() if c is not None else "" for c in row] for row_raw in rows_raw for row in [row_raw]]

    # Remove fully-empty rows
    str_rows = [r for r in str_rows if any(c for c in r)]
    if not str_rows:
        return None

    columns: list[str] | None = None
    data_rows = str_rows

    if len(str_rows) > 1 and _is_header_row(str_rows[0]):
        columns = str_rows[0]
        data_rows = str_rows[1:]

    return ExtractedTable(
        page_number=page_number,
        columns=columns,
        rows=data_rows,
        source="pymupdf",
        confidence=0.9,
    )


def _detect_kv_blocks(text_blocks: list[TextBlock]) -> dict[str, str]:
    """Extract key-value pairs from text blocks using simple heuristics."""
    fields: dict[str, str] = {}
    for block in text_blocks:
        for line in block.text.splitlines():
            line = line.strip()
            for sep in _KV_SEPARATORS:
                if sep in line:
                    parts = line.split(sep, 1)
                    key = parts[0].strip()
                    val = parts[1].strip()
                    if 1 < len(key) <= 60 and val:
                        fields[key] = val
                    break
    return fields


def extract_document(pdf_path: Path) -> ExtractedDocument:
    """Return an ExtractedDocument with raw tables and text blocks from a PDF."""
    import fitz  # PyMuPDF

    warnings: list[ExtractionWarning] = []
    all_tables: list[ExtractedTable] = []
    all_text_blocks: list[TextBlock] = []
    pages: list[ExtractedPage] = []

    try:
        with fitz.open(str(pdf_path)) as fitz_doc:
            page_count = len(fitz_doc)

            for i, page in enumerate(fitz_doc, start=1):
                page_tables: list[ExtractedTable] = []
                table_rects: list[tuple] = []

                # ── Table extraction ────────────────────────────────────────
                try:
                    tabs = page.find_tables()
                    for tab in tabs.tables:
                        et = _raw_to_extracted_table(tab, i)
                        if et:
                            page_tables.append(et)
                            all_tables.append(et)
                            table_rects.append(tab.bbox)
                except Exception as e:
                    warnings.append(ExtractionWarning(
                        code="TABLE_EXTRACTION_ERROR",
                        message=str(e),
                        page_number=i,
                    ))

                # ── Text blocks (outside table areas) ───────────────────────
                page_text_blocks: list[TextBlock] = []
                blocks = page.get_text("blocks", sort=True)
                for b in blocks:
                    bx0, by0, bx1, by1 = b[0], b[1], b[2], b[3]
                    in_table = any(
                        bx0 >= tb[0] - 2 and by0 >= tb[1] - 2
                        and bx1 <= tb[2] + 2 and by1 <= tb[3] + 2
                        for tb in table_rects
                    )
                    if not in_table:
                        txt = b[4].strip()
                        if txt:
                            tb = TextBlock(page_number=i, text=txt, block_type="paragraph")
                            page_text_blocks.append(tb)
                            all_text_blocks.append(tb)

                page_text = "\n\n".join(tb.text for tb in page_text_blocks)
                pages.append(ExtractedPage(
                    page_number=i,
                    text=page_text,
                    tables=page_tables,
                    extraction_method="pymupdf",
                ))

    except Exception as e:
        raise ExtractionError(f"Failed to open {pdf_path.name}: {e}") from e

    if not pages:
        raise ExtractionError(f"No content extracted from {pdf_path.name}")

    if not all_tables and not any(p.text.strip() for p in pages):
        warnings.append(ExtractionWarning(
            code="EMPTY_DOCUMENT",
            message="No tables or text found — document may be image-only or encrypted",
        ))

    return ExtractedDocument(
        source_file=pdf_path.name,
        pages=pages,
        tables=all_tables,
        text_blocks=all_text_blocks,
        warnings=warnings,
        extraction_method="pymupdf",
        page_count=page_count,
    )


def document_to_structured_record(doc: ExtractedDocument) -> StructuredRecord:
    """Derive a StructuredRecord from an ExtractedDocument using heuristics only.

    This is the P1 path (no schema, no LLM).
    P2 will replace/augment this with schema-guided LLM extraction.
    """
    fields = _detect_kv_blocks(doc.text_blocks)

    # Flatten all table rows into line_items
    line_items: list[dict] = []
    for table in doc.tables:
        line_items.extend(table.to_dicts())

    return StructuredRecord(
        document_id=doc.document_id,
        source_file=doc.source_file,
        document_type="unknown",
        fields=fields,
        line_items=line_items,
        confidence=None,
        warnings=[w.message for w in doc.warnings],
        extraction_method="heuristic",
    )
