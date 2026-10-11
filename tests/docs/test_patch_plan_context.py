from __future__ import annotations

from pathlib import Path

import docmancer.docs.patch_plan_context as patch_plan_context
from docmancer.docs.patch_plan_context import build_patch_plan_context


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


