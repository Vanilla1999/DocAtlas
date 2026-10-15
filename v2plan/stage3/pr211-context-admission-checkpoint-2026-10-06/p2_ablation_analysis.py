"""Source-path-bound witness analysis of saved real MCP stage returns."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]


def source_texts(value):
    if isinstance(value, dict):
        meta = value.get("metadata") or {}
        meta = meta if isinstance(meta, dict) else {}
        paths = [value.get(k) or meta.get(k) for k in ("path_or_url", "path", "project_doc_path", "source")]
        texts = [value.get(k) for k in ("snippet", "text", "content")]
        for path in paths:
            if not isinstance(path, str):
                continue
            p = Path(path)
            if p.is_absolute():
                try:
                    path = str(p.relative_to(ROOT))
                except ValueError:
                    continue
            for text in texts:
                if isinstance(text, str):
                    yield path, text
        for item in value.values():
            yield from source_texts(item)
    elif isinstance(value, list):
        for item in value:
            yield from source_texts(item)


def present(witnesses, pairs):
    return any(p == w["path"] and w["text"].casefold() in t.casefold()
               for w in witnesses for p, t in pairs)


def witness_candidates(observed, witnesses):
    rows = {}
    for event in observed["events"]:
        if event["function"] != "select_context_candidates" or not isinstance(event["result"], list):
            continue
        for candidate in event["result"]:
            if not isinstance(candidate, dict) or not present(witnesses, list(source_texts(candidate))):
                continue
            meta = candidate.get("metadata") or {}
            identity = meta.get("stable_chunk_id") or candidate.get("stable_chunk_id")
            if not identity:
                continue
            matches = meta.get("retrieval_query_matches") or {}
            rows[identity] = dict(stable_chunk_id=identity,
                path=meta.get("project_doc_path") or candidate.get("source"),
                content_hash=meta.get("content_hash"),
                query_qualification=[dict(query_id=qid, qualified=trace.get("qualified"),
                    reason=trace.get("qualification_reason")) for qid, trace in matches.items()],
                qualification_outcomes=[outcome for outcome in (observed["payload"].get("diagnostics") or {}).get("qualification_outcomes", [])
                                        if outcome.get("stable_chunk_id") == identity])
    return list(rows.values())


def main():
    path = BASE / "archives/p2-real-mcp-alias-ablation-v1.json.gz"
    report = json.loads(gzip.decompress(path.read_bytes()))
    cases = json.loads((ROOT / "eval/direct_docatlas_questions_15/cases.json").read_text())["cases"]
    rows = []
    for case, pair in zip(cases, report["pairs"], strict=True):
        row = dict(case_id=case["id"], groups=[])
        for group in case["fact_groups"]:
            arms = {}
            for arm, observed in pair["arms"].items():
                traces = {}
                for stage in ("_run", "rerank_project_doc_chunks", "select_context_candidates", "project_docs_context"):
                    texts = [p for event in observed["events"] if event["function"] == stage
                             for p in source_texts(event["result"])]
                    traces[stage] = dict(observed_calls=sum(e["function"] == stage for e in observed["events"]),
                                         source_bound_witness=present(group["witnesses"], texts))
                traces["final"] = dict(source_bound_witness=present(group["witnesses"], list(source_texts(observed["payload"]))))
                traces["witness_candidates"] = witness_candidates(observed, group["witnesses"])
                arms[arm] = traces
            lost = arms["published-baseline"]["final"]["source_bound_witness"] and not arms["no-alias"]["final"]["source_bound_witness"]
            diagnosis = None
            if lost:
                if not arms["no-alias"]["_run"]["source_bound_witness"]:
                    diagnosis = "not_observed_in_raw_retrieval"
                elif not arms["no-alias"]["select_context_candidates"]["source_bound_witness"]:
                    diagnosis = "retrieved_but_not_observed_in_candidate_selection"
                else:
                    candidates = arms["no-alias"]["witness_candidates"]
                    qualifications = [q for c in candidates for q in c["query_qualification"]]
                    if qualifications and all(q["qualified"] is False and q["reason"] == "insufficient_visible_match" for q in qualifications):
                        diagnosis = "observed_witness_candidates_rejected_insufficient_visible_match"
                    else:
                        diagnosis = "selected_but_not_delivered_final"
            row["groups"].append(dict(id=group["id"], arms=arms, baseline_witness_lost=lost, diagnosis=diagnosis))
        rows.append(row)
    result = dict(schema="p2-alias-ablation-source-bound-analysis-v1", input_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), rows=rows,
        limitations=["Missing witness means absent in observed source/text field pairs, not universal absence proof",
                     "Stage invocations may branch; summaries are not a linear replayed call graph",
                     "Qualification rejection reason needs candidate/probe binding; no automatic guard weakening",
                     "Diagnosis is bounded first-loss interval, not exact failure line"])
    (BASE / "archives/p2-real-mcp-ablation-analysis-v1.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({r["case_id"]: [{"group": g["id"], "diagnosis": g["diagnosis"]} for g in r["groups"] if g["baseline_witness_lost"]]
                      for r in rows if any(g["baseline_witness_lost"] for g in r["groups"])}))


if __name__ == "__main__":
    main()
