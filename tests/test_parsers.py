from pathlib import Path

from docmancer.connectors.parsers.text import TextLoader
from docmancer.connectors.parsers.markdown import MarkdownLoader
from docmancer.connectors.parsers.html import HTMLLoader
from docmancer.connectors.parsers.pdf import PDFLoader
from docmancer.connectors.parsers.rtf import RTFLoader






def test_pdf_loader_extracts_generated_story_pdf():
    pdf = (
        Path(__file__).resolve().parents[2]
        / "test-corpora"
        / "stories-pdf"
        / "11-alice-s-adventures-in-wonderland.pdf"
    )
    if not pdf.exists():
        import pytest

        pytest.skip("story PDF fixture has not been generated")
    doc = PDFLoader().load(pdf)
    assert "Alice" in doc.content
    assert doc.metadata["format"] == "pdf"
    assert doc.metadata["pages"]
