from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
import re

from docmancer.docs.application.project_answer_outline import build_project_answer_outline
from docmancer.docs.application.evidence_selection import (
    build_requirements,
    project_docs_selection_config,
    select_evidence,
)
from docmancer.docs.application.evidence_requirements import build_patch_evidence_requirements
from docmancer.docs.domain.request_intent import is_change_request
from docmancer.docs.domain.answer_completeness import (
    derive_project_answer_completeness,
    extract_project_answer_requirements,
    extract_query_relevance_terms,
)
from docmancer.docs.domain.mutation_intent import MutationIntentContract, build_mutation_intent
from docmancer.docs.domain.lifecycle_policy import (
    lifecycle_allows,
    lifecycle_intent as lifecycle_intent_for_question,
    temporal_relevance_for_status,
)
from docmancer.docs.domain.project_doc_ranking import is_changelog_path, normalize_doc_path, project_source_taxonomy, rerank_project_doc_chunks
from docmancer.docs.domain.project_query_intent import classify_project_query_intent
from docmancer.docs.domain.project_state import bound_project_docs_handoff, evaluate_documentation_sections
from docmancer.docs.domain.project_evidence import classify_project_evidence
from docmancer.docs.domain.quality import has_code_symbol_evidence, internal_noise_score, is_trivial_section, looks_like_code_or_command
from docmancer.docs.domain.snippets import best_context_pack_snippet, build_snippet_presentation, validate_response_style
from docmancer.docs.domain.source_map import build_project_repo_map, build_project_source_evidence, collect_project_source_facts, source_evidence_diagnostics, source_map_diagnostics
from docmancer.docs.domain.code_graph import build_code_graph_context_items, build_project_code_graph, code_graph_context_diagnostics, code_graph_diagnostics
from docmancer.docs.domain.trust_contract import build_project_context_trust_contract
from docmancer.docs.domain.content_trust import annotate_context_pack
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.retrieval_routing import (
    fit_stage_items,
    new_routing_record,
    record_stage,
    route_gap_recovery_stages,
    route_initial_stages,
    should_run_code_graph,
    should_run_repo_map,
    validate_routing_record,
)
from docmancer.docs.models import SOURCE_CLASS_PROJECT_FILE, DeliveryDecision, DocsChunk, DocsResult, ProjectContextResult, ProjectDocsChunk, ProjectDocsResult, ProjectMetadata

LOW_TRUST_PROJECT_RISK_FLAGS = frozenset({
    "research_artifact",
    "dogfood_artifact",
    "patch_review_artifact",
    "generated_review_output",
})
LOW_TRUST_QUERY_TERMS = (
    "dogfood",
    "research",
    "experiment",
    "benchmark",
    "baseline",
    "patch review",
    "patch-review",
    "review artifact",
    "generated review",
    "eval",
    "evaluation",
)
LOW_SIGNAL_SINGLE_TOKEN_QUERIES = {"test", "tests", "doc", "docs", "readme", "todo", "fixme"}
PLACEHOLDER_CONTEXT_DOC_RE = re.compile(
    r"\b(todo|tbd|placeholder|coming soon|lorem ipsum|under construction|work in progress|wip)\b|"
    r"TODO:\s*Put a short description|const\s+like\s*=\s*['\"]sample['\"]",
    re.IGNORECASE,
)

_DEPENDENCY_REFERENCE_CUE_RE = re.compile(
    r"\b(?:dependency|dependencies|package|packages|library|libraries|sdk|version|"
    r"pypi|pub\.dev|pub package|npm|crate|gradle|maven)\b",
    re.IGNORECASE,
)
_AMBIGUOUS_DEPENDENCY_NAMES = frozenset({"mcp"})


def _dependency_confirmation_blocks_local_answer(
    *,
    has_confirmation: bool,
    explicit_dependency_requested: bool,
    local_answer_available: bool,
) -> bool:
    """Return whether dependency acquisition must block local delivery.

    Auto-detected dependencies are a recall hint.  They may request network
    access only when local project evidence did not already prove the answer.
    Explicit dependency/deps-only requests retain the confirmation boundary.
    """

    return bool(
        has_confirmation
        and (explicit_dependency_requested or not local_answer_available)
    )


