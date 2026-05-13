"""Schema-guided LLM extraction: ExtractedDocument → StructuredRecord.

Uses Gemini to extract structured JSON matching the schema fields.
Falls back to the P1 heuristic record on any failure — never crashes the batch.

Raw Gemini responses are saved as <stem>.llm_response.json for debugging.
"""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential

from pdf_to_markdown.structured.extract_document import document_to_structured_record
from pdf_to_markdown.structured.models import ExtractedDocument, StructuredRecord
from pdf_to_markdown.structured.schema import ExtractionSchema, build_prompt
from pdf_to_markdown.structured.validation import validate_and_build_record

logger = logging.getLogger(__name__)

_MAX_DOCUMENT_CHARS = 32_000  # truncate very long docs to stay within token limits


def _is_retryable(exc: BaseException) -> bool:
    msg = str(exc)
    return "429" not in msg and "RESOURCE_EXHAUSTED" not in msg


_retry = retry(
    retry=lambda rs: _is_retryable(rs.outcome.exception()) if rs.outcome.failed else False,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)


def _strip_fences(text: str) -> str:
    """Remove markdown code fences Gemini sometimes wraps JSON in."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _document_text(doc: ExtractedDocument) -> str:
    """Build a compact text representation of the document for the prompt."""
    parts: list[str] = []

    # Full text from pages
    full = doc.full_text
    if full:
        parts.append(full[:_MAX_DOCUMENT_CHARS])

    # Append table data as compact pipe tables if not already in text
    for i, table in enumerate(doc.tables, 1):
        if not table.rows:
            continue
        cols = table.columns or [f"col_{j}" for j in range(len(table.rows[0]))]
        header = "| " + " | ".join(cols) + " |"
        sep = "| " + " | ".join("---" for _ in cols) + " |"
        rows = ["| " + " | ".join(row) + " |" for row in table.rows[:50]]
        parts.append(f"\n[Table {i}]\n" + "\n".join([header, sep] + rows))

    combined = "\n\n".join(parts)
    return combined[:_MAX_DOCUMENT_CHARS]


async def extract_structured(
    doc: ExtractedDocument,
    schema: ExtractionSchema,
    api_key: str,
    model: str,
    semaphore: asyncio.Semaphore,
    intermediate_dir: Path | None = None,
) -> StructuredRecord:
    """Call Gemini with schema-guided prompt. Returns validated StructuredRecord.

    On any failure (network, JSON parse, validation error) returns the P1
    heuristic record with a warning attached — never raises.
    """
    fallback = document_to_structured_record(doc)

    system_prompt, user_prompt = build_prompt(schema, _document_text(doc))

    @_retry
    async def _call() -> str:
        client = genai.Client(api_key=api_key)
        response = await client.aio.models.generate_content(
            model=model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.0,
                max_output_tokens=4096,
            ),
        )
        return response.text

    raw_text: str = ""
    async with semaphore:
        logger.info(f"  LLM extract: {doc.source_file} ({schema.document_type})")
        try:
            raw_text = await _call()
            logger.info(f"  LLM done: {doc.source_file} ({len(raw_text)} chars)")
        except Exception as e:
            logger.warning(f"  LLM call failed for {doc.source_file}: {e} — using P1 fallback")
            fallback.warnings.append(f"LLM call failed: {e}")
            return fallback

    # Save raw response for debugging
    if intermediate_dir:
        stem = Path(doc.source_file).stem
        raw_path = intermediate_dir / f"{stem}.llm_response.json"
        raw_path.write_text(
            json.dumps({"raw": raw_text}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # Parse JSON
    try:
        parsed: dict[str, Any] = json.loads(_strip_fences(raw_text))
    except json.JSONDecodeError as e:
        logger.warning(f"  LLM returned invalid JSON for {doc.source_file}: {e} — using P1 fallback")
        fallback.warnings.append(f"LLM returned invalid JSON: {e}")
        return fallback

    # Validate and build record
    record, warnings = validate_and_build_record(
        document_id=doc.document_id,
        source_file=doc.source_file,
        parsed=parsed,
        schema=schema,
        extraction_method="llm",
    )

    if warnings:
        for w in warnings:
            logger.info(f"  Validation warning [{doc.source_file}]: {w}")

    return record


def run_llm_extract_sync(
    doc: ExtractedDocument,
    schema: ExtractionSchema,
    api_key: str,
    model: str = "gemini-2.0-flash",
    llm_concurrency: int = 2,
    intermediate_dir: Path | None = None,
) -> StructuredRecord:
    """Synchronous wrapper for use in ThreadPoolExecutor contexts."""
    semaphore = asyncio.Semaphore(llm_concurrency)
    return asyncio.run(
        extract_structured(doc, schema, api_key, model, semaphore, intermediate_dir)
    )
