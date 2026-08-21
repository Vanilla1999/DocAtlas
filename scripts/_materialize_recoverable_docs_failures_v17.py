#!/usr/bin/env python3
"""Materialize v16 and freeze the new installed recovery workflow contract."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
v16 = root / "scripts/_materialize_recoverable_docs_failures_v16.py"
exec(compile(v16.read_text(encoding="utf-8"), str(v16), "exec"), {"__name__": "__main__", "__file__": str(v16)})

path = root / "tests/docs/test_mcp_docs_tools_registration.py"
text = path.read_text(encoding="utf-8")
old = '''    assert workflow["docs_status"]["discovery"] is False\n    assert workflow["recovery"]["stop_before_edit_status"] == "insufficient_evidence"\n'''
new = '''    assert workflow["docs_status"]["discovery"] is False\n    recovery = workflow["recovery"]\n    assert recovery["after_prepare"] == "retry_original_get_docs_context_unchanged"\n    assert recovery["rephrase_retry_limit"] == 1\n    assert recovery["rephrase_auto_execute"] is False\n    assert recovery["investigation_allowed_when_hard_stop_false"] is True\n    assert recovery["source_search_after_rephrase_exhausted"] is True\n    assert recovery["documentation_claim_requires_support"] is True\n    assert recovery["stop_before_edit_when"] == "hard_stop"\n'''
if text.count(old) != 1:
    raise SystemExit(f"installed recovery workflow assertion patch count={text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
