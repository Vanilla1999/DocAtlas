from __future__ import annotations

from pathlib import Path

from docmancer.core.models import Document


def _missing_pdf_extra() -> ImportError:
    return ImportError("PDF loader unavailable; reinstall docmancer (pypdf ships in core).")


class PDFLoader:
    supported_extensions = [".pdf"]
    chunking_strategy = "paragraph"

    def load(self, path: Path) -> Document:
        pages, title = self._load_with_pypdf(path)
        if not pages or self._average_chars(pages) < 50:
            fallback = self._load_with_pdfplumber(path)
            if fallback:
                pages = fallback
        if not pages:
            raise ValueError(f"No extractable text found in PDF: {path}")

        content = "\n\n".join(f"## Page {page_number}\n\n{text.strip()}" for page_number, text in pages if text.strip())
        return Document(
            source=str(path),
            content=content,
            metadata={
                "format": "pdf",
                "pages": [page_number for page_number, _ in pages],
                "title": title or path.stem,
            },
        )

    def _load_with_pypdf(self, path: Path) -> tuple[list[tuple[int, str]], str | None]:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise _missing_pdf_extra() from exc

        reader = PdfReader(str(path))
        pages: list[tuple[int, str]] = []
        for index, page in enumerate(reader.pages, start=1):
            pages.append((index, page.extract_text() or ""))
        title = None
        if reader.metadata and reader.metadata.title:
            title = str(reader.metadata.title)
        return pages, title

    def _load_with_pdfplumber(self, path: Path) -> list[tuple[int, str]]:
        try:
            import pdfplumber
        except ImportError:
            return []

        pages: list[tuple[int, str]] = []
        with pdfplumber.open(str(path)) as pdf:
            for index, page in enumerate(pdf.pages, start=1):
                pages.append((index, page.extract_text() or ""))
        return pages

    @staticmethod
    def _average_chars(pages: list[tuple[int, str]]) -> float:
        if not pages:
            return 0
        return sum(len(text.strip()) for _, text in pages) / len(pages)
