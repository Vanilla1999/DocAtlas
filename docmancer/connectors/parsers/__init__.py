from docmancer.connectors.parsers.text import TextLoader
from docmancer.connectors.parsers.markdown import MarkdownLoader
from docmancer.connectors.parsers.pdf import PDFLoader
from docmancer.connectors.parsers.docx import DOCXLoader
from docmancer.connectors.parsers.rtf import RTFLoader
from docmancer.connectors.parsers.html import HTMLLoader

__all__ = ["TextLoader", "MarkdownLoader", "PDFLoader", "DOCXLoader", "RTFLoader", "HTMLLoader"]
