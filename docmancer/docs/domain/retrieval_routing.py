"""Versioned deterministic routing for bounded project retrieval stages."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable

from docmancer.docs.domain.request_intent import is_change_request


RETRIEVAL_ROUTING_SCHEMA_VERSION = 1
STAGE_ITEM_LIMITS = {
    "project_docs": 20,
    "dependency_docs": 20,
    "source_evidence": 12,
    "repo_map": 8,
    "code_graph": 8,
}
STAGE_BYTE_LIMITS = {
    "project_docs": 64 * 1024,
    "dependency_docs": 64 * 1024,
    "source_evidence": 48 * 1024,
    "repo_map": 32 * 1024,
    "code_graph": 32 * 1024,
}

_SOURCE_NAV_RE = re.compile(
    r"\b(where|which file|find (?:the )?(?:class|function|symbol)|where.*used|references?|imports?|"
    r"где|какой файл|какие файлы|найди|используется|нужно менять|ссылки|импорты)\b",
    re.IGNORECASE,
)
_SOURCE_CONCEPT_RE = re.compile(
    r"(?:[A-Za-z_][A-Za-z0-9_]*(?:Service|Controller|Repository|Provider|Screen|View|Client|Manager|Module|Router|Cubit|Bloc))|"
    r"(?:\b(?:class|function|method|symbol|module|file|service|controller|repository|provider|screen|cubit|bloc)\b)|"
    r"(?:[A-Za-z0-9_./-]+\.(?:py|dart|js|ts|tsx|rs|go|java|kt))|(?:['\"][^'\"]{3,80}['\"])",
    re.IGNORECASE,
)
_CROSS_MODULE_RE = re.compile(
    r"\b(cross[- ]module|cross[- ]package|across modules?|call chain|dependency chain|imports?|references?|"
    r"между модулями|цепочк\w+ вызов\w+|импорт\w+|ссылк\w+)\b",
    re.IGNORECASE,
)
_PATH_HINT_RE = re.compile(r"\b(?:src|lib|app|packages?)/[A-Za-z0-9_./-]+")


@dataclass(frozen=True)
class RetrievalRoute:
    schema_version: int
    intent: str
    project_mode: bool
    dependency_requested: bool
    use_source_evidence: bool
    source_reason: str


@dataclass(frozen=True)
class GapRecoveryRoute:
    use_repo_map: bool
    repo_map_reason: str
    use_code_graph: bool
    code_graph_reason: str


def route_initial_stages(
    *, question: str, mode: str, dependency_requested: bool, project_doc_items: Iterable[Any]
) -> RetrievalRoute:
    text = str(question or "")
    project_mode = mode in {"auto", "project-only"}
    patch = is_change_request(text)
    source_navigation = bool(_SOURCE_NAV_RE.search(text))
    source_concepts = bool(_SOURCE_CONCEPT_RE.search(text))
    doc_target_hint = any(_doc_has_target_hint(item) for item in project_doc_items)
    symbol_grounding = source_concepts and doc_target_hint and not dependency_requested
    if source_navigation:
        intent = "source_navigation"
    elif patch:
        intent = "mixed" if dependency_requested else "patch"
    elif symbol_grounding:
        intent = "docs"
    elif dependency_requested:
        intent = "api" if not project_mode or mode in {"deps-only", "public-docs"} else "mixed"
    else:
        intent = "docs"
    use_source = project_mode and (
        source_navigation or symbol_grounding or (patch and (source_concepts or doc_target_hint))
    )
    if not project_mode:
        reason = "project source stages are outside the selected mode"
    elif source_navigation:
        reason = "the question explicitly requests source navigation"
    elif symbol_grounding:
        reason = "project documentation names the requested source symbol"
    elif patch and source_concepts:
        reason = "the patch request names a bounded source concept"
    elif patch and doc_target_hint:
        reason = "project documentation names an implementation target"
    elif patch:
        reason = "patch target is not yet source-grounded"
    else:
        reason = "complete documentation/API intent does not require source evidence"
    return RetrievalRoute(
        RETRIEVAL_ROUTING_SCHEMA_VERSION, intent, project_mode,
        dependency_requested, use_source, reason,
    )


def should_run_repo_map(route: RetrievalRoute, source_items: Iterable[dict[str, Any]]) -> tuple[bool, str]:
    items = list(source_items)
    if not route.project_mode:
        return False, "project repository map is outside the selected mode"
    if route.intent == "source_navigation":
        return True, "explicit source navigation requires bounded repository paths"
    if route.intent not in {"patch", "mixed"}:
        return False, "documentation/API evidence does not require repository cartography"
    if any(item.get("evidence_class") == "absent_in_source" for item in items):
        return True, "required target terms remain unresolved after source evidence"
    if _proven_source_paths(items):
        return False, "bounded source evidence already proves a target path"
    if route.use_source_evidence:
        return True, "required patch target remains unresolved after source evidence"
    return False, "no deterministic source signal authorizes repository scanning"


def should_run_code_graph(
    route: RetrievalRoute,
    *, question: str,
    source_items: Iterable[dict[str, Any]],
    repo_map_items: Iterable[dict[str, Any]],
) -> tuple[bool, str]:
    source = list(source_items)
    repo = list(repo_map_items)
    if not route.project_mode or route.intent in {"docs", "api"}:
        return False, "documentation/API intent does not require connectivity evidence"
    if _CROSS_MODULE_RE.search(str(question or "")):
        return True, "the question explicitly requires cross-module/reference connectivity"
    modules = {_top_module(path) for path in _proven_source_paths([*source, *repo]) if _top_module(path)}
    if len(modules) > 1:
        return True, "earlier evidence supports multiple target modules"
    unresolved = any(item.get("evidence_class") == "absent_in_source" for item in source)
    if unresolved and route.intent in {"patch", "source_navigation", "mixed"}:
        return True, "target resolution remains incomplete after bounded source retrieval"
    return False, "one bounded source target is already resolved"


def route_gap_recovery_stages(
    *, has_documentation_gap: bool, repo_map_attempted: bool, code_graph_attempted: bool
) -> GapRecoveryRoute:
    """Own the exceptional authoring-evidence decision without repeating a stage."""

    use_repo_map = has_documentation_gap and not repo_map_attempted
    use_code_graph = has_documentation_gap and not code_graph_attempted
    return GapRecoveryRoute(
        use_repo_map=use_repo_map,
        repo_map_reason=(
            "missing project documentation requires bounded authoring evidence"
            if use_repo_map else
            "no documentation gap requires repository authoring evidence"
            if not has_documentation_gap else
            "repository-map stage was already attempted"
        ),
        use_code_graph=use_code_graph,
        code_graph_reason=(
            "missing project documentation requires bounded module evidence"
            if use_code_graph else
            "no documentation gap requires module authoring evidence"
            if not has_documentation_gap else
            "code-graph stage was already attempted"
        ),
    )


def new_routing_record(route: RetrievalRoute, *, project_docs_used: bool, dependency_docs_used: bool) -> dict[str, Any]:
    return {
        "schema_version": route.schema_version,
        "intent": route.intent,
        "stages": {
            "project_docs": _stage("used" if project_docs_used else "skipped", "selected project documentation mode" if project_docs_used else "project documentation not selected"),
            "dependency_docs": _stage("used" if dependency_docs_used else "skipped", "selected exact-version dependency documentation" if dependency_docs_used else "dependency documentation not selected or not available"),
            "source_evidence": _stage("skipped", route.source_reason),
            "repo_map": _stage("skipped", "not evaluated"),
            "code_graph": _stage("skipped", "not evaluated"),
        },
        "raw_retrieval_bytes": 0,
        "model_visible_bytes": 0,
    }


def record_stage(
    record: dict[str, Any], stage: str, *, status: str, reason: str,
    items: Iterable[dict[str, Any]] = (), error: str | None = None,
) -> None:
    observed_items = list(items)
    bounded_items, budget = fit_stage_items(stage, observed_items)
    row = _stage(status, reason)
    row["item_count"] = len(bounded_items)
    row["raw_bytes"] = sum(len(_canonical_bytes(item)) for item in bounded_items)
    row["estimated_tokens"] = (row["raw_bytes"] + 3) // 4
    row["observed_item_count"] = len(observed_items)
    row["observed_raw_bytes"] = sum(len(_canonical_bytes(item)) for item in observed_items)
    row["budget_exceeded"] = bool(budget)
    if budget:
        row["status"] = "insufficient"
        row["reason"] = f"{reason}; {budget}"
    if error:
        row["error_type"] = str(error)[:80]
    record["stages"][stage] = row
    record["raw_retrieval_bytes"] = sum(
        int(value.get("raw_bytes") or 0) for value in record["stages"].values()
    )


def fit_stage_items(stage: str, items: Iterable[Any]) -> tuple[list[Any], str | None]:
    """Fit whole stage items under both item and serialized-byte ceilings."""

    item_limit = STAGE_ITEM_LIMITS[stage]
    byte_limit = STAGE_BYTE_LIMITS[stage]
    values = list(items)
    bounded: list[Any] = []
    used = 0
    for item in values:
        encoded = len(_canonical_bytes(item))
        if len(bounded) >= item_limit or used + encoded > byte_limit:
            break
        bounded.append(item)
        used += encoded
    if len(bounded) == len(values):
        return bounded, None
    return bounded, (
        f"stage budget exceeded (observed_items={len(values)}, retained_items={len(bounded)}, "
        f"item_limit={item_limit}, byte_limit={byte_limit})"
    )


def validate_routing_record(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict) or record.get("schema_version") != RETRIEVAL_ROUTING_SCHEMA_VERSION:
        return ["invalid retrieval routing record"]
    if set(record) != {"schema_version", "intent", "stages", "raw_retrieval_bytes", "model_visible_bytes"}:
        errors.append("unexpected routing record fields")
    stages = record.get("stages")
    if not isinstance(stages, dict) or set(stages) != set(STAGE_ITEM_LIMITS):
        errors.append("routing record must contain every stage")
        return errors
    for name, row in stages.items():
        if row.get("status") not in {"used", "skipped", "failed", "insufficient"}:
            errors.append(f"{name}: invalid stage status")
        if not isinstance(row.get("reason"), str) or not row["reason"]:
            errors.append(f"{name}: missing deterministic reason")
        if any(key in row for key in ("content", "snippet", "context_pack", "source")):
            errors.append(f"{name}: raw evidence leaked into routing diagnostics")
        if int(row.get("item_count") or 0) > STAGE_ITEM_LIMITS[name]:
            errors.append(f"{name}: item budget exceeded")
        if int(row.get("raw_bytes") or 0) > STAGE_BYTE_LIMITS[name]:
            errors.append(f"{name}: byte budget exceeded")
        budget_exceeded = row.get("budget_exceeded")
        if not isinstance(budget_exceeded, bool):
            errors.append(f"{name}: missing budget status")
        elif budget_exceeded and row.get("status") not in {"insufficient", "failed"}:
            errors.append(f"{name}: exceeded budget must fail closed")
    return errors


def _stage(status: str, reason: str) -> dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "item_count": 0,
        "raw_bytes": 0,
        "estimated_tokens": 0,
        "observed_item_count": 0,
        "observed_raw_bytes": 0,
        "budget_exceeded": False,
    }


def _doc_has_target_hint(item: Any) -> bool:
    content = str(getattr(item, "content", None) or (item.get("content") if isinstance(item, dict) else "") or "")
    return bool(_PATH_HINT_RE.search(content) or _SOURCE_CONCEPT_RE.search(content))


def _proven_source_paths(items: Iterable[dict[str, Any]]) -> list[str]:
    return [
        str(item.get("path")) for item in items
        if item.get("path") and item.get("evidence_class") != "absent_in_source"
    ]


def _top_module(path: str) -> str:
    parts = [part for part in str(path).replace("\\", "/").split("/") if part]
    return "/".join(parts[:2]) if len(parts) > 1 else (parts[0] if parts else "")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
