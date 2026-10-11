from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import subprocess
import sys

from scripts.check_legacy_project_context_lineage import verify_legacy_lineage_floor
from scripts.run_project_context_quality_v2_gate import load_acceptance_lock, verify_v2_acceptance


def _v2_report():
    lock = load_acceptance_lock()
    lanes = {}
    for lane, thresholds in lock["lanes"].items():
        metrics = {}
        for metric, threshold in thresholds.items():
            numerator = threshold.get("minimum", threshold.get("maximum", 0))
            metrics[metric] = {"numerator": numerator, "denominator": threshold["denominator"]}
        lanes[lane] = {"metrics": metrics}
    return {
        "schema_version": "project-context-quality-v2-result-4",
        "run_mode": "live_self_host",
        "output_cost_policy": deepcopy(lock["output_cost_policy"]),
        "validation": {"case_count": 25},
        "lanes": lanes,
    }








def _legacy_report(source_root):
    """Authored local oracle fixture; it is not a live retrieval quality report."""
    import hashlib
    import json

    cases_path = Path(__file__).parents[1] / "eval/project_context_quality/cases.json"
    raw = cases_path.read_bytes()
    cases = json.loads(raw)["cases"]
    partial = "This authored fixture contains a safe partial context window."
    documents = {}
    for case in cases[:-1]:
        for fact in case["required_facts"]:
            documents.setdefault(fact["source"], []).append(
                "Frozen fixture source: " + fact["text"] + "\nThe original request remains a question."
            )
    for path, bodies in documents.items():
        target = source_root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n\n".join([*bodies, partial]) + "\n", encoding="utf-8")
    rows = []
    for index, case in enumerate(cases):
        receipt = {
            "schema_version": "legacy-same-call-source-evidence-v1",
            "request": {
                "question": case["question"], "scope": "project",
                "lookup_queries": case.get("lookup_queries", []), "project_path": str(source_root),
            },
            "observer_counts": {"retrieval_calls": 1, "validation_calls": 1},
            "source_bindings": {},
        }
        payload = {
            "status": "insufficient_evidence", "kind": "docs_context",
            "answer_supported": False, "answer_available": False, "edit_ready": False,
            "sources": [],
        }
        if case["expected_kind"] != "insufficient_evidence":
            fact = case["required_facts"][0]
            text = (
                "Frozen fixture source: " + fact["text"] + "\nThe original request remains a question."
                if index < 12 else partial
            )
            material = {
                "path": fact["source"], "section": "Authored oracle fixture",
                "content": text, "snippet": text, "version": "unversioned",
            }
            digest = hashlib.sha256(json.dumps(
                material, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            ).encode("utf-8")).hexdigest()
            file_text = (source_root / fact["source"]).read_text(encoding="utf-8")
            start = file_text.index(text)
            source = {
                "evidence_id": f"fixture-{index}", "path_or_url": fact["source"],
                "section": "Authored oracle fixture", "snippet": text,
                "version_binding": "unversioned", "content_sha256": digest,
                "project_identity": "local:" + hashlib.sha256(str(source_root).encode("utf-8")).hexdigest(),
                "authority": "source_of_truth", "scope": "project",
                "line_start": file_text[:start].count("\n") + 1,
                "line_end": file_text[:start + len(text)].count("\n") + 1,
            }
            payload.update({
                "status": "ok", "context_status": "ready", "answer_policy": "cite_only", "facets": [],
                "sources": [source], "covered_query_ids": ["query-lookup-1"], "missing_query_ids": ["query-original"],
            })
            receipt["source_bindings"][source["evidence_id"]] = {
                "projected_source": deepcopy(source),
                "source_hash_material": material,
                "retrieval_query_matches": {"query-lookup-1": {
                    "query_text": case["lookup_queries"][0], "query_origin": "host_lookup",
                    "relation": "host_lookup", "qualified": True, "context_only": True,
                }},
            }
        rows.append({
            "case_id": case["id"], "question": case["question"], "scope": "project",
            "observed": {"original_query_covered": False},
            "checks": {"required_facts": index < 12},
            "payload": payload, "legacy_fact_evidence": receipt,
        })
    floor = load_acceptance_lock()["legacy_lineage_floor"]
    metric = "verified_original_case_fact_count"
    return {
        "schema_version": "project-answer-quality-live-result-v1", "run_mode": "live_self_host",
        "provider_free": True, "lane": "legacy", "input_mode": "question_with_lookups",
        "corpus_sha256": hashlib.sha256(raw).hexdigest(),
        "case_count": 16, "positive_case_count": 15, "negative_case_count": 1,
        "results": rows,
        "metrics": {**{name: 0 for name in floor["hard_zero_metrics"]},
                    "original_query_covered_count": 0, metric: 12},
        "legacy_fact_acceptance": {
            "schema_version": "legacy-source-fact-oracle-result-v1", metric: 12,
            "positive_case_count": 15, "verified_case_ids": [case["id"] for case in cases[:12]],
            "raw_original_query_covered_count": 0, "errors": [],
        },
    }



def test_acceptance_clis_run_without_repo_pythonpath(tmp_path):
    root = Path(__file__).parents[1]
    for script in (
        root / "scripts/run_project_context_quality_v2_gate.py",
        root / "scripts/check_legacy_project_context_lineage.py",
    ):
        completed = subprocess.run(
            [sys.executable, str(script), "--help"],
            cwd=tmp_path,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env={"PATH": str(Path(sys.executable).parent)},
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
