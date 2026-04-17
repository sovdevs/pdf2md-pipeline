from pathlib import Path
import pytest
from pdf_to_markdown.extractor import extract_pages, extract_with_pymupdf, PageText

SAMPLES_DIR = Path(__file__).parent.parent / "samples"
SAMPLE_PDFS = sorted(SAMPLES_DIR.glob("*.pdf"))


@pytest.mark.parametrize("pdf_path", SAMPLE_PDFS, ids=lambda p: p.name)
def test_extract_pages_returns_text(pdf_path):
    pages = extract_pages(pdf_path)
    assert len(pages) > 0
    assert all(isinstance(p, PageText) for p in pages)
    assert all(p.text.strip() for p in pages), "At least one page returned empty text"
    assert all(p.page_number >= 1 for p in pages)


@pytest.mark.parametrize("pdf_path", SAMPLE_PDFS, ids=lambda p: p.name)
def test_pymupdf_fallback(pdf_path):
    pages = extract_with_pymupdf(pdf_path)
    assert len(pages) > 0
    assert pages[0].extraction_method == "pymupdf"
