"""Intermediate representation models for structured PDF extraction.

All exporters (CSV, XLSX) target these models — extraction logic is
decoupled from output format.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class ExtractionWarning(BaseModel):
    code: str
    message: str
    page_number: Optional[int] = None


class TextBlock(BaseModel):
    page_number: int
    text: str
    block_type: str = "paragraph"  # paragraph | heading | list_item | caption | key_value


class ExtractedTable(BaseModel):
    table_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    page_number: Optional[int] = None
    columns: Optional[list[str]] = None      # None = no header row detected
    rows: list[list[str]] = []               # data rows (header excluded if columns set)
    confidence: Optional[float] = None
    source: str = "pymupdf"                  # pymupdf | docling | gemini | markdown_import
    notes: list[str] = []

    def to_dicts(self) -> list[dict[str, str]]:
        """Return rows as list of dicts. Falls back to positional keys if no columns."""
        cols = self.columns or [f"col_{i}" for i in range(len(self.rows[0]))] if self.rows else []
        return [dict(zip(cols, row)) for row in self.rows]


class ExtractedPage(BaseModel):
    page_number: int
    text: str
    tables: list[ExtractedTable] = []
    extraction_method: str = "pymupdf"


class ExtractedDocument(BaseModel):
    document_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    source_file: str
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pages: list[ExtractedPage] = []
    tables: list[ExtractedTable] = []    # all tables across all pages (flat view)
    text_blocks: list[TextBlock] = []    # all non-table text blocks
    warnings: list[ExtractionWarning] = []
    extraction_method: str = "pymupdf"
    page_count: int = 0

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text.strip())


class StructuredRecord(BaseModel):
    """Schema-extracted fields from one document.

    At P1 this is created directly from ExtractedDocument (tables → line_items,
    text blocks → fields where key:value patterns are found).
    At P2+ it will be populated by schema-guided LLM extraction.
    """
    document_id: str
    source_file: str
    document_type: str = "unknown"
    fields: dict[str, Any] = {}
    line_items: list[dict[str, Any]] = []
    confidence: Optional[float] = None
    warnings: list[str] = []
    extraction_method: str = "heuristic"


class BatchResult(BaseModel):
    source_file: str
    status: str                          # success | failed | partial
    document_id: Optional[str] = None
    pages: int = 0
    tables_found: int = 0
    fields_found: int = 0
    warnings_count: int = 0
    errors_count: int = 0
    output_json: Optional[str] = None
    output_xlsx: Optional[str] = None
    output_csv_dir: Optional[str] = None
    processing_seconds: float = 0.0
    extraction_methods: list[str] = []
    error_message: Optional[str] = None
