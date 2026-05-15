from pathlib import Path

from docmancer.connectors.parsers.text import TextLoader
from docmancer.connectors.parsers.markdown import MarkdownLoader
from docmancer.connectors.parsers.html import HTMLLoader
from docmancer.connectors.parsers.pdf import PDFLoader
from docmancer.connectors.parsers.rtf import RTFLoader

def test_text_loader(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("Hello world")
    doc = TextLoader().load(f)
    assert doc.content == "Hello world"
    assert ".txt" in TextLoader.supported_extensions

def test_markdown_loader(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("# Title\nContent")
    doc = MarkdownLoader().load(f)
    assert "Title" in doc.content
    assert ".md" in MarkdownLoader.supported_extensions

def test_markdown_loader_reads_front_matter_title(tmp_path):
    f = tmp_path / "test.md"
    f.write_text('---\ntitle: "Front Matter Title"\n---\n\n# Body\nContent')
    doc = MarkdownLoader().load(f)
    assert doc.metadata["title"] == "Front Matter Title"

def test_html_loader_extracts_main_content(tmp_path):
    f = tmp_path / "test.html"
    f.write_text("<html><body><nav>skip</nav><main><h1>Title</h1><p>Body</p></main></body></html>")
    doc = HTMLLoader().load(f)
    assert "Title" in doc.content
    assert "Body" in doc.content
    assert "skip" not in doc.content
    assert doc.metadata["format"] == "html"

def test_rtf_loader_extracts_text(tmp_path):
    f = tmp_path / "test.rtf"
    f.write_text(r"{\rtf1\ansi This is {\b bold} text.}")
    doc = RTFLoader().load(f)
    assert "bold" in doc.content
    assert doc.metadata["format"] == "rtf"

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
