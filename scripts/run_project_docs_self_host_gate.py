#!/usr/bin/env python3
"""Provider-free current-repository gate for the context-first Docs pipeline.

The gate indexes this repository into an isolated temporary SQLite store and then
runs canonical Project Docs questions through the unpatched public
``get_docs_context`` MCP handler. It proves the current production chain:

question -> retrieval -> proof metadata -> final answer-or-context projection.

The corpus intentionally covers the stable QuestionPlan families plus two
premise/condition cases that depend on the clear-index source of truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import DocsJobTracker, LibraryDocsService


REPO_ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True, slots=True)
class LiveCase:
    question: str
    relevant_paths: tuple[str, ...]
    required_fragments: tuple[str, ...] = ()
    surface_case_id: int | None = None


GOLD_CASES: tuple[LiveCase, ...] = tuple(LiveCase(*row) for row in (
    ("Which source types are supported for indexing?", ("docs/modules/question-planning.md", "wiki/Supported-Sources.md")),
    ("Which command syncs project docs after file changes?", ("README.md", "docs/capabilities.md", "docs/project-docs-mcp-workflow.md")),
    ("Which command starts the Docs MCP server?", ("README.md", "docs/project-docs-demo.md", "wiki/Commands.md")),
    ("How do I run the offline test suite for DocAtlas?", ("docs/testing.md",)),
    ("How do I run the project answer quality v4 protocol?", ("eval/project_answer_quality_v4/README.md",)),
    ("How does the two-cell smoke procedure verify provider-call cardinality?", ("eval/task_level/README.md",)),
    ("Which docs files must stay under the 1000-line release limit?", ("docs/RELEASE_CHECKLIST.md",)),
    ("What is the storage mutation coordination contract for cleanup and refresh?", ("docs/index-cleanup.md", "docs/modules/storage-mutation-coordination.md"), ("writer lease", "cleanup barrier")),
    ("What happens if remove_library_docs runs while a library refresh is in flight?", ("docs/index-cleanup.md", "docs/modules/storage-mutation-coordination.md")),
    ("What is the release checklist and what gates block release?", ("docs/RELEASE_CHECKLIST.md",)),
    ("What is the model-visible projection and how is the answer token-bounded?", ("docs/mcp-docs-server.md",)),
    ("What does clear-index do when a live process holds the index?", ("docs/index-cleanup.md",)),
    ("How do I configure a project in docmancer.yaml?", ("wiki/Configuration.md",)),
    ("How does evidence selection choose which candidates are selected?", ("docs/mcp-docs-server.md", "docs/modules/evidence-selection.md")),
    ("What is contamination protection in the eval protocols?", ("eval/project_answer_quality_v4/README.md",)),
    ("What is the two-cell smoke procedure for local Task 33 benchmarks?", ("eval/task_level/README.md",)),
    ("What does the two-cell smoke procedure require?", ("eval/task_level/README.md",)),
    ("How do I sync project docs after changing a file?", ("README.md", "docs/capabilities.md", "docs/modules/README.md", "docs/project-docs-mcp-workflow.md")),
    ("How does indexing split documents into sections and chunks?", ("wiki/Architecture.md",)),
    ("What are the three public Docs MCP tools and when do I use each one?", ("docs/mcp-docs-server.md",)),
    ("How does evidence selection differ from question planning?", ("docs/modules/question-planning.md", "docs/modules/evidence-selection.md")),
    ("Where is the project answer contract documented?", ("docs/mcp-docs-server.md", "docs/modules/question-planning.md")),
    ("What happens when the preview plan is stale?", ("docs/index-cleanup.md",)),
    ("Why does clear-index always delete remote Qdrant collections?", ("docs/index-cleanup.md",)),
)) + tuple(LiveCase(*row) for row in (
    ("What source types are supported for indexing?", ("wiki/Supported-Sources.md", "docs/modules/question-planning.md"), ("GitBook sites",), 1),
    ("Which source types can DocAtlas index?", ("wiki/Supported-Sources.md", "docs/modules/question-planning.md"), ("GitBook sites",), 2),
    ("List the supported source types.", ("wiki/Supported-Sources.md", "docs/modules/question-planning.md"), ("GitBook sites",), 3),
    ("What file formats are supported for local files?", ("wiki/Supported-Sources.md",), (".md",), 4),
    ("Which document formats does indexing accept?", ("wiki/Supported-Sources.md",), (".md",), 5),
    ("List the pytest markers.", ("docs/testing.md",), ("integration",), 6),
    ("What markers does the offline suite define?", ("docs/testing.md",), ("integration", "advanced", "live_network"), 7),
    ("Какие типы источников можно индексировать?", ("wiki/Supported-Sources.md", "docs/modules/question-planning.md"), ("GitBook sites",), 8),
    ("Какие форматы локальных файлов поддерживаются?", ("wiki/Supported-Sources.md",), (".md",), 9),
    ("Какие pytest-маркеры есть в проекте?", ("docs/testing.md",), ("integration",), 10),
    ("How do I sync project docs after editing a file?", ("README.md", "docs/project-docs-mcp-workflow.md", "docs/capabilities.md"), ("sync_project_docs",), 11),
    ("Which command should I run after project docs change?", ("README.md", "docs/project-docs-mcp-workflow.md", "docs/capabilities.md"), ("sync_project_docs",), 12),
    ("Refresh project documentation after a file changes.", ("README.md", "docs/project-docs-mcp-workflow.md", "docs/capabilities.md"), ("sync_project_docs",), 13),
    ("Как обновить документацию проекта после изменения файла?", ("README.md", "docs/project-docs-mcp-workflow.md", "docs/capabilities.md"), ("sync_project_docs",), 14),
    ("Какой командой синхронизировать документацию проекта?", ("README.md", "docs/project-docs-mcp-workflow.md", "docs/capabilities.md"), ("sync_project_docs",), 15),
    ("How do I run the offline suite?", ("docs/testing.md",), ("DOCMANCER_OFFLINE=1", "not advanced and not live and not live_network"), 16),
    ("How can I run the offline suite?", ("docs/testing.md",), ("DOCMANCER_OFFLINE=1",), 17),
    ("How do I configure project docs in docmancer.yaml?", ("wiki/Configuration.md", "docs/project-docs-mcp-workflow.md"), ("docmancer.yaml",), 18),
    ("Where is project docs configuration defined?", ("docs/project-docs-mcp-workflow.md", "wiki/Configuration.md"), ("project-docs-mcp-workflow.md",), 19),
    ("What command starts the Docs MCP server?", ("README.md", "wiki/Commands.md", "docs/project-docs-demo.md"), ("docs-serve",), 20),
))

NEGATIVE_CASES = (
    "What lunar quantum retention policy does DocAtlas use?",
)


def _source_paths(payload: dict[str, object]) -> tuple[str, ...]:
    rows = payload.get("sources") or ()
    if not isinstance(rows, list):
        return ()
    result: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            value = str(row.get("path_or_url") or "").strip()
            if value:
                result.append(value)
    return tuple(result)


def _citations(payload: dict[str, object]) -> list[dict[str, object]]:
    citations: list[dict[str, object]] = []
    for row in payload.get("sources") or ():
        if not isinstance(row, dict):
            continue
        citations.append({
            "path": str(row.get("path_or_url") or ""),
            "evidence_id": str(row.get("evidence_id") or ""),
            "content_sha256": str(row.get("content_sha256") or ""),
            "retrieval_query_ids": list(row.get("retrieval_query_ids") or ()),
        })
    return citations


def _historical_paths() -> set[str]:
    catalog = yaml.safe_load((REPO_ROOT / "docatlas.project-docs.yaml").read_text(encoding="utf-8")) or {}
    return {
        str(row.get("path") or "")
        for row in catalog.get("documents") or ()
        if row.get("status") != "active"
    }


def _query_coverage(payload: dict[str, object]) -> float:
    value = payload.get("query_coverage")
    if value is None and payload.get("kind") == "docs_answer" and payload.get("answer_supported") is True:
        return float(payload.get("mandatory_coverage") or 1.0)
    if value in {"full", "complete"}:
        return 1.0
    if value in {"partial"}:
        return 0.5
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _validate_context_result(payload: dict[str, object]) -> str | None:
    kind = str(payload.get("kind") or "")
    if kind == "docs_answer":
        if payload.get("answer_supported") is not True or payload.get("answer_available") is not True:
            return "docs_answer lacks strict answer support"
    elif kind == "docs_context":
        if not (
            payload.get("context_status") == "ready"
            and payload.get("answer_supported") is False
            and payload.get("answer_available") is False
            and payload.get("edit_ready") is False
            and payload.get("safe_to_answer_from_sources") is True
        ):
            return "docs_context violates the context-first safety contract"
    else:
        return f"unexpected result kind={kind!r}"
    for source in payload.get("sources") or ():
        if not isinstance(source, dict):
            return "source is not structured"
        digest = str(source.get("content_sha256") or "")
        if (
            not str(source.get("snippet") or "").strip()
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            return "source lacks a grounded snippet or content hash"
    return None


def run(output: Path | None = None) -> dict[str, object]:
    previous_home = os.environ.get("DOCMANCER_HOME")
    errors: list[str] = []
    results: list[dict[str, object]] = []
    historical_paths = _historical_paths()
    try:
        with TemporaryDirectory(prefix="docatlas-self-host-") as raw_tmp:
            tmp = Path(raw_tmp)
            os.environ["DOCMANCER_HOME"] = str(tmp / "home")
            config = DocmancerConfig()
            config.index.db_path = str(tmp / "docmancer.db")
            config.index.extracted_dir = str(tmp / "extracted")
            service = LibraryDocsService(
                config=config,
                registry=LibraryRegistry(config.index.db_path),
                agent=DocmancerAgent(config=config),
                job_tracker=DocsJobTracker(),
            )

            preflight_question = GOLD_CASES[0].question
            preflight = handle_context_tool(
                "get_docs_context",
                {
                    "question": preflight_question,
                    "project_path": str(REPO_ROOT),
                    "mode": "project",
                },
                service,
            )
            preflight_action = (
                (preflight or {}).get("recommended_next_action")
                or (preflight or {}).get("next_action")
                or {}
            )
            action_patch = preflight_action.get("arguments_patch") or {}
            if action_patch.get("action") != "sync_project_docs":
                errors.append(f"pre-sync query did not recommend sync_project_docs: {preflight!r}")

            sync = service.sync_project_docs(str(REPO_ROOT), with_vectors=False)
            if getattr(sync, "status", None) != "success":
                errors.append(f"self-host sync status={getattr(sync, 'status', None)!r}")

            for index, case in enumerate(GOLD_CASES, 1):
                question = case.question
                payload = handle_context_tool(
                    "get_docs_context",
                    {
                        "question": question,
                        "project_path": str(REPO_ROOT),
                        "mode": "project",
                        "delivery_strategy": "bounded_direct",
                        "prepare_project_docs": False,
                    },
                    service,
                )
                if payload is None:
                    errors.append(f"{index:02d}: no payload: {question}")
                    continue
                status = str(payload.get("status") or "")
                paths = _source_paths(payload)
                contract_error = _validate_context_result(payload)
                visible = json.dumps(payload.get("sources") or (), ensure_ascii=False).casefold()
                fact_checks = {
                    fragment: fragment.casefold() in visible
                    for fragment in case.required_fragments
                }
                top3 = paths[:3]
                relevant_ranks = [rank for rank, path in enumerate(paths, 1) if path in case.relevant_paths]
                reciprocal_rank = 1.0 / relevant_ranks[0] if relevant_ranks else 0.0
                distractors = [
                    path for path in top3
                    if path.startswith((".hermes/plans/", "roadmap/"))
                    and not any(token in question.casefold() for token in ("plan", "roadmap", "status"))
                ]
                checks = {
                    "status_ok": status == "ok",
                    "source_backed": bool(paths),
                    "context_contract": contract_error is None,
                    "relevant_source_in_top3": any(path in case.relevant_paths for path in top3),
                    "required_facts": all(fact_checks.values()),
                    "no_top3_distractor": not distractors,
                }
                result = {
                    "case_id": f"live_{index:02d}",
                    "surface_case_id": case.surface_case_id,
                    "question": question,
                    "expected": {
                        "relevant_paths": list(case.relevant_paths),
                        "required_fragments": list(case.required_fragments),
                    },
                    "observed": {
                        "status": status,
                        "kind": payload.get("kind"),
                        "support_status": payload.get("support_status"),
                        "answer_supported": payload.get("answer_supported"),
                        "query_coverage": _query_coverage(payload),
                    },
                    "ranking": {
                        "top3_paths": list(top3),
                        "first_relevant_rank": relevant_ranks[0] if relevant_ranks else None,
                        "reciprocal_rank": reciprocal_rank,
                        "distractor_paths": distractors,
                        "historical_paths": [path for path in top3 if path in historical_paths],
                    },
                    "fact_checks": fact_checks,
                    "citations": _citations(payload),
                    "checks": checks,
                    "decision_hash": payload.get("decision_hash"),
                    "passed": all(checks.values()),
                }
                results.append(result)
                if not result["passed"]:
                    errors.append(f"{index:02d}: failed checks={checks!r}: {question}")
                if paths and paths[0].startswith((".hermes/plans/", "roadmap/")) and not any(
                    token in question.casefold() for token in ("plan", "roadmap", "status")
                ):
                    errors.append(f"{index:02d}: operational query ranked a plan first: {paths[0]!r}: {question}")
            for question in NEGATIVE_CASES:
                payload = handle_context_tool(
                    "get_docs_context",
                    {"question": question, "project_path": str(REPO_ROOT), "mode": "project"},
                    service,
                )
                if not payload or payload.get("status") != "insufficient_evidence":
                    errors.append(f"negative query did not fail closed: {question}: {payload!r}")
                results.append({
                    "case_id": "negative_lunar_quantum",
                    "question": question,
                    "expected": {"status": "insufficient_evidence"},
                    "observed": {
                        "status": (payload or {}).get("status"),
                        "kind": (payload or {}).get("kind"),
                        "support_status": (payload or {}).get("support_status"),
                        "answer_supported": (payload or {}).get("answer_supported"),
                    },
                    "checks": {"correct_abstention": bool(payload and payload.get("status") == "insufficient_evidence")},
                    "passed": bool(payload and payload.get("status") == "insufficient_evidence"),
                })
    finally:
        if previous_home is None:
            os.environ.pop("DOCMANCER_HOME", None)
        else:
            os.environ["DOCMANCER_HOME"] = previous_home

    positives = results[:len(GOLD_CASES)]
    source_count = sum(len(row.get("ranking", {}).get("top3_paths", ())) for row in positives)
    distractor_count = sum(len(row.get("ranking", {}).get("distractor_paths", ())) for row in positives)
    historical_count = sum(len(row.get("ranking", {}).get("historical_paths", ())) for row in positives)
    report: dict[str, object] = {
        "schema_version": "project-answer-quality-live-result-v1",
        "run_mode": "live_self_host",
        "provider_free": True,
        "case_count": len(results),
        "passed_count": sum(bool(row.get("passed")) for row in results),
        "metrics": {
            "top3_relevance": sum(bool(row.get("checks", {}).get("relevant_source_in_top3")) for row in positives) / max(len(positives), 1),
            "mrr": sum(float(row.get("ranking", {}).get("reciprocal_rank", 0.0)) for row in positives) / max(len(positives), 1),
            "distractor_rate": distractor_count / max(source_count, 1),
            "historical_source_rate": historical_count / max(source_count, 1),
            "mean_query_coverage": sum(float(row.get("observed", {}).get("query_coverage", 0.0)) for row in positives) / max(len(positives), 1),
            "false_abstention_count": sum(not bool(row.get("checks", {}).get("status_ok")) for row in positives),
        },
        "verdict": "FAIL" if errors else "PASS",
        "errors": errors,
        "results": results,
    }
    digest_payload = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    report["deterministic_result_digest"] = hashlib.sha256(digest_payload.encode()).hexdigest()
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run(args.output)
    if report["verdict"] == "PASS":
        print(
            f"PASS: {len(GOLD_CASES)} current-repository questions and "
            f"{len(NEGATIVE_CASES)} negative query close the unpatched context-first production path"
        )
        return 0
    print("FAIL: Project Docs self-hosting closure")
    for error in report["errors"]:
        print(f"- {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
