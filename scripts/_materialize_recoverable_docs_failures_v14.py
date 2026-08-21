#!/usr/bin/env python3
"""Materialize the clean v11 tree plus optional-span identity preservation."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
v11 = root / "scripts/_materialize_recoverable_docs_failures_v11.py"
exec(compile(v11.read_text(encoding="utf-8"), str(v11), "exec"), {"__name__": "__main__", "__file__": str(v11)})

# ProjectDocsChunk represents optional line/character spans with None when the
# active index generation does not persist that coordinate family. Do not turn
# absence into an explicitly supplied null span: EvidenceCandidate identity
# validation intentionally rejects supplied-but-invalid coordinates.
path = root / "docmancer/docs/application/_project_context_service_shared.py"
text = path.read_text(encoding="utf-8")
old = '''            pack.append({\n                "stable_chunk_id": item.stable_chunk_id,\n                "parent_logical_id": item.parent_logical_id,\n                "display_content_hash": item.display_content_hash,\n                "char_start": item.char_start,\n                "char_end": item.char_end,\n                "line_start": item.line_start,\n                "line_end": item.line_end,\n                "source_class": "project_doc",\n'''
new = '''            pack.append({\n                "stable_chunk_id": item.stable_chunk_id,\n                "parent_logical_id": item.parent_logical_id,\n                "display_content_hash": item.display_content_hash,\n                **({\n                    "char_start": item.char_start,\n                    "char_end": item.char_end,\n                } if item.char_start is not None and item.char_end is not None else {}),\n                **({\n                    "line_start": item.line_start,\n                    "line_end": item.line_end,\n                } if item.line_start is not None and item.line_end is not None else {}),\n                "source_class": "project_doc",\n'''
if text.count(old) != 1:
    raise SystemExit(f"optional span projection patch count={text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")

# Freeze the identity distinction: absent line coordinates are valid; an
# explicitly partial span remains invalid in the existing selector tests.
gate_path = root / "scripts/run_recovery_contract_gate.py"
gate = gate_path.read_text(encoding="utf-8")
old = '''        assert result["status"] == "ok", json.dumps(result, indent=2, default=str)\n        assert result["answer_supported"] is True\n'''
new = '''        assert result["status"] == "ok", json.dumps(result, indent=2, default=str)\n        assert result["answer_supported"] is True\n        assert result.get("recovery_reason_code") in (None, "")\n'''
if gate.count(old) != 1:
    raise SystemExit(f"exact identity success assertion patch count={gate.count(old)}")
gate_path.write_text(gate.replace(old, new, 1), encoding="utf-8")
