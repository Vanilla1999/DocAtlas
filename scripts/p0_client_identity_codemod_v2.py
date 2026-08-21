from __future__ import annotations

from pathlib import Path

import p0_client_identity_codemod as codemod


_original_replace = codemod.replace


def _replace(path: str, old: str, new: str, *, expected: int | None = None) -> None:
    if old == 'help="Path to docmancer.yaml."' and old not in Path(path).read_text(encoding="utf-8"):
        return
    _original_replace(path, old, new, expected=expected)


codemod.replace = _replace
codemod.main()
