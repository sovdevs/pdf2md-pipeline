import asyncio
import pytest
from pathlib import Path

from pdf_to_markdown.extractor import extract_with_pymupdf
from pdf_to_markdown.llm import process_page
from pdf_to_markdown.config import load_settings

SAMPLE = Path(__file__).parent.parent / "samples" / "NTA_PdR_PdS_Parte prima_Page3.pdf"


@pytest.mark.skipif(not SAMPLE.exists(), reason="sample PDF not found")
def test_process_page_returns_markdown():
    settings = load_settings()
    pages = extract_with_pymupdf(SAMPLE)
    assert pages, "No pages extracted"

    page = pages[0]
    semaphore = asyncio.Semaphore(1)
    result = asyncio.run(process_page(page, total_pages=1, settings=settings, semaphore=semaphore))

    assert result.strip(), "LLM returned empty string"
    # Page 1 should produce YAML front matter
    assert "---" in result, f"Expected YAML front matter, got:\n{result[:300]}"
    # Should contain at least one heading
    assert any(line.startswith("#") for line in result.splitlines()), \
        f"No heading found in output:\n{result[:300]}"

    print("\n--- LLM output preview ---")
    print(result[:600])
