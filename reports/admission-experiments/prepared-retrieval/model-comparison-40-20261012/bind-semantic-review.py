"""Bind completed human/agent judgments to saved V40 public packets only.

Uses Python stdlib and saved artifacts. It never imports or calls DocAtlas,
a model, the product runner or the frozen scorer. It does not infer relevance:
all semantic labels and rationales are explicit inputs in semantic-decisions.json.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPORT = Path(__file__).resolve().parent
REPO = REPORT.parents[3]
RUN = REPORT / "attempt-01"
CORPUS = REPO / "eval" / "prepared_model_comparison40"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def artifact(path):
    raw = path.read_bytes()
    return {"path": str(path.relative_to(REPO)), "bytes": len(raw), "sha256": sha(raw)}


def transition(before, after):
    return ("both_pass" if before else "gain") if after else ("loss" if before else "both_fail")


decisions = read(REPORT / "semantic-decisions.json")
questions = read(CORPUS / "questions.json")["cases"]
question_map = {q["id"]: q for q in questions}
evaluation = read(RUN / "evaluation.json")
strict_map = {(r["case_id"], r["mode"]): r for r in evaluation["cases"]}
manifest = read(RUN / "RUN_MANIFEST.json")
expected = {(q["id"], mode) for q in questions for mode in ("budget", "mini")}
actual = {(d["case_id"], d["mode"]) for d in decisions}
assert len(decisions) == len(actual) == 80 and actual == expected
assert artifact(CORPUS / "questions.json")["sha256"] == manifest["inputs_sha256"]["eval/prepared_model_comparison40/questions.json"]

rows = []
for decision in decisions:
    case_id, mode = decision["case_id"], decision["mode"]
    question = question_map[case_id]
    directory = RUN / "calls" / case_id / mode
    payload_raw = (directory / "public-payload.json").read_bytes()
    public = json.loads(payload_raw)
    metadata = read(directory / "metadata.json")
    assert metadata["case_id"] == case_id and metadata["mode"] == mode
    assert metadata["question"] == question["question"]
    assert metadata["wire_sha256"] == sha(payload_raw)
    assert metadata["wire_utf8_bytes"] == len(payload_raw)
    assert len(public.get("sources", [])) == len(decision["sources"])
    sources = []
    for ordinal, (source, judgment) in enumerate(zip(public.get("sources", []), decision["sources"])):
        category, rationale = judgment
        assert category in ("direct_support", "useful_context", "tangential")
        original_path = CORPUS / "sources" / question["project_group"] / source["path_or_url"]
        assert original_path.is_relative_to(CORPUS / "sources")
        original_raw = original_path.read_bytes()
        original_text = original_raw.decode("utf-8")
        declared = "".join(original_text.splitlines(keepends=True)[source["line_start"] - 1:source["line_end"]])
        snippet = source["snippet"]
        # Edge whitespace is immaterial to this binding check; no words are
        # synthesized, reordered, normalized or supplied by a production helper.
        raw_span_match = bool(snippet.strip()) and snippet.strip() in declared
        sources.append({
            "public_ordinal": ordinal,
            "evidence_id": source["evidence_id"],
            "path_or_url": source["path_or_url"],
            "section": source.get("section"),
            "line_start": source["line_start"],
            "line_end": source["line_end"],
            "public_content_sha256": source.get("content_sha256"),
            "snippet_utf8_sha256": sha(snippet.encode("utf-8")),
            "snippet_characters": len(snippet),
            "scope": source.get("scope"),
            "authority": source.get("authority"),
            "version_binding": source.get("version_binding"),
            "project_identity": source.get("project_identity"),
            "raw_source": artifact(original_path),
            "snippet_in_declared_raw_lines_after_edge_trim": raw_span_match,
            "classification": category,
            "reason": rationale,
        })
    strict = strict_map[(case_id, mode)]
    rows.append({
        "case_id": case_id,
        "mode": mode,
        "question": question["question"],
        "project_group": question["project_group"],
        "answerability": question["answerability"],
        "manual_support": decision["support"],
        "manual_packet_classification": decision["packet"],
        "reason": decision["reason"],
        "public_state": {k: public.get(k) for k in (
            "status", "kind", "context_status", "context_available", "answer_supported",
            "answer_available", "support_status", "query_coverage", "retrieval_coverage",
            "facet_coverage", "context_quality",
        )},
        "metadata_status": metadata["status"],
        "public_source_count": len(sources),
        "sources": sources,
        "strict_frozen_gold_result": {k: strict[k] for k in (
            "valid_public_call_and_integrity", "strict_positive_pass",
            "strict_partial_documented_pass", "strict_empty_source_pass", "within_wire_budget",
        )},
        "artifacts": {name: artifact(directory / name) for name in (
            "public-payload.json", "metadata.json", "selection.json", "trace.jsonl",
        )},
    })

by_key = {(r["case_id"], r["mode"]): r for r in rows}
summary = {}
for mode in ("budget", "mini"):
    own = [r for r in rows if r["mode"] == mode]
    sources = [s for r in own for s in r["sources"]]
    positives = [r for r in own if r["answerability"] == "within_budget"]
    partials = [r for r in own if r["answerability"] == "partial"]
    negatives = [r for r in own if r["answerability"] == "unanswerable"]
    summary[mode] = {
        "manually_reviewed_packets": len(own),
        "manually_reviewed_source_rows": len(sources),
        "positive_full_semantic_support": sum(r["manual_support"] == "full" for r in positives),
        "positive_cases": len(positives),
        "complete_documented_part_of_partial_tasks": sum(r["manual_support"] == "documented_part_only" for r in partials),
        "partial_cases": len(partials),
        "empty_negative_packets": sum(r["manual_packet_classification"] == "empty" for r in negatives),
        "negative_cases": len(negatives),
        "negative_source_rows": sum(len(r["sources"]) for r in negatives),
        "negative_tangential_source_rows": sum(
            s["classification"] == "tangential" for r in negatives for s in r["sources"]
        ),
        "nonempty_negative_packets_with_only_tangential_sources": sum(
            r["manual_packet_classification"] == "unrelated" for r in negatives
        ),
        "source_row_classifications": dict(Counter(s["classification"] for s in sources)),
        "packet_classifications": dict(Counter(r["manual_packet_classification"] for r in own)),
        "support_classifications": dict(Counter(r["manual_support"] for r in own)),
    }

pairs = []
for question in questions:
    a, b = (by_key[(question["id"], mode)] for mode in ("budget", "mini"))
    target = {"within_budget": "full", "partial": "documented_part_only"}.get(question["answerability"])
    if target is None:
        before, after = (r["manual_packet_classification"] == "empty" for r in (a, b))
        criterion = "Empty final packet under the unchanged negative source contract"
    else:
        before, after = (r["manual_support"] == target for r in (a, b))
        criterion = target
    pairs.append({
        "case_id": question["id"],
        "answerability": question["answerability"],
        "manual_criterion": criterion,
        "budget_meets": before,
        "mini_meets": after,
        "transition": transition(before, after),
    })

result = {
    "schema_version": 1,
    "created_utc": datetime.now(timezone.utc).isoformat(),
    "reviewer": "Independent reviewer /root/eval40_review; did not author frozen product, model selector, corpus, runner or scorer",
    "review_boundary": "All 80 final saved public get_docs_context packets and their source snippets; no generated answers",
    "independence_and_limits": [
        "Source/question semantic judgments were made by reading every final snippet. Model logits and selector scores are not a relevance oracle.",
        "This review is not blinded: arm labels were visible and root communicated aggregate strict results before manual labeling was complete.",
        "Historical V40 is exposed, not a new blind holdout. Reused metadata saying frozen_unseen_validation does not describe the present comparison.",
        "The frozen strict scorer and gold remain unchanged. Its result is linked only after manual decisions, not rewritten by semantic review.",
        "Source-row relevance is not token-level precision: a useful or supporting wide row may contain substantial unrequested text.",
        "Full support is a manual reading of the supplied context, not measured correctness, refusals, or citation quality of a generated answer.",
        "No new product, model, scorer, query or test run was performed by this reviewer. The binding program uses only saved artifacts and Python stdlib.",
        "Downstream context construction/finalization can change selected evidence. Final arm differences must not automatically be attributed to logits alone.",
    ],
    "taxonomy": {
        "source": {
            "direct_support": "Explicitly supports at least one requested relationship or condition; need not answer the full question or make every byte necessary.",
            "useful_context": "Tied explanatory/application context, but not sufficient proof of the requested relation on its own.",
            "tangential": "Same topic/product/term/number but wrong relation, condition, API or metric; does not support the requested information.",
        },
        "packet": {
            "all_relevant": "At least one direct source, and no wholly tangential source row. Does not assert full answer or token precision.",
            "mixed": "Has both supporting/contextual and tangential rows.",
            "useful_context_only": "Only contextual rows, no direct proof of the asked relation.",
            "unrelated": "All nonempty source rows tangential to the asked information.",
            "empty": "No final source rows. Correct under the negative contract, not a successful positive or documented-part delivery.",
        },
        "support": {
            "full": "All requested facts of the positive question are semantically available.",
            "documented_part_only": "All independently documented part of a partial question is available; unavailable part remains unanswered.",
            "partial": "Some requested information available, but documented/conditional question coverage is incomplete.",
            "none": "No requested fact is adequately supported in the final packet.",
        },
    },
    "inputs": {name: artifact(path) for name, path in (
        ("manual_decisions", REPORT / "semantic-decisions.json"),
        ("binder", Path(__file__)),
        ("questions", CORPUS / "questions.json"),
        ("gold", CORPUS / "gold_spans.json"),
        ("source_manifest", CORPUS / "source-manifest.json"),
        ("run_manifest", RUN / "RUN_MANIFEST.json"),
        ("frozen_strict_evaluation", RUN / "evaluation.json"),
    )},
    "binding_checks": {
        "expected_case_arms": 80,
        "unique_complete_manual_case_arms": len(rows),
        "manual_source_rows": sum(len(r["sources"]) for r in rows),
        "wire_hash_and_bytes_match_all": True,
        "manual_source_cardinality_matches_public_all": True,
        "snippet_declared_raw_span_matches": sum(
            s["snippet_in_declared_raw_lines_after_edge_trim"] for r in rows for s in r["sources"]
        ),
        "snippet_declared_raw_span_mismatches": [
            {"case_id": r["case_id"], "mode": r["mode"], "evidence_id": s["evidence_id"]}
            for r in rows for s in r["sources"]
            if not s["snippet_in_declared_raw_lines_after_edge_trim"]
        ],
    },
    "summary": summary,
    "manual_pairs": pairs,
    "manual_transitions_by_answerability": {
        kind: dict(Counter(p["transition"] for p in pairs if p["answerability"] == kind))
        for kind in ("within_budget", "partial", "unanswerable")
    },
    "cases": rows,
}

(REPORT / "semantic-review.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: result[k] for k in ("binding_checks", "summary", "manual_transitions_by_answerability")}, ensure_ascii=False, indent=2))