@dataclass(frozen=True)
class ContextTrustDecision:
    answer_available: bool
    reason: str
    confidence: str
    passed_relevance_gate: bool
    max_project_score: float | None
    query_terms_matched: list[str]
    query_terms_missing: list[str]


def _documentation_gap_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [action for action in actions if action.get("action") == "create_reviewable_project_doc"]


def _source_ground_documentation_gap(
    actions: list[dict[str, Any]],
    *,
    root: Path,
    repo_map: list[dict[str, Any]] | None = None,
    code_graph: Any = None,
    allow_repo_map_build: bool = True,
    allow_code_graph_build: bool = True,
) -> tuple[list[dict[str, Any]], Any]:
    """Attach bounded paths while returning the observed repo map for host diagnostics."""
    gap_actions = _documentation_gap_actions(actions)
    if not gap_actions:
        return repo_map or [], code_graph
    observed_repo_map = repo_map
    if repo_map is None and allow_repo_map_build:
        observed_repo_map = collect_project_source_facts(
            root,
            max_files=24,
            token_budget=4000,
            include_unmatched=True,
        )
        repo_map, _ = fit_stage_items("repo_map", observed_repo_map)
    repo_map = repo_map or []
    if code_graph is None and allow_code_graph_build:
        code_graph = build_project_code_graph(
            root,
            max_files=24,
            token_budget=4000,
            include_unmatched=True,
        )
    evidence = classify_project_evidence(root, repo_map=repo_map, code_graph=code_graph)
    for action in gap_actions:
        gap = dict(action.get("documentation_gap") or {})
        sections, evidence_complete = evaluate_documentation_sections(
            list(gap.get("required_sections") or []),
            evidence,
        )
        gap["required_sections"] = sections
        gap["evidence_to_collect"] = evidence
        gap["evidence_complete"] = evidence_complete
        action["documentation_gap"] = gap
        compact = bound_project_docs_handoff(action)
        action.clear()
        action.update(compact)
    return observed_repo_map or repo_map, code_graph




