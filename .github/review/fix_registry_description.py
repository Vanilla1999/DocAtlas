from __future__ import annotations

import json
from pathlib import Path

path = Path("server.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["description"] = (
    "Local-first MCP docs context for coding agents: bounded, source-attributed, version-aware evidence."
)
assert len(payload["description"]) <= 100
path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
