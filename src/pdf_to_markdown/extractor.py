from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    pass


@dataclass
class PageText:
    page_number: int  # 1-based
    text: str
    extraction_method: str  # "docling" or "pymupdf"


def extract_with_docling(pdf_path: Path) -> list[PageText]:
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))
    doc = result.document

    pages: list[PageText] = []
    for page_no, page in doc.pages.items():
        # Export just this page's content as markdown text
        # We collect text elements belonging to this page
        texts = []
        for item, _ in doc.iterate_items():
            prov = getattr(item, "prov", None)
            if prov and any(p.page_no == page_no for p in prov):
                raw = getattr(item, "text", None)
                if raw:
                    texts.append(raw)

        page_text = "\n\n".join(texts)
        if page_text.strip():
            pages.append(PageText(
                page_number=page_no,
                text=page_text,
                extraction_method="docling",
            ))

    if not pages:
        raise ExtractionError(f"Docling returned no text for {pdf_path}")
    return pages


def extract_with_pymupdf(pdf_path: Path) -> list[PageText]:
    import fitz  # PyMuPDF

    pages: list[PageText] = []
    with fitz.open(str(pdf_path)) as doc:
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text")
            if text.strip():
                pages.append(PageText(
                    page_number=i,
                    text=text,
                    extraction_method="pymupdf",
                ))

    if not pages:
        raise ExtractionError(f"PyMuPDF returned no text for {pdf_path}")
    return pages


def extract_pages(pdf_path: Path) -> list[PageText]:
    docling_err: Exception | None = None
    try:
        pages = extract_with_docling(pdf_path)
        logger.info(f"Docling extracted {len(pages)} page(s) from {pdf_path.name}")
        return pages
    except Exception as exc:
        docling_err = exc
        logger.warning(f"Docling failed for {pdf_path.name}: {exc} — falling back to PyMuPDF")

    try:
        pages = extract_with_pymupdf(pdf_path)
        logger.info(f"PyMuPDF extracted {len(pages)} page(s) from {pdf_path.name}")
        return pages
    except Exception as pymupdf_err:
        raise ExtractionError(
            f"Both extractors failed for {pdf_path.name}. "
            f"Docling: {docling_err}. PyMuPDF: {pymupdf_err}"
        ) from pymupdf_err
