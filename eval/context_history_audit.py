"""Independent audit of captured REAL stdio client history; no model calls.

No production decoder or selector is imported. This compares evidence data
blocks, not provider invoices or autonomous agent behavior.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import tiktoken


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def body(result):
    if isinstance(result.get("structuredContent"), dict):
        return result["structuredContent"]
    assert len(result["content"]) == 1 and result["content"][0]["type"] == "text"
    return json.loads(result["content"][0]["text"])


def sources(packet):
    if "sources" in packet:
        return packet["sources"]
    assert packet["context_format"] in {"docatlas.sections.v1", "docatlas.sections.v2"}
    result = {}
    for group in packet["source_groups"]:
        for fragment in group["fragments"]:
            index = fragment["index"]
            assert index not in result
            fields = {**packet["source_defaults"], **group["common"], **fragment["fields"]}
            result[index] = fields
    assert sorted(result) == list(range(len(result)))
    return [result[i] for i in range(len(result))]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--controls", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    codec = tiktoken.get_encoding("o200k_base")
    count = lambda value: len(codec.encode(canonical(value), disallowed_special=()))
    rows = []
    for path in sorted(args.controls.glob("*/managed-session.json")):
        capture = json.loads(path.read_text())
        view, audit = capture["input"], capture["audit"]
        profile = body(next(a["result"] for a in audit if a["tool"] == "docs_status"))["documentation_language"]
        calls = [a for a in audit if a["tool"] == "get_docs_context"]
        assert len(calls) == 2
        expected, replay, occurrences = {}, [], 0
        for number, call in enumerate(calls):
            result = call["result"]
            assert not result.get("isError")
            public = body(result)
            replay.append(public)  # Only public model text, NEVER private _meta.
            packet = ((result.get("_meta") or {}).get("docatlas/source-packet") or {}).get("packet", public)
            request = call["arguments"]
            bindings = {k: request[k] for k in ("project_path", "library", "version", "module_path", "scope") if k in request}
            original = sources(packet)
            occurrences += len(original)
            current_refs = set()
            for source in original:
                assert profile["snapshot_sha256"] and source.get("source_uri")
                identity = {"binding": {"source": bindings, "snapshot": profile["snapshot_sha256"]},
                            "row": source, "unverified_snapshot_response": None}
                ref = "s" + hashlib.sha256(canonical(identity).encode()).hexdigest()[:20]
                assert ref not in expected or expected[ref] == source
                expected[ref] = source
                current_refs.add(ref)
            event = {**view["result_context"], **view["results"][number]}
            assert set(event["source_refs"]) == current_refs
            if public.get("context_format") == "docatlas.model-context.v1":
                for key, value in public.items():
                    if key not in {"sources", "source_context"}:
                        assert event[key] == value, (path, key)
        assert set(expected) == {row["ref"] for row in view["sources"]}
        for row in view["sources"]:
            restored = {**view["source_context"], **row}
            original = expected[row["ref"]]
            assert restored["text"] == original["snippet"]
            assert restored["path"] == original["path_or_url"]
            for key in ("scope", "version_binding", "authority", "instruction_trust", "freshness", "source_type", "section", "line_start", "line_end"):
                assert restored.get(key) == original.get(key), (path, key)
        short_language = {k: v for k, v in profile.items() if k not in {"snapshot_sha256", "catalog_sha256", "manifest_digest"}}
        assert view["language"] == short_language
        replay_input = {"question": view["question"], "language": short_language, "results": replay}
        before, after = count(replay_input), count(view)
        assert occurrences > len(expected) and after < before
        assert "docatlas/source-packet" not in canonical(view) and "source_uri" not in canonical(view)
        rows.append({"arm": path.parent.name, "source_occurrences_before": occurrences,
                     "unique_sources_after": len(expected), "replayed_model_blocks_tokens": before,
                     "managed_model_input_tokens": after, "reduction_percent": round(100 * (1-after/before), 2),
                     "source_and_envelope_fidelity": True})
    assert len(rows) == 4
    args.out.write_text(json.dumps({"passed": True, "rows": rows, "model_calls": 0,
        "provider_usage": None, "boundary": "same question and language; public evidence blocks only; private metadata excluded from baseline"},
        ensure_ascii=False, indent=2) + "\n")
    print(args.out.read_text())


if __name__ == "__main__":
    main()
