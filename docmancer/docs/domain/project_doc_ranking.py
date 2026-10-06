"""Lexical project ranking without topic-derived boosts or source promotion."""
from __future__ import annotations

import dataclasses
from dataclasses import replace
from typing import Any

from docmancer.docs.domain.lifecycle_policy import lifecycle_allows, lifecycle_intent
from docmancer.docs.domain.documentation_query_plan import technical_anchors


def normalize_doc_path(path: str | None) -> str:
    return (path or "").replace("\\", "/").lower().strip()


def normalize_doc_path_for_match(path: str | None) -> str:
    return normalize_doc_path(path).replace("-", "_")


def basename(path: str | None) -> str:
    return normalize_doc_path(path).rsplit("/", 1)[-1]


def is_changelog_path(path: str | None) -> bool:
    return False


def condition_lead_priority(question: str, snippet: str) -> int:
    return 0


def project_question_lane(question: str) -> str:
    return "operational"


def project_source_lane(path: str | None) -> str:
    # Retained exclusion boundaries, not query-to-topic mappings. No question
    # phrasing can grant an exemption to these artifact/history lanes.
    p = normalize_doc_path(path)
    if p.startswith(("eval/", "docs/analysis/")):
        return "evaluation"
    if p.startswith((".hermes/plans/", "roadmap/")) or "/roadmap/" in p:
        return "planning"
    if p.startswith(("archive/", "legacy/")) or "/archive/" in p or "/legacy/" in p:
        return "history"
    if basename(p) in {"changelog", "changelog.md", "changes", "changes.md", "history", "history.md"} or basename(p).startswith("changelog."):
        return "history"
    return "operational"


def source_lane_allowed(path: str | None, question: str, *, impact_policy: str | None = None) -> bool:
    # No prose-derived exemption for artifacts. Explicit catalog impact policy
    # can only restrict selection, never promote an unverified source.
    return (project_source_lane(path) == "operational"
            and impact_policy not in {"evaluation", "planning", "history"})


def project_source_taxonomy(path: str | None, *, doc_scope: str | None = None,
                            module_path: str | None = None) -> dict[str, Any]:
    # Filename/topic guesses cannot assign primary authority. Callers must use
    # catalog/source metadata for authority and source-specific trust checks.
    p = normalize_doc_path(path)
    # Missing answer authority is not an instruction-risk finding. Ordinary
    # repo-owned docs can be quoted as untrusted data without becoming proof.
    # Actual source/catalog risk flags are merged and checked by the caller.
    risk_flags = []
    if p.startswith("docs/research/") or "/research/" in p:
        risk_flags.append("research_artifact")
    if "dogfood" in p:
        risk_flags.append("dogfood_artifact")
    if "patch-review" in p:
        risk_flags.append("patch_review_artifact")
    if basename(p) in {"review_summary.md", "constraints.md", "review_summary_quality.json",
                       "review_summary_actions.json", "review_summary_manifest.json"}:
        risk_flags.append("generated_review_output")
    source_type = "project_doc"
    if "patch_review_artifact" in risk_flags:
        source_type = "patch_review_artifact"
    elif "dogfood_artifact" in risk_flags:
        source_type = "dogfood_artifact"
    elif "research_artifact" in risk_flags:
        source_type = "research"
    return {"source_type": source_type, "source_kind": source_type,
            "authority": "unknown", "risk_flags": risk_flags}


def is_readme_source(chunk: Any) -> bool:
    return False


def is_specific_docs_mcp_source(chunk: Any) -> bool:
    return False


def is_specific_packs_mcp_source(chunk: Any) -> bool:
    return False


def _source_key(chunk: Any, idx: int | None = None) -> str:
    return normalize_doc_path(getattr(chunk, "path", None)) or f"unknown:{idx}"


def has_project_structure_terms(question: str) -> bool:
    return False


def source_weight_for_intent(path: str | None, heading_path: str | None, intent: Any) -> float:
    return 1.0


def source_requirement_boost(path: str | None, question: str, intent: Any) -> float:
    return 1.0


def query_requests_artifact_sources(question: str) -> bool:
    return False


def query_requests_history(question: str) -> bool:
    return False


def source_weight_reason(path: str | None, heading_path: str | None, intent: Any) -> str:
    return "base retrieval score; no topic-derived source weight"


def requirement_boost_reason(path: str | None, question: str, intent: Any) -> str | None:
    return None


