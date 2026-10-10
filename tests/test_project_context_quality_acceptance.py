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


def test_v2_acceptance_requires_semantics_safety_sources_cost_observations_and_zero_false_full():
    report = _v2_report()
    assert verify_v2_acceptance(report) == []
    for lane, metric in (
        ("natural", "semantic_usefulness"),
        ("exposed_paraphrases", "semantic_usefulness"),
        ("natural", "safety"),
        ("exposed_paraphrases", "evaluator_verified_full_semantic_component_coverage"),
        ("natural", "cost_observation_completeness"),
    ):
        broken = deepcopy(report)
        broken["lanes"][lane]["metrics"][metric]["numerator"] -= 1
        assert verify_v2_acceptance(broken)
    broken = deepcopy(report)
    broken["lanes"]["natural"]["metrics"]["false_full_coverage"]["numerator"] = 1
    assert verify_v2_acceptance(broken)
    broken = deepcopy(report)
    broken.pop("output_cost_policy")
    assert verify_v2_acceptance(broken)


def test_v2_acceptance_keeps_lookup_attribution_as_a_non_regression_floor():
    report = _v2_report()
    broken = deepcopy(report)
    broken["lanes"]["natural"]["metrics"]["lookup_attribution"]["numerator"] = 32
    assert verify_v2_acceptance(broken)


def test_v2_acceptance_rejects_inventory_denominator_changes():
    report = _v2_report()
    report["lanes"]["natural"]["metrics"]["semantic_usefulness"]["denominator"] = 14
    assert verify_v2_acceptance(report)


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

