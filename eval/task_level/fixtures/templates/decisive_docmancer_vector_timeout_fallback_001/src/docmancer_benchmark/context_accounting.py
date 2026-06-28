from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ContextInjectionSummary:
    status: str
    docatlas_retrieval_status: str
    vector_indexing_timed_out: bool
    fallback_used: bool
    fallback_source: str | None
    harness_docatlas_calls: int
    vector_retrieval_success: bool
    context_used: bool
    warnings: tuple[str, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "docatlas_retrieval_status": self.docatlas_retrieval_status,
            "vector_indexing_timed_out": self.vector_indexing_timed_out,
            "fallback_used": self.fallback_used,
            "fallback_source": self.fallback_source,
            "harness_docatlas_calls": self.harness_docatlas_calls,
            "vector_retrieval_success": self.vector_retrieval_success,
            "context_used": self.context_used,
            "warnings": list(self.warnings),
        }


def summarize_context_injection(*, retrieval_error: str | None, context_used: bool) -> ContextInjectionSummary:
    """Summarize DocAtlas context injection metadata for benchmark reports.

    `retrieval_error` is None when DocAtlas project-context retrieval completed.
    When retrieval fails, the harness injects visible project docs as a fallback.
    """
    if retrieval_error is None:
        return ContextInjectionSummary(
            status="success",
            docatlas_retrieval_status="success",
            vector_indexing_timed_out=False,
            fallback_used=False,
            fallback_source=None,
            harness_docatlas_calls=1,
            vector_retrieval_success=True,
            context_used=context_used,
            warnings=(),
        )

    # BUG: fallback is currently counted as successful vector retrieval, and the
    # timeout flag is lost even when the error clearly came from the vector path.
    return ContextInjectionSummary(
        status="success",
        docatlas_retrieval_status="success",
        vector_indexing_timed_out=False,
        fallback_used=True,
        fallback_source="visible_fixture_project_docs",
        harness_docatlas_calls=1,
        vector_retrieval_success=True,
        context_used=context_used,
        warnings=(f"fallback used after DocAtlas retrieval error: {retrieval_error}",),
    )
