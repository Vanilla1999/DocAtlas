#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "docmancer/docs/interfaces/mcp/prefetch_tools.py"
text = path.read_text(encoding="utf-8")
old = '''        "diagnostics": (\n            {"active_index": {"db_path": active_db_path}}\n            if active_db_path not in (None, "") else {}\n        ),\n'''
new = '''        "diagnostics": (\n            {\n                "active_index": {\n                    key: active_index.get(key)\n                    for key in ("db_path", "config_source", "config_path", "retrieval_mode")\n                    if active_index.get(key) not in (None, "")\n                }\n            }\n            if active_db_path not in (None, "") else {}\n        ),\n'''
if text.count(old) != 1:
    raise RuntimeError(f"bounded diagnostics anchor count={text.count(old)}, expected 1")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("preserved bounded active_index identity fields")