def test_legacy_compatibility_floor_keeps_original_threshold_and_hard_safety(tmp_path):
    import hashlib
    import json

    from eval.project_context_quality.legacy_fact_acceptance import capture_legacy_evidence

    report = _legacy_report(tmp_path)
    metric = "verified_original_case_fact_count"
    floor = load_acceptance_lock()["legacy_lineage_floor"]
    assert floor["original_query_coverage_min"] == 12
    assert report["metrics"]["original_query_covered_count"] == 0
    assert verify_legacy_lineage_floor(report, source_root=tmp_path) == [], "legacy_healthy_context_fact_baseline"

    # A completed mirror's captured host root differs from the checked-out byte root.
    mirror_report = deepcopy(report)
    mirror_root = tmp_path / "completed_mirror"
    assert not mirror_root.exists()
    mirror_identity = "local:" + hashlib.sha256(str(mirror_root).encode("utf-8")).hexdigest()
    for mirror_row in mirror_report["results"]:
        mirror_row["legacy_fact_evidence"]["request"]["project_path"] = str(mirror_root)
        for mirror_source in mirror_row["payload"]["sources"]:
            mirror_source["project_identity"] = mirror_identity
            mirror_row["legacy_fact_evidence"]["source_bindings"][mirror_source["evidence_id"]]["projected_source"] = deepcopy(mirror_source)
    assert verify_legacy_lineage_floor(mirror_report, source_root=tmp_path) == [], "legacy_host_root_distinct_from_source_bytes"

    # The observer only copies supplied actual material and never manufactures a receipt.
    row = report["results"][0]
    source = row["payload"]["sources"][0]
    assert source["content_sha256"] == "0180c2e1aea9e5c3960e140171879049dac9507516f299c7e75d532da7ee7c9f"
    receipt = row["legacy_fact_evidence"]
    bound = receipt["source_bindings"][source["evidence_id"]]
    material = bound["source_hash_material"]
    snapshot = {source["evidence_id"]: {
        "source": {"path": material["path"], "heading_path": material["section"],
                   "content": material["content"], "snippet": material["snippet"], "version_binding": material["version"]},
        "projected_source": source,
        "qualification": {"retrieval_query_matches": bound["retrieval_query_matches"]},
    }}
    payload = {**row["payload"], "diagnostics": {"observer_counts": receipt["observer_counts"]}}
    copied = capture_legacy_evidence(receipt["request"], payload, snapshot)
    assert copied == receipt
    assert capture_legacy_evidence(receipt["request"], {}, {})["observer_counts"] is None
    snapshot[source["evidence_id"]]["source"]["content"] = "changed after observation"
    assert copied == receipt, "legacy_snapshot_copy_isolation"

    def rebind(broken, *, text=None, path=None):
        value = broken["results"][0]["payload"]["sources"][0]
        if text is not None:
            value["snippet"] = text
        if path is not None:
            value["path_or_url"] = path
            (tmp_path / path).write_text(value["snippet"] + "\n", encoding="utf-8")
        target_text = (tmp_path / value["path_or_url"]).read_text(encoding="utf-8")
        start = target_text.index(value["snippet"])
        value["line_start"] = target_text[:start].count("\n") + 1
        value["line_end"] = target_text[:start + len(value["snippet"])].count("\n") + 1
        material = {
            "path": value["path_or_url"], "section": value["section"],
            "content": value["snippet"], "snippet": value["snippet"], "version": value["version_binding"],
        }
        value["content_sha256"] = hashlib.sha256(json.dumps(
            material, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        binding = broken["results"][0]["legacy_fact_evidence"]["source_bindings"][value["evidence_id"]]
        binding["source_hash_material"] = material
        binding["projected_source"] = deepcopy(value)

    # A separate literal original lane may receive its own credit while remaining context-only.
    original = deepcopy(report)
    row = original["results"][0]
    value = row["payload"]["sources"][0]
    text = value["snippet"] + "\n" + row["question"]
    target = tmp_path / value["path_or_url"]
    target.write_text(target.read_text(encoding="utf-8") + "\n" + text + "\n", encoding="utf-8")
    rebind(original, text=text)
    trace = {
        "query_text": row["question"], "query_origin": "original", "relation": "direct",
        "qualified": True, "context_only": True, "coverage_kind": "direct",
    }
    row["legacy_fact_evidence"]["source_bindings"][value["evidence_id"]]["retrieval_query_matches"]["query-original"] = trace
    row["payload"]["covered_query_ids"] = ["query-original", "query-lookup-1"]
    row["payload"]["missing_query_ids"] = []
    row["observed"]["original_query_covered"] = True
    original["metrics"]["original_query_covered_count"] = 1
    original["legacy_fact_acceptance"]["raw_original_query_covered_count"] = 1
    assert verify_legacy_lineage_floor(original, source_root=tmp_path) == [], "legacy_independent_original_lane_baseline"
    for patch in ({"admission_only": True}, {"query_origin": "host_lookup"}, {"public_parent_query_id": "query-lookup-1"}):
        broken = deepcopy(original)
        broken["results"][0]["legacy_fact_evidence"]["source_bindings"][value["evidence_id"]]["retrieval_query_matches"]["query-original"].update(patch)
        assert any("legacy_no_lookup_to_original_transfer" in error for error in verify_legacy_lineage_floor(
            broken, source_root=tmp_path,
        )), "legacy_original_lane_identity_guard"

    # Honest partial evidence keeps its source/hash; the missing full fact must lose credit.
    for patch in (
        {"text": "This authored fixture contains a safe partial context window."},
        {"path": "wiki/Commands.md.shadow"},
    ):
        broken = deepcopy(report)
        rebind(broken, **patch)
        broken["metrics"][metric] = broken["legacy_fact_acceptance"][metric] = 11
        broken["legacy_fact_acceptance"]["verified_case_ids"].remove("ru-install")
        assert any("legacy_fact_floor:" in error for error in verify_legacy_lineage_floor(
            broken, source_root=tmp_path,
        )), "legacy_full_fact_and_exact_path_guard"

    # Metadata-only facts stay uncredited even beside unrelated substantive text,
    # with self-consistent source/hash/line bindings and a forged zero metadata rollup.
    for text in (
        "# doc-atlas setup",
        "# doc-atlas setup\n\nUnrelated preserved explanatory sentence.",
        "doc-atlas setup\n================",
        "- [doc-atlas setup](https://example.invalid/command)",
        "1. [doc-atlas setup](https://example.invalid/command)",
        "![doc-atlas setup](fixture.png)",
        "![doc-atlas setup](fixture.png) Unrelated preserved explanation.",
        'Unrelated preserved text [guide](https://example.invalid/command "doc-atlas setup")',
        "[doc-atlas setup]: https://example.invalid/command",
        "| doc-atlas setup | Other field |\n| --- | --- |",
        "| doc-atlas setup | Other field |\n| --- | --- |\n| unrelated | preserved data |",
    ):
        broken = deepcopy(report)
        target = tmp_path / "wiki/Commands.md"
        target.write_text(target.read_text(encoding="utf-8") + "\n" + text + "\n", encoding="utf-8")
        rebind(broken, text=text)
        broken["metrics"][metric] = broken["legacy_fact_acceptance"][metric] = 11
        broken["legacy_fact_acceptance"]["verified_case_ids"].remove("ru-install")
        assert broken["metrics"]["metadata_only_evidence_count"] == 0
        assert any("legacy_fact_floor:" in error for error in verify_legacy_lineage_floor(
            broken, source_root=tmp_path,
        )), "legacy_substantive_fact_guard"
    for text in (
        "Run `doc-atlas setup` to create the stores.",
        "```sh\ndoc-atlas setup\n```",
        "| Command | Result |\n| --- | --- |\n| doc-atlas setup | Creates local stores |",
    ):
        positive = deepcopy(report)
        target = tmp_path / "wiki/Commands.md"
        target.write_text(target.read_text(encoding="utf-8") + "\n" + text + "\n", encoding="utf-8")
        rebind(positive, text=text)
        assert verify_legacy_lineage_floor(positive, source_root=tmp_path) == [], "legacy_native_body_fact_baseline"

    # Consistent public/snapshot metadata cannot change the host owner, scope or source lines.
    for patch, guard in (
        ({"project_identity": "local:" + "0" * 64}, "legacy_host_project_identity"),
        ({"project_identity": "fixture:legacy"}, "legacy_host_project_identity"),
        ({"scope": "library"}, "legacy_project_scope"),
        ({"scope": "module"}, "legacy_project_scope"),
        ({"line_start": True}, "legacy_current_line_span"),
        ({"line_end": "2"}, "legacy_current_line_span"),
        ({"line_start": 0}, "legacy_current_line_span"),
        ({"line_end": 1000000}, "legacy_current_line_span"),
        ({"line_start": 2, "line_end": 3}, "legacy_current_line_span"),
        ({"line_end": 3}, "legacy_current_line_span"),
    ):
        broken = deepcopy(report)
        value = broken["results"][0]["payload"]["sources"][0]
        value.update(patch)
        binding = broken["results"][0]["legacy_fact_evidence"]["source_bindings"][value["evidence_id"]]
        binding["projected_source"] = deepcopy(value)
        assert value["content_sha256"] == source["content_sha256"]
        assert all(broken["metrics"][name] == 0 for name in floor["hard_zero_metrics"])
        assert any(guard in error for error in verify_legacy_lineage_floor(
            broken, source_root=tmp_path,
        )), f"legacy_independent_owner_scope_span_guard:{guard}"

    # A matching forged public/snapshot row still has to hash the actual copied source material.
    broken = deepcopy(report)
    value = broken["results"][0]["payload"]["sources"][0]
    value["content_sha256"] = "0" * 64
    broken["results"][0]["legacy_fact_evidence"]["source_bindings"][value["evidence_id"]]["projected_source"] = deepcopy(value)
    assert any("legacy_source_hash_binding" in error for error in verify_legacy_lineage_floor(
        broken, source_root=tmp_path,
    )), "legacy_independent_source_hash_guard"

    broken = deepcopy(report)
    value = broken["results"][0]["payload"]["sources"][0]
    value["snippet"] += " invisible forged fact"
    assert any("legacy_exact_snapshot_projection" in error for error in verify_legacy_lineage_floor(
        broken, source_root=tmp_path,
    )), "legacy_exact_projection_guard"

    broken = deepcopy(report)
    row = broken["results"][0]
    row["payload"]["covered_query_ids"] = ["query-original", "query-lookup-1"]
    row["payload"]["missing_query_ids"] = []
    row["observed"]["original_query_covered"] = True
    broken["metrics"]["original_query_covered_count"] = 1
    broken["legacy_fact_acceptance"]["raw_original_query_covered_count"] = 1
    assert any("legacy_no_lookup_to_original_transfer" in error for error in verify_legacy_lineage_floor(
        broken, source_root=tmp_path,
    )), "legacy_original_credit_guard"

    for guard, mutate in (
        ("legacy_fact_rollup", lambda value: value["metrics"].update({metric: 13})),
        ("legacy_fact_receipt_rollup", lambda value: value["legacy_fact_acceptance"].update({metric: 13})),
        ("legacy_same_call_observation", lambda value: value["results"][0]["legacy_fact_evidence"]["observer_counts"].update(retrieval_calls=2)),
        ("legacy_literal_request_binding", lambda value: value["results"][0]["legacy_fact_evidence"]["request"].update(question="rewritten question")),
        ("legacy_literal_project_root", lambda value: value["results"][0]["legacy_fact_evidence"]["request"].update(project_path="relative/project")),
        ("legacy_literal_project_root", lambda value: value["results"][0]["legacy_fact_evidence"]["request"].update(project_path="/selected/../other")),
        ("legacy_frozen_report_inventory", lambda value: value["results"].pop()),
        ("legacy_no_answer_or_edit_authority", lambda value: value["results"][0]["payload"].update(answer_supported=True)),
        ("legacy_negative_abstention", lambda value: value["results"][-1]["payload"].update(status="ok")),
    ):
        broken = deepcopy(report)
        mutate(broken)
        assert any(guard in error for error in verify_legacy_lineage_floor(
            broken, source_root=tmp_path,
        )), f"legacy_independent_acceptance_fault:{guard}"
    for safety in floor["hard_zero_metrics"]:
        broken = deepcopy(report)
        broken["metrics"][safety] = 1
        assert any(f"legacy hard-safety metric {safety}" in error for error in verify_legacy_lineage_floor(
            broken, source_root=tmp_path,
        )), "legacy_retained_hard_safety_guard"


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
