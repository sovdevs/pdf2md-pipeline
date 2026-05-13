"""P2 tests: schema loading, prompt building, validation, LLM extract pipeline.

LLM calls are mocked — no API key required.
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pdf_to_markdown.structured.models import ExtractedDocument, ExtractedPage, ExtractedTable
from pdf_to_markdown.structured.schema import ExtractionSchema, build_prompt, load_schema
from pdf_to_markdown.structured.validation import validate_and_build_record

FIXTURES = Path(__file__).parent / "fixtures"
SCHEMAS = Path(__file__).parent.parent.parent / "schemas"


# ── Schema loading ────────────────────────────────────────────────────────────

def test_load_generic_invoice_schema():
    schema = load_schema(SCHEMAS / "generic_invoice.json")
    assert schema.document_type == "generic_invoice"
    assert "invoice_number" in schema.all_field_names
    assert "total_amount" in schema.required_fields


def test_load_logistics_schema():
    schema = load_schema(SCHEMAS / "logistics_load.json")
    assert schema.document_type == "logistics_load"
    assert "load_number" in schema.required_fields
    assert "carrier" in schema.required_fields


def test_schema_missing_file():
    from pdf_to_markdown.structured.schema import SchemaError
    with pytest.raises(SchemaError):
        load_schema(Path("/nonexistent/schema.json"))


def test_schema_required_fields():
    schema = load_schema(SCHEMAS / "generic_invoice.json")
    required = schema.required_fields
    assert "invoice_number" in required
    assert "total_amount" in required
    assert "due_date" not in required  # optional


# ── Prompt building ───────────────────────────────────────────────────────────

def test_build_prompt_contains_field_names():
    schema = load_schema(SCHEMAS / "generic_invoice.json")
    _, user_prompt = build_prompt(schema, "Invoice Number: INV-001\nTotal: $1200")
    assert "invoice_number" in user_prompt
    assert "total_amount" in user_prompt
    assert "INV-001" in user_prompt


def test_build_prompt_marks_required():
    schema = load_schema(SCHEMAS / "generic_invoice.json")
    _, user_prompt = build_prompt(schema, "some text")
    assert "REQUIRED" in user_prompt


def test_build_prompt_includes_line_items():
    schema = load_schema(SCHEMAS / "logistics_load.json")
    _, user_prompt = build_prompt(schema, "Load: LD-001")
    assert "line_items" in user_prompt.lower() or "Line items" in user_prompt


# ── Validation ────────────────────────────────────────────────────────────────

def _invoice_schema() -> ExtractionSchema:
    return load_schema(SCHEMAS / "generic_invoice.json")


def test_validation_happy_path():
    schema = _invoice_schema()
    parsed = {
        "document_type": "generic_invoice",
        "fields": {
            "invoice_number": "INV-001",
            "invoice_date": "2024-03-15",
            "total_amount": "1200.00",
            "vendor_name": "Acme",
        },
        "line_items": [{"description": "Freight", "amount": "1200.00"}],
        "confidence": 0.9,
        "warnings": [],
    }
    record, warnings = validate_and_build_record("doc1", "invoice.pdf", parsed, schema)
    assert record.fields["invoice_number"] == "INV-001"
    assert record.confidence == 0.9
    assert not any("Required" in w for w in warnings)


def test_validation_missing_required_field():
    schema = _invoice_schema()
    parsed = {
        "fields": {"vendor_name": "Acme"},  # missing invoice_number and total_amount
        "line_items": [],
        "confidence": 0.5,
        "warnings": [],
    }
    record, warnings = validate_and_build_record("doc1", "invoice.pdf", parsed, schema)
    warning_text = " ".join(warnings)
    assert "invoice_number" in warning_text
    assert "total_amount" in warning_text


def test_validation_strips_unexpected_fields():
    schema = _invoice_schema()
    parsed = {
        "fields": {
            "invoice_number": "INV-001",
            "total_amount": "500",
            "hallucinated_field": "bogus",
        },
        "line_items": [],
        "confidence": 0.8,
        "warnings": [],
    }
    record, warnings = validate_and_build_record("doc1", "invoice.pdf", parsed, schema)
    assert "hallucinated_field" not in record.fields
    assert any("hallucinated_field" in w for w in warnings)


def test_validation_invalid_line_item_skipped():
    schema = _invoice_schema()
    parsed = {
        "fields": {"invoice_number": "INV-001", "total_amount": "100"},
        "line_items": ["not_a_dict", {"description": "Valid", "amount": "100"}],
        "confidence": 0.7,
        "warnings": [],
    }
    record, warnings = validate_and_build_record("doc1", "invoice.pdf", parsed, schema)
    assert len(record.line_items) == 1
    assert any("not a dict" in w for w in warnings)


# ── LLM extract (mocked) ──────────────────────────────────────────────────────

def _make_doc(text: str) -> ExtractedDocument:
    return ExtractedDocument(
        source_file="test.pdf",
        page_count=1,
        pages=[ExtractedPage(page_number=1, text=text)],
    )


def _mock_gemini_response(json_payload: dict):
    """Return a mock Gemini client that yields the given JSON payload."""
    mock_response = MagicMock()
    mock_response.text = json.dumps(json_payload)
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
    return mock_client


@pytest.mark.asyncio
async def test_llm_extract_invoice_fixture():
    """Invoice fixture markdown → structured JSON fields via mocked LLM."""
    schema = load_schema(SCHEMAS / "generic_invoice.json")
    doc = _make_doc((FIXTURES / "synthetic_invoice.md").read_text())

    llm_payload = {
        "document_type": "generic_invoice",
        "fields": {
            "invoice_number": "INV-2024-0042",
            "invoice_date": "2024-03-15",
            "total_amount": "1395.00",
            "vendor_name": "Acme Freight Solutions LLC",
        },
        "line_items": [
            {"description": "LTL Freight", "amount": "1200.00"},
        ],
        "confidence": 0.95,
        "warnings": [],
    }

    with patch("pdf_to_markdown.structured.llm_extract.genai.Client", return_value=_mock_gemini_response(llm_payload)):
        from pdf_to_markdown.structured.llm_extract import extract_structured
        semaphore = asyncio.Semaphore(1)
        record = await extract_structured(doc, schema, "fake-key", "gemini-2.0-flash", semaphore)

    assert record.fields["invoice_number"] == "INV-2024-0042"
    assert record.fields["total_amount"] == "1395.00"
    assert record.extraction_method == "llm"
    assert len(record.line_items) == 1


@pytest.mark.asyncio
async def test_llm_extract_logistics_fixture():
    """Logistics fixture markdown → structured JSON fields via mocked LLM."""
    schema = load_schema(SCHEMAS / "logistics_load.json")
    doc = _make_doc((FIXTURES / "synthetic_logistics.md").read_text())

    llm_payload = {
        "document_type": "logistics_load",
        "fields": {
            "load_number": "LD-88210",
            "carrier": "Swift Transport Inc.",
            "total_amount": "1095.00",
            "origin": "Chicago, IL",
            "destination": "Detroit, MI",
        },
        "line_items": [
            {"description": "Base Rate", "amount": "950.00"},
        ],
        "confidence": 0.92,
        "warnings": [],
    }

    with patch("pdf_to_markdown.structured.llm_extract.genai.Client", return_value=_mock_gemini_response(llm_payload)):
        from pdf_to_markdown.structured.llm_extract import extract_structured
        semaphore = asyncio.Semaphore(1)
        record = await extract_structured(doc, schema, "fake-key", "gemini-2.0-flash", semaphore)

    assert record.fields["load_number"] == "LD-88210"
    assert record.fields["carrier"] == "Swift Transport Inc."
    assert record.extraction_method == "llm"


@pytest.mark.asyncio
async def test_llm_invalid_json_falls_back_to_p1():
    """Invalid JSON from LLM → P1 heuristic fallback, no crash."""
    schema = load_schema(SCHEMAS / "generic_invoice.json")
    doc = _make_doc("Invoice Number: INV-001")

    mock_response = MagicMock()
    mock_response.text = "This is not JSON at all"
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    with patch("pdf_to_markdown.structured.llm_extract.genai.Client", return_value=mock_client):
        from pdf_to_markdown.structured.llm_extract import extract_structured
        semaphore = asyncio.Semaphore(1)
        record = await extract_structured(doc, schema, "fake-key", "gemini-2.0-flash", semaphore)

    assert record.extraction_method == "heuristic"
    assert any("invalid JSON" in w for w in record.warnings)


@pytest.mark.asyncio
async def test_llm_api_failure_falls_back_to_p1():
    """LLM API error → P1 fallback, no crash."""
    schema = load_schema(SCHEMAS / "generic_invoice.json")
    doc = _make_doc("Invoice Number: INV-001")

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("API down"))

    with patch("pdf_to_markdown.structured.llm_extract.genai.Client", return_value=mock_client):
        from pdf_to_markdown.structured.llm_extract import extract_structured
        semaphore = asyncio.Semaphore(1)
        record = await extract_structured(doc, schema, "fake-key", "gemini-2.0-flash", semaphore)

    assert record.extraction_method == "heuristic"
    assert any("LLM call failed" in w for w in record.warnings)