def attach_project_ranking_metadata(chunk: Any, *, base_score: float, final_score: float,
        original_rank: int, selected_rank: int, question: str, intent: Any,
        selected_by: str, diversity_relaxed: bool = False) -> Any:
    metadata = getattr(chunk, "metadata", None)
    if metadata is not None and not isinstance(metadata, dict):
        return chunk
    metadata = dict(metadata or {})
    metadata["project_ranking"] = {
        "query_intent": "general", "base_score": base_score, "final_score": final_score,
        "original_rank": original_rank, "selected_rank": selected_rank,
        "source_weight_reason": source_weight_reason(None, None, None),
        "requirement_reason": None, "selected_by": selected_by,
        "diversity_relaxed": diversity_relaxed,
        "reasons": ["independent qualified query coverage and base retrieval score"],
    }
    # Never overwrite real source metadata with an inferred taxonomy.
    if hasattr(chunk, "model_copy"):
        return chunk.model_copy(update={"metadata": metadata})
    if dataclasses.is_dataclass(chunk):
        return replace(chunk, metadata=metadata) if any(
            field.name == "metadata" for field in dataclasses.fields(chunk)) else chunk
    try:
        setattr(chunk, "metadata", metadata)
    except Exception:
        pass
    return chunk


def chunk_base_score(chunk: Any, original_rank: int) -> float:
    for attr in ("score", "rank_score", "rrf_score", "similarity"):
        value = getattr(chunk, attr, None)
        if isinstance(value, (int, float)):
            return float(value)
    metadata = getattr(chunk, "metadata", None) or {}
    for key in ("score", "rank_score", "rrf_score", "similarity"):
        value = metadata.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return 1.0 / (original_rank + 1)


def _query_allows_internal_noise(question: str, intent: Any) -> bool:
    return False


def find_replaceable_index(selected: list[Any]) -> int | None:
    return len(selected) - 1 if selected else None


def ensure_broad_query_sources(selected: list[Any], candidates: list[Any], *,
                               question: str, intent: Any, limit: int | None) -> list[Any]:
    return selected[:limit] if limit else selected


def rerank_project_doc_chunks(chunks: list[Any], *, question: str, intent: Any,
        limit: int | None = None, broad_max_per_source: int = 2,
        narrow_max_per_source: int = 4, lifecycle_intent_value: str | None = None,
        context_candidate_ids: frozenset[int] = frozenset()) -> list[Any]:
    lifecycle = lifecycle_intent_value or lifecycle_intent(question)
    scored = []
    for index, chunk in enumerate(chunks):
        if bool(getattr(chunk, "stale", False)) or not lifecycle_allows({
            "lifecycle_status": getattr(chunk, "lifecycle_status", None) or "active",
        }, lifecycle):
            continue
        if not source_lane_allowed(getattr(chunk, "path", None), question,
                                   impact_policy=getattr(chunk, "impact_policy", None)):
            continue
        metadata = getattr(chunk, "metadata", None) or {}
        matches = metadata.get("retrieval_query_matches") or {}
        qualified = {str(key) for key, trace in matches.items()
            if isinstance(trace, dict) and trace.get("qualified") is True}
        # Failed qualification cannot be rescued by rank. The existing explicit
        # context-candidate channel still undergoes downstream admission guards.
        if "retrieval_query_matches" in metadata and not qualified and id(chunk) not in context_candidate_ids:
            continue
        public = {key for key in qualified if key == "query-original"
                  or key.startswith("query-lookup-")}
        scored.append((chunk_base_score(chunk, index), index, chunk, public))
    scored.sort(key=lambda row: (-row[0], row[1]))
    selected = []
    counts: dict[str, int] = {}
    covered: set[str] = set()
    max_per_source = broad_max_per_source if getattr(intent, "broad", False) else narrow_max_per_source
    while scored:
        next_index = max(range(len(scored)), key=lambda i: (
            len(scored[i][3] - covered), -i,
        ))
        score, index, chunk, public = scored.pop(next_index)
        key = _source_key(chunk, index)
        relaxed = counts.get(key, 0) >= max_per_source
        if relaxed and not public - covered:
            continue
        selected.append(attach_project_ranking_metadata(chunk, base_score=score,
            final_score=score, original_rank=index, selected_rank=len(selected) + 1,
            question=question, intent=intent, selected_by="ranking", diversity_relaxed=relaxed))
        covered.update(public)
        counts[key] = counts.get(key, 0) + 1
        if limit and len(selected) >= limit:
            break
    return selected
