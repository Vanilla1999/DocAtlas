from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
import re

from docmancer.docs.application.project_answer_outline import build_project_answer_outline
from docmancer.docs.domain.answer_completeness import (
    evaluate_project_answer_completeness,
    extract_project_answer_requirements,
    extract_query_relevance_terms,
)
from docmancer.docs.domain.project_doc_ranking import is_changelog_path, normalize_doc_path, project_source_taxonomy, rerank_project_doc_chunks
from docmancer.docs.domain.project_query_intent import classify_project_query_intent
from docmancer.docs.domain.quality import has_code_symbol_evidence, internal_noise_score, is_trivial_section, looks_like_code_or_command
from docmancer.docs.domain.snippets import best_context_pack_snippet, build_snippet_presentation, validate_response_style
from docmancer.docs.domain.source_map import build_project_repo_map, build_project_source_evidence, source_evidence_diagnostics, source_map_diagnostics
from docmancer.docs.domain.trust_contract import build_project_context_trust_contract
from docmancer.docs.models import DocsChunk, DocsResult, ProjectContextResult, ProjectDocsResult, ProjectMetadata

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


@dataclass(frozen=True)
class ContextTrustDecision:
    answer_available: bool
    reason: str
    confidence: str
    passed_relevance_gate: bool
    max_project_score: float | None
    query_terms_matched: list[str]
    query_terms_missing: list[str]


