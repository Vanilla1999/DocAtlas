"""Re-score immutable real-MCP stock text replies with installed text encoder.

Source rows and actual exact original tool-visible text come from previously
published CI, not synthetic string fixtures. We do not rerun/change selection.
This is a recorded-corpus check, NOT live OpenCode or provider token billing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from docmancer.docs.application.projection_tokenizer import projection_token_count
from docmancer.docs.application.section_compression import expand_sections
from docmancer.docs.application.standalone_text_view import encode_standalone_text, FORMAT


def check(root: Path) -> dict:
    result = {"format": FORMAT, "recorded_github_run": 40737675270,
              "per_suite": {}, "errors_preserved": 0, "source_rows_checked": 0}
    cases = set()
    total_old = total_new = 0
    for suite in ("v40", "pilot", "fresh"):
        paths = sorted(root.rglob(f"lowmem-stock-text-{suite}-*/run/*/*-reply.json"))
        assert len(paths) == {"v40": 40, "pilot": 10, "fresh": 8}[suite], (suite, len(paths))
        old = new = 0
        for path in paths:
            raw_reply = json.loads(path.read_text(encoding="utf-8"))
            contents = raw_reply["content"]
            assert len(contents) == 1 and contents[0]["type"] == "text" and raw_reply.get("structuredContent") is None
            original_text = contents[0]["text"]
            payload = json.loads(original_text)
            key = (suite, path.name)
            assert key not in cases, key
            cases.add(key)
            rendered = encode_standalone_text(payload)
            if rendered is None:
                assert payload.get("status") not in ("ok", "truncated") or not payload.get("sources"), path
                result["errors_preserved"] += 1
                continue
            view = json.loads(rendered)
            assert view["context_format"] == FORMAT
            expanded = expand_sections(payload)
            rows = expanded["sources"]
            assert len(rows) == len(view["sources"])
            for row, visible in zip(rows, view["sources"], strict=True):
                assert (row["snippet"], row["path_or_url"], row["evidence_id"]) == (
                    visible["text"], visible["path"], visible["ref"])
                assert visible.get("source_uri") == row.get("source_uri")
                for field in ("scope", "version_binding", "authority", "instruction_trust", "freshness", "source_type", "project_identity"):
                    assert (view.get("source_context") or {}).get(field, visible.get(field)) == row.get(field), (path, field)
                for field in ("section", "line_start", "line_end"):
                    assert visible.get(field) == row.get(field)
                result["source_rows_checked"] += 1
            assert view["status"] == payload["status"] and view["kind"] == payload["kind"]
            assert (view.get("source_selection") or {}) == (payload.get("source_selection") or {})
            assert (view.get("context_quality") or {}) == (payload.get("context_quality") or {})
            old += projection_token_count(original_text.encode("utf-8"))
            new += projection_token_count(rendered.encode("utf-8"))
        result["per_suite"][suite] = {"cases": len(paths), "old_text_tokens": old,
                                       "new_text_tokens": new, "reduction_percent": round((old-new)*100/old,2)}
        total_old += old
        total_new += new
    assert len(cases) == 58 and result["errors_preserved"] == 1
    assert total_new < total_old, (total_new, total_old)
    result.update(cases=len(cases), old_text_tokens=total_old,
                  new_text_tokens=total_new,
                  reduction_percent=round((total_old-total_new)*100/total_old,2),
                  provider_usage=None, paid_calls=0, accepted=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    outcome = check(args.artifacts)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "CORPUS.json").write_text(json.dumps(outcome, indent=2) + "\n")
    print(json.dumps(outcome))
