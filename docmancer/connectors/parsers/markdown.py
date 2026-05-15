from __future__ import annotations
from pathlib import Path
import re
import yaml

from docmancer.core.models import Document


_FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class MarkdownLoader:
    supported_extensions = [".md"]
    chunking_strategy = "heading"

    def load(self, path: Path) -> Document:
        content = path.read_text(encoding="utf-8")
        title = path.stem
        match = _FRONT_MATTER_RE.match(content)
        if match:
            try:
                front_matter = yaml.safe_load(match.group(1)) or {}
            except yaml.YAMLError:
                front_matter = {}
            if isinstance(front_matter, dict) and front_matter.get("title"):
                title = str(front_matter["title"])
        return Document(source=str(path), content=content, metadata={"format": "markdown", "title": title})
