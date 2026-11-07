"""Account actual agent usage and independently check delivered source spans.

Final-answer grading is manual and separate; literal evidence is not an answer.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path

from corpus import documents
from score import covers, decode_context, placements, rows_of
import tiktoken


def packets(value):
    if isinstance(value, dict):
        if value.get("context_format") or ("sources" in value and "status" in value):
            yield value
        else:
            for v in value.values():
                yield from packets(v)
    elif isinstance(value, list):
        for v in value:
            yield from packets(v)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--prepared-root", type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    gold = {t["topic_id"]: t for t in json.loads((here / "oracle.json").read_text())["topics"]}
    audit = {f["fact_id"]: f["occurrences"] for f in json.loads((here / "witness-audit.json").read_text())["facts"]}
    docs = {c: documents(args.prepared_root / (c + "-0/project")) for c in ("L0", "L2")}
    encoder = tiktoken.get_encoding("o200k_base")
    results, review = [], []
    for path in sorted(args.out.glob("*/*/*.receipt.json")):
        receipt = json.loads(path.read_text())
        case = receipt["case"]
        base = path.parent / case
        events = [json.loads(line) for line in base.with_suffix(".jsonl").read_text().splitlines()]
        state = json.loads(base.with_suffix(".session.json").read_text())["data"]
        assert state["model"] == {"id": "gpt-6.1-terra", "providerID": "openai", "variant": "low"}
        corpus = receipt["corpus"]
        totals = defaultdict(int)
        spans = defaultdict(list)
        known_refs, flow, anomalies, texts, errors = {}, [], [], [], []
        seen_pages = defaultdict(set)
        issued = {}
        continuation_checks = []
        for event in events:
            if event["type"] == "step_finish":
                t = event["part"]["tokens"]
                for key in ("input", "output", "reasoning"):
                    totals[key] += t[key]
                totals["cache_read"] += t["cache"]["read"]
                totals["steps"] += 1
            if event["type"] == "text":
                texts.append(event["part"]["text"])
            if event["type"] == "error":
                errors.append(event)
            if event["type"] != "tool_use":
                continue
            tool = event["part"]
            state_tool = tool["state"]
            output = state_tool.get("output", "")
            meta = state_tool.get("metadata", {}).get("metadata", {})
            calls = meta.get("toolCalls", [])
            totals["tool_output_tokens"] += len(encoder.encode(output))
            item = {"calls": calls, "input": state_tool.get("input"), "code_error": bool(meta.get("error")),
                    "truncated": bool(meta.get("truncated")), "output_tokens": len(encoder.encode(output))}
            requests = [c.get("input", {}) for c in calls if c.get("tool") == "docatlas.get_docs_context"]
            for request in requests:
                if request.get("portion", 1) > 1:
                    earlier = issued.get(request.get("continuation_token"))
                    binding = {k: v for k, v in request.items() if k not in {"portion", "continuation_token"}}
                    continuation_checks.append({"portion": request["portion"], "issued": earlier is not None,
                        "unchanged_arguments": bool(earlier and binding == earlier["binding"]),
                        "issued_next_portion": bool(earlier and request["portion"] == earlier["next_portion"])})
            try:
                parsed = json.loads(output)
            except ValueError:
                parsed = None
            for packet in packets(parsed):
                more = packet.get("more_context") or {}
                item["more_context"] = more
                if packet.get("error"):
                    item["error"] = packet["error"]
                rows = rows_of(packet)
                identities = {(r["path"], r["line_start"], r["line_end"], r["text"]) for r in rows}
                if more:
                    token = more["continuation_token"]
                    if more["portion"] > 1 and identities & seen_pages[token]:
                        anomalies.append("repeated_continuation_window")
                    seen_pages[token].update(identities)
                    if len(requests) == 1:
                        issued[token] = {"binding": {k: v for k, v in requests[0].items()
                            if k not in {"portion", "continuation_token"}}, "next_portion": more.get("next_portion")}
                for row in rows:
                    spots = placements(docs[corpus].get(row["path"]), row["line_start"], row["line_end"], row["text"])
                    if len(spots) == 1:
                        spans[row["path"]].append(spots[0])
                    elif not spots:
                        anomalies.append({"not_verbatim": row})
                if packet.get("context_format"):
                    for row in decode_context(packet).get("sources", []):
                        known_refs[row.get("ref")] = [row.get("path"), row.get("line_start"), row.get("line_end")]
                focused = [n for n in calls if n.get("input", {}).get("source_path")]
                if focused and any(r["path"] != focused[0]["input"]["source_path"] for r in rows):
                    anomalies.append("focused_source_mismatch")
            if isinstance(parsed, dict) and parsed.get("error"):
                item["error"] = parsed["error"]
            flow.append(item)
        for key in ("input", "output", "reasoning"):
            assert totals[key] == state["tokens"][key], (base, key)
        assert totals["cache_read"] == state["tokens"]["cache"]["read"]
        totals["input_with_cache"] = totals["input"] + totals["cache_read"]
        topic = gold[case.split("-")[0]]
        evidence = {f["fact_id"]: any(covers(spans[o["path"]], spot)
            for o in audit[f["fact_id"]][corpus]
            for spot in placements(docs[corpus].get(o["path"]), o["line_start"], o["line_end"], f["quote"]))
            for f in topic["facts"]}
        import re
        final = texts[-1] if texts else ""
        unknown_refs = sorted(set(re.findall(r"ev-[0-9a-f]+", final)) - known_refs.keys())
        result = {**receipt, "usage": dict(totals), "final": final, "commentary": texts[:-1], "flow": flow,
                  "literal_evidence": evidence, "source_anomalies": anomalies, "unknown_cited_refs": unknown_refs,
                  "continuation_checks": continuation_checks, "errors": errors}
        results.append(result)
        base.with_suffix(".answer.md").write_text(final + "\n")
        review.extend([f"## {corpus}/{receipt['arm']}/{case}", json.dumps(dict(totals)), final,
                       "### Trace", *[json.dumps(f, ensure_ascii=False) for f in flow], ""])
    (args.out / "analysis.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
    (args.out / "answers-and-flow.md").write_text("\n\n".join(review))
    print(f"Analyzed {len(results)} completed sessions")


if __name__ == "__main__":
    main()
