from __future__ import annotations
from pathlib import Path
from docmancer.core.models import Document

class TextLoader:
    supported_extensions = [".txt"]
    chunking_strategy = "paragraph"

    def load(self, path: Path) -> Document:
        data = path.read_bytes()
        try:
            from charset_normalizer import from_bytes
        except ImportError:
            content = data.decode("utf-8", errors="replace")
        else:
            match = from_bytes(data).best()
            content = str(match) if match is not None else data.decode("utf-8", errors="replace")
        return Document(source=str(path), content=content, metadata={"format": "txt", "title": path.stem})
