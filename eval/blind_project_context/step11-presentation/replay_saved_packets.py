"""Render 16 already-seen Qwen packets; this is offline analysis, not inference.

The actual new renderer runs with the ordinary configuration. These small
packets fit its stricter delivery guard; this does not exercise minimal-context
dispatch, scoring, atomic binding or its 50000-token guard. Historical rendering
costs come from the saved public-run receipts (12 nonempty packets). Empty
packet fallback is reconstructed exactly as the minimal MCP text route does.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import statistics
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    repo, out = args.repo.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(repo))
    os.environ.update(DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT="0", DOCATLAS_OFFLINE="1",
                      DOCATLAS_AUTO_VECTORS="0", ORT_DISABLE_TELEMETRY="1",
                      DOCATLAS_CONTEXT_PRESENTATION="literal-v2", DOCATLAS_CONTEXT_ASSEMBLY="table")
    for name in ("DOCATLAS_MINILM_MODEL_DIR", "DOCATLAS_EXPERIMENT_CONTEXT_MAX_TOKENS",
                 "DOCATLAS_EXPERIMENT_DELIVERY_MAX_TOKENS"):
        os.environ.pop(name, None)
    os.environ["DOCATLAS_CONTEXT_COMPRESSION"] = "off"

    base = repo / "eval/blind_project_context"
    inputs, records = {}, []

    def track(path):
        inputs[str(path.relative_to(repo))] = digest(path)
        return path

    paths = ["docmancer/docs/application/standalone_text_view.py",
             "docmancer/docs/application/context_assembly.py",
             "docmancer/docs/application/model_context_view.py",
             "docmancer/docs/application/projection_tokenizer.py",
             "docmancer/docs/application/section_compression.py",
             "docmancer/docs/domain/context_presentation.py",
             "docmancer/docs/domain/delivery_limits.py",
             "docmancer/docs/domain/minimal_context_config.py",
             "docmancer/docs/data/o200k_base.tiktoken.gz"]
    for relative in paths:
        track(repo / relative)
    for phase, folder in (("recovery", "step10-qwen-recovery"), ("validation", "step10-qwen-validation")):
        run = base / folder / "run-01"
        metrics = {row["id"]: row for row in json.loads(track(run / "results.json").read_text())}
        for path in sorted((run / phase).glob("*/*.json")):
            if not re.fullmatch(r"[CV]-[A-Z][0-9]\.json", path.name):
                continue
            data = json.loads(track(path).read_text())
            assert data["error"] is None
            fixture = run / "fixtures" / path.parent.name / "project"
            documents = {source["path_or_url"]: track(fixture / source["path_or_url"]).read_bytes().decode()
                         for source in data["packet"]["sources"]}
            records.append((phase, path.stem, data, documents, metrics[path.stem]))
    assert len(records) == 16
    plan = {"schema_version": 1, "script_sha256": digest(Path(__file__)), "inputs_sha256": inputs,
            "boundary": "offline rendering of already-seen saved packets; ordinary renderer guards; no model or MCP calls",
            "historical_baseline": "saved supported_rendering_tokens for 12 nonempty packets; reconstructed canonical fallback for 4 empty packets",
            "runtime": {"python": sys.version, "tiktoken": importlib.metadata.version("tiktoken")},
            "counter": "local o200k_base; not provider usage", "minimal_runtime_proven": False}
    save(out / "offline-plan.json", plan)

    from docmancer.docs.application import standalone_text_view
    from docmancer.docs.application.projection_tokenizer import projection_token_count

    assert Path(standalone_text_view.__file__).resolve() == repo / paths[0]
    summaries = []
    for phase, case, data, documents, metrics in records:
        packet = data["packet"]
        before = canonical(packet)
        document_hashes = {path: hashlib.sha256(text.encode()).hexdigest() for path, text in documents.items()}
        for source in packet["sources"]:
            raw = documents[source["path_or_url"]]
            assert source["snippet"] == "".join(raw.splitlines(keepends=True)[source["line_start"] - 1:source["line_end"]])
            material = {"path": source["path_or_url"], "section": source.get("section"),
                        "content": source["snippet"], "snippet": source["snippet"], "version": None}
            assert hashlib.sha256(canonical(material).encode()).hexdigest() == source["content_sha256"]
        confirmed = set()
        for score in data["observations"][0]["scores"]:
            if score["path"] in document_hashes:
                assert score["source_sha256"].removeprefix("sha256:") == document_hashes[score["path"]]
                confirmed.add(score["path"])
        assert confirmed == set(document_hashes)
        rendered = standalone_text_view.render_standalone_text(packet)
        if packet["sources"]:
            assert rendered.text is not None, (case, rendered.reason_code)
            text = rendered.text
            view = json.loads(text)
            assert view["context_format"] == "docatlas.standalone-text.v2"
            assert "source_groups" not in view and "source_columns" not in view
            assert len(view["sources"]) == len(packet["sources"])
            mapping = {"evidence_id": "ref", "path_or_url": "path", "snippet": "text"}
            for visible, source in zip(view["sources"], packet["sources"], strict=True):
                assert isinstance(visible, dict) and "content_sha256" not in visible and "group" not in visible
                effective = {**view.get("source_context", {}), **visible}
                for key, value in source.items():
                    if key != "content_sha256":
                        assert effective[mapping.get(key, key)] == value, (case, key)
            for key in ("status", "reason_code", "source_selection", "context_quality", "more_context",
                        "recommended_next_action", "next_action", "next_actions", "warnings", "missing", "read_next"):
                if packet.get(key):
                    assert view[key] == packet[key], (case, key)
            historical = metrics["supported_rendering_tokens"]
            assert isinstance(historical, int)
        else:
            assert rendered.text is None
            text = before
            historical = projection_token_count(text.encode())
            assert metrics["supported_rendering_tokens"] is None
        assert canonical(packet) == before
        assert projection_token_count(before.encode()) == metrics["packet_json_tokens"]
        summaries.append({"id": case, "phase": phase, "source_rows": len(packet["sources"]),
                          "historical_local_tokens": historical,
                          "literal_v2_local_tokens": projection_token_count(text.encode()),
                          "literal_v2_utf8_bytes": len(text.encode()), "source_fields_preserved_except_visible_hash": True,
                          "source_bytes_hashes_spans_verified": True, "canonical_packet_unchanged": True,
                          "empty_fallback_reconstructed": not bool(packet["sources"])})
    assert all(digest(repo / path) == sha for path, sha in inputs.items())
    summary = {key: {"total": sum(row[key] for row in summaries), "median": statistics.median(row[key] for row in summaries),
                     "max": max(row[key] for row in summaries)}
               for key in ("historical_local_tokens", "literal_v2_local_tokens", "literal_v2_utf8_bytes")}
    results = {"status": "OFFLINE_REPLAY_PASS", "minimal_runtime_proven": False, "inference_calls": 0,
               "packet_count": len(summaries), "source_rows": sum(row["source_rows"] for row in summaries),
               "summary": summary, "cases": summaries}
    save(out / "offline-results.json", results)
    save(out / "offline-receipt.json", {"script_sha256": digest(Path(__file__)),
        "plan_sha256": digest(out / "offline-plan.json"), "results_sha256": digest(out / "offline-results.json"),
        "all_input_hashes_rechecked": True, "minimal_runtime_proven": False, "inference_calls": 0})
    print(canonical({"status": results["status"], "packet_count": len(summaries), "summary": summary}))


if __name__ == "__main__":
    main()
