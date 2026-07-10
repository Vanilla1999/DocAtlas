"""Generate the committed 150-item Context7 parity dataset from its catalog."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / "catalog.json"
DATASET_PATH = ROOT / "dataset.jsonl"


def build_items(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    templates = catalog["question_templates"]
    for library in catalog["libraries"]:
        for template in templates:
            kind = template["kind"]
            item_id = f"{library['ecosystem']}-{library['library']}-{kind}".replace("_", "-")
            items.append({
                "id": item_id,
                "ecosystem": library["ecosystem"],
                "library": library["library"],
                "requested_version": library["version"],
                "question_type": kind,
                "question": (
                    f"For {library['library']} {library['version']}, explain {library['topic']}. "
                    f"{template['suffix']}"
                ),
                "allowed_corpus": {"policy": "official-docs-only", "sources": [library["docs_url"]]},
                "expected_evidence": {"source": library["docs_url"], "section": library["section"], "symbols": [library["symbol"]]},
                "requires_code_snippet": template["requires_code_snippet"],
                "expected_first_tool": {"docatlas": "get_docs_context", "context7": "resolve-library-id"},
                "context7_library_id": library["context7_library_id"],
            })
    return items


def dataset_digest(items: list[dict[str, Any]]) -> str:
    payload = "\n".join(json.dumps(item, sort_keys=True, separators=(",", ":")) for item in items)
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def main() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    items = build_items(catalog)
    if len(items) < 150:
        raise SystemExit(f"Expected at least 150 items, got {len(items)}")
    DATASET_PATH.write_text("".join(json.dumps(item, sort_keys=True) + "\n" for item in items), encoding="utf-8")
    print(json.dumps({"items": len(items), "digest": dataset_digest(items)}, sort_keys=True))


if __name__ == "__main__":
    main()
