from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from eval.evidence_quality_v2.run import run


OUTPUT = Path("/tmp/docatlas-semantic-recovery-probe")
TARGET_PATH = "docs/environment_variables.md"


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _walk(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk(nested)


def _path(item: dict[str, Any]) -> str:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    for value in (
        item.get("path"), item.get("source_path"), item.get("project_doc_path"),
        item.get("source"), metadata.get("project_doc_path"), metadata.get("source_path"),
    ):
        if isinstance(value, str) and value:
            return value
    return ""


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items() if key not in {"content", "text", "retrieval_text", "display_text"}}
    if isinstance(value, list):
        return [_safe(item) for item in value[:24]]
    if isinstance(value, tuple):
        return [_safe(item) for item in value[:24]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def main() -> int:
    shutil.rmtree(OUTPUT, ignore_errors=True)
    run(OUTPUT, projects=["httpx"])
    trace = json.loads((OUTPUT / "traces" / "A-current" / "httpx-06.json").read_text(encoding="utf-8"))
    report: dict[str, Any] = {}
    for stage in ("retrieved_candidates", "query_window", "qualified_fragments", "projector_inputs"):
        matches = []
        seen = set()
        for item in _walk((trace.get("stages") or {}).get(stage, [])):
            if _path(item).replace("\\", "/").casefold() != TARGET_PATH.casefold():
                continue
            signature = json.dumps(_safe(item), sort_keys=True, ensure_ascii=False)
            if signature in seen:
                continue
            seen.add(signature)
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            content = item.get("content") or item.get("text") or item.get("retrieval_text") or item.get("display_text") or ""
            matches.append({
                "top_level": _safe(item),
                "metadata": _safe(metadata),
                "content": " ".join(str(content).split())[:500],
            })
        report[stage] = matches[:8]
    print("SEMANTIC_RECOVERY_PROVENANCE=" + json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
