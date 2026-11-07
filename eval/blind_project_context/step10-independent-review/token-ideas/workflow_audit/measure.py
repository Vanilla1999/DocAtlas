"""Offline workflow accounting only: no model/MCP/test/product imports or edits.

All source fixtures below are already-seen Step10 development data. The six-file
bundle is an illustrative delivery-size control, NOT a returned MCP result or a
claim about answer quality, live authorization, provider tokens, or latency.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

COMMIT = "9e2c331c45e8f9a86f809a1f4d66c43125250702"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("/workspace/scratch/66f7674793b8/DocAtlas-step10-review"))
    parser.add_argument("--out", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    root, out = args.repo.resolve(), args.out.resolve()
    assert not out.is_relative_to(root)
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip() == COMMIT
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root))
    codec_path = root / "docmancer/docs/application/projection_tokenizer.py"
    spec = importlib.util.spec_from_file_location("workflow_offline_codec", codec_path)
    codec = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(codec)
    count = codec.projection_token_count
    inputs = {}

    def raw(path):
        value = path.read_bytes()
        inputs[str(path.relative_to(root))] = hashlib.sha256(value).hexdigest()
        return value

    def read(path):
        return json.loads(raw(path))

    def encoded(value):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()

    def measure(value):
        data = value.encode() if isinstance(value, str) else value
        return {"utf8_bytes": len(data), "o200k_tokens": count(data)}

    raw(codec_path)
    raw(root / "docmancer/docs/data/o200k_base.tiktoken.gz")
    base = root / "eval/blind_project_context"
    dataset = base / "step10-reference-closure-v3"
    project = next(item for item in read(dataset / "projects.json") if item["id"] == "meridian")
    project_root = (dataset / project["root"]).resolve()
    paths = project["project_documents"]
    assert len(paths) == 6 and len(set(paths)) == 6
    assert all(not path.startswith("modules/") for path in paths)
    documents, file_rows = {}, []
    for name in paths:
        data = raw(project_root / name)
        documents[name] = data.decode()
        file_rows.append({"path": name, "sha256": hashlib.sha256(data).hexdigest(),
                          "lines": len(data.decode().splitlines()), **measure(data)})
    simple_bundle = "".join(f"SOURCE {name}\n{documents[name]}\n" for name in paths)
    example_envelope = {"scope": "project", "files": [
        {"path": row["path"], "sha256": row["sha256"], "line_start": 1,
         "line_end": row["lines"], "text": documents[row["path"]]} for row in file_rows]}
    facts = [quote for task in read(dataset / "tasks.json") if task["project"] == "meridian"
             for _key, quote in task["facts"]]
    assert len(facts) == 19
    assert all(any(quote in text for text in documents.values()) for quote in facts)
    source_control = {
        "source_scope": "Six allowed Meridian project documents; excluded laser module is not included",
        "files": file_rows,
        "total_original_bytes": sum(row["utf8_bytes"] for row in file_rows),
        "sum_per_file_source_tokens": sum(row["o200k_tokens"] for row in file_rows),
        "illustrative_named_text_bundle": measure(simple_bundle),
        "illustrative_file_hash_line_json": measure(encoded(example_envelope)),
        "authored_fact_occurrences_present_in_full_sources": len(facts),
        "interpretation": "Literal availability control, not answering-model correctness; illustrative wrappers do not implement the full native MCP authorization/identity contract",
    }
    saved_packets = []
    for case in ("V-M1", "V-M2", "V-M3", "V-M4"):
        saved = read(base / "step10-qwen-validation/run-01/validation/meridian" / (case + ".json"))
        packet = saved["packet"]
        saved_packets.append({"case": case, "status": packet.get("status"),
                              "source_rows": len(packet.get("sources", [])),
                              "source_text_sum": {"utf8_bytes": sum(len(s["snippet"].encode()) for s in packet.get("sources", [])),
                                                  "o200k_tokens": sum(count(s["snippet"].encode()) for s in packet.get("sources", []))},
                              "canonical_saved_packet": measure(encoded(packet)),
                              "interpretation": "Whole saved public packet serialized compactly offline; not actual provider wire/input usage"})
    renewed = read(base / "step10-agent-evaluation/renewed-accounting.json")["sessions"][0]
    steps = []
    for number, step in enumerate(renewed["step_usage"], 1):
        tokens = step["tokens"]
        steps.append({"step": number, "reason": step["reason"], "input": tokens["input"],
                      "cache_read": tokens.get("cache", {}).get("read", 0),
                      "input_plus_cache": tokens["input"] + tokens.get("cache", {}).get("read", 0),
                      "output": tokens["output"]})
    trace = []
    for item in renewed["tool_trace"]:
        state = item["state"]
        trace.append({"tool": item["tool"], "assistant_message_id": item.get("messageID"),
                      "input": state["input"], "returned_text": measure(state["output"])})
    assert sum(step["input_plus_cache"] for step in steps) == renewed["usage"]["input_with_cache"]
    probe = read(base / "step10-client-adapter-evidence.json")
    selected_probe = [{k: row[k] for k in ("arm", "tokens", "tool_schema_tokens", "system_tokens", "bytes_equal") if k in row}
                      for row in probe["results"] if "tool_schema_tokens" in row]
    captures = []
    for folder in ("step10-client-question-audit", "step10-client-question-stdin"):
        for path in sorted((base / folder).glob("provider-*.json")):
            captured = read(path)
            captures.append({"file": str(path.relative_to(root)), "model": captured["model"],
                             "tool_count": len(captured.get("tools", [])),
                             "tool_schema": measure(encoded(captured.get("tools", []))),
                             "messages": [{"role": message["role"],
                                           "content": measure(message.get("content") or ""),
                                           "tool_call_count": len(message.get("tool_calls", []))}
                                          for message in captured.get("messages", [])],
                             "interpretation": "Scripted localhost request-shape evidence only; no paid answering model"})
    summary = {"source_commit": COMMIT, "tokenizer": "vendored offline o200k_base; not arbitrary provider billing",
               "six_document_control": source_control, "saved_meridian_packets": saved_packets,
               "old_terra_T01_dev": {"usage": renewed["usage"], "steps": steps, "top_level_tools": trace,
                                     "nested_tool_counts": renewed["nested_tool_counts"],
                                     "distinct_tool_assistant_messages": len({row["assistant_message_id"] for row in trace}),
                                     "final_request_share_of_input_plus_cache": steps[-1]["input_plus_cache"] / renewed["usage"]["input_with_cache"],
                                     "earlier_requests_total_input_plus_cache": sum(step["input_plus_cache"] for step in steps[:-1]),
                                     "limitations": ["Old T01 is a different corpus/task from Meridian and the new user numbers", "Four recorded provider steps; wrappers are not extra model rounds", "No provider HTTP payload was captured for the actual Terra run", "Skipping a step changes later history: summing earlier steps is not an exact new-total forecast"]},
               "saved_localhost_transport_probe": {"results": selected_probe,
                                                    "limits": probe["limitations"]},
               "saved_question_capture_shapes": captures,
               "new_user_numbers": {"input_values": [69419, 28657], "verified": False,
                                    "reason": "New raw traces/usage receipts are not available in this checkout"},
               "limits": ["No inference, public MCP, tests, source edits or new client run", "No monetary cost estimate", "Source byte/token counts do not include tools, system prompt, history or future answer", "No old blind260 holdout read"]}
    for name, expected in inputs.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected
    forbidden = [name for name in sys.modules if name.split(".")[0] in {"torch", "transformers", "onnxruntime", "mcp", "fastembed"}]
    assert not forbidden, forbidden
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip()
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    (out / "receipt.json").write_text(json.dumps({"source_commit": COMMIT, "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                                 "metrics_sha256": hashlib.sha256((out / "metrics.json").read_bytes()).hexdigest(),
                                                 "input_sha256": inputs, "source_tree_clean_before_after": True,
                                                 "forbidden_modules_imported": forbidden, "new_model_calls": 0, "new_MCP_calls": 0,
                                                 "new_tests": 0}, indent=2) + "\n")
    print(json.dumps({"six_document_control": source_control, "saved_meridian_packets": saved_packets,
                      "old_steps": steps, "old_tools": trace, "probe": selected_probe}, ensure_ascii=False))


if __name__ == "__main__":
    main()
