from __future__ import annotations

from pathlib import Path
from typing import Any

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
        mode: str = "auto",
    ) -> ProjectContextResult:
        mode = mode.lower()
        if mode not in {"auto", "project-only", "deps-only", "public-docs"}:
            raise ValueError("mode must be one of: auto, project-only, deps-only, public-docs")
        root = Path(project_path).expanduser().resolve()
        metadata = self.facade.read_project_metadata(str(root))
        project_docs = None
        if mode in {"auto", "project-only"}:
            project_docs = self.facade.get_project_docs(str(root), question, tokens=tokens, limit=limit, expand=expand)

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
        context_pack = project_context_pack(project_docs=project_docs, dependency_docs=dependency_docs)
        metrics = project_context_metrics(context_pack=context_pack, project_docs=project_docs, dependency_docs=dependency_docs)
        answer_available = bool(project_docs and project_docs.answer_available) or bool(dependency_docs and dependency_docs.results)
        status = "success" if answer_available else (project_docs.status if project_docs else dependency_docs.status if dependency_docs else "no_results")
        if (project_docs and project_docs.status == "stale") or (dependency_docs and dependency_docs.stale_before_refresh):
            status = "stale"
        reason = "trusted_context_available" if answer_available else "no_trusted_context"
        return ProjectContextResult(
            project_path=str(root),
            question=question,
            status=status,
            answer_available=answer_available,
            mode=mode,
            reason=reason,
            context_pack=context_pack,
            project_docs=project_docs,
            dependency_docs=dependency_docs,
            trust_contract=trust_contract,
            warnings=warnings,
            next_actions=next_actions,
            metrics=metrics,
            message="Returned project context with Trust Contract." if answer_available else (project_docs.message if project_docs else "No trusted context matched this question."),
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
            token_estimate = max(1, len(item.content) // 4) if item.content else 0
            pack.append({
                "source_class": "project_doc",
                "path": item.path,
                "url": item.url,
                "title": item.title,
                "heading_path": item.heading_path,
                "freshness": "stale" if item.stale else "current",
                "why_selected": "matches repo-owned project documentation for the question",
                "content": item.content,
                "token_estimate": token_estimate,
            })
            snippet = context_pack_snippet(item)
            if snippet:
                pack[-1]["snippet"] = snippet
                pack[-1]["surrounding_context"] = item.content
    if dependency_docs:
        for item in dependency_docs.results:
            token_estimate = max(1, len(item.content) // 4) if item.content else 0
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
                "source": item.source,
                "title": item.title,
                "freshness": "stale" if dependency_docs.stale_before_refresh else "current",
                "why_selected": "dependency docs resolved through Docmancer registry/project metadata",
                "content": item.content,
                "token_estimate": token_estimate,
            })
            snippet = context_pack_snippet(item)
            if snippet:
                pack[-1]["snippet"] = snippet
                pack[-1]["surrounding_context"] = item.content
    return pack


def context_pack_snippet(item: DocsChunk) -> dict[str, Any] | None:
    metadata = item.metadata or {}
    snippets = metadata.get("code_snippets") or []
    snippet = snippets[0] if snippets and isinstance(snippets[0], dict) else None
    if not snippet:
        return None
    code = str(snippet.get("code") or "").strip()
    if not code:
        return None
    language = str(snippet.get("language") or "").strip() or None
    title = item.title or metadata.get("title") or "section"
    return {
        "language": language,
        "code": code,
        "why_relevant": f"code example extracted from matching {title} section",
    }


def project_context_metrics(
    *,
    context_pack: list[dict[str, Any]],
    project_docs: ProjectDocsResult | None,
    dependency_docs: DocsResult | None,
) -> dict[str, Any]:
    source_classes = [item.get("source_class") for item in context_pack]
    return {
        "context_pack_items": len(context_pack),
        "selected_source_count": len(context_pack),
        "project_result_count": len(project_docs.results) if project_docs else 0,
        "dependency_result_count": len(dependency_docs.results) if dependency_docs else 0,
        "token_estimate": sum(int(item.get("token_estimate") or 0) for item in context_pack),
        "source_classes": sorted({str(item) for item in source_classes if item}),
    }