class ProjectContextService:
    """Application boundary for composing repo-grounded context packs."""

    def __init__(self, facade: Any):
        self.facade = facade

    def get_project_context(
        self,
        project_path: str,
        question: str,
        *,
        tokens: int | None = None,
        limit: int | None = None,
        expand: str | None = None,
        library: str | None = None,
        libraries: list[str] | None = None,
        ecosystem: str | None = None,
        version: str | None = None,
        module: str | None = None,
        module_path: str | None = None,
        scope: str | None = None,
        mode: str = "auto",
        response_style: str | None = None,
        allow_network: bool = False,
    ) -> ProjectContextResult:
        response_style = validate_response_style(response_style)
        mode = mode.lower()
        if mode not in {"auto", "project-only", "deps-only", "public-docs"}:
            raise ValueError("mode must be one of: auto, project-only, deps-only, public-docs")
        root = Path(project_path).expanduser().resolve()
        intent = classify_project_query_intent(question)
        metadata = self.facade.read_project_metadata(str(root))
        project_docs = None
        if mode in {"auto", "project-only"}:
            project_docs = self.facade.get_project_docs(str(root), question, tokens=tokens, limit=limit, expand=expand, module=module, module_path=module_path, scope=scope)
            if project_docs and project_docs.results:
                project_docs = replace(
                    project_docs,
                    results=rerank_project_doc_chunks(project_docs.results, question=question, intent=intent, limit=limit),
                )

        explicit_dependency = library or (libraries[0] if libraries else None)
        inferred_dependency = self.dependency_mentioned_in_question(metadata, question)
        selected_dependency = explicit_dependency or inferred_dependency
        explicit_dependency_requested = bool(explicit_dependency or mode in {"deps-only", "public-docs"})
        dependency_docs: DocsResult | None = None
        dependency_confirmation: dict[str, Any] | None = None
        if selected_dependency and mode in {"auto", "deps-only", "public-docs"}:
            if not allow_network:
                dependency_confirmation = {
                    "type": "ask_user_to_fetch_dependency_docs",
                    "tool": "get_project_context",
                    "reason": "dependency_docs_network_fetch_required",
                    "dependency": selected_dependency,
                    "requires_confirmation": True,
                    "confirmation_reason": "network_fetch",
                    "arguments_patch": {
                        "project_path": str(root),
                        "question": question,
                        "library": selected_dependency,
                        "mode": "deps-only" if mode in {"deps-only", "public-docs"} else "auto",
                        "allow_network": True,
                    },
                    "user_message": "Dependency/public documentation may require network fetch. Proceed?",
                }
            else:
                dependency_docs = self.facade.get_docs(
                    selected_dependency,
                    topic=question,
                    tokens=tokens,
                    ecosystem=ecosystem,
                    version=version,
                    project_path=str(root),
                )

        warnings = [*(project_docs.warnings if project_docs else [])]
        if dependency_docs:
            warnings.extend(dependency_docs.warnings)
        next_actions = [*(project_docs.next_actions if project_docs else [])]
        if dependency_docs:
            next_actions.extend(_library_next_action(dependency_docs, action) for action in dependency_docs.next_actions)
        if dependency_confirmation:
            next_actions.append(dependency_confirmation)
        requires_confirmation = bool(project_docs and project_docs.requires_confirmation) or bool(dependency_confirmation and explicit_dependency_requested)
        confirmation_reason = project_docs.confirmation_reason if project_docs and project_docs.requires_confirmation else ("network_fetch" if dependency_confirmation and explicit_dependency_requested else None)
        next_action = project_docs.next_action if project_docs and project_docs.requires_confirmation else (dependency_confirmation or {})
        arguments_patch = project_docs.arguments_patch if project_docs and project_docs.requires_confirmation else ({"allow_network": True} if dependency_confirmation else {})
        context_pack = project_context_pack(question=question, project_docs=project_docs, dependency_docs=dependency_docs)
        requirements = extract_project_answer_requirements(question)
        repo_map_items: list[dict[str, Any]] = []
        source_evidence_items: list[dict[str, Any]] = []
        if mode in {"auto", "project-only"}:
            repo_map_items = build_project_repo_map(
                root,
                question=question,
                max_files=max(1, min(8, limit or 4)),
                token_budget=_repo_map_token_budget(tokens),
            )
            context_pack.extend(repo_map_items)
            source_evidence_items = build_project_source_evidence(
                root,
                question=question,
                requirements=requirements,
                max_items=max(1, min(12, (limit or 4) * 2)),
                token_budget=_source_evidence_token_budget(tokens),
            )
            context_pack.extend(source_evidence_items)
        trust_contract = build_project_context_trust_contract(
            project_docs=project_docs,
            dependency_docs=dependency_docs,
            requested_library=selected_dependency,
            mode=mode,
            context_pack=context_pack,
        )
        answer_outline = build_project_answer_outline(question=question, intent=intent, context_pack=context_pack)
        metrics = project_context_metrics(context_pack=context_pack, project_docs=project_docs, dependency_docs=dependency_docs, intent=intent)
        lane_priority = ["project"] if mode == "project-only" else (["dependency"] if mode in {"deps-only", "public-docs"} else ["project", "dependency"])
        snippet_presentation = build_snippet_presentation(
            context_pack,
            question=question,
            response_style=response_style,
            lane_priority=lane_priority,
        )
        metrics["snippet_metrics"] = snippet_presentation.metrics
        diagnostics: dict[str, Any] = {"query_intent": intent.name}
        if repo_map_items:
            diagnostics["repo_map"] = source_map_diagnostics(repo_map_items)
        if source_evidence_items:
            diagnostics["source_evidence"] = source_evidence_diagnostics(source_evidence_items)
        if project_docs is not None and hasattr(self.facade, "active_index_diagnostics"):
            diagnostics["active_index"] = self.facade.active_index_diagnostics(str(root))
        if intent.name == "mcp_disambiguation":
            diagnostics["mcp_surfaces"] = [
                {
                    "name": "Docs MCP server",
                    "command": "doc-atlas mcp docs-serve",
                    "purpose": "Serve local/version-aware documentation context to agents.",
                    "preferred_for": ["documentation Q&A", "Context7-style docs", "project docs", "library docs"],
                },
                {
                    "name": "Packs MCP runtime",
                    "command": "doc-atlas mcp serve",
                    "purpose": "Expose version-pinned API action tools from installed packs.",
                    "preferred_for": ["API calls", "agent actions", "installed packs"],
                },
            ]
        relevance_terms = [] if requirements else extract_query_relevance_terms(question, intent=intent)
        source_evidence_answer_available = any(
            item.get("evidence_class") == "source_snippet"
            and _context_has_query_evidence([item], relevance_terms)
            for item in source_evidence_items
        )
        answer_available = bool(project_docs and project_docs.answer_available) or bool(dependency_docs and dependency_docs.results) or source_evidence_answer_available
        relevance_gate = _query_relevance_gate(
            question=question,
            intent=intent,
            context_pack=context_pack,
            relevance_terms=relevance_terms,
        )
        diagnostics["relevance_gate"] = relevance_gate
        if answer_available and not relevance_gate["passed"]:
            warning = {
                "code": "no_query_relevance_evidence",
                "message": (
                    "Selected context does not contain high-signal terms from the question; "
                    "do not treat the result as an exact trusted answer."
                ),
                "missing_terms": relevance_gate.get("required_terms", []),
            }
            answer_available = False
            answer_outline.setdefault("warnings", []).append(warning)
            metrics.setdefault("quality", {}).setdefault("warnings", []).append(warning)
            next_actions.append({
                "tool": "code_search",
                "reason": "No selected trusted source contains high-signal query terms; search project docs/source before answering.",
                "query_terms": relevance_gate.get("required_terms", [])[:8],
            })
        if getattr(intent, "wants_code_symbols", False) and not any(
            has_code_symbol_evidence(
                str(item.get("content") or ""),
                str(item.get("title") or ""),
                str(item.get("heading_path") or ""),
                str(item.get("path") or ""),
            )
            for item in context_pack
        ):
            warning = {
                "code": "insufficient_code_symbol_evidence",
                "message": "Selected project docs do not contain concrete files, classes, or functions for this code-symbol query.",
            }
            answer_available = False
            answer_outline.setdefault("warnings", []).append(warning)
            metrics.setdefault("quality", {}).setdefault("warnings", []).append(warning)
            next_actions.extend([
                {"tool": "code_search", "reason": "Use code search / ripgrep for MCP server classes and functions"},
                {"tool": "project_docs", "reason": "Add module docs or ADR linking MCP server implementation files"},
            ])
        completeness_result = evaluate_project_answer_completeness(
            question=question,
            context_pack=context_pack,
            answer_available=answer_available,
            intent=intent,
        )
        answer_type = completeness_result["answer_type"]
        answer_completeness = completeness_result["answer_completeness"]
        recommended_next_actions = completeness_result["recommended_next_actions"]
        if recommended_next_actions:
            next_actions.extend(recommended_next_actions)
            warning = {
                "code": answer_type,
                "message": "Selected context is partial/navigational for this story-specific question; search project source for missing source-backed terms.",
            }
            answer_outline.setdefault("warnings", []).append(warning)
            metrics.setdefault("quality", {}).setdefault("warnings", []).append(warning)
        answer_outline["answer_completeness"] = answer_completeness
        metrics["answer_completeness"] = answer_completeness
        trust_decision = _make_context_trust_decision(
            question=question,
            context_pack=context_pack,
            project_docs=project_docs,
            dependency_docs=dependency_docs,
            source_evidence_items=source_evidence_items,
            relevance_gate=relevance_gate,
            answer_available=answer_available,
            answer_type=answer_type,
            source_search_required=bool(answer_completeness.get("source_search_required")),
            completeness_reason_codes=list(answer_completeness.get("reason_codes") or []),
            intent=intent,
        )
        diagnostics["trust_decision"] = {
            "answer_available": trust_decision.answer_available,
            "reason": trust_decision.reason,
            "confidence": trust_decision.confidence,
            "passed_relevance_gate": trust_decision.passed_relevance_gate,
            "max_project_score": trust_decision.max_project_score,
            "query_terms_matched": trust_decision.query_terms_matched,
            "query_terms_missing": trust_decision.query_terms_missing,
        }
        answer_available = trust_decision.answer_available
        status = "success" if answer_available else (project_docs.status if project_docs else dependency_docs.status if dependency_docs else "no_results")
        if not answer_available and trust_decision.reason == "no_reliable_context" and _is_low_signal_single_token_query(question):
            status = "no_results"
        if (project_docs and project_docs.status == "stale") or (dependency_docs and dependency_docs.stale_before_refresh):
            status = "stale"
        if dependency_confirmation and not answer_available and status != "stale":
            status = "confirmation_required"
        elif requires_confirmation and not answer_available and status != "stale":
            status = "confirmation_required"
        reason = trust_decision.reason
        if dependency_confirmation and not answer_available:
            reason = "dependency_docs_network_fetch_required"
        elif getattr(intent, "wants_code_symbols", False) and trust_decision.confidence != "trusted":
            reason = "insufficient_code_symbol_evidence"
        message = "Returned project context with Trust Contract." if answer_available else (project_docs.message if project_docs else "No trusted context matched this question.")
        if answer_available and answer_type == "partial_navigational":
            message = "Returned partial/navigational project context; search project source for missing story-specific terms."
        if dependency_confirmation and not answer_available:
            message = f"Dependency docs for {selected_dependency} require network access; retry with allow_network=true after user confirmation."
        return ProjectContextResult(
            project_path=str(root),
            question=question,
            status=status,
            answer_available=answer_available,
            answer_type=answer_type,
            answer_completeness=answer_completeness,
            mode=mode,
            reason=reason,
            context_pack=context_pack,
            project_docs=project_docs,
            dependency_docs=dependency_docs,
            trust_contract=trust_contract,
            warnings=[*warnings, *[warning["code"] for warning in snippet_presentation.warnings]],
            next_actions=next_actions,
            recommended_next_actions=recommended_next_actions,
            next_action=next_action,
            requires_confirmation=requires_confirmation,
            confirmation_reason=confirmation_reason,
            arguments_patch=arguments_patch,
            response_style=snippet_presentation.response_style,
            primary_snippet=snippet_presentation.primary_snippet,
            supporting_snippets=snippet_presentation.supporting_snippets,
            snippet_metrics=snippet_presentation.metrics,
            metrics=metrics,
            diagnostics=diagnostics,
            answer_outline=answer_outline,
            message=message,
        )

    @staticmethod
    def dependency_mentioned_in_question(metadata: ProjectMetadata, question: str) -> str | None:
        normalized_question = question.lower().replace("-", "_")
        for dependency in metadata.dependencies:
            name = dependency.package_name
            if name.lower() in normalized_question or name.lower().replace("-", "_") in normalized_question:
                return name
        return None


