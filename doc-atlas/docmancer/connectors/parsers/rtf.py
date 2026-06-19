from __future__ import annotations

from pathlib import Path

from docmancer.core.models import Document


class RTFLoader:
    supported_extensions = [".rtf"]
    chunking_strategy = "paragraph"

    def load(self, path: Path) -> Document:
        try:
            from striprtf.striprtf import rtf_to_text
        except ImportError as exc:
            raise ImportError("RTF loader unavailable; reinstall docmancer (striprtf ships in core).") from exc

        text = rtf_to_text(path.read_text(encoding="utf-8", errors="replace")).strip()
        if not text:
            raise ValueError(f"No extractable text found in RTF: {path}")
        content = "\n\n".join(part.strip() for part in text.splitlines() if part.strip())
        return Document(source=str(path), content=content, metadata={"format": "rtf", "title": path.stem})