def project_context_pack(*, question: str = "", project_docs: ProjectDocsResult | None, dependency_docs: DocsResult | None) -> list[dict[str, Any]]:
    pack: list[dict[str, Any]] = []
    answer_lifecycle_intent = lifecycle_intent_for_question(question)
    if project_docs:
        for item in project_docs.results:
            lifecycle_metadata = {"lifecycle_status": item.lifecycle_status or "active"}
            if not lifecycle_allows(lifecycle_metadata, answer_lifecycle_intent):
                continue
            if _drop_placeholder_context_doc(item):
                continue
            if _drop_low_value_context_section(item.content, item.title, item.heading_path):
                continue
            token_estimate = max(1, len(item.content) // 4) if item.content else 0
            freshness = "stale" if item.stale else "current"
            source_taxonomy = project_source_taxonomy(item.path, doc_scope=item.doc_scope, module_path=item.module_path)
            if item.authority:
                source_taxonomy["authority"] = item.authority
            if _should_skip_low_trust_project_source(question, source_taxonomy):
                continue
            pack.append({
                "stable_chunk_id": item.stable_chunk_id,
                "parent_logical_id": item.parent_logical_id,
                "display_content_hash": item.display_content_hash,
                **({
                    "char_start": item.char_start,
                    "char_end": item.char_end,
                } if item.char_start is not None and item.char_end is not None else {}),
                **({
                    "line_start": item.line_start,
                    "line_end": item.line_end,
                } if item.line_start is not None and item.line_end is not None else {}),
                "source_class": "project_doc",
                "source_type": source_taxonomy["source_type"],
                "source_kind": source_taxonomy["source_kind"],
                "authority": source_taxonomy["authority"],
                "risk_flags": source_taxonomy["risk_flags"],
                "doc_scope": item.doc_scope,
                "module_id": item.module_id,
                "module_name": item.module_name,
                "module_path": item.module_path,
                "module_type": item.module_type,
                "description": item.description,
                "lifecycle_status": item.lifecycle_status or "active",
                "temporal_relevance": temporal_relevance_for_status(item.lifecycle_status),
                "index_freshness": "stale" if item.stale else "synchronized",
                "impact_policy": item.impact_policy,
                "project_identity": item.project_identity,
                "retrieval_query_ids": list(item.metadata.get("retrieval_query_ids") or ()),
                "retrieval_query_matches": dict(item.metadata.get("retrieval_query_matches") or {}),
                "path": item.path,
                "url": item.url,
                "title": item.title,
                "heading_path": item.heading_path,
                "freshness": freshness,
                "why_selected": project_why_selected(item),
                "content": item.content,
                "display_text": item.content,
                "token_estimate": token_estimate,
                "source": {
                    "source_class": "project_doc",
                    "source_type": source_taxonomy["source_type"],
                    "source_kind": source_taxonomy["source_kind"],
                    "authority": source_taxonomy["authority"],
                    "risk_flags": source_taxonomy["risk_flags"],
                    "doc_scope": item.doc_scope,
                    "module_id": item.module_id,
                    "module_name": item.module_name,
                    "module_path": item.module_path,
                    "module_type": item.module_type,
                    "description": item.description,
                    "lifecycle_status": item.lifecycle_status or "active",
                    "temporal_relevance": temporal_relevance_for_status(item.lifecycle_status),
                    "index_freshness": "stale" if item.stale else "synchronized",
                    "impact_policy": item.impact_policy,
                    "project_identity": item.project_identity,
                    "path": item.path,
                    "url": item.url,
                    "title": item.title,
                },
                "section": {
                    "title": item.title,
                    "heading_path": item.heading_path,
                    "freshness": freshness,
                },
            })
            snippet = context_pack_snippet(item)
            if snippet:
                pack[-1]["snippet"] = snippet
                pack[-1]["surrounding_context"] = item.content
    if dependency_docs:
        for item in dependency_docs.results:
            if _drop_low_value_context_section(item.content, item.title, getattr(item, "heading_path", None)):
                continue
            token_estimate = max(1, len(item.content) // 4) if item.content else 0
            freshness = "stale" if dependency_docs.stale_before_refresh else "current"
            pack.append({
                "source_class": "dependency_doc",
                "dependency": dependency_docs.library,
                "requested_version": dependency_docs.requested_version,
                "resolved_version": dependency_docs.resolved_version or dependency_docs.version,
                "version_source": dependency_docs.version_source,
                "docs_exactness": dependency_docs.docs_exactness,
                "docs_binding_source": dependency_docs.docs_binding_source,
                "confidence": dependency_docs.confidence,
                "url": item.url,
                "source_url": item.source,
                "title": item.title,
                "freshness": freshness,
                "why_selected": "dependency docs resolved through Docmancer registry/project metadata",
                "content": item.content,
                "token_estimate": token_estimate,
                "source": {
                    "source_class": "dependency_doc",
                    "library": dependency_docs.library,
                    "requested_version": dependency_docs.requested_version,
                    "version": dependency_docs.resolved_version or dependency_docs.version,
                    "url": item.url,
                    "source_url": item.source,
                    "title": item.title,
                },
                "section": {
                    "title": item.title,
                    "heading_path": getattr(item, "heading_path", None),
                    "freshness": freshness,
                },
            })
            snippet = context_pack_snippet(item)
            if snippet:
                pack[-1]["snippet"] = snippet
                pack[-1]["surrounding_context"] = item.content
    return pack


def _library_next_action(dependency_docs: DocsResult, action: Any) -> dict[str, Any]:
    if isinstance(action, dict):
        return action
    return {"tool": dependency_docs.tool, "reason": action}


def _project_docs_preflight_confirmation_result(*, root: Path, question: str, mode: str, project_docs: ProjectDocsResult) -> ProjectContextResult:
    answer_completeness = {
        "schema_version": "answer-completeness-1.0",
        "status": "unavailable",
        "answer_type": "unavailable",
        "coverage_score": 0.0,
        "matched_terms": [],
        "missing_terms": [],
        "coverage_by_requirement": [],
        "source_search_required": False,
        "reason_codes": ["project_docs_preflight_confirmation_required"],
    }
    return ProjectContextResult(
        project_path=str(root),
        question=question,
        status=project_docs.status if project_docs.status in {"stale", "confirmation_required"} else "confirmation_required",
        answer_available=False,
        answer_type="unavailable",
        answer_completeness=answer_completeness,
        mode=mode,
        reason="project_docs_preflight_confirmation_required",
        context_pack=[],
        project_docs=project_docs,
        dependency_docs=None,
        trust_contract={
            "sources": {"selected": [], "rejected": [], "risky": []},
            "policy": {"direct_webfetch": "forbidden", "reason_code": "project_docs_preflight_confirmation_required"},
        },
        warnings=project_docs.warnings,
        next_actions=project_docs.next_actions,
        recommended_next_actions=project_docs.next_actions,
        next_action=project_docs.next_action,
        requires_confirmation=True,
        confirmation_reason=project_docs.confirmation_reason,
        arguments_patch=project_docs.arguments_patch,
        metrics={"answer_completeness": answer_completeness},
        diagnostics={"preflight": project_docs.diagnostics.get("preflight") if isinstance(project_docs.diagnostics, dict) else project_docs.diagnostics},
        answer_outline={"answer_completeness": answer_completeness},
        message=project_docs.message or "Project docs preflight requires confirmation before returning trusted project context.",
    )


def _inject_broad_architecture_docs(
    project_docs: ProjectDocsResult,
    *,
    root: Path,
    intent: Any,
    evidence_path: str | None = None,
    lifecycle_intent_value: str = "current",
    catalog_authoritative: bool = False,
) -> ProjectDocsResult:
    if evidence_path or not getattr(intent, "wants_architecture", False):
        return project_docs
    existing = {normalize_doc_path(chunk.path) for chunk in project_docs.results}
    injected: list[ProjectDocsChunk] = []
    if catalog_authoritative:
        injection_rows = [
            item
            for item in project_docs.candidate_sources
            if item.get("reason") in {"overview", "project_architecture"}
            and item.get("doc_scope") == "project"
            and lifecycle_allows(item, lifecycle_intent_value)
        ][:3]
    else:
        injection_rows = (
            [
                {"path": rel, "doc_scope": "project", "lifecycle_status": "active"}
                for rel in ("ARCHITECTURE.md", "docs/INDEX.md", "README.md")
            ]
            if lifecycle_intent_value != "historical"
            else []
        )
    for row in injection_rows:
        rel = str(row.get("path") or "")
        if normalize_doc_path(rel) in existing:
            continue
        path = root / rel
        if not path.is_file() or path.stat().st_size > 80_000:
            continue
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if not text or _looks_like_placeholder_context_doc(rel, text):
            continue
        injected.append(ProjectDocsChunk(
            title=path.stem if path.stem else rel,
            content=text[:12_000],
            source=str(path),
            url=None,
            metadata={
                "score": 1.0,
                "injected_for": "broad_architecture_query",
                "injection_policy": "root_reviewable_project_doc_after_preflight",
                "lifecycle_status": row.get("lifecycle_status") or "active",
                "temporal_relevance": temporal_relevance_for_status(row.get("lifecycle_status")),
                "index_freshness": "synchronized",
            },
            source_class=SOURCE_CLASS_PROJECT_FILE,
            path=rel,
            doc_scope=str(row.get("doc_scope") or "project"),
            module_id=row.get("module_id"),
            module_name=row.get("module_name"),
            module_path=row.get("module_path"),
            module_type=row.get("module_type"),
            description=row.get("description"),
            authority=row.get("authority"),
            lifecycle_status=row.get("lifecycle_status"),
            impact_policy=row.get("impact_policy"),
        ))
    if not injected:
        return project_docs
    return replace(project_docs, results=[*project_docs.results, *injected])


def _drop_placeholder_context_doc(item: ProjectDocsChunk) -> bool:
    return _looks_like_placeholder_context_doc(getattr(item, "path", None), getattr(item, "content", None))


def _looks_like_placeholder_context_doc(path: str | None, content: str | None) -> bool:
    normalized_path = normalize_doc_path(path)
    name = normalized_path.rsplit("/", 1)[-1]
    if not (name.startswith("readme") or name.startswith("architecture") or name in {"license", "copying"}):
        return False
    return bool(PLACEHOLDER_CONTEXT_DOC_RE.search((content or "")[:4096]))


def _should_skip_low_trust_project_source(question: str, source_taxonomy: dict[str, Any]) -> bool:
    risk_flags = set(source_taxonomy.get("risk_flags") or [])
    if not risk_flags.intersection(LOW_TRUST_PROJECT_RISK_FLAGS):
        return False
    return not _question_explicitly_targets_low_trust_artifacts(question)


def _question_explicitly_targets_low_trust_artifacts(question: str) -> bool:
    normalized = (question or "").lower()
    return any(term in normalized for term in LOW_TRUST_QUERY_TERMS)


_GATE_WEIGHT_PATH = 1.0
_GATE_WEIGHT_TITLE_HEADING = 2.0
_GATE_WEIGHT_CONTENT = 3.0
_GATE_WEIGHT_SYMBOL = 4.0
_GATE_WEIGHT_DEPENDENCY = 4.0


def _query_relevance_gate(
    *,
    question: str,
    intent: Any,
    context_pack: list[dict[str, Any]],
    relevance_terms: list[str] | None = None,
) -> dict[str, Any]:
    terms = relevance_terms if relevance_terms is not None else extract_query_relevance_terms(question, intent=intent)
    if not terms:
        return {
            "passed": True,
            "reason": "no_high_signal_terms_required",
            "required_terms": [],
            "matched_terms": [],
            "weighted_score": None,
            "matched_term_count": 0,
            "required_term_count": 0,
        }
    matched_details: list[dict[str, Any]] = []
    for term in terms:
        normalized_term = _normalize_gate_text(term)
        if not normalized_term:
            continue
        best_weight = 0.0
        hit_fields: list[str] = []
        for item in context_pack:
            item_text = _normalize_gate_text(_context_item_text_for_gate(item))
            if normalized_term not in item_text:
                continue
            path = (item.get("source") or {}).get("path") if isinstance(item.get("source"), dict) else item.get("path")
            if path and normalized_term in _normalize_gate_text(path):
                best_weight = max(best_weight, _GATE_WEIGHT_PATH)
                hit_fields.append("path")
            heading = item.get("heading_path") or (item.get("section") or {}).get("heading_path")
            if heading and normalized_term in _normalize_gate_text(heading):
                best_weight = max(best_weight, _GATE_WEIGHT_TITLE_HEADING)
                hit_fields.append("heading")
            title = item.get("title") or (item.get("section") or {}).get("title")
            if title and normalized_term in _normalize_gate_text(title):
                best_weight = max(best_weight, _GATE_WEIGHT_TITLE_HEADING)
                hit_fields.append("title")
            snippet = item.get("snippet") or item.get("content")
            if snippet and normalized_term in _normalize_gate_text(snippet):
                weight = _GATE_WEIGHT_DEPENDENCY if item.get("source_class") == "dependency_doc" else _GATE_WEIGHT_CONTENT
                best_weight = max(best_weight, weight)
                hit_fields.append("content")
            evidence_class = item.get("evidence_class")
            if evidence_class:
                best_weight = max(best_weight, _GATE_WEIGHT_SYMBOL)
                hit_fields.append("evidence")
        if best_weight > 0:
            matched_details.append({"term": term, "weight": best_weight, "fields": sorted(set(hit_fields))})
    total_weight = sum(d["weight"] for d in matched_details)
    matched_count = len(matched_details)
    required_count = len(terms)
    coverage_ratio = matched_count / required_count if required_count > 0 else 0.0
    has_strong_match = any(d["weight"] >= _GATE_WEIGHT_SYMBOL for d in matched_details)
    high_signal_count = sum(1 for d in matched_details if d["weight"] >= _GATE_WEIGHT_CONTENT)
    passes = (
        matched_count >= 2 and high_signal_count >= 1
    ) or coverage_ratio >= 0.5 or has_strong_match
    matched_terms_list = [d["term"] for d in matched_details]
    missing_terms_list = [t for t in terms[:8] if t not in matched_terms_list]
    return {
        "passed": passes,
        "reason": "weighted_relevance_sufficient" if passes else "insufficient_weighted_relevance",
        "required_terms": terms[:8],
        "matched_terms": matched_terms_list,
        "missing_terms": missing_terms_list,
        "matched_details": matched_details,
        "weighted_score": round(total_weight, 1),
        "matched_term_count": matched_count,
        "required_term_count": required_count,
    }


def _make_context_trust_decision(
    *,
    question: str,
    context_pack: list[dict[str, Any]],
    project_docs: ProjectDocsResult | None,
    dependency_docs: DocsResult | None,
    source_evidence_items: list[dict[str, Any]],
    relevance_gate: dict[str, Any],
    answer_available: bool,
    answer_type: str,
    intent: Any,
    support_decision: Any | None = None,
) -> ContextTrustDecision:
    max_project_score = _max_project_ranking_score(project_docs)
    matched_terms = list(relevance_gate.get("matched_terms") or [])
    missing_terms = list(relevance_gate["missing_terms"] if "missing_terms" in relevance_gate else relevance_gate.get("required_terms") or [])
    passed = bool(relevance_gate.get("passed"))

    if _is_low_signal_single_token_query(question):
        return ContextTrustDecision(False, "no_reliable_context", "low", passed, max_project_score, matched_terms, missing_terms)

    # The typed selector has already revalidated a bounded, model-visible answer
    # unit for every mandatory obligation.  Legacy lexical relevance remains a
    # diagnostic, but cannot veto that stronger proof contract merely because
    # an interrogative word such as ``value`` is not repeated in the answer.
    if (
        bool(getattr(support_decision, "answer_supported", False))
        and context_pack
        and project_docs
        and project_docs.answer_available
    ):
        return ContextTrustDecision(
            True, "typed_evidence_contract_satisfied", "trusted", passed,
            max_project_score, matched_terms, missing_terms,
        )

    has_dependency_answer = bool(dependency_docs and dependency_docs.results)
    has_source_evidence = any(item.get("evidence_class") == "source_snippet" for item in source_evidence_items)
    has_strong_project_answer = bool(project_docs and project_docs.answer_available and _score_is_strong(max_project_score))
    if answer_available and not missing_terms and passed and (has_dependency_answer or has_source_evidence or has_strong_project_answer):
        return ContextTrustDecision(True, "trusted_context_available", "trusted", passed, max_project_score, matched_terms, missing_terms)

    if context_pack and (passed or getattr(intent, "broad", False) or answer_type in {"partial", "partial_navigational"}):
        return ContextTrustDecision(False, "partial_navigational_context", "partial", passed, max_project_score, matched_terms, missing_terms)

    return ContextTrustDecision(False, "no_reliable_context", "low", passed, max_project_score, matched_terms, missing_terms)


def _max_project_ranking_score(project_docs: ProjectDocsResult | None) -> float | None:
    scores: list[float] = []
    for chunk in project_docs.results if project_docs else []:
        metadata = getattr(chunk, "metadata", None) or {}
        ranking = metadata.get("project_ranking") if isinstance(metadata, dict) else None
        value = ranking.get("final_score") if isinstance(ranking, dict) else None
        if isinstance(value, (int, float)):
            scores.append(float(value))
    if scores:
        return max(scores)
    return 1.0 if project_docs and project_docs.results else None


STRONG_PROJECT_SCORE_THRESHOLD = 0.35


def _score_is_strong(score: float | None) -> bool:
    return score is not None and score >= STRONG_PROJECT_SCORE_THRESHOLD


def _is_low_signal_single_token_query(question: str) -> bool:
    tokens = re.findall(r"[\wА-Яа-яЁё]+", (question or "").lower())
    return len(tokens) == 1 and tokens[0] in LOW_SIGNAL_SINGLE_TOKEN_QUERIES


def _context_has_query_evidence(context_pack: list[dict[str, Any]], terms: list[str] | None) -> bool:
    if not terms:
        return True
    return bool(_matched_query_terms(context_pack, terms))


def _matched_query_terms(context_pack: list[dict[str, Any]], terms: list[str]) -> list[str]:
    matched: list[str] = []
    normalized_items = [_normalize_gate_text(_context_item_text_for_gate(item)) for item in context_pack]
    for term in terms:
        normalized_term = _normalize_gate_text(term)
        if normalized_term and any(normalized_term in text for text in normalized_items):
            if term not in matched:
                matched.append(term)
    return matched


def _context_item_text_for_gate(item: dict[str, Any]) -> str:
    source = item.get("source") if isinstance(item.get("source"), dict) else {}
    section = item.get("section") if isinstance(item.get("section"), dict) else {}
    parts = [
        item.get("path"),
        item.get("title"),
        item.get("heading_path"),
        item.get("content"),
        item.get("snippet"),
        source.get("path"),
        source.get("title"),
        section.get("title"),
    ]
    return "\n".join(str(part) for part in parts if part)


def _normalize_gate_text(value: Any) -> str:
    if isinstance(value, dict):
        parts = [
            value.get("code"),
            value.get("text"),
            value.get("content"),
            value.get("title"),
            value.get("why_relevant"),
        ]
        value = "\n".join(str(part) for part in parts if part)
    elif isinstance(value, list):
        value = "\n".join(str(part) for part in value if part)
    text = str(value or "").replace("\\", "/").lower().replace("-", "_")
    return re.sub(r"\s+", " ", text)


def _repo_map_token_budget(tokens: int | None) -> int:
    if not tokens:
        return 900
    return max(120, min(900, tokens // 4))


def _source_evidence_token_budget(tokens: int | None) -> int:
    if not tokens:
        return 700
    return max(120, min(700, tokens // 5))


def _code_graph_build_token_budget(tokens: int | None) -> int:
    if not tokens:
        return 3000
    return max(1200, min(5000, int(tokens * 0.35)))


def _code_graph_context_token_budget(tokens: int | None) -> int:
    if not tokens:
        return 900
    return max(400, min(1400, int(tokens * 0.12)))


def _compact_code_graph_diagnostics(diagnostics: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "node_count",
        "edge_count",
        "selected_files",
        "selected_paths",
        "edge_kinds",
        "confidence_summary",
        "unresolved_import_count",
        "unresolved_reference_count",
        "graph_scope",
        "limitations",
    )
    return {key: diagnostics[key] for key in keys if key in diagnostics}


def _drop_low_value_context_section(content: str, title: str | None = None, heading_path: str | None = None) -> bool:
    if not is_trivial_section(content, title, heading_path):
        return False
    text = (content or "").strip()
    lowered = text.lower()
    title_lower = (title or "").strip().lower()
    return (
        not text
        or lowered == title_lower
        or bool(re.fullmatch(r"\d+(?:\.\d+){1,3}(?:\s+-\s+\d{4}-\d{2}-\d{2})?", text))
    )


def context_pack_snippet(item: DocsChunk) -> dict[str, Any] | None:
    return best_context_pack_snippet(item)


def project_why_selected(item: Any) -> str:
    path = normalize_doc_path(getattr(item, "path", None))
    metadata = getattr(item, "metadata", None) or {}
    ranking = metadata.get("project_ranking") if isinstance(metadata, dict) else None
    ranking_reasons = ranking.get("reasons") if isinstance(ranking, dict) else None
    if ranking_reasons:
        base_reason = _project_source_kind_reason(path)
        reasons = [str(reason) for reason in ranking_reasons if reason]
        return "; ".join([base_reason, *reasons])

    return _project_source_kind_reason(path)


def _project_source_kind_reason(path: str) -> str:
    if path.endswith("readme.md"):
        return "selected as high-level project overview / usage documentation"
    if path.endswith("contributing.md"):
        return "selected as project structure and extension-point documentation"
    if "architecture" in path:
        return "selected as internal architecture / pipeline documentation"
    if "mcp-packs" in path:
        return "selected as MCP Packs / API action runtime documentation"
    if is_changelog_path(path):
        return "selected as release-history evidence"
    return "selected because it matched repo-owned project documentation for the question"


def project_context_metrics(
    *,
    context_pack: list[dict[str, Any]],
    project_docs: ProjectDocsResult | None,
    dependency_docs: DocsResult | None,
    intent: Any | None = None,
) -> dict[str, Any]:
    source_classes = [item.get("source_class") for item in context_pack]
    paths = [normalize_doc_path(item.get("path") or ((item.get("source") or {}).get("path") if isinstance(item.get("source"), dict) else None)) for item in context_pack]
    path_counts: dict[str, int] = {}
    for path in paths:
        if path:
            path_counts[path] = path_counts.get(path, 0) + 1
    changelog_count = sum(1 for path in paths if is_changelog_path(path))
    project_result_count = len(project_docs.results) if project_docs else 0
    dependency_result_count = len(dependency_docs.results) if dependency_docs else 0
    raw_result_count = project_result_count + dependency_result_count
    raw_results = [*(project_docs.results if project_docs else []), *(dependency_docs.results if dependency_docs else [])]
    context_tokens = sum(int(item.get("token_estimate") or 0) for item in context_pack)
    raw_docs_tokens = sum(int(((item.metadata or {}).get("raw_tokens") or 0)) for item in (project_docs.results if project_docs else []))
    max_items_from_single_source = max(path_counts.values(), default=0)
    quality_warnings = []
    if intent and not getattr(intent, "wants_release_history", False) and changelog_count:
        quality_warnings.append({
            "code": "changelog_in_non_release_context",
            "message": "CHANGELOG.md appeared in context for a non-release query.",
        })
    if intent and getattr(intent, "broad", False) and max_items_from_single_source > 2:
        quality_warnings.append({
            "code": "low_source_diversity",
            "message": "Broad query returned too many chunks from one source.",
        })
    return {
        "context_pack_items": len(context_pack),
        "selected_source_count": len(context_pack),
        "project_result_count": project_result_count,
        "dependency_result_count": dependency_result_count,
        "token_estimate": context_tokens,
        "source_classes": sorted({str(item) for item in source_classes if item}),
        "quality": {
            "query_intent": getattr(intent, "name", None),
            "changelog_items": changelog_count,
            "changelog_ratio": changelog_count / len(context_pack) if context_pack else 0.0,
            "unique_source_count": len(path_counts),
            "max_items_from_single_source": max_items_from_single_source,
            "has_readme": any(path.endswith("readme.md") for path in paths),
            "has_architecture": any("architecture" in path for path in paths),
            "has_contributing": any(path.endswith("contributing.md") for path in paths),
            "has_docs_mcp_source": any("mcp-docs" in path or "docs-server" in path for path in paths),
            "has_packs_mcp_source": any("mcp-packs" in path for path in paths),
            "relevance_coverage": len(context_pack) / max(1, raw_result_count),
            "trivial_sections_filtered": max(0, raw_result_count - len(context_pack)),
            "noise_sections_demoted": sum(1 for item in raw_results if internal_noise_score(getattr(item, "content", "")) >= 0.5),
            "warnings": quality_warnings,
        },
        "token_savings": _token_savings_metrics(raw_docs_tokens, context_tokens),
    }


def _token_savings_metrics(raw_docs_tokens: int, context_pack_tokens: int) -> dict[str, Any]:
    raw = max(0, int(raw_docs_tokens or 0))
    pack = max(0, int(context_pack_tokens or 0))
    if raw == 0:
        return {
            "raw_docs_tokens": raw,
            "context_pack_tokens": pack,
            "savings_percent": None,
            "used_percent": None,
            "agentic_runway_multiplier": None,
            "meaning": "compression_vs_raw_docs_not_relevance_score",
        }
    return {
        "raw_docs_tokens": raw,
        "context_pack_tokens": pack,
        "savings_percent": round(max(0, raw - pack) / raw * 100, 1),
        "used_percent": round(pack / raw * 100, 1),
        "agentic_runway_multiplier": round(raw / pack, 2) if pack else None,
        "meaning": "compression_vs_raw_docs_not_relevance_score",
    }
from docmancer.retrieval.query_planning import extract_document_locator

__all__ = [name for name in globals() if not name.startswith('__')]
