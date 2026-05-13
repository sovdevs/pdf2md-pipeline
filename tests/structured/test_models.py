"""Tests for IR model serialization and basic behaviour."""

import json

from pdf_to_markdown.structured.models import (
    BatchResult,
    ExtractedDocument,
    ExtractedTable,
    ExtractionWarning,
    StructuredRecord,
    TextBlock,
)


def _make_doc() -> ExtractedDocument:
    table = ExtractedTable(
        page_number=1,
        columns=["Description", "Amount"],
        rows=[["Freight", "1200.00"], ["Fuel surcharge", "120.00"]],
        source="pymupdf",
        confidence=0.9,
    )
    return ExtractedDocument(
        source_file="test.pdf",
        page_count=1,
        tables=[table],
        text_blocks=[TextBlock(page_number=1, text="Invoice Number: INV-001")],
        warnings=[ExtractionWarning(code="TEST", message="synthetic")],
    )


def test_extracted_document_round_trip():
    doc = _make_doc()
    json_str = doc.model_dump_json()
    restored = ExtractedDocument.model_validate_json(json_str)
    assert restored.source_file == "test.pdf"
    assert len(restored.tables) == 1
    assert restored.tables[0].columns == ["Description", "Amount"]


def test_table_to_dicts():
    table = ExtractedTable(
        columns=["Item", "Qty", "Price"],
        rows=[["Widget", "2", "9.99"], ["Gadget", "1", "24.99"]],
        source="pymupdf",
    )
    dicts = table.to_dicts()
    assert len(dicts) == 2
    assert dicts[0] == {"Item": "Widget", "Qty": "2", "Price": "9.99"}


def test_table_to_dicts_no_columns():
    table = ExtractedTable(
        columns=None,
        rows=[["a", "b"], ["c", "d"]],
        source="markdown_import",
    )
    dicts = table.to_dicts()
    assert dicts[0] == {"col_0": "a", "col_1": "b"}


def test_structured_record_serialization():
    record = StructuredRecord(
        document_id="abc123",
        source_file="test.pdf",
        fields={"invoice_number": "INV-001", "total_amount": "1320.00"},
        line_items=[{"description": "Freight", "amount": "1200.00"}],
    )
    data = json.loads(record.model_dump_json())
    assert data["fields"]["invoice_number"] == "INV-001"
    assert len(data["line_items"]) == 1


def test_batch_result_partial():
    r = BatchResult(source_file="bad.pdf", status="failed", error_message="unreadable")
    assert r.status == "failed"
    assert r.tables_found == 0
