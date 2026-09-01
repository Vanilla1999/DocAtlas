#!/usr/bin/env python3
"""Hermetic production-path quality protocol for project documentation answers."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.docs.application.docs_job_service import DocsJobTracker
from docmancer.docs.application.evidence_selection import build_requirements
from docmancer.docs.domain import project_doc_ranking
from docmancer.docs.interfaces.mcp import context_tools
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import call_docs_tool_payload


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "eval" / "project_answer_quality_v1"
CASES_PATH = DATA_ROOT / "cases.json"
LOCK_PATH = DATA_ROOT / "protocol_v1.lock.json"
PUBLIC_ARGUMENT_FIELDS = ("mode", "project_path", "question")
SUPPORTED_TOKEN_LIMIT = 1500
INSUFFICIENT_TOKEN_LIMIT = 300


@dataclass(frozen=True, slots=True)
class ExpectedOutcome:
    status: str
    evidence_paths: tuple[str, ...]
    required_fragments: tuple[str, ...]
    forbidden_fragments: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    kind: str = "docs_answer"


@dataclass(frozen=True, slots=True)
class QualityCase:
    case_id: str
    question: str
    files: tuple[tuple[str, str], ...]
    documents: tuple[Mapping[str, str], ...]
    expected: ExpectedOutcome


@dataclass(frozen=True, slots=True)
class CaseResult:
    case_id: str
    status: str
    passed: bool
    checks: Mapping[str, bool]
    diagnostics: tuple[str, ...]
    stage_metrics: Mapping[str, float | int | bool]
    public_arguments: Mapping[str, str]
    selected_paths: tuple[str, ...]
    candidate_paths: tuple[str, ...]
    visible_tokens: int
    decision_hash: str | None
    kind: str
    support_status: str
    answer_supported: bool
    query_coverage: float
    citations: tuple[Mapping[str, Any], ...]


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_cases(path: Path = CASES_PATH) -> tuple[QualityCase, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "project-answer-quality-corpus-v1":
        raise ValueError("unsupported project-answer quality corpus schema")
    rows: list[QualityCase] = []
    seen: set[str] = set()
    for raw in payload.get("cases") or ():
        case_id = str(raw.get("case_id") or "").strip()
        question = str(raw.get("question") or "").strip()
        if not case_id or case_id in seen or not question:
            raise ValueError("quality cases require unique IDs and non-empty questions")
        seen.add(case_id)
        files = tuple(sorted(
            (str(path), str(text))
            for path, text in dict(raw.get("files") or {}).items()
        ))
        documents = tuple(dict(row) for row in raw.get("documents") or ())
        file_paths = {path for path, _ in files}
        document_paths = {str(row.get("path") or "") for row in documents}
        if not files or file_paths != document_paths:
            raise ValueError(f"{case_id}: every fixture file must have one catalog entry")
        expected_raw = dict(raw.get("expected") or {})
        expected = ExpectedOutcome(
            status=str(expected_raw.get("status") or ""),
            evidence_paths=tuple(str(value) for value in expected_raw.get("evidence_paths") or ()),
            required_fragments=tuple(str(value) for value in expected_raw.get("required_fragments") or ()),
            forbidden_fragments=tuple(str(value) for value in expected_raw.get("forbidden_fragments") or ()),
            forbidden_paths=tuple(str(value) for value in expected_raw.get("forbidden_paths") or ()),
        )
        if expected.status not in {"ok", "insufficient_evidence"}:
            raise ValueError(f"{case_id}: unsupported expected status")
        if not set(expected.evidence_paths).issubset(file_paths):
            raise ValueError(f"{case_id}: expected evidence path is not in the fixture")
        rows.append(QualityCase(
            case_id=case_id,
            question=question,
            files=files,
            documents=documents,
            expected=expected,
        ))
    return tuple(rows)


def validate_protocol_lock(path: Path = LOCK_PATH) -> dict[str, Any]:
    lock = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if lock.get("schema_version") != "project-answer-quality-protocol-v1":
        errors.append("schema_version")
    if lock.get("case_file") != "cases.json":
        errors.append("case_file")
    if lock.get("case_file_sha256") != file_sha256(CASES_PATH):
        errors.append("case_file_sha256")
    if tuple(lock.get("public_argument_fields") or ()) != PUBLIC_ARGUMENT_FIELDS:
        errors.append("public_argument_fields")
    if int(lock.get("supported_token_limit") or 0) != SUPPORTED_TOKEN_LIMIT:
        errors.append("supported_token_limit")
    if int(lock.get("insufficient_token_limit") or 0) != INSUFFICIENT_TOKEN_LIMIT:
        errors.append("insufficient_token_limit")
    case_ids = tuple(case.case_id for case in load_cases())
    if tuple(lock.get("case_ids") or ()) != case_ids:
        errors.append("case_ids")
    if errors:
        raise ValueError("invalid project-answer quality protocol lock: " + ", ".join(errors))
    return lock


@contextmanager
def _isolated_home(path: Path) -> Iterator[None]:
    previous = os.environ.get("DOCATLAS_HOME")
    os.environ["DOCATLAS_HOME"] = str(path)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("DOCATLAS_HOME", None)
        else:
            os.environ["DOCATLAS_HOME"] = previous


@contextmanager
def _frozen_answer_projection() -> Iterator[None]:
    """Keep the hermetic v1-v4 proof oracle separate from live final routing."""

    original_projection = context_tools.maybe_project_docs_context
    original_lane_eligibility = project_doc_ranking.source_lane_allowed
    context_tools.maybe_project_docs_context = lambda **kwargs: (
        kwargs["projection"], kwargs["snapshot"]
    )
    project_doc_ranking.source_lane_allowed = (
        lambda _path, _question, *, impact_policy=None: True
    )
    try:
        yield
    finally:
        context_tools.maybe_project_docs_context = original_projection
        project_doc_ranking.source_lane_allowed = original_lane_eligibility


def _write_repository(root: Path, case: QualityCase) -> None:
    for relative, text in case.files:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    rows = ["schema_version: 1", "documents:"]
    for document in case.documents:
        rows.extend((
            f"  - path: {document['path']}",
            f"    role: {document.get('role', 'other')}",
            "    scope: project",
            "    description: Immutable project-answer quality fixture.",
            f"    authority: {document.get('authority', 'source_of_truth')}",
            f"    status: {document.get('status', 'active')}",
            f"    impact: {document.get('impact', 'track')}",
        ))
    (root / "docatlas.project-docs.yaml").write_text(
        "\n".join(rows) + "\n", encoding="utf-8",
    )


def _service(workspace: Path) -> LibraryDocsService:
    config = DocmancerConfig()
    config.index.db_path = str(workspace / "index.sqlite")
    config.index.extracted_dir = str(workspace / "extracted")
    return LibraryDocsService(
        config=config,
        registry=LibraryRegistry(config.index.db_path),
        agent=DocmancerAgent(config=config),
        job_tracker=DocsJobTracker(),
    )


def _indexed_text_by_path(db_path: str) -> dict[str, str]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT COALESCE(source_path, source), text FROM sections ORDER BY id"
        ).fetchall()
    grouped: dict[str, list[str]] = {}
    for path, text in rows:
        normalized = str(path or "").replace("\\", "/")
        grouped.setdefault(normalized, []).append(str(text or ""))
    return {path: "\n".join(values) for path, values in grouped.items()}


def _query_coverage(payload: dict[str, Any]) -> float:
    value = payload.get("query_coverage")
    if (
        value is None
        and payload.get("kind") == "docs_answer"
        and payload.get("answer_supported") is True
    ):
        mandatory_coverage = payload.get("mandatory_coverage")
        return 1.0 if mandatory_coverage is None else float(mandatory_coverage)
    if value in {"full", "complete"}:
        return 1.0
    if value == "partial":
        return 0.5
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
def _chunk_path(chunk: Any) -> str:
    metadata = dict(getattr(chunk, "metadata", None) or {})
    return str(
        metadata.get("project_doc_path")
        or metadata.get("source_path")
        or getattr(chunk, "source", "")
        or ""
    ).replace("\\", "/")


def _citation_integrity(
    payload: Mapping[str, Any], indexed: Mapping[str, str],
) -> bool:
    """Validate public citations against the hermetic indexed corpus.

    ``content_sha256`` binds the canonical internal source snapshot rather than
    only the visible snippet, so a public-only oracle must not recompute it from
    the snippet.  It can still prove that every citation has a strong digest,
    maps to a selected evidence ID, and quotes text that exists verbatim in the
    cited indexed source.
    """

    sources = tuple(payload.get("sources") or ())
    answer_ids = {str(value) for value in payload.get("answer_evidence_ids") or ()}
    selected_ids = {str(value) for value in payload.get("selected_evidence_ids") or ()}
    source_ids: set[str] = set()
    for source in sources:
        evidence_id = str(source.get("evidence_id") or "")
        snippet = str(source.get("snippet") or "").strip()
        digest = str(source.get("content_sha256") or "")
        path = str(source.get("path_or_url") or "").replace("\\", "/")
        indexed_text = str(indexed.get(path) or "")
        if (
            not evidence_id
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
            or not snippet
            or (snippet not in indexed_text and snippet != path)
        ):
            return False
        source_ids.add(evidence_id)
    return (
        answer_ids.issubset(source_ids)
        and selected_ids.issubset(source_ids)
        and (not answer_ids or bool(sources))
    )


def _expected_projection_contract(
    expected: ExpectedOutcome,
    payload: Mapping[str, Any],
) -> tuple[bool, bool]:
    status_matches = payload.get("status") == expected.status
    kind_matches = payload.get("kind") == expected.kind
    if expected.status == "insufficient_evidence":
        return status_matches, bool(
            kind_matches
            and not payload.get("answer")
            and not payload.get("sources")
            and not payload.get("answer_supported")
            and not payload.get("answer_available")
        )
    if expected.kind == "docs_answer":
        return status_matches and kind_matches, bool(
            payload.get("answer_supported") is True
            and payload.get("answer_available") is True
            and float(payload.get("mandatory_coverage") or 0.0) == 1.0
        )
    if expected.kind == "docs_context":
        return status_matches and kind_matches, bool(
            payload.get("answer_supported") is False
            and not payload.get("answer_available")
            and payload.get("edit_ready") is False
        )
    return False, False


def run_case(
    case: QualityCase,
    workspace: Path,
    *,
    enforce_expected_kind: bool = False,
) -> CaseResult:
    repository = workspace / "repository"
    repository.mkdir(parents=True, exist_ok=True)
    _write_repository(repository, case)
    with _isolated_home(workspace / "home"):
        service = _service(workspace)
        inspection = service.inspect_project_docs(str(repository))
        acquired_paths = tuple(sorted(
            str(row.get("path") or "").replace("\\", "/")
            for row in inspection.candidate_sources
        ))
        sync = service.sync_project_docs(str(repository), with_vectors=False)
        indexed = _indexed_text_by_path(service.config.index.db_path)
        requirements = build_requirements(
            case.question, profile="project_docs_answer",
        )
        candidates = service.query_project_docs(
            str(repository), case.question, requirements=requirements,
            limit=10, tokens=SUPPORTED_TOKEN_LIMIT,
        )
        candidate_paths = tuple(dict.fromkeys(
            path for chunk in candidates if (path := _chunk_path(chunk))
        ))
        public_arguments = {
            "question": case.question,
            "project_path": str(repository),
            "mode": "project",
        }
        with _frozen_answer_projection():
            payload = call_docs_tool_payload(
                "get_docs_context", public_arguments, service,
            )

    expected = case.expected
    expected_paths = set(expected.evidence_paths)
    selected_paths = tuple(dict.fromkeys(
        str(row.get("path_or_url") or "").replace("\\", "/")
        for row in payload.get("sources") or ()
    ))
    visible_text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    visible_folded = visible_text.casefold()
    supported = expected.status == "ok"
    retrieval_only = bool(
        payload.get("status") == "ok"
        and payload.get("kind") == "docs_context"
        and payload.get("answer_supported") is False
        and payload.get("answer_available") is False
        and payload.get("edit_ready") is False
    )
    token_limit = (
        SUPPORTED_TOKEN_LIMIT
        if supported or (retrieval_only and not enforce_expected_kind)
        else INSUFFICIENT_TOKEN_LIMIT
    )
    visible_tokens = int(payload.get("estimated_tokens") or token_limit + 1)

    acquisition_recall = (
        not expected_paths or expected_paths.issubset(set(acquired_paths))
    )
    indexed_fact_coverage = all(
        (
            fragment.replace("\\", "/") in expected_paths
            or any(
                fragment.casefold() in text.casefold()
                for path, text in indexed.items()
                if not expected_paths or path in expected_paths
            )
        )
        for fragment in expected.required_fragments
    )
    candidate_recall = (
        not expected_paths or expected_paths.issubset(set(candidate_paths))
    )
    if retrieval_only:
        selected_coverage = _query_coverage(payload) >= 0.5
    elif enforce_expected_kind and expected.status == "insufficient_evidence":
        selected_coverage = not payload.get("answer_supported", False)
    elif enforce_expected_kind and expected.kind == "docs_context":
        selected_coverage = _query_coverage(payload) >= 0.5
    else:
        selected_coverage = (
            float(payload.get("mandatory_coverage") or 0.0) == 1.0
            if supported else not payload.get("answer_supported", False)
        )
    projected_coverage = all(
        fragment.casefold() in visible_folded
        for fragment in expected.required_fragments
    )
    citation_integrity = _citation_integrity(payload, indexed)
    if enforce_expected_kind:
        status_kind_correct, authorization_correct = _expected_projection_contract(
            expected, payload,
        )
        abstention_correctness = status_kind_correct
    else:
        authorization_correct = True
        abstention_correctness = bool(
            payload.get("status") == expected.status if supported else (
                retrieval_only
                or (
                    payload.get("status") == "insufficient_evidence"
                    and not payload.get("answer")
                    and not payload.get("sources")
                    and not payload.get("answer_supported", False)
                )
            )
        )
    contamination_free = bool(
        all(fragment.casefold() not in visible_folded for fragment in expected.forbidden_fragments)
        and not set(selected_paths).intersection(expected.forbidden_paths)
    )
    correct_evidence = set(selected_paths) == expected_paths
    public_surface = tuple(sorted(public_arguments)) == PUBLIC_ARGUMENT_FIELDS
    token_ceiling = visible_tokens <= token_limit
    sync_success = sync.status == "success"

    checks = {
        "sync_success": sync_success,
        "public_surface": public_surface,
        "document_acquisition_recall": acquisition_recall,
        "indexed_fact_coverage": indexed_fact_coverage,
        "candidate_recall_at_k": candidate_recall,
        "selected_obligation_coverage": selected_coverage,
        "projected_answer_coverage": projected_coverage,
        "citation_integrity": citation_integrity,
        "abstention_correctness": abstention_correctness,
        "authorization_contract": authorization_correct,
        "correct_evidence": correct_evidence,
        "contamination_free": contamination_free,
        "visible_token_ceiling": token_ceiling,
    }
    diagnostics = tuple(name for name, passed in checks.items() if not passed)
    return CaseResult(
        case_id=case.case_id,
        status=str(payload.get("status") or ""),
        passed=all(checks.values()),
        checks=checks,
        diagnostics=diagnostics,
        stage_metrics={
            "document_acquisition_recall": int(acquisition_recall),
            "indexed_fact_coverage": int(indexed_fact_coverage),
            "candidate_recall_at_k": int(candidate_recall),
            "selected_obligation_coverage": int(selected_coverage),
            "projected_answer_coverage": int(projected_coverage),
            "citation_integrity": int(citation_integrity),
            "abstention_correctness": int(abstention_correctness),
            "contamination_free": int(contamination_free),
            "visible_tokens": visible_tokens,
        },
        public_arguments=public_arguments,
        selected_paths=selected_paths,
        candidate_paths=candidate_paths,
        visible_tokens=visible_tokens,
        decision_hash=str(payload.get("decision_hash") or "") or None,
        kind=str(payload.get("kind") or ""),
        support_status=str(payload.get("support_status") or ""),
        answer_supported=bool(payload.get("answer_supported")),
        query_coverage=_query_coverage(payload),
        citations=tuple({
            "path": str(row.get("path_or_url") or ""),
            "evidence_id": str(row.get("evidence_id") or ""),
            "content_sha256": str(row.get("content_sha256") or ""),
        } for row in payload.get("sources") or ()),
    )


def _mean(rows: Sequence[CaseResult], key: str) -> float:
    if not rows:
        return 0.0
    return sum(float(row.stage_metrics[key]) for row in rows) / len(rows)


def run(output: Path | None = None) -> dict[str, Any]:
    lock = validate_protocol_lock()
    cases = load_cases()
    results: list[CaseResult] = []
    with tempfile.TemporaryDirectory(prefix="docatlas-project-answer-quality-") as temporary:
        root = Path(temporary)
        for case in cases:
            results.append(run_case(case, root / case.case_id))
    supported = [row for row, case in zip(results, cases) if case.expected.status == "ok"]
    report = {
        "schema_version": "project-answer-quality-result-v1",
        "provider_free": True,
        "protocol_sha256": file_sha256(LOCK_PATH),
        "case_file_sha256": lock["case_file_sha256"],
        "public_argument_fields": list(PUBLIC_ARGUMENT_FIELDS),
        "case_count": len(results),
        "passed_count": sum(row.passed for row in results),
        "stage_metrics": {
            "document_acquisition_recall": _mean(results, "document_acquisition_recall"),
            "indexed_fact_coverage": _mean(supported, "indexed_fact_coverage"),
            "candidate_recall_at_k": _mean(supported, "candidate_recall_at_k"),
            "selected_obligation_coverage": _mean(supported, "selected_obligation_coverage"),
            "projected_answer_coverage": _mean(supported, "projected_answer_coverage"),
            "citation_integrity": _mean(results, "citation_integrity"),
            "abstention_correctness": _mean(results, "abstention_correctness"),
            "contamination_free": _mean(results, "contamination_free"),
            "maximum_visible_tokens": max(row.visible_tokens for row in results),
        },
        "verdict": "PASS" if all(row.passed for row in results) else "FAIL",
        "results": [
            {
                "case_id": row.case_id,
                "status": row.status,
                "passed": row.passed,
                "checks": dict(row.checks),
                "diagnostics": list(row.diagnostics),
                "stage_metrics": dict(row.stage_metrics),
                "public_arguments": dict(row.public_arguments),
                "selected_paths": list(row.selected_paths),
                "candidate_paths": list(row.candidate_paths),
                "visible_tokens": row.visible_tokens,
                "decision_hash": row.decision_hash,
            }
            for row in results
        ],
    }
    report["deterministic_result_digest"] = hashlib.sha256(canonical_bytes(report)).hexdigest()
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate-protocol", action="store_true")
    args = parser.parse_args()
    if args.validate_protocol:
        validate_protocol_lock()
        load_cases()
        print("PASS")
        return 0
    report = run(args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
