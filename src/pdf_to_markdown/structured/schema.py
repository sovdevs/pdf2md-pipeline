"""Schema loader and prompt builder for structured LLM extraction.

A schema JSON defines document_type, fields (with required/type/description),
and line_items. This module:
  - loads and validates schema files
  - builds the Gemini prompt from schema + document content
  - defines the expected LLM JSON output shape
"""

import json
from pathlib import Path
from typing import Any


class SchemaError(Exception):
    pass


class ExtractionSchema:
    def __init__(self, data: dict):
        self.document_type: str = data.get("document_type", "unknown")
        self.description: str = data.get("description", "")
        self.fields: list[dict] = data.get("fields", [])
        self.line_items: list[dict] = data.get("line_items", [])

    @property
    def required_fields(self) -> list[str]:
        return [f["name"] for f in self.fields if f.get("required")]

    @property
    def all_field_names(self) -> list[str]:
        return [f["name"] for f in self.fields]

    def empty_record(self) -> dict[str, Any]:
        """Return a dict with all field names set to None."""
        return {f["name"]: None for f in self.fields}


def load_schema(path: Path) -> ExtractionSchema:
    if not path.exists():
        raise SchemaError(f"Schema file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SchemaError(f"Invalid JSON in schema {path}: {e}") from e
    if "fields" not in data:
        raise SchemaError(f"Schema {path} must have a 'fields' list")
    return ExtractionSchema(data)


# ── Prompt construction ───────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a document data extraction system.
Your only job is to extract structured data from a document and return valid JSON.
Return ONLY a JSON object — no markdown, no code fences, no explanations.
If a field is not found in the document, use null.
Never invent or hallucinate values. If uncertain, use null and add a warning.
"""


def _field_description(f: dict) -> str:
    parts = [f"  - {f['name']} ({f.get('type', 'string')}"]
    if f.get("required"):
        parts[0] += ", REQUIRED"
    parts[0] += ")"
    if f.get("description"):
        parts.append(f"    Description: {f['description']}")
    return "\n".join(parts)


def build_prompt(schema: ExtractionSchema, document_text: str) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for a structured extraction call."""
    field_block = "\n".join(_field_description(f) for f in schema.fields)

    line_item_block = ""
    if schema.line_items:
        li_parts = "\n".join(
            f"  - {li['name']} ({li.get('type', 'string')}): {li.get('description', '')}"
            for li in schema.line_items
        )
        line_item_block = f"\nLine items (repeating rows, may be empty list):\n{li_parts}\n"

    # Build the expected JSON shape as an example
    example_fields = {f["name"]: f"<{f.get('type','string')}|null>" for f in schema.fields}
    example_items = [{li["name"]: f"<{li.get('type','string')}>" for li in schema.line_items}] if schema.line_items else []
    example_json = json.dumps({
        "document_type": schema.document_type,
        "fields": example_fields,
        "line_items": example_items,
        "confidence": "<0.0-1.0>",
        "warnings": ["<optional warning strings>"],
    }, indent=2)

    user_prompt = f"""\
Extract data from the document below using this schema.

Document type: {schema.document_type}
{f'Description: {schema.description}' if schema.description else ''}

Fields to extract:
{field_block}
{line_item_block}
Return JSON in exactly this shape:
{example_json}

DOCUMENT TEXT:
{document_text}
"""
    return _SYSTEM_PROMPT, user_prompt
