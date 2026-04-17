"""
Demo server — serves the static demo page and handles PDF upload processing.
Run with: uv run uvicorn demo.server:app --reload
"""
import asyncio
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from pdf_to_markdown.config import load_settings
from pdf_to_markdown.extractor import extract_pages, ExtractionError
from pdf_to_markdown.llm import process_page
from pdf_to_markdown.assembler import assemble, extract_front_matter
from pdf_to_markdown.validator import validate_document
import yaml

app = FastAPI(title="PDF → Markdown Demo")

DEMO_DIR = Path(__file__).parent
REPO_ROOT = DEMO_DIR.parent


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/convert")
async def convert_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    if file.size and file.size > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large — 20 MB max for the demo.")

    settings = load_settings()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        pages = extract_pages(tmp_path)
    except ExtractionError as e:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Could not extract text from PDF: {e}")

    semaphore = asyncio.Semaphore(settings.max_concurrent_pages)
    try:
        pages_md = await asyncio.gather(
            *[process_page(p, len(pages), settings, semaphore) for p in pages]
        )
    except Exception as e:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=502, detail=f"Gemini API error: {e}")

    markdown = assemble(list(pages_md), file.filename)
    metadata, body = extract_front_matter(markdown)
    fixed_body, warnings = validate_document(body, metadata)
    yaml_block = yaml.dump(metadata, allow_unicode=True, default_flow_style=False).strip()
    final_markdown = f"---\n{yaml_block}\n---\n\n{fixed_body}\n"

    tmp_path.unlink(missing_ok=True)

    return JSONResponse({
        "filename": file.filename,
        "markdown": final_markdown,
        "warnings": warnings,
        "pages": len(pages),
        "extractor": pages[0].extraction_method if pages else "unknown",
    })


# Serve attachments (PDFs) and static demo files — API routes registered first take priority
app.mount("/attachments", StaticFiles(directory=str(REPO_ROOT / "attachments")), name="attachments")
app.mount("/", StaticFiles(directory=str(DEMO_DIR), html=True), name="static")
