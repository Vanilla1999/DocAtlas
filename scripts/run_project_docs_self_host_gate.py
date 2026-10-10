#!/usr/bin/env python3
"""Provider-free current-repository gate for the context-first Docs pipeline.

The gate indexes this repository into an isolated temporary SQLite store and then
runs canonical Project Docs questions through the unpatched public
``get_docs_context`` MCP handler. It proves the current production chain:

question -> explicit retrieval lineage -> current source qualification -> final visible context.

The immutable historical corpus retains its original questions plus two
premise/condition cases that depend on the clear-index source of truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections.abc import Mapping
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

# Preserve direct `python scripts/run_project_docs_self_host_gate.py` as well as
# imported evaluator entrypoints; the mirrored checkout is never an import root.
_SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(_SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_ROOT))

from scripts._project_docs_self_host_fixture import self_host_fixture
from eval.project_context_quality.legacy_fact_acceptance import capture_legacy_evidence

import yaml

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.mcp.docs_server import call_docs_tool_payload
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import DocsJobTracker, LibraryDocsService
from docmancer.docs.application import docs_context_projection
from docmancer.docs.application.model_visible_projection import (
    DOCS_CONTEXT_SOURCE_FIELDS,
    _source_digest,
    estimate_projection_tokens,
)
from docmancer.docs.interfaces.mcp import context_tools


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_LOCK = json.loads(
    (REPO_ROOT / "eval/project_context_quality/protocol.lock.json").read_text(
        encoding="utf-8"
    )
)
PROTOCOL_THRESHOLDS = dict(PROTOCOL_LOCK.get("thresholds") or {})

@dataclass(frozen=True, slots=True)
class LiveCase:
    question: str
    relevant_paths: tuple[str, ...]
    required_fragments: tuple[str, ...] = ()
    surface_case_id: int | None = None
    expected_kind: str | None = None
    required_facts_by_path: tuple[tuple[str, str], ...] = ()
    forbidden_source_prefixes: tuple[str, ...] = ()
    forbidden_answer_fragments: tuple[str, ...] = ()
    lookup_queries: tuple[str, ...] = ()
    minimum_lookup_coverage: int = 0
    allowed_paths: tuple[str, ...] = ()
    expected_public_query_ids: tuple[str, ...] = ()
    case_id: str | None = None
    scope: str = "project"
    required_fact_groups: tuple[tuple[tuple[str, str], ...], ...] = ()


def _load_gold_cases() -> tuple[LiveCase, ...]:
    payload = json.loads(
        (REPO_ROOT / "eval/project_context_quality/cases.json").read_text(
            encoding="utf-8"
        )
    )
    return tuple(
        LiveCase(
            question=str(case["question"]),
            relevant_paths=tuple(str(value) for value in case.get("sources") or ()),
            expected_kind=str(case["expected_kind"]),
            required_facts_by_path=tuple(
                (str(item["source"]), str(item["text"]))
                for item in case.get("required_facts") or ()
            ),
            forbidden_source_prefixes=tuple(
                str(value) for value in case.get("forbidden_source_prefixes") or ()
            ),
            forbidden_answer_fragments=tuple(
                str(value) for value in case.get("forbidden_answer_fragments") or ()
            ),
            lookup_queries=tuple(
                str(value) for value in case.get("lookup_queries") or ()
            ),
            minimum_lookup_coverage=int(case.get("minimum_lookup_coverage") or 0),
            allowed_paths=tuple(
                str(value) for value in case.get("allowed_paths") or case.get("sources") or ()
            ),
            expected_public_query_ids=tuple(
                str(value) for value in case.get("expected_public_query_ids") or ()
            ),
        )
        for case in payload.get("cases") or () if case.get("intent")
    )


GOLD_CASES = _load_gold_cases()


def _load_negative_cases() -> tuple[str, ...]:
    payload = json.loads(
        (REPO_ROOT / "eval/project_context_quality/cases.json").read_text(
            encoding="utf-8"
        )
    )
    return tuple(
        str(case["question"])
        for case in payload.get("cases") or () if not case.get("intent")
    )


NEGATIVE_CASES = _load_negative_cases()


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
    covered = {
        str(value) for value in payload.get("covered_query_ids") or () if value
    }
    missing = {
        str(value) for value in payload.get("missing_query_ids") or () if value
    }
    if covered or missing:
        return len(covered) / len(covered | missing)
    value = payload.get("query_coverage")
    if value is None and payload.get("kind") == "docs_answer" and payload.get("answer_supported") is True:
        return float(payload.get("mandatory_coverage") or 1.0)
    if value in {"full", "complete"}:
        return 1.0
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _validate_context_result(payload: dict[str, object]) -> str | None:
    payload = {key: value for key, value in payload.items() if key != "diagnostics"}
    kind = str(payload.get("kind") or "")
    if kind == "docs_answer":
        if (
            payload.get("answer_supported") is not True
            or payload.get("answer_available") is not True
            or payload.get("edit_ready") is not False
        ):
            return "docs_answer lacks strict answer support"
    elif kind == "docs_context":
        if not (
            payload.get("context_status") == "ready"
            and payload.get("answer_supported") is False
            and payload.get("answer_available") is False
            and payload.get("edit_ready") is False
            and payload.get("answer_policy") == "cite_only"
            and isinstance(payload.get("facets"), list)
            and not payload.get("answer")
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


def _citation_integrity(payload: dict[str, object], snapshot: dict[str, dict]) -> bool:
    answer_ids = {str(value) for value in payload.get("answer_evidence_ids") or ()}
    source_ids: set[str] = set()
    for source in payload.get("sources") or ():
        if not isinstance(source, dict):
            return False
        evidence_id = str(source.get("evidence_id") or "")
        path = str(source.get("path_or_url") or "")
        snippet = str(source.get("snippet") or "").strip()
        bound = snapshot.get(evidence_id) or {}
        if (
            evidence_id in source_ids
            or bound.get("projected_source") != source
            or source.get("content_sha256") != _source_digest(bound.get("source") or {})
        ):
            return False
        target = (REPO_ROOT / path).resolve()
        if (
            not evidence_id
            or not path
            or not target.is_relative_to(REPO_ROOT)
            or not target.is_file()
            or not snippet
            or snippet not in target.read_text(encoding="utf-8", errors="replace")
        ):
            return False
        source_ids.add(evidence_id)
    facet_ids = {
        str(value) for facet in payload.get("facets") or () if isinstance(facet, dict)
        for value in facet.get("evidence_ids") or ()
    }
    return (
        answer_ids.issubset(source_ids) and facet_ids.issubset(source_ids)
        and (payload.get("kind") != "docs_answer" or bool(answer_ids))
    )


def _threshold_failures(metrics: dict[str, object], case_count: int) -> list[str]:
    failures: list[str] = []
    if int(metrics["false_supported_count"]):
        failures.append("false-supported answers must be zero")
    if int(metrics["operational_contamination_count"]):
        failures.append("forbidden source contamination must be zero")
    if int(metrics["useful_result_count"]) < int(PROTOCOL_THRESHOLDS["live_useful_result_min"]):
        failures.append("useful onboarding context is below the frozen minimum")
    if int(metrics["top1_fact_bearing_count"]) < int(PROTOCOL_THRESHOLDS["live_top1_fact_bearing_min"]):
        failures.append("Top-1 fact-bearing context is below the frozen minimum")
    if int(metrics["top3_relevant_count"]) < int(PROTOCOL_THRESHOLDS["live_top3_relevant_min"]):
        failures.append("relevant context is missing from Top-3 too often")
    if int(metrics["original_query_covered_count"]) < int(PROTOCOL_THRESHOLDS["original_query_coverage_min"]):
        failures.append("direct or audited-derived original coverage is below the frozen minimum")
    for name in (
        "metadata_only_evidence_count", "packs_contamination_count",
        "docs_analysis_contamination_count", "false_docs_answer_count",
    ):
        if int(metrics[name]):
            failures.append(f"{name} must be zero")
    return failures


def _is_metadata_only_source(source: object) -> bool:
    if not isinstance(source, dict):
        return True
    snippet = str(source.get("snippet") or "")
    for line in snippet.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or re.fullmatch(r"[|:\- ]+", stripped):
            continue
        without_links = re.sub(r"\[[^]]+\]\([^)]*\)", "", stripped)
        if len(re.findall(r"[A-Za-zА-Яа-яЁё0-9_.-]+", without_links)) >= 3:
            return False
    return True



def _delivery_observation(stage: str, result: object, args: tuple, kwargs: dict) -> dict:
    """Summarize actual returned DTO fields; never read or emit source bodies."""
    missing = object()

    def value(obj, key, default=None):
        return obj.get(key, default) if isinstance(obj, Mapping) else getattr(obj, key, default)

    def scalar(item):
        if item is None or type(item) in (bool, int, float):
            return item
        if isinstance(item, str):
            return item if len(item) <= 512 else {
                "characters": len(item), "sha256": hashlib.sha256(item.encode("utf-8")).hexdigest(),
            }
        return {"type": type(item).__name__}

    def fields(obj, names):
        pairs = ((key, value(obj, key, missing)) for key in names)
        return {key: scalar(item) for key, item in pairs if item is not missing}

    def sequence(items, render=scalar):
        if items is None:
            return None
        if not isinstance(items, (list, tuple)):
            return {"type": type(items).__name__}
        return {"count": len(items), "items": [render(item) for item in items[:32]],
                "omitted": max(0, len(items) - 32)}

    def window(item):
        metadata = value(item, "metadata")
        metadata = metadata if isinstance(metadata, Mapping) else {}
        matches = value(item, "retrieval_query_matches", metadata.get("retrieval_query_matches"))
        row = {}
        for key in (
            "source", "chunk_index", "stable_chunk_id", "parent_logical_id", "path",
            "project_identity", "doc_scope", "module_path", "source_class", "stale",
            "lifecycle_status", "freshness", "char_start", "char_end", "display_content_hash",
            "generation_id", "project_doc_catalog_entry_hash", "project_doc_content_hash",
        ):
            observed = value(item, key, metadata.get(key, missing))
            if observed is not missing:
                row[key] = scalar(observed)
        row["qualified_query_ids"] = sequence([
            str(key) for key, trace in matches.items()
            if isinstance(trace, Mapping) and trace.get("qualified") is True
        ]) if isinstance(matches, Mapping) else scalar(matches)
        return row

    scope_fields = (
        "schema_version", "query", "project_path", "project_identity",
        "requested_scope", "requested_module", "requested_module_path",
        "doc_scope", "module_path", "evidence_path",
    )
    state_fields = (
        "status", "reason", "reason_code", "mode", "mode_requested", "mode_selected",
        "context_available", "answer_available", "answer_supported", "support_status",
        "requires_confirmation", "confirmation_reason", "stale_before_refresh",
    )

    def packet(obj):
        observed = fields(obj, state_fields)
        observed["delivery_decision"] = fields(value(obj, "delivery_decision"), ("deliverable", "reason_code"))
        observed["context_windows"] = sequence(value(obj, "context_pack"), window)
        observed["result_windows"] = sequence(value(obj, "results"), window)
        observed["request_scope"] = fields(value(obj, "request_scope"), scope_fields)
        requirements = value(value(obj, "requirements"), "requirements")
        observed["requirements"] = sequence(requirements, lambda row: fields(row, (
            "requirement_id", "kind", "value", "mandatory", "public_provenance", "proof_role",
        )))
        support = value(obj, "support_decision")
        observed["support_decision"] = {
            **fields(support, ("answer_supported", "support_status", "reason_code")),
            **{key: sequence(value(support, key)) for key in (
                "missing_requirement_ids", "mandatory_requirement_ids", "satisfied_requirement_ids",
            )},
        }
        return observed

    question = kwargs.get("query", kwargs.get("question",
        args[0] if stage == "unified" and args else args[1] if len(args) > 1 else None))
    root = kwargs.get("project_path", args[0] if stage != "unified" and args else None)
    observation = {
        "stage": stage,
        "request": {
            "question": scalar(question), "project_path": scalar(root),
            **fields(kwargs, ("scope", "module", "module_path", "evidence_path",
                              "limit", "tokens", "expand", "retain_found_windows",
                              "allow_network", "prepare_project_docs")),
            "lookup_queries": sequence(kwargs.get("lookup_queries")),
        },
        "result": packet(result),
    }
    for key in ("project_docs", "dependency_docs"):
        nested = value(result, key, missing)
        if nested is not missing:
            observation[key] = None if nested is None else packet(nested)
    lanes = value(result, "lanes")
    if isinstance(lanes, Mapping):
        observation["lanes"] = {key: fields(lanes[key], (
            "status", "reason_code", "source_count", "requires_confirmation",
        )) for key in ("project", "dependency", "library") if key in lanes}
    observation["routing"] = fields(value(result, "routing"), (
        "reason_code", "project_path_used", "dependency_detected", "delegated_mode",
    ))
    diagnostics = value(result, "diagnostics")
    if not isinstance(diagnostics, Mapping):
        diagnostics = value(value(result, "ingestion_diagnostics"), "project", {})
    observation["project_trust_decision"] = fields(value(diagnostics, "trust_decision"), (
        "reason", "confidence", "answer_available", "passed_relevance_gate",
    ))
    stages = value(value(diagnostics, "retrieval_routing"), "stages")
    if isinstance(stages, Mapping):
        observation["routing_stages"] = {key: fields(stages[key], (
            "status", "reason", "item_count", "observed_item_count",
            "budget_projection_bytes", "observed_budget_projection_bytes", "budget_exceeded", "error_type",
        )) for key in ("project_docs", "dependency_docs", "source_evidence", "repo_map", "code_graph")
            if key in stages}
    return observation

def _call_with_snapshot(arguments: dict, service: LibraryDocsService, *, trace_enabled: bool = True) -> tuple[dict | None, dict]:
    """Observe the public call without replaying retrieval or changing its result."""
    from docmancer.docs.application.query_trace import query_trace
    raw_results: list[object] = []
    qualified_sources: list[dict] = []
    snapshots: list[dict] = []
    diagnostics: list[dict] = []
    component_bindings: list[dict] = []
    app = getattr(service, "unified_context", service)
    retrieve = app.get_docs_context
    # Downstream diagnostic stages are optional capabilities of the observed app.
    facade = getattr(app, "service", None)
    member_facade = getattr(getattr(facade, "project_context", None), "facade", None)
    project_read = getattr(facade, "get_project_context", None)
    member_read = getattr(member_facade, "get_project_docs", None)
    delivery_observations: list[dict] = []
    delivery_counts: dict[str, int] = {}
    select = docs_context_projection.context_selection_decision
    validate = context_tools.validate_model_visible_projection
    coverage = docs_context_projection.component_coverage_decision

    def capture_coverage(contract, assignments, sources, **kwargs):
        contract, assignments, sources = tuple(contract), tuple(assignments), tuple(sources)
        decision = coverage(contract, assignments, sources, **kwargs)
        if not trace_enabled:
            return decision
        component_bindings.clear()
        for source in sources:
            original = source.get("_qualification_candidate") or {}
            source_ids = {original.get(key) for key in ("stable_id", "stable_chunk_id", "evidence_id") if original.get(key)}
            source_ids.add(source.get("evidence_id"))
            for component_id, runtime_evidence_id in getattr(decision, "_component_evidence", ()):
                if runtime_evidence_id not in source_ids:
                    continue
                component_bindings.append({
                    "component_id": component_id,
                    "evidence_id": source.get("evidence_id"),
                    "path_or_url": source.get("path_or_url"),
                    "snippet_sha256": hashlib.sha256(str(source.get("snippet") or "").encode()).hexdigest(),
                    "runtime_evidence_ids": [runtime_evidence_id],
                })
        return decision

    def capture_delivery(stage, result, args, kwargs):
        delivery_counts[stage] = delivery_counts.get(stage, 0) + 1
        if not trace_enabled:
            return
        if len(delivery_observations) < 32:
            try:
                delivery_observations.append(_delivery_observation(stage, result, args, kwargs))
            except Exception as exc:
                delivery_observations.append({"stage": stage, "observation_error": type(exc).__name__})

    def delivery_observer(read, stage):
        @wraps(read)
        def capture_read(*args, **kwargs):
            result = read(*args, **kwargs)
            capture_delivery(stage, result, args, kwargs)
            return result
        return capture_read

    def capture_result(*args, **kwargs):
        result = retrieve(*args, **kwargs)
        raw_results.append(result)
        capture_delivery("unified", result, args, kwargs)
        return result

    def capture_selection(sources, requested_query_ids):
        sources = list(sources)
        decision = select(sources, requested_query_ids)
        qualified_sources[:] = deepcopy(sources)
        return decision

    def capture_validation(payload, *, snapshot, **kwargs):
        snapshots.append(deepcopy(snapshot))
        return validate(payload, snapshot=snapshot, **kwargs)

    missing_observer = object()
    previous_observer = getattr(service, "_same_call_diagnostics_observer", missing_observer)
    if trace_enabled:
        service._same_call_diagnostics_observer = lambda value: diagnostics.append(deepcopy(value))
    try:
        with (
        query_trace(trace_enabled),
        patch.object(app, "get_docs_context", capture_result),
        patch.object(facade, "get_project_context", delivery_observer(project_read, "project_context"))
            if callable(project_read) else nullcontext(),
        patch.object(member_facade, "get_project_docs", delivery_observer(member_read, "member_read"))
            if callable(member_read) else nullcontext(),
        patch.object(docs_context_projection, "context_selection_decision", capture_selection),
        patch.object(context_tools, "validate_model_visible_projection", capture_validation),
        patch.object(docs_context_projection, "component_coverage_decision", capture_coverage),
        ):
            payload = call_docs_tool_payload("get_docs_context", arguments, service)
    finally:
        if trace_enabled:
            if previous_observer is missing_observer:
                del service._same_call_diagnostics_observer
            else:
                service._same_call_diagnostics_observer = previous_observer
    if isinstance(payload, dict) and diagnostics:
        diagnostics[-1]["component_evidence_bindings"] = component_bindings
        diagnostics[-1]["observer_counts"] = {"retrieval_calls": len(raw_results), "validation_calls": len(snapshots)}
        diagnostics[-1]["delivery_observations"] = {
            "return_counts": delivery_counts, "returns": delivery_observations,
            "omitted": max(0, sum(delivery_counts.values()) - len(delivery_observations)),
        }
        payload = {**payload, "diagnostics": diagnostics[-1]}
    if len(raw_results) != 1 or len(snapshots) != 1:
        return payload, {}
    snapshot = snapshots[0]
    for bound in snapshot.values():
        bound.pop("qualification", None)
    for source in qualified_sources:
        bound = snapshot.get(str(source.get("evidence_id") or ""))
        public_source = {
            key: value for key, value in source.items()
            if key in DOCS_CONTEXT_SOURCE_FIELDS
        }
        # Optional locators are attached after selection, without altering its
        # evidence. Bind qualification to the exact evidence-bearing fields;
        # _coverage_attribution still checks the whole final source (URI included).
        projected_evidence = {
            key: value for key, value in (bound or {}).get("projected_source", {}).items()
            if key != "source_uri"
        }
        if bound and public_source == projected_evidence:
            bound["qualification"] = source
    return payload, snapshot


def _coverage_attribution(snapshot: dict, payload: dict) -> set[str]:
    kinds: set[str] = set()
    if "query-original" not in (payload.get("covered_query_ids") or ()):
        return kinds
    for source in payload.get("sources") or ():
        if not isinstance(source, dict):
            continue
        bound = snapshot.get(str(source.get("evidence_id") or "")) or {}
        if bound.get("projected_source") != source:
            continue
        trace = ((bound.get("qualification") or {}).get("retrieval_query_matches") or {}).get("query-original") or {}
        if trace.get("qualified") is True:
            kinds.update(str(value) for value in trace.get("coverage_kinds") or (trace.get("coverage_kind"),))
    return kinds & {"direct", "derived"}


def _packs_contamination(question: str, payload: dict) -> bool:
    """Detect Docs→Packs command substitution, not a mention of another subsystem.

    Relevance and required Docs facts are checked separately. A project-map
    paragraph mentioning the Packs gateway can be irrelevant without claiming
    that Packs is the Docs server. Paths and titles alone never establish this
    factual substitution.
    """
    explicit_docs = re.search(r"\bdocs\b|get_docs_context|prepare_docs|docs_status", question, re.I)
    requested_packs = re.search(r"\bpacks?\b", question, re.I)
    excluded_packs = re.search(r"\b(?:not|without|excluding)\s+(?:the\s+)?packs?\b", question, re.I)
    if not explicit_docs or (requested_packs and not excluded_packs):
        return False
    pack_command = re.compile(
        r"\b(?:doc-atlas|docmancer)\s+(?:mcp\s+packs-serve|install-pack)\b"
        r"|\bdocmancer_(?:search_tools|call_tool)\s*\(", re.I,
    )
    snippets = [str(source.get("snippet") or "") for source in payload.get("sources") or ()
                if isinstance(source, dict)]
    if payload.get("answer"):
        snippets.append(str(payload["answer"]))
    for snippet in snippets:
        for line in snippet.splitlines():
            for command in pack_command.finditer(line):
                # Negation must govern this exact Packs occurrence. A correct
                # Docs command elsewhere cannot excuse a Packs substitution.
                prefix = line[:command.start()]
                if re.search(r"\b(?:do not|don't|never|must not|not)\s+(?:run\s+|use\s+)?[` ]*$", prefix, re.I):
                    continue
                return True
    return False


def _safe_abstention(payload: Mapping) -> bool:
    return (
        payload.get("status") == "insufficient_evidence"
        and payload.get("kind") != "docs_answer"
        and all(payload.get(flag) is None or payload.get(flag) is False for flag in (
            "answer_supported", "answer_available", "edit_ready", "mutation_ready",
        ))
    )


def run(
    output: Path | None = None,
    *,
    cases: tuple[LiveCase, ...] = GOLD_CASES,
    negative_cases: tuple[str | LiveCase, ...] = NEGATIVE_CASES,
) -> dict[str, object]:
    errors: list[str] = []
    results: list[dict[str, object]] = []
    historical_paths = _historical_paths()
    with self_host_fixture(REPO_ROOT) as fixture:
        service = fixture.service
        setup_provenance = fixture.provenance
        preflight_question = cases[0].question if cases else "How do Project Docs work?"
        preflight = call_docs_tool_payload(
            "get_docs_context",
            {
                "question": preflight_question,
                "project_path": str(fixture.root),
                "scope": cases[0].scope if cases else "project",
            },
            service,
        )
        if not fixture.verify_cold_read(preflight):
            errors.append(f"pre-sync query did not preserve the cold read boundary: {preflight!r}")
        else:
            fixture.prepare()

            for index, case in enumerate(cases, 1):
                question = case.question
                arguments = {
                    "question": question,
                    "project_path": str(fixture.root),
                    **({"lookup_queries": list(case.lookup_queries)} if case.lookup_queries else {}),
                    "scope": case.scope,
                }
                payload, snapshot = _call_with_snapshot(arguments, service)
                if not isinstance(payload, Mapping):
                    errors.append(f"{index:02d}: missing or non-mapping payload={payload!r}: {question}")
                    payload = {}
                else:
                    payload = dict(payload)
                status = str(payload.get("status") or "")
                observed_kind = str(payload.get("kind") or "")
                paths = _source_paths(payload)
                contract_error = (
                    None if case.expected_kind == "insufficient_evidence"
                    else _validate_context_result(payload)
                )
                relevant_sources = [
                    row for row in payload.get("sources") or ()
                    if isinstance(row, dict)
                    and str(row.get("path_or_url") or "") in case.relevant_paths
                ]
                visible = "\n".join(str(row.get("snippet") or "") for row in relevant_sources).casefold()
                fact_checks = {
                    fragment: fragment.casefold() in visible
                    for fragment in case.required_fragments
                }
                path_fact_checks = {
                    f"{path}:{fragment}": any(
                        str(row.get("path_or_url") or "") == path
                        and fragment.casefold() in str(row.get("snippet") or "").casefold()
                        for row in payload.get("sources") or () if isinstance(row, dict)
                    )
                    for path, fragment in case.required_facts_by_path
                }
                answer_text = str(payload.get("answer") or "").casefold()
                answer_fact_checks = {
                    fragment: fragment.casefold() in answer_text
                    for fragment in case.required_fragments
                }
                answer_path_fact_checks = {
                    f"{path}:{fragment}": fragment.casefold() in answer_text
                    for path, fragment in case.required_facts_by_path
                }
                group_fact_checks = {
                    f"fact-group-{index}": any(
                        str(row.get("path_or_url") or "") == path
                        and fragment.casefold() in str(row.get("snippet") or "").casefold()
                        for path, fragment in alternatives
                        for row in payload.get("sources") or () if isinstance(row, dict)
                    )
                    for index, alternatives in enumerate(case.required_fact_groups, 1)
                }
                answer_group_fact_checks = {
                    f"fact-group-{index}": any(
                        fragment.casefold() in answer_text for _, fragment in alternatives
                    )
                    for index, alternatives in enumerate(case.required_fact_groups, 1)
                }
                top3 = paths[:3]
                allowed_paths = set(case.allowed_paths or case.relevant_paths)
                unexpected_paths = [path for path in paths if path not in allowed_paths]
                relevant_ranks = [rank for rank, path in enumerate(paths, 1) if path in case.relevant_paths]
                reciprocal_rank = 1.0 / relevant_ranks[0] if relevant_ranks else 0.0
                distractors = [
                    path for path in paths
                    if any(path.startswith(prefix) for prefix in case.forbidden_source_prefixes)
                ]
                forbidden_visible = json.dumps(payload, ensure_ascii=False).casefold()
                covered_lookup_ids = {
                    str(value) for value in payload.get("covered_query_ids") or ()
                    if str(value).startswith("query-lookup-")
                }
                original_query_covered = "query-original" in {
                    str(value) for value in payload.get("covered_query_ids") or ()
                }
                expected_public_ids = set(case.expected_public_query_ids) or {
                    "query-original",
                    *(f"query-lookup-{item}" for item in range(1, len(case.lookup_queries) + 1)),
                }
                actual_public_ids = {
                    str(value) for value in (
                        *(payload.get("covered_query_ids") or ()),
                        *(payload.get("missing_query_ids") or ()),
                    )
                }
                covered_ids = set(payload.get("covered_query_ids") or ())
                missing_ids = set(payload.get("missing_query_ids") or ())
                attribution = _coverage_attribution(snapshot, payload)
                first_source = (payload.get("sources") or [{}])[0]
                top1_path = str(first_source.get("path_or_url") or "") if isinstance(first_source, dict) else ""
                top1_visible = str(first_source.get("snippet") or "").casefold() if isinstance(first_source, dict) else ""
                top1_fact_bearing = any(
                    path == top1_path and fragment.casefold() in top1_visible
                    for path, fragment in case.required_facts_by_path
                ) or bool(top1_path in case.relevant_paths and any(
                    fragment.casefold() in top1_visible for fragment in case.required_fragments
                ))
                top1_fact_bearing = top1_fact_bearing or any(
                    path == top1_path and fragment.casefold() in top1_visible
                    for alternatives in case.required_fact_groups
                    for path, fragment in alternatives
                )
                packs_contamination = _packs_contamination(question, payload)
                metadata_only_sources = [
                    str(row.get("path_or_url") or "")
                    for row in payload.get("sources") or () if isinstance(row, dict)
                    and _is_metadata_only_source(row)
                ]
                if case.expected_kind == "insufficient_evidence":
                    checks = {
                        "correct_abstention": _safe_abstention(payload),
                        "not_false_supported": payload.get("answer_supported") is not True,
                        "no_answer_or_edit_authorization": _safe_abstention(payload),
                    }
                else:
                    checks = {
                        "status_ok": status == "ok",
                        "kind_matches": case.expected_kind is None or observed_kind == case.expected_kind,
                        "source_backed": bool(paths),
                        "context_contract": contract_error is None,
                        "relevant_source_in_top3": any(path in case.relevant_paths for path in top3),
                        "required_facts": all((*fact_checks.values(), *path_fact_checks.values(), *group_fact_checks.values())),
                        "answer_contains_required_facts": (
                            observed_kind != "docs_answer"
                            or all((*answer_fact_checks.values(), *answer_path_fact_checks.values(), *answer_group_fact_checks.values()))
                        ),
                        "citation_integrity": _citation_integrity(payload, snapshot),
                        "no_packs_contamination": not packs_contamination,
                        "no_forbidden_source": not distractors,
                        "only_allowed_sources": not unexpected_paths,
                        "no_forbidden_answer_fragment": not any(
                            fragment.casefold() in forbidden_visible
                            for fragment in case.forbidden_answer_fragments
                        ),
                        "minimum_lookup_coverage": (
                            len(covered_lookup_ids) >= case.minimum_lookup_coverage
                        ),
                        "public_query_inventory": (
                            expected_public_ids == actual_public_ids
                            and not covered_ids.intersection(missing_ids)
                            and isinstance(payload.get("covered_query_ids"), list)
                            and isinstance(payload.get("missing_query_ids"), list)
                            and len(covered_ids) == len(payload["covered_query_ids"])
                            and len(missing_ids) == len(payload["missing_query_ids"])
                        ),
                        "original_coverage_attribution": not original_query_covered or bool(attribution),
                    }
                score = round(10 * sum(checks.values()) / max(len(checks), 1), 2)
                result = {
                    "case_id": case.case_id or f"live_{index:02d}",
                    "scope": case.scope,
                    "surface_case_id": case.surface_case_id,
                    "question": question,
                    "expected": {
                        "kind": case.expected_kind,
                        "relevant_paths": list(case.relevant_paths),
                        "required_fragments": list(case.required_fragments),
                        "minimum_lookup_coverage": case.minimum_lookup_coverage,
                        "public_query_ids": sorted(expected_public_ids),
                        "required_fact_groups": case.required_fact_groups,
                    },
                    "observed": {
                        "status": status,
                        "kind": payload.get("kind"),
                        "support_status": payload.get("support_status"),
                        "answer_supported": payload.get("answer_supported"),
                        "query_coverage": _query_coverage(payload),
                        "covered_lookup_ids": sorted(covered_lookup_ids),
                        "original_query_covered": original_query_covered and bool(attribution),
                        "coverage_attribution": sorted(attribution),
                        "packs_contamination": packs_contamination,
                        "public_utf8_bytes": len(json.dumps({key: value for key, value in payload.items() if key != "diagnostics"}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")),
                        "actual_estimated_tokens": estimate_projection_tokens({key: value for key, value in payload.items() if key != "diagnostics"}),
                        "metadata_only_sources": metadata_only_sources,
                    },
                    "ranking": {
                        "top3_paths": list(top3),
                        "first_relevant_rank": relevant_ranks[0] if relevant_ranks else None,
                        "reciprocal_rank": reciprocal_rank,
                        "distractor_paths": distractors,
                        "unexpected_paths": unexpected_paths,
                        "historical_paths": [path for path in paths if path in historical_paths],
                    },
                    "fact_checks": fact_checks,
                    "path_fact_checks": path_fact_checks,
                    "group_fact_checks": group_fact_checks,
                    "answer_group_fact_checks": answer_group_fact_checks,
                    "top1_fact_bearing": top1_fact_bearing,
                    "answer_fact_checks": answer_fact_checks,
                    "citations": _citations(payload),
                    "legacy_fact_evidence": capture_legacy_evidence(arguments, payload, snapshot),
                    "payload": payload,
                    "checks": checks,
                    "decision_hash": payload.get("decision_hash"),
                    "passed": all(checks.values()),
                    "score": score,
                }
                results.append(result)
                if not result["passed"]:
                    failed_checks = [name for name, passed in checks.items() if not passed]
                    errors.append(f"{index:02d}: failed positive checks={failed_checks!r}: {question}")
                if (
                    case.expected_kind not in {None, "docs_answer"}
                    and payload.get("answer_supported") is True
                ):
                    errors.append(f"{index:02d}: false-supported answer: {question}")
                if distractors:
                    errors.append(f"{index:02d}: forbidden source contamination={distractors!r}: {question}")
                if case.expected_kind == "insufficient_evidence" and status != "insufficient_evidence":
                    errors.append(f"{index:02d}: nonexistent fact did not abstain: {question}")
                if paths and paths[0].startswith((".hermes/plans/", "roadmap/")) and not any(
                    token in question.casefold() for token in ("plan", "roadmap", "status")
                ):
                    errors.append(f"{index:02d}: operational query ranked a plan first: {paths[0]!r}: {question}")
            for index, negative in enumerate(negative_cases, 1):
                question = negative.question if isinstance(negative, LiveCase) else negative
                scope = negative.scope if isinstance(negative, LiveCase) else "project"
                arguments = {"question": question, "project_path": str(fixture.root), "scope": scope}
                payload, snapshot = _call_with_snapshot(arguments, service)
                if not isinstance(payload, Mapping):
                    errors.append(f"negative query returned missing or non-mapping payload: {question}: {payload!r}")
                    payload = {}
                safe_abstention = _safe_abstention(payload)
                if not safe_abstention:
                    errors.append(f"negative query did not fail closed: {question}: {payload!r}")
                results.append({
                    "case_id": (negative.case_id if isinstance(negative, LiveCase) else None) or f"negative_{index:02d}",
                    "scope": scope,
                    "question": question,
                    "expected": {"status": "insufficient_evidence"},
                    "observed": {
                        "status": (payload or {}).get("status"),
                        "kind": (payload or {}).get("kind"),
                        "support_status": (payload or {}).get("support_status"),
                        "answer_supported": (payload or {}).get("answer_supported"),
                    },
                    "payload": dict(payload),
                    "legacy_fact_evidence": capture_legacy_evidence(arguments, dict(payload), snapshot),
                    "checks": {"correct_abstention": safe_abstention},
                    "passed": safe_abstention,
                })
    positives = results[:len(cases)]
    source_count = sum(len(row.get("payload", {}).get("sources") or ()) for row in positives)
    distractor_count = sum(len(row.get("ranking", {}).get("distractor_paths", ())) for row in positives)
    historical_count = sum(len(row.get("ranking", {}).get("historical_paths", ())) for row in positives)
    false_supported_count = sum(
        row.get("expected", {}).get("kind") not in {None, "docs_answer"}
        and row.get("observed", {}).get("answer_supported") is True
        for row in positives
    )
    scores = [float(row.get("score", 10.0 if row.get("passed") else 0.0)) for row in positives]
    failed_negative_cases = [
        str(row.get("case_id")) for row in results[len(cases):] if not row.get("passed")
    ]
    if failed_negative_cases:
        errors.append(f"failed negative cases: {failed_negative_cases!r}")
    report: dict[str, object] = {
        "schema_version": "project-answer-quality-live-result-v1",
        "run_mode": "live_self_host",
        "provider_free": True,
        "setup_provenance": setup_provenance,
        "case_count": len(results),
        "positive_case_count": len(positives),
        "positive_passed_count": sum(bool(row.get("passed")) for row in positives),
        "negative_case_count": len(results) - len(positives),
        "passed_count": sum(bool(row.get("passed")) for row in results),
        "metrics": {
            "top1_relevance": sum(
                bool(row.get("ranking", {}).get("first_relevant_rank") == 1)
                for row in positives
            ) / max(len(positives), 1),
            "top3_relevance": sum(bool(row.get("checks", {}).get("relevant_source_in_top3")) for row in positives) / max(len(positives), 1),
            "top3_relevant_count": sum(bool(row.get("checks", {}).get("relevant_source_in_top3")) for row in positives),
            "mrr": sum(float(row.get("ranking", {}).get("reciprocal_rank", 0.0)) for row in positives) / max(len(positives), 1),
            "distractor_rate": distractor_count / max(source_count, 1),
            "historical_source_rate": historical_count / max(source_count, 1),
            "mean_query_coverage": sum(float(row.get("observed", {}).get("query_coverage", 0.0)) for row in positives) / max(len(positives), 1),
            "original_query_covered_count": sum(
                bool(row.get("observed", {}).get("original_query_covered"))
                for row in positives
            ),
            "direct_coverage_count": sum("direct" in row.get("observed", {}).get("coverage_attribution", ()) for row in positives),
            "derived_coverage_count": sum("derived" in row.get("observed", {}).get("coverage_attribution", ()) for row in positives),
            "direct_only_coverage_count": sum(row.get("observed", {}).get("coverage_attribution") == ["direct"] for row in positives),
            "derived_only_coverage_count": sum(row.get("observed", {}).get("coverage_attribution") == ["derived"] for row in positives),
            "both_coverage_count": sum(set(row.get("observed", {}).get("coverage_attribution", ())) == {"direct", "derived"} for row in positives),
            "lookup_coverage_count": sum(len(row.get("observed", {}).get("covered_lookup_ids", ())) for row in positives),
            "zero_coverage_count": sum(float(row.get("observed", {}).get("query_coverage", 0.0)) == 0.0 for row in positives),
            "useful_result_count": sum(
                bool(row.get("checks", {}).get("status_ok"))
                and bool(row.get("checks", {}).get("relevant_source_in_top3"))
                and bool(row.get("checks", {}).get("required_facts"))
                for row in positives
            ),
            "top1_fact_bearing_count": sum(bool(row.get("top1_fact_bearing")) for row in positives),
            "metadata_only_evidence_count": sum(len(row.get("observed", {}).get("metadata_only_sources", ())) for row in positives),
            "packs_contamination_count": sum(
                bool(row.get("observed", {}).get("packs_contamination"))
                for row in positives
            ),
            "docs_analysis_contamination_count": sum(
                any(str(path).startswith("docs/analysis/") for path in _source_paths(row.get("payload", {})))
                for row in positives
            ),
            "false_docs_answer_count": sum(row.get("observed", {}).get("kind") == "docs_answer" and row.get("expected", {}).get("kind") != "docs_answer" for row in positives),
            "max_source_count": max((len(row.get("payload", {}).get("sources") or ()) for row in positives), default=0),
            "max_public_utf8_bytes": max((row.get("observed", {}).get("public_utf8_bytes", 0) for row in positives), default=0),
            "max_estimated_tokens": max((row.get("observed", {}).get("actual_estimated_tokens", 0) for row in positives), default=0),
            "false_abstention_count": sum(
                row.get("expected", {}).get("kind") != "insufficient_evidence"
                and not bool(row.get("checks", {}).get("status_ok"))
                for row in positives
            ),
            "false_supported_count": false_supported_count,
            "operational_contamination_count": distractor_count,
            "cases_scoring_8_plus": sum(score >= 8.0 for score in scores),
            "mean_score": sum(scores) / max(len(scores), 1),
        },
        "output_cost_policy": {
            "objective": "minimize_full_public_dto_without_fixed_output_ceiling",
            "measurement": "source_count_canonical_utf8_bytes_and_existing_serialized_token_estimate",
            "constraints": "quality_source_identity_fidelity_and_safety_unchanged",
        },
        "verdict": "FAIL" if errors else "PASS",
        "errors": errors,
        "results": results,
    }
    threshold_failures = _threshold_failures(report["metrics"], len(cases))
    if threshold_failures:
        errors.extend(threshold_failures)
        report["errors"] = errors
        report["verdict"] = "FAIL"
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
