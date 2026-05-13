"""Two-phase batch processor for structured PDF extraction.

Phase 1 — parallel per-PDF extraction:
  Each PDF → ExtractedDocument → (optional LLM) → StructuredRecord → JSON artifacts

Phase 2 — sequential XLSX write:
  All JSON artifacts → single batch_results.xlsx (never written from parallel workers)

Retry/resume: Phase 1 skips PDFs that already have a .extracted_document.json
unless --force is passed.
"""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from pdf_to_markdown.structured.extract_document import (
    document_to_structured_record,
    extract_document,
)
from pdf_to_markdown.structured.models import BatchResult, ExtractedDocument, StructuredRecord
from pdf_to_markdown.structured.xlsx_writer import write_batch_xlsx

logger = logging.getLogger(__name__)


def _artifact_path(intermediate_dir: Path, stem: str, kind: str) -> Path:
    return intermediate_dir / f"{stem}.{kind}.json"


def _save_artifacts(
    intermediate_dir: Path,
    stem: str,
    doc: ExtractedDocument,
    record: StructuredRecord,
) -> None:
    intermediate_dir.mkdir(parents=True, exist_ok=True)
    _artifact_path(intermediate_dir, stem, "extracted_document").write_text(
        doc.model_dump_json(indent=2), encoding="utf-8"
    )
    _artifact_path(intermediate_dir, stem, "structured_record").write_text(
        record.model_dump_json(indent=2), encoding="utf-8"
    )


def _load_artifacts(
    intermediate_dir: Path, stem: str
) -> tuple[ExtractedDocument, StructuredRecord] | None:
    ed_path = _artifact_path(intermediate_dir, stem, "extracted_document")
    sr_path = _artifact_path(intermediate_dir, stem, "structured_record")
    if ed_path.exists() and sr_path.exists():
        doc = ExtractedDocument.model_validate_json(ed_path.read_text(encoding="utf-8"))
        record = StructuredRecord.model_validate_json(sr_path.read_text(encoding="utf-8"))
        return doc, record
    return None


def _process_one(
    pdf_path: Path,
    intermediate_dir: Path,
    force: bool,
    schema=None,
    api_key: str = "",
    model: str = "gemini-2.0-flash",
    llm_concurrency: int = 2,
) -> BatchResult:
    stem = pdf_path.stem
    start = time.monotonic()

    # Resume: skip if artifacts already exist (unless force)
    if not force:
        cached = _load_artifacts(intermediate_dir, stem)
        if cached:
            doc, record = cached
            logger.info(f"  RESUME {pdf_path.name} (artifacts exist)")
            return BatchResult(
                source_file=pdf_path.name,
                status="success",
                document_id=doc.document_id,
                pages=doc.page_count,
                tables_found=len(doc.tables),
                fields_found=len(record.fields),
                warnings_count=len(doc.warnings),
                output_json=str(_artifact_path(intermediate_dir, stem, "extracted_document")),
                processing_seconds=0.0,
                extraction_methods=[doc.extraction_method],
            )

    try:
        # ── P1: deterministic extraction ──────────────────────────────────────
        doc = extract_document(pdf_path)
        record = document_to_structured_record(doc)

        # ── P2: optional schema-guided LLM extraction ─────────────────────────
        if schema and api_key:
            from pdf_to_markdown.structured.llm_extract import run_llm_extract_sync
            record = run_llm_extract_sync(
                doc=doc,
                schema=schema,
                api_key=api_key,
                model=model,
                llm_concurrency=llm_concurrency,
                intermediate_dir=intermediate_dir,
            )

        _save_artifacts(intermediate_dir, stem, doc, record)

        elapsed = time.monotonic() - start
        methods = [doc.extraction_method, record.extraction_method] if schema else [doc.extraction_method]
        logger.info(
            f"  OK  {pdf_path.name} — "
            f"{doc.page_count}p, {len(doc.tables)} tables, "
            f"{len(record.fields)} fields ({elapsed:.1f}s)"
        )
        return BatchResult(
            source_file=pdf_path.name,
            status="success",
            document_id=doc.document_id,
            pages=doc.page_count,
            tables_found=len(doc.tables),
            fields_found=len(record.fields),
            warnings_count=len(doc.warnings) + len(record.warnings),
            errors_count=0,
            output_json=str(_artifact_path(intermediate_dir, stem, "extracted_document")),
            processing_seconds=elapsed,
            extraction_methods=methods,
        )

    except Exception as e:
        elapsed = time.monotonic() - start
        logger.error(f"  ERR {pdf_path.name}: {e}")
        err_path = intermediate_dir / f"{stem}.error.json"
        err_path.write_text(
            json.dumps({"file": pdf_path.name, "error": str(e)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return BatchResult(
            source_file=pdf_path.name,
            status="failed",
            errors_count=1,
            processing_seconds=elapsed,
            error_message=str(e),
        )


def run_batch(
    pdf_paths: list[Path],
    intermediate_dir: Path,
    output_dir: Path,
    workers: int = 2,
    force: bool = False,
    template_path: Optional[Path] = None,
    schema=None,
    api_key: str = "",
    model: str = "gemini-2.0-flash",
    llm_concurrency: int = 2,
) -> dict:
    """Run full two-phase batch. Returns summary dict."""
    output_dir.mkdir(parents=True, exist_ok=True)
    intermediate_dir.mkdir(parents=True, exist_ok=True)

    # ── Phase 1: parallel extraction (+ optional LLM per PDF) ────────────────
    mode = f"LLM ({schema.document_type})" if schema and api_key else "deterministic"
    logger.info(f"Phase 1: {mode} extraction of {len(pdf_paths)} PDF(s) with {workers} worker(s)…")
    batch_results: list[BatchResult] = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _process_one, p, intermediate_dir, force,
                schema, api_key, model, llm_concurrency,
            ): p
            for p in pdf_paths
        }
        for future in as_completed(futures):
            batch_results.append(future.result())

    succeeded = [r for r in batch_results if r.status == "success"]
    failed = [r for r in batch_results if r.status != "success"]

    # ── Phase 2: sequential XLSX write ───────────────────────────────────────
    logger.info(f"Phase 2: writing XLSX from {len(succeeded)} successful extraction(s)…")
    records: list[tuple[ExtractedDocument, StructuredRecord]] = []
    for result in succeeded:
        stem = Path(result.source_file).stem
        cached = _load_artifacts(intermediate_dir, stem)
        if cached:
            records.append(cached)

    batch_xlsx = output_dir / "batch_results.xlsx"
    if records:
        write_batch_xlsx(records, batch_xlsx, template_path=template_path)
        logger.info(f"  → {batch_xlsx}")

    # ── Batch report ──────────────────────────────────────────────────────────
    report = {
        "total": len(pdf_paths),
        "succeeded": len(succeeded),
        "failed": len(failed),
        "results": [r.model_dump() for r in batch_results],
    }
    (output_dir / "batch_report.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    if failed:
        (output_dir / "failed_files.json").write_text(
            json.dumps([r.model_dump() for r in failed], indent=2, default=str),
            encoding="utf-8",
        )

    return report
