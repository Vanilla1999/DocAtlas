#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


path = Path("scripts/run_systemic_retrieval_plan_gate.py")
text = path.read_text(encoding="utf-8")
anchor = "\ndef _candidate_pool_fingerprint(pool: list[Any]) -> str:\n"
if anchor not in text:
    raise SystemExit("candidate fingerprint anchor missing")

if "def _semantic_source_identity(" not in text:
    helper = r'''

def _semantic_source_identity(value: Any) -> str:
    """Remove only the eval lane root from isolated corpus source paths."""
    normalized = str(value or "").replace("\\", "/")
    parts = [part for part in normalized.split("/") if part and part != "."]
    corpus_positions = [index for index, part in enumerate(parts) if part == "corpus"]
    if corpus_positions:
        suffix = parts[corpus_positions[-1] + 1 :]
        if len(suffix) >= 2:
            return "/".join(suffix)
    return normalized
'''
    text = text.replace(anchor, helper + anchor, 1)

old = '''        canonical.append(
            {
                "path": path,
                "chunk_index": chunk_index,
                "text_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            }
        )
'''
new = '''        canonical.append(
            {
                "path": _semantic_source_identity(path),
                "chunk_index": chunk_index,
                "text_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            }
        )
'''
if old not in text:
    raise SystemExit("candidate fingerprint canonicalization anchor missing")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

# This is a one-shot branch finalization helper; a successful acceptance commit
# must not retain the carrier script itself.
Path(__file__).unlink()
