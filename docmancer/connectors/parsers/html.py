from __future__ import annotations

from pathlib import Path

from docmancer.core.html_utils import extract_main_content
from docmancer.core.models import Document


class HTMLLoader:
    supported_extensions = [".html", ".htm"]
    chunking_strategy = "heading"

    def load(self, path: Path) -> Document:
        html = path.read_text(encoding="utf-8", errors="replace")
        content = extract_main_content(html)
        if not content:
            raise ValueError(f"No extractable text found in HTML: {path}")
        return Document(source=str(path), content=content, metadata={"format": "html", "title": path.stem})
