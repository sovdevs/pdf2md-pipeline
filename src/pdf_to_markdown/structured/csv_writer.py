"""Write CSV outputs from ExtractedDocument / StructuredRecord.

Output per document:
  <stem>__table_001.csv   one per detected table
  <stem>__fields.csv      key-value fields (always written, may be empty)
  <stem>__pages.csv       page-level text fallback (when no tables found)
  <stem>__warnings.csv    extraction warnings (always written, may be empty)
"""

import csv
from pathlib import Path

from pdf_to_markdown.structured.models import ExtractedDocument, StructuredRecord


def _write(path: Path, headers: list[str], rows: list[list]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(headers)
        writer.writerows(rows)


def write_csv_outputs(
    doc: ExtractedDocument,
    record: StructuredRecord,
    out_dir: Path,
    stem: str,
) -> list[Path]:
    """Write all CSV files for one document. Returns list of paths written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    # ── Per-table CSVs ────────────────────────────────────────────────────────
    for idx, table in enumerate(doc.tables, start=1):
        cols = table.columns or [f"col_{i}" for i in range(len(table.rows[0]))] if table.rows else []
        if not cols:
            continue
        path = out_dir / f"{stem}__table_{idx:03d}.csv"
        _write(path, ["page"] + cols, [[table.page_number or ""] + row for row in table.rows])
        written.append(path)

    # ── Fields CSV ────────────────────────────────────────────────────────────
    fields_path = out_dir / f"{stem}__fields.csv"
    _write(
        fields_path,
        ["field_name", "value", "extraction_method"],
        [[k, v, record.extraction_method] for k, v in record.fields.items()],
    )
    written.append(fields_path)

    # ── Pages CSV (fallback when no tables) ───────────────────────────────────
    if not doc.tables:
        pages_path = out_dir / f"{stem}__pages.csv"
        _write(
            pages_path,
            ["page_number", "text", "extraction_method"],
            [[p.page_number, p.text, p.extraction_method] for p in doc.pages if p.text.strip()],
        )
        written.append(pages_path)

    # ── Warnings CSV (always written) ─────────────────────────────────────────
    warn_path = out_dir / f"{stem}__warnings.csv"
    _write(
        warn_path,
        ["code", "message", "page_number"],
        [[w.code, w.message, w.page_number or ""] for w in doc.warnings],
    )
    written.append(warn_path)

    return written