def project_context_pack(*, question: str = "", project_docs: ProjectDocsResult | None, dependency_docs: DocsResult | None) -> list[dict[str, Any]]:
    pack: list[dict[str, Any]] = []
    if project_docs:
        for item in project_docs.results:
            if _drop_low_value_context_section(item.content, item.title, item.heading_path):
                continue
            token_estimate = max(1, len(item.content) // 4) if item.content else 0
            freshness = "stale" if item.stale else "current"
            source_taxonomy = project_source_taxonomy(item.path, doc_scope=item.doc_scope, module_path=item.module_path)
            if _should_skip_low_trust_project_source(question, source_taxonomy):
                continue
            pack.append({
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
                "path": item.path,
                "url": item.url,
                "title": item.title,
                "heading_path": item.heading_path,
                "freshness": freshness,
                "why_selected": project_why_selected(item),
                "content": item.content,
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
    source_search_required: bool,
    completeness_reason_codes: list[str],
    intent: Any,
) -> ContextTrustDecision:
    max_project_score = _max_project_ranking_score(project_docs)
    matched_terms = list(relevance_gate.get("matched_terms") or [])
    missing_terms = list(relevance_gate.get("missing_terms") or relevance_gate.get("required_terms") or [])
    passed = bool(relevance_gate.get("passed"))

    if _is_low_signal_single_token_query(question):
        return ContextTrustDecision(False, "no_reliable_context", "low", passed, max_project_score, matched_terms, missing_terms)

    has_dependency_answer = bool(dependency_docs and dependency_docs.results)
    has_source_evidence = any(item.get("evidence_class") == "source_snippet" for item in source_evidence_items)
    has_strong_project_answer = bool(project_docs and project_docs.answer_available and _score_is_strong(max_project_score))
    source_search_is_simple_relevance_gap = (
        source_search_required
        and not getattr(intent, "wants_code_symbols", False)
        and "high_signal_query_terms_missing_from_context" in completeness_reason_codes
    )
    if answer_available and passed and (has_dependency_answer or has_source_evidence or (has_strong_project_answer and (not source_search_required or source_search_is_simple_relevance_gap))):
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


def _normalize_gate_text(value: str | None) -> str:
    text = (value or "").replace("\\", "/").lower().replace("-", "_")
    return re.sub(r"\s+", " ", text)


def _repo_map_token_budget(tokens: int | None) -> int:
    if not tokens:
        return 900
    return max(120, min(900, tokens // 4))


def _source_evidence_token_budget(tokens: int | None) -> int:
    if not tokens:
        return 700
    return max(120, min(700, tokens // 5))


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
