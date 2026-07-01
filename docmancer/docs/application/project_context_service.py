from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any
import re

from docmancer.docs.application.project_answer_outline import build_project_answer_outline
from docmancer.docs.domain.answer_completeness import evaluate_project_answer_completeness
from docmancer.docs.domain.project_doc_ranking import is_changelog_path, normalize_doc_path, rerank_project_doc_chunks
from docmancer.docs.domain.project_query_intent import classify_project_query_intent
from docmancer.docs.domain.quality import has_code_symbol_evidence, internal_noise_score, is_trivial_section, looks_like_code_or_command
from docmancer.docs.domain.snippets import best_context_pack_snippet, build_snippet_presentation, validate_response_style
from docmancer.docs.domain.source_map import build_project_repo_map, source_map_diagnostics
from docmancer.docs.domain.trust_contract import build_project_context_trust_contract
from docmancer.docs.models import DocsChunk, DocsResult, ProjectContextResult, ProjectDocsResult, ProjectMetadata


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

        selected_dependency = library or (libraries[0] if libraries else None) or self.dependency_mentioned_in_question(metadata, question)
        dependency_docs: DocsResult | None = None
        if selected_dependency and mode in {"auto", "deps-only", "public-docs"}:
            dependency_docs = self.facade.get_docs(
                selected_dependency,
                topic=question,
                tokens=tokens,
                ecosystem=ecosystem,
                version=version,
                project_path=str(root),
            )

        trust_contract = build_project_context_trust_contract(
            project_docs=project_docs,
            dependency_docs=dependency_docs,
            requested_library=selected_dependency,
            mode=mode,
        )
        warnings = [*(project_docs.warnings if project_docs else [])]
        if dependency_docs:
            warnings.extend(dependency_docs.warnings)
        next_actions = [*(project_docs.next_actions if project_docs else [])]
        if dependency_docs:
            next_actions.extend({"tool": dependency_docs.tool, "reason": action} for action in dependency_docs.next_actions)
        requires_confirmation = bool(project_docs and project_docs.requires_confirmation)
        confirmation_reason = project_docs.confirmation_reason if requires_confirmation and project_docs else None
        next_action = project_docs.next_action if requires_confirmation and project_docs else {}
        arguments_patch = project_docs.arguments_patch if requires_confirmation and project_docs else {}
        context_pack = project_context_pack(project_docs=project_docs, dependency_docs=dependency_docs)
        repo_map_items: list[dict[str, Any]] = []
        if mode in {"auto", "project-only"}:
            repo_map_items = build_project_repo_map(
                root,
                question=question,
                max_files=max(1, min(8, limit or 4)),
                token_budget=_repo_map_token_budget(tokens),
            )
            context_pack.extend(repo_map_items)
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
        answer_available = bool(project_docs and project_docs.answer_available) or bool(dependency_docs and dependency_docs.results)
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
                "message": "Selected project docs are partial/navigational for this story-specific question; search project source for missing terms.",
            }
            answer_outline.setdefault("warnings", []).append(warning)
            metrics.setdefault("quality", {}).setdefault("warnings", []).append(warning)
        answer_outline["answer_completeness"] = answer_completeness
        metrics["answer_completeness"] = answer_completeness
        status = "success" if answer_available else (project_docs.status if project_docs else dependency_docs.status if dependency_docs else "no_results")
        if (project_docs and project_docs.status == "stale") or (dependency_docs and dependency_docs.stale_before_refresh):
            status = "stale"
        if requires_confirmation and not answer_available and status != "stale":
            status = "confirmation_required"
        reason = "trusted_context_available" if answer_available else ("insufficient_code_symbol_evidence" if getattr(intent, "wants_code_symbols", False) else "no_trusted_context")
        if answer_available and answer_type in {"partial", "partial_navigational"}:
            reason = answer_type
        message = "Returned project context with Trust Contract." if answer_available else (project_docs.message if project_docs else "No trusted context matched this question.")
        if answer_available and answer_type == "partial_navigational":
            message = "Returned partial/navigational project context; search project source for missing story-specific terms."
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


def project_context_pack(*, project_docs: ProjectDocsResult | None, dependency_docs: DocsResult | None) -> list[dict[str, Any]]:
    pack: list[dict[str, Any]] = []
    if project_docs:
        for item in project_docs.results:
            if _drop_low_value_context_section(item.content, item.title, item.heading_path):
                continue
            token_estimate = max(1, len(item.content) // 4) if item.content else 0
            freshness = "stale" if item.stale else "current"
            pack.append({
                "source_class": "project_doc",
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


def _repo_map_token_budget(tokens: int | None) -> int:
    if not tokens:
        return 900
    return max(120, min(900, tokens // 4))


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
        "token_savings": {
            "raw_docs_tokens": sum(int(((item.metadata or {}).get("raw_tokens") or 0)) for item in (project_docs.results if project_docs else [])),
            "context_pack_tokens": context_tokens,
            "savings_percent": next((item.metadata.get("savings_percent") for item in (project_docs.results if project_docs else []) if item.metadata and item.metadata.get("savings_percent") is not None), None),
            "meaning": "compression_vs_raw_docs_not_relevance_score",
        },
    }
