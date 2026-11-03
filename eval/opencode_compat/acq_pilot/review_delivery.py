"""Independent exact-source audit of saved table MCP replies.

No production retrieval, selector, tokenizer or evaluator is imported. This is
an artifact evaluator, not a new unit test. It accepts only the observed public
table/grouped-table formats and fails explicitly for other representations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def review(project: Path, oracle: dict, question: str, payload: dict) -> dict:
    assert payload.get("context_format") in {
        "docatlas.assembled-grouped-table.v1", "docatlas.assembled-table.v1"}
    expected_identity = "local:" + hashlib.sha256(str(project.resolve()).encode()).hexdigest()
    texts, covered, receipts = {}, {}, []
    for values in payload["sources"]:
        assert len(values) == len(payload["source_columns"])
        fields = dict(zip(payload["source_columns"], values))
        group = payload["source_groups"][fields["group"]] if "group" in fields else {}
        row = {**payload.get("source_context", {}), **group, **fields}
        path = row["path"]
        target = (project / path).resolve()
        assert target.is_relative_to(project.resolve()), path
        text = texts.setdefault(path, target.read_text(encoding="utf-8"))
        lines = text.splitlines(keepends=True)
        a, b = row["line_start"], row["line_end"]
        assert type(a) is int and type(b) is int and 1 <= a <= b <= len(lines)
        assert row["project_identity"] == expected_identity
        assert row["scope"] == "project" and row["version_binding"] == "unversioned"
        assert row["source_uri"].startswith("docatlas://source/")
        span = "".join(lines[a - 1:b])
        snippet = row["text"]
        assert snippet and snippet in span, (path, a, b)
        offset = span.index(snippet)
        assert span.find(snippet, offset + 1) == -1, "Ambiguous snippet within cited span"
        start = len("".join(lines[:a - 1])) + offset
        covered.setdefault(path, []).append((start, start + len(snippet)))
        receipts.append({"path": path, "start": a, "end": b, "ref": row["ref"],
                         "source_sha256": hashlib.sha256(target.read_bytes()).hexdigest()})

    results = []
    item = next(q for q in oracle["questions"] if q["id"] == question)
    for fact in item["facts"]:
        path, quote = fact["path"], fact["quote"]
        source = (project / path).read_text(encoding="utf-8")
        lines = source.splitlines(keepends=True)
        original_span = "".join(lines[fact["start"] - 1:fact["end"]])
        assert quote in original_span, fact["id"]
        expected_start = len("".join(lines[:fact["start"] - 1])) + original_span.index(quote)
        expected_end = expected_start + len(quote)
        cursor = expected_start
        for start, end in sorted(covered.get(path, [])):
            if start <= cursor:
                cursor = max(cursor, end)
        results.append({"id": fact["id"], "canonical_quote_delivered": cursor >= expected_end,
                        "path": path, "quote": quote})
    return {"question": question, "source_rows": len(receipts), "source_span_fidelity": True,
            "facts": results, "receipts": receipts,
            "limitation": "Canonical exact quotes; alternative sources assessed separately."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--oracle", type=Path, default=Path(__file__).with_name("oracle.json"))
    parser.add_argument("--question", required=True)
    parser.add_argument("--response", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(review(args.project, json.loads(args.oracle.read_text()), args.question,
                            json.loads(args.response.read_text())), ensure_ascii=False, indent=2))
