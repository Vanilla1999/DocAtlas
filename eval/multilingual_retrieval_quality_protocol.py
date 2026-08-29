#!/usr/bin/env python3
"""Preregistered gates for Context7-style multilingual project retrieval."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "eval" / "multilingual_retrieval_quality" / "protocol_v3.lock.json"
DATA_ROOT = LOCK_PATH.parent
EXPECTED_LANGUAGE_PAIRS = ("en-en", "ru-en", "ru-ru")
EXPECTED_SPLITS = ("development", "holdout", "adversarial")
EXPECTED_SYSTEMS = (
    "open-lexical",
    "open-multilingual-dense",
    "open-hybrid-rrf",
)


@dataclass(frozen=True, slots=True)
class FrozenCorpus:
    projects: tuple[Mapping[str, Any], ...]
    cases: tuple[Mapping[str, Any], ...]
    digests: Mapping[str, str]


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def protocol_sha256() -> str:
    return hashlib.sha256(LOCK_PATH.read_bytes()).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repository_span(revision: str, path: str, line_start: int, line_end: int) -> str:
    result = subprocess.run(
        ["git", "show", f"{revision}:{path}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return "\n".join(result.stdout.splitlines()[line_start - 1:line_end])


def validate_protocol_lock() -> dict[str, Any]:
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    errors: list[str] = []
    if lock.get("schema_version") != "multilingual-retrieval-quality-protocol-v3":
        errors.append("schema_version")
    if tuple(lock.get("language_pairs") or ()) != EXPECTED_LANGUAGE_PAIRS:
        errors.append("language_pairs")
    if tuple(lock.get("splits") or ()) != EXPECTED_SPLITS:
        errors.append("splits")
    if tuple(row.get("id") for row in lock.get("systems") or ()) != EXPECTED_SYSTEMS:
        errors.append("systems")
    corpus = lock.get("corpus_gates") or {}
    quality = lock.get("quality_gates") or {}
    activation = lock.get("activation_policy") or {}
    model = lock.get("model_configuration") or {}
    artifacts = lock.get("frozen_artifacts") or {}
    if corpus.get("project_scope") != "self_hosting_only":
        errors.append("project_scope")
    if corpus.get("required_project_count") != 1:
        errors.append("required_project_count")
    if int(corpus.get("minimum_cases_per_language_pair") or 0) < 5:
        errors.append("minimum_cases_per_language_pair")
    if int(corpus.get("minimum_cases_per_language_pair_per_split") or 0) < 1:
        errors.append("minimum_cases_per_language_pair_per_split")
    if float(quality.get("recall_at_5_overall_min") or 0) < 0.9:
        errors.append("recall_at_5_overall_min")
    if float(quality.get("recall_at_5_per_language_pair_min") or 0) < 0.85:
        errors.append("recall_at_5_per_language_pair_min")
    if quality.get("degraded_or_fallback_runs_max") != 0:
        errors.append("degraded_or_fallback_runs_max")
    if activation.get("change_default_retrieval") is not False:
        errors.append("change_default_retrieval")
    if activation.get("self_hosting_proves_external_generalization") is not False:
        errors.append("self_hosting_proves_external_generalization")
    if model != {
        "dense_provider": "fastembed",
        "dense_model": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        "dense_dimensions": 768,
        "sparse_model": "prithivida/Splade_PP_en_v1",
        "fusion": "rrf",
        "rrf_k": 60,
        "allow_degraded": False,
    }:
        errors.append("model_configuration")
    if len(str(artifacts.get("repository_revision") or "")) != 40:
        errors.append("repository_revision")
    digest_manifest = DATA_ROOT / "digests.json"
    if not digest_manifest.is_file() or artifacts.get("corpus_digest_manifest_sha256") != file_sha256(digest_manifest):
        errors.append("corpus_digest_manifest_sha256")
    if artifacts.get("runner_sha256") != file_sha256(Path(__file__)):
        errors.append("runner_sha256")
    adapter_path = ROOT / "eval" / "multilingual_retrieval_matrix_adapter.py"
    if artifacts.get("adapter_sha256") != file_sha256(adapter_path):
        errors.append("adapter_sha256")
    if errors:
        raise ValueError("invalid multilingual retrieval protocol lock: " + ", ".join(errors))
    return lock


def validate_corpus(cases: Iterable[dict[str, Any]]) -> dict[str, Any]:
    lock = validate_protocol_lock()
    rows = list(cases)
    ids = [str(row.get("id") or "") for row in rows]
    errors: list[str] = []
    if not ids or any(not value for value in ids) or len(ids) != len(set(ids)):
        errors.append("case_ids")
    projects = {str(row.get("project_id")) for row in rows if row.get("project_id")}
    if len(projects) != lock["corpus_gates"]["required_project_count"]:
        errors.append("project_count")
    if not rows or not all(row.get("self_hosting_control") for row in rows):
        errors.append("self_hosting_only")
    for language_pair in EXPECTED_LANGUAGE_PAIRS:
        count = sum(row.get("language_pair") == language_pair for row in rows)
        if count < lock["corpus_gates"]["minimum_cases_per_language_pair"]:
            errors.append(f"language_pair:{language_pair}")
    for split in EXPECTED_SPLITS:
        for language_pair in EXPECTED_LANGUAGE_PAIRS:
            count = sum(
                row.get("split") == split and row.get("language_pair") == language_pair
                for row in rows
            )
            if count < lock["corpus_gates"]["minimum_cases_per_language_pair_per_split"]:
                errors.append(f"split_language_pair:{split}:{language_pair}")
    taxonomies = set(lock.get("taxonomies") or ())
    if any(str(row.get("taxonomy") or "") not in taxonomies for row in rows):
        errors.append("taxonomy")
    semantic_splits: dict[str, set[str]] = {}
    for row in rows:
        family = str(row.get("semantic_family") or "")
        if not family:
            errors.append("semantic_family")
            continue
        semantic_splits.setdefault(family, set()).add(str(row.get("split") or ""))
    if any(len(splits) != 1 for splits in semantic_splits.values()):
        errors.append("semantic_family_split_isolation")
    if not any(row.get("multi_concept_gold_spans") for row in rows):
        errors.append("multi_concept_gold_spans")
    if not any(row.get("absent_fact") for row in rows):
        errors.append("absent_fact")
    if errors:
        raise ValueError("invalid multilingual retrieval corpus: " + ", ".join(errors))
    return {"case_count": len(rows), "project_count": len(projects), "self_hosting_only": True}


def load_frozen_corpus(data_root: Path = DATA_ROOT) -> FrozenCorpus:
    digests_path = data_root / "digests.json"
    if not digests_path.is_file():
        raise ValueError("frozen multilingual corpus requires digests.json")
    digest_lock = json.loads(digests_path.read_text(encoding="utf-8"))
    if digest_lock.get("schema_version") != "multilingual-retrieval-quality-digests-v1":
        raise ValueError("unsupported multilingual corpus digest schema")
    locked_files = dict(digest_lock.get("files") or {})
    required_files = ("corpus.json", *(f"{split}.json" for split in EXPECTED_SPLITS))
    if set(locked_files) != set(required_files):
        raise ValueError("digest lock must bind the corpus and every protocol split")
    payloads: dict[str, dict[str, Any]] = {}
    for relative_path in required_files:
        path = data_root / relative_path
        if not path.is_file() or file_sha256(path) != locked_files[relative_path]:
            raise ValueError(f"frozen corpus digest mismatch: {relative_path}")
        payloads[relative_path] = json.loads(path.read_text(encoding="utf-8"))

    corpus = payloads["corpus.json"]
    if corpus.get("schema_version") != "multilingual-retrieval-quality-corpus-v1":
        raise ValueError("unsupported multilingual corpus schema")
    projects = tuple(dict(row) for row in corpus.get("projects") or ())
    project_ids = [str(row.get("id") or "") for row in projects]
    if not project_ids or any(not value for value in project_ids) or len(project_ids) != len(set(project_ids)):
        raise ValueError("frozen corpus requires unique project IDs")
    projects_by_id = {str(row["id"]): row for row in projects}
    if len(projects) != 1 or not projects[0].get("self_hosting_control"):
        raise ValueError("frozen corpus requires exactly one self-hosting project")

    spans: dict[str, str] = {}
    for project in projects:
        project_id = str(project["id"])
        if not str(project.get("project_identity") or "") or not str(project.get("revision") or ""):
            raise ValueError(f"{project_id}: project identity and immutable revision are required")
        if project.get("revision") != validate_protocol_lock()["frozen_artifacts"]["repository_revision"]:
            raise ValueError(f"{project_id}: revision is not bound to the protocol lock")
        documents = project.get("documents") or ()
        if len(documents) <= 5:
            raise ValueError(f"{project_id}: frozen corpus requires more source spans than Recall@5")
        for document in documents:
            span_id = str(document.get("span_id") or "")
            content = str(document.get("content") or "")
            if not span_id or span_id in spans:
                raise ValueError("frozen corpus requires globally unique span IDs")
            if hashlib.sha256(content.encode("utf-8")).hexdigest() != document.get("content_sha256"):
                raise ValueError(f"{span_id}: content digest mismatch")
            if int(document.get("line_start") or 0) < 1 or int(document.get("line_end") or 0) < int(document.get("line_start") or 0):
                raise ValueError(f"{span_id}: invalid source line range")
            if not str(document.get("section") or "").strip():
                raise ValueError(f"{span_id}: source section is required")
            if data_root.resolve() == DATA_ROOT.resolve() and content != _repository_span(
                str(project["revision"]),
                str(document["path"]),
                int(document["line_start"]),
                int(document["line_end"]),
            ):
                raise ValueError(f"{span_id}: content does not match the frozen repository revision")
            spans[span_id] = project_id

    cases: list[dict[str, Any]] = []
    for split in EXPECTED_SPLITS:
        payload = payloads[f"{split}.json"]
        if payload.get("schema_version") != "multilingual-retrieval-quality-cases-v1":
            raise ValueError(f"{split}: unsupported case schema")
        for raw in payload.get("cases") or ():
            row = dict(raw)
            row["split"] = split
            project_id = str(row.get("project_id") or "")
            if project_id not in project_ids or not str(row.get("query") or "").strip():
                raise ValueError(f"{row.get('id') or split}: invalid project or query")
            row["self_hosting_control"] = bool(projects_by_id[project_id].get("self_hosting_control"))
            expected = tuple(str(value) for value in row.get("expected_source_spans") or ())
            if row.get("absent_fact") and expected:
                raise ValueError(f"{row.get('id')}: absent-fact cases cannot have gold spans")
            if any(spans.get(span_id) != project_id for span_id in expected):
                raise ValueError(f"{row.get('id')}: gold span is outside the target project")
            cases.append(row)
    validate_corpus(cases)
    return FrozenCorpus(projects=projects, cases=tuple(cases), digests=locked_files)


MatrixAdapter = Callable[[Mapping[str, Any], Mapping[str, Any], FrozenCorpus], Mapping[str, Any]]

_EXECUTION_CASE_FIELDS = (
    "project_id",
    "query",
    "language_pair",
)


def _execution_case(case: Mapping[str, Any]) -> dict[str, Any]:
    execution = {field: case[field] for field in _EXECUTION_CASE_FIELDS if field in case}
    execution["id"] = hashlib.sha256(
        f"{protocol_sha256()}:{case.get('id')}".encode()
    ).hexdigest()
    return execution


def _execution_corpus(corpus: FrozenCorpus) -> FrozenCorpus:
    return FrozenCorpus(
        projects=corpus.projects,
        cases=(),
        digests=corpus.digests,
    )


def run_matrix(adapter: MatrixAdapter, data_root: Path = DATA_ROOT) -> dict[str, Any]:
    corpus = load_frozen_corpus(data_root)
    execution_corpus = _execution_corpus(corpus)
    lock = validate_protocol_lock()
    corpus_manifest_sha256 = file_sha256(data_root / "digests.json")
    corpus_bound = corpus_manifest_sha256 == lock["frozen_artifacts"]["corpus_digest_manifest_sha256"]
    catalog = _source_catalog(corpus)
    rows_by_system: dict[str, list[dict[str, Any]]] = {}
    for system in lock["systems"]:
        system_id = str(system["id"])
        system_rows: list[dict[str, Any]] = []
        for case in corpus.cases:
            execution_case = _execution_case(case)
            result = dict(adapter(system, execution_case, execution_corpus))
            if result.get("id") != execution_case.get("id"):
                raise ValueError(f"{system_id}: adapter returned a mismatched case ID")
            result["id"] = case.get("id")
            result["language_pair"] = case.get("language_pair")
            result["split"] = case.get("split")
            result["absent_fact"] = bool(case.get("absent_fact"))
            result["expected_source_spans"] = list(case.get("expected_source_spans") or ())
            result["requested_mode"] = system["requested_mode"]
            result["fallback_used"] = bool(result.get("failures")) or (
                result.get("mode_used") != system["requested_mode"]
            )
            expected_identity = next(
                str(project["project_identity"])
                for project in corpus.projects if project["id"] == case["project_id"]
            )
            result["wrong_project_evidence_accepted"] = sum(
                1 for source in result.get("visible_sources") or ()
                if source.get("project_identity") != expected_identity
            ) + sum(
                1 for span_id in result.get("retrieved_source_spans") or ()
                if span_id not in catalog or catalog[span_id]["project_identity"] != expected_identity
            )
            system_rows.append(result)
        rows_by_system[system_id] = system_rows

    baseline = rows_by_system[EXPECTED_SYSTEMS[0]]
    evaluations = {
        system_id: evaluate_results(rows_by_system[system_id], baseline, corpus=corpus)
        for system_id in EXPECTED_SYSTEMS[1:]
    }
    holdout_baseline = [row for row in baseline if row.get("split") == "holdout"]
    holdout_evaluations = {
        system_id: evaluate_results(
            [row for row in rows_by_system[system_id] if row.get("split") == "holdout"],
            holdout_baseline,
            corpus=corpus,
        )
        for system_id in EXPECTED_SYSTEMS[1:]
    }
    return {
        "schema_version": "multilingual-retrieval-quality-matrix-v2",
        "protocol_sha256": protocol_sha256(),
        "corpus_digests": dict(corpus.digests),
        "systems": rows_by_system,
        "evaluations_against_open_lexical": evaluations,
        "holdout_evaluations_against_open_lexical": holdout_evaluations,
        "corpus_bound_to_protocol": corpus_bound,
        "corpus_digest_manifest_sha256": corpus_manifest_sha256,
        "profile_activation_eligible": _profile_activation_eligible(
            corpus_bound, evaluations, holdout_evaluations,
        ),
        "default_retrieval_changed": False,
        "external_generalization_claimed": False,
    }


def _profile_activation_eligible(
    corpus_bound: bool,
    evaluations: Mapping[str, Mapping[str, Any]],
    holdout_evaluations: Mapping[str, Mapping[str, Any]],
) -> bool:
    return corpus_bound and all(
        report.get("verdict") == "PASS"
        for reports in (evaluations, holdout_evaluations)
        for report in reports.values()
    )


def _recall_at_5(row: dict[str, Any]) -> float:
    expected = set(str(value) for value in row.get("expected_source_spans") or ())
    if not expected:
        return 0.0
    retrieved = set(str(value) for value in (row.get("retrieved_source_spans") or ())[:5])
    return len(expected & retrieved) / len(expected)


def paired_bootstrap_lower_bound(
    candidate: list[float], baseline: list[float], *, iterations: int, seed: int, confidence: float
) -> float:
    if len(candidate) != len(baseline) or not candidate:
        raise ValueError("paired bootstrap requires equal non-empty samples")
    differences = [left - right for left, right in zip(candidate, baseline)]
    randomizer = random.Random(seed)
    means = sorted(
        sum(differences[randomizer.randrange(len(differences))] for _ in differences) / len(differences)
        for _ in range(iterations)
    )
    index = max(0, int((1.0 - confidence) * len(means)))
    return means[min(index, len(means) - 1)]


def _source_catalog(corpus: FrozenCorpus) -> dict[str, dict[str, Any]]:
    return {
        str(document["span_id"]): {
            "span_id": str(document["span_id"]),
            "project_identity": str(project["project_identity"]),
            "content_sha256": str(document["content_sha256"]),
            "line_start": int(document["line_start"]),
            "line_end": int(document["line_end"]),
            "path": str(document["path"]),
            "section": str(document["section"]),
        }
        for project in corpus.projects
        for document in project.get("documents") or ()
    }


def _provenance_failures(
    rows: Iterable[dict[str, Any]], required: set[str], catalog: Mapping[str, Mapping[str, Any]] | None,
) -> int:
    failures = 0
    for row in rows:
        retrieved = tuple(str(value) for value in row.get("retrieved_source_spans") or ())
        sources = tuple(row.get("visible_sources") or ())
        visible_span_ids = {
            str(source.get("span_id") or "")
            for source in sources if isinstance(source, Mapping)
        }
        if set(retrieved) != visible_span_ids:
            failures += 1
        for source in sources:
            if not isinstance(source, Mapping) or not required.issubset(source):
                failures += 1
                continue
            span_id = str(source.get("span_id") or "")
            if span_id not in retrieved:
                failures += 1
                continue
            if catalog is not None and (
                span_id not in catalog
                or any(source.get(field) != catalog[span_id].get(field) for field in required)
            ):
                failures += 1
    return failures


def evaluate_results(
    candidate_rows: Iterable[dict[str, Any]], baseline_rows: Iterable[dict[str, Any]],
    *, corpus: FrozenCorpus | None = None,
) -> dict[str, Any]:
    lock = validate_protocol_lock()
    candidate = list(candidate_rows)
    baseline_by_id = {str(row.get("id")): row for row in baseline_rows}
    candidate_by_id = {str(row.get("id")): row for row in candidate}
    if set(candidate_by_id) != set(baseline_by_id) or not candidate_by_id:
        raise ValueError("candidate and baseline case IDs must match")
    ordered_ids = sorted(
        case_id for case_id, row in candidate_by_id.items() if not row.get("absent_fact")
    )
    if not ordered_ids:
        raise ValueError("retrieval evaluation requires positive cases")
    candidate_recall = [_recall_at_5(candidate_by_id[case_id]) for case_id in ordered_ids]
    baseline_recall = [_recall_at_5(baseline_by_id[case_id]) for case_id in ordered_ids]
    overall = sum(candidate_recall) / len(candidate_recall)
    per_language = {
        language_pair: sum(values) / len(values)
        for language_pair in EXPECTED_LANGUAGE_PAIRS
        for values in [[
            _recall_at_5(row) for row in candidate
            if row.get("language_pair") == language_pair and not row.get("absent_fact")
        ]]
        if values
    }
    wrong_project = sum(int(row.get("wrong_project_evidence_accepted") or 0) for row in candidate)
    absent_candidates = sum(
        len(row.get("retrieved_source_spans") or ())
        for row in candidate if row.get("absent_fact")
    )
    degraded = sum(
        1 for row in candidate
        if row.get("fallback_used") or row.get("mode_used") != row.get("requested_mode")
    )
    required_provenance = set(lock["quality_gates"]["visible_source_provenance_required"])
    provenance_failures = _provenance_failures(
        candidate, required_provenance, _source_catalog(corpus) if corpus else None,
    )
    quality = lock["quality_gates"]
    lower_bound = paired_bootstrap_lower_bound(
        candidate_recall,
        baseline_recall,
        iterations=int(quality["paired_bootstrap_iterations"]),
        seed=int(quality["paired_bootstrap_seed"]),
        confidence=float(quality["paired_bootstrap_confidence"]),
    )
    improvement_points = (overall - (sum(baseline_recall) / len(baseline_recall))) * 100
    checks = {
        "overall_recall": overall >= quality["recall_at_5_overall_min"],
        "per_language_recall": set(per_language) == set(EXPECTED_LANGUAGE_PAIRS) and all(
            value >= quality["recall_at_5_per_language_pair_min"] for value in per_language.values()
        ),
        "minimum_improvement": improvement_points >= quality["improvement_percentage_points_min"],
        "positive_bootstrap_lower_bound": lower_bound > 0,
        "wrong_project_free": wrong_project == 0,
        "no_degraded_or_fallback_runs": degraded == 0,
        "source_provenance_complete": provenance_failures == 0,
    }
    return {
        "schema_version": "multilingual-retrieval-quality-result-v1",
        "protocol_sha256": protocol_sha256(),
        "metrics": {
            "recall_at_5_overall": round(overall, 6),
            "recall_at_5_per_language_pair": {key: round(value, 6) for key, value in per_language.items()},
            "improvement_percentage_points": round(improvement_points, 6),
            "paired_bootstrap_lower_bound": round(lower_bound, 6),
            "wrong_project_evidence_accepted": wrong_project,
            "absent_fact_candidate_source_spans": absent_candidates,
            "degraded_or_fallback_runs": degraded,
            "source_provenance_failures": provenance_failures,
        },
        "checks": checks,
        "verdict": "PASS" if all(checks.values()) else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-protocol", action="store_true")
    parser.add_argument("--validate-corpus", action="store_true")
    parser.add_argument("--run-production-matrix", action="store_true")
    parser.add_argument("--data-root", type=Path, default=DATA_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.validate_protocol:
        validate_protocol_lock()
        print("PASS")
        return 0
    if args.validate_corpus:
        inventory = load_frozen_corpus(args.data_root)
        print(json.dumps({"projects": len(inventory.projects), "cases": len(inventory.cases)}, sort_keys=True))
        return 0
    if args.run_production_matrix:
        from eval.multilingual_retrieval_matrix_adapter import ProductionMultilingualMatrixAdapter

        adapter = ProductionMultilingualMatrixAdapter()
        try:
            report = run_matrix(adapter, args.data_root)
        finally:
            adapter.close()
        rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        else:
            print(rendered, end="")
        return 0 if report["profile_activation_eligible"] else 1
    parser.error("select --validate-protocol, --validate-corpus, or --run-production-matrix")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
