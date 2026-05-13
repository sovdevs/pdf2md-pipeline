"""Validate a parsed LLM JSON response against the extraction schema.

Returns a (StructuredRecord, warnings) tuple.
Never raises — validation failures become warnings so the batch continues.
"""

from typing import Any

from pdf_to_markdown.structured.models import StructuredRecord
from pdf_to_markdown.structured.schema import ExtractionSchema


def validate_and_build_record(
    document_id: str,
    source_file: str,
    parsed: dict[str, Any],
    schema: ExtractionSchema,
    extraction_method: str = "llm",
) -> tuple[StructuredRecord, list[str]]:
    """Validate parsed LLM output and return (StructuredRecord, warnings)."""
    warnings: list[str] = list(parsed.get("warnings") or [])

    fields: dict[str, Any] = parsed.get("fields") or {}
    line_items: list[dict] = parsed.get("line_items") or []
    confidence: float | None = _parse_confidence(parsed.get("confidence"))

    # Check required fields
    for name in schema.required_fields:
        val = fields.get(name)
        if val is None or (isinstance(val, str) and not val.strip()):
            warnings.append(f"Required field missing or empty: '{name}'")

    # Drop fields not in schema (avoid hallucinated keys)
    known = set(schema.all_field_names)
    extra = [k for k in fields if k not in known]
    for k in extra:
        warnings.append(f"Unexpected field ignored: '{k}'")
        fields.pop(k)

    # Validate line items have at least the expected keys
    li_keys = {li["name"] for li in schema.line_items}
    cleaned_items = []
    for i, item in enumerate(line_items):
        if not isinstance(item, dict):
            warnings.append(f"Line item {i} is not a dict — skipped")
            continue
        cleaned_items.append({k: v for k, v in item.items() if k in li_keys})

    record = StructuredRecord(
        document_id=document_id,
        source_file=source_file,
        document_type=schema.document_type,
        fields=fields,
        line_items=cleaned_items,
        confidence=confidence,
        warnings=warnings,
        extraction_method=extraction_method,
    )
    return record, warnings


def _parse_confidence(value: Any) -> float | None:
    try:
        f = float(value)
        return max(0.0, min(1.0, f))
    except (TypeError, ValueError):
        return None
