from __future__ import annotations

import dataclasses
import re
from collections import Counter
from dataclasses import replace
from typing import Any

from docmancer.docs.domain.quality import has_code_symbol_evidence, internal_noise_score


CHANGELOG_FILENAMES = {"changelog", "changelog.md", "changes", "changes.md", "history", "history.md"}
PROJECT_MODULE_ROOTS = {"packages", "apps", "services", "modules", "libs", "crates", "plugins", "components"}
GENERATED_REVIEW_FILENAMES = {"review_summary.md", "constraints.md", "review_summary_quality.json", "review_summary_actions.json", "review_summary_manifest.json"}


def normalize_doc_path(path: str | None) -> str:
    return (path or "").replace("\\", "/").lower().strip()

def normalize_doc_path_for_match(path: str | None) -> str:
    """Like normalize_doc_path but treats _ and - as equivalent for matching."""
    return normalize_doc_path(path).replace("-", "_")


def basename(path: str | None) -> str:
    return normalize_doc_path(path).rsplit("/", 1)[-1]


def is_changelog_path(path: str | None) -> bool:
    name = basename(path)
    return name in CHANGELOG_FILENAMES or name.startswith("changelog.")


def project_source_taxonomy(path: str | None, *, doc_scope: str | None = None, module_path: str | None = None) -> dict[str, Any]:
    """Classify project-doc source authority without excluding it from retrieval."""
    p = normalize_doc_path(path)
    parts = [part for part in p.split("/") if part]
    name = parts[-1] if parts else ""
    risk_flags: list[str] = []
    if p.startswith("docs/research/") or "/research/" in p:
        risk_flags.append("research_artifact")
    if "docatlas-dogfood" in p or "dogfood" in p:
        risk_flags.append("dogfood_artifact")
    if "patch-review" in p or ".docatlas/patch-review" in p:
        risk_flags.append("patch_review_artifact")
    if name in GENERATED_REVIEW_FILENAMES:
        risk_flags.append("generated_review_output")

    if "patch_review_artifact" in risk_flags:
        return {"source_type": "patch_review_artifact", "source_kind": "patch_review_artifact", "authority": "artifact", "risk_flags": risk_flags}
    if "dogfood_artifact" in risk_flags:
        return {"source_type": "dogfood_artifact", "source_kind": "dogfood_artifact", "authority": "artifact", "risk_flags": risk_flags}
    if "research_artifact" in risk_flags:
        return {"source_type": "research", "source_kind": "research", "authority": "research", "risk_flags": risk_flags}

    module_doc = bool(doc_scope == "module" or module_path or (parts and parts[0] in PROJECT_MODULE_ROOTS))
    if is_changelog_path(p):
        return {"source_type": "changelog", "source_kind": "changelog", "authority": "historical", "risk_flags": []}
    if name.startswith("architecture.") or name in {"architecture.md", "architecture.mdx", "arch.md", "arch.mdx"} or "architecture" in parts:
        source_type = "package_architecture" if module_doc else "architecture"
        authority = "secondary" if module_doc else "primary"
        return {"source_type": source_type, "source_kind": source_type, "authority": authority, "risk_flags": []}
    if p == "docs/index.md" or p == "doc/index.md" or (len(parts) == 2 and parts[0] in {"docs", "doc"} and name.startswith("index.")):
        return {"source_type": "index", "source_kind": "index", "authority": "primary", "risk_flags": []}
    if (parts and parts[0] in {"adr", "adrs"}) or "adr" in parts or "adrs" in parts:
        return {"source_type": "adr", "source_kind": "adr", "authority": "primary", "risk_flags": []}
    if (parts and parts[0] in {"runbook", "runbooks"}) or "runbook" in parts or "runbooks" in parts:
        return {"source_type": "runbook", "source_kind": "runbook", "authority": "primary", "risk_flags": []}
    if name.endswith("readme.md") or name.startswith("readme."):
        source_type = "package_readme" if module_doc else "readme"
        authority = "secondary" if module_doc else "primary"
        return {"source_type": source_type, "source_kind": source_type, "authority": authority, "risk_flags": []}
    if p.startswith("docs/") or "/docs/" in p:
        return {"source_type": "docs", "source_kind": "docs", "authority": "supporting", "risk_flags": []}
    if p.startswith("wiki/") or "/wiki/" in p:
        return {"source_type": "wiki", "source_kind": "wiki", "authority": "supporting", "risk_flags": []}
    return {"source_type": "project_doc", "source_kind": "project_doc", "authority": "supporting", "risk_flags": []}


def is_readme_source(chunk: Any) -> bool:
    return normalize_doc_path(getattr(chunk, "path", None)).endswith("readme.md")


def is_specific_docs_mcp_source(chunk: Any) -> bool:
    p = normalize_doc_path(getattr(chunk, "path", None))
    h = (getattr(chunk, "heading_path", None) or "").lower()
    content = (getattr(chunk, "content", None) or "").lower()

    return (
        "mcp-docs" in p
        or "docs-server" in p
        or "/mcp/docs_server" in p
        or "/interfaces/mcp/" in p
        or "docs mcp" in h
        or "documentation mcp server" in h
        or "docs mcp runtime" in h
        or "docs-serve" in h
        or "docs-serve" in content[:500]
    )


def is_specific_packs_mcp_source(chunk: Any) -> bool:
    p = normalize_doc_path(getattr(chunk, "path", None))
    h = (getattr(chunk, "heading_path", None) or "").lower()
    content = (getattr(chunk, "content", None) or "").lower()

    return (
        "mcp-packs" in p
        or "mcp packs" in h
        or "action packs" in h
        or "install-pack" in h
        or "packs-serve" in content[:500]
        or "mcp serve" in content[:500]
    )


def _source_key(chunk: Any, idx: int | None = None) -> str:
    path = normalize_doc_path(getattr(chunk, "path", None))
    if path:
        return path
    return f"unknown:{idx}" if idx is not None else "unknown"


def has_project_structure_terms(question: str) -> bool:
    q = (question or "").lower()
    return any(term in q for term in ["project structure", "structured", "layout", "folders", "directories", "tree", "codebase", "where is"])


def source_weight_for_intent(path: str | None, heading_path: str | None, intent: Any) -> float:
    p = normalize_doc_path(path)
    h = (heading_path or "").lower()
    name = getattr(intent, "name", "general")
    taxonomy = project_source_taxonomy(p)
    source_type = taxonomy["source_type"]
    authority = taxonomy["authority"]

    if authority == "artifact":
        artifact_sensitive = getattr(intent, "broad", False) or getattr(intent, "wants_architecture", False) or getattr(intent, "wants_how_to", False) or getattr(intent, "wants_docs_mcp", False)
        return 0.25 if artifact_sensitive else 0.6
    if source_type == "research" and (getattr(intent, "broad", False) or getattr(intent, "wants_architecture", False) or getattr(intent, "wants_how_to", False)):
        return 0.45

    if is_changelog_path(p):
        return 1.8 if getattr(intent, "wants_release_history", False) else 0.05

    if getattr(intent, "wants_code_symbols", False):
        if p.endswith(".py") or ".py" in h:
            return 2.0
        if p.startswith("wiki/"):
            return 0.15

    if name == "ingestion_internals":
        if "architecture" in p and any(term in h for term in ["ingest", "index", "retriev"]):
            return 1.65
        if source_type == "index":
            return 1.45
        if p.endswith("readme.md"):
            return 1.25
        if p.startswith("docs/") or "/docs/" in p:
            return 1.3
        return 1.0

    if name in {"how_to", "ingestion_how_to"}:
        if source_type == "index":
            return 1.5
        if p.endswith("readme.md"):
            return 1.45
        if p.startswith("docs/") or "/docs/" in p:
            return 1.4
        if p.startswith("wiki/") or "/wiki/" in p:
            return 1.15
        if "architecture" in p and any(term in h for term in ["ingest", "index", "retriev"]):
            return 1.35

    if name == "docs_mcp":
        if source_type == "index":
            return 1.5
        if "mcp-docs" in p or "docs-server" in p or "docs_mcp" in p or "/mcp/docs_server" in p or "/interfaces/mcp/" in p:
            return 1.7
        if p.endswith("readme.md"):
            return 1.5
        if "architecture" in p and "docs mcp" in h:
            return 1.55
        if "mcp-packs" in p:
            return 0.2

    if name == "packs_mcp":
        if "mcp-packs" in p:
            return 2.0
        if p.endswith("readme.md"):
            return 1.1
        if "docs" in p and "docs serve" in h:
            return 0.65

    if name == "mcp_disambiguation":
        if source_type == "architecture" and "mcp" in h:
            return 1.55
        if source_type == "index":
            return 1.45
        if p.endswith("readme.md"):
            return 1.6
        if "mcp-docs" in p or "mcp-packs" in p:
            return 1.35
        if "architecture" in p and "mcp" in h:
            return 1.3
        if "/mcp/docs_server" in p or "/interfaces/mcp/" in p:
            return 1.3

    if name == "troubleshooting":
        if p.endswith("readme.md") or p.startswith("docs/") or "/docs/" in p:
            return 1.25

    if name == "release_history":
        return 1.0

    if getattr(intent, "wants_architecture", False) or name == "architecture":
        if source_type == "architecture":
            return 2.0
        if source_type == "index":
            return 1.8
        if source_type in {"adr", "runbook"}:
            return 1.5
        if source_type in {"package_architecture", "package_readme"}:
            return 1.2
        if "architecture" in p or "architecture" in h:
            return 1.7
        if p.endswith("readme.md"):
            return 1.4
        if p.endswith("contributing.md"):
            return 1.35
        if p.startswith("docs/") or "/docs/" in p:
            return 1.15
        if p.startswith("wiki/") or "/wiki/" in p:
            return 1.2
    return 1.0


def source_requirement_boost(path: str | None, question: str, intent: Any) -> float:
    p = normalize_doc_path(path)
    taxonomy = project_source_taxonomy(p)
    if query_requests_artifact_sources(question) and taxonomy["source_type"] in {"research", "dogfood_artifact", "patch_review_artifact"}:
        return 16.0
    if has_project_structure_terms(question):
        if p.endswith("contributing.md"):
            return 2.2
        if p.endswith("readme.md"):
            return 1.5
    if getattr(intent, "wants_architecture", False):
        if "architecture" in p:
            return 1.6
        if p.endswith("readme.md"):
            return 1.3
    return 1.0


def query_requests_artifact_sources(question: str) -> bool:
    q = (question or "").lower().replace("_", "-")
    return any(
        term in q
        for term in [
            "dogfood",
            "docatlas-dogfood",
            "research",
            "artifact",
            "artifacts",
            "patch-review",
            "patch review",
            "review summary",
            "experiment",
            "evaluation",
        ]
    )


def query_requests_history(question: str) -> bool:
    q = " ".join((question or "").lower().split())
    if any(phrase in q for phrase in ("previous plan", "old plan", "past decision")):
        return True
    if re.search(r"\bhistorical\b", q):
        return True
    if re.search(r"\bhistory\s+(?:of|for)\b", q):
        return True
    if re.search(
        r"\b(?:project|repository|decision|release|roadmap|plan)\s+history\b",
        q,
    ):
        return True
    return bool(
        re.search(
            r"\b(?:completed|superseded)\s+(?:roadmap|plan|task|document|docs?)\b"
            r"|\b(?:roadmap|plan|task|document|docs?)\s+(?:completed|superseded)\b",
            q,
        )
    )


def source_weight_reason(path: str | None, heading_path: str | None, intent: Any) -> str:
    """Human-readable reason for source weighting in project-doc ranking."""
    p = normalize_doc_path(path)
    h = (heading_path or "").lower()
    name = getattr(intent, "name", "general")
    taxonomy = project_source_taxonomy(p)
    if taxonomy["authority"] == "artifact":
        return "demoted as generated/research artifact context for ordinary project-doc questions"
    if taxonomy["source_type"] == "research":
        return "demoted as research context unless the query explicitly asks for research/history artifacts"

    if is_changelog_path(p):
        if getattr(intent, "wants_release_history", False):
            return "boosted because the query asks about recent changes or release history"
        return "demoted because CHANGELOG.md is not primary evidence for this non-release query"

    if getattr(intent, "wants_code_symbols", False):
        if p.endswith(".py") or ".py" in h:
            return "boosted because the query asks for concrete code symbols or files"
        if p.startswith("wiki/"):
            return "demoted because generic wiki context is insufficient for code-symbol queries"

    if name == "ingestion_internals":
        if any(term in h for term in ["ingest", "index", "retriev"]):
            return "boosted because the section heading matches ingestion/indexing/retrieval intent"
        if p.endswith("readme.md") or p.startswith("docs/") or "architecture" in p:
            return "boosted as project-doc ingestion/indexing/retrieval implementation evidence"

    if name in {"how_to", "ingestion_how_to"}:
        if any(term in h for term in ["ingest", "index", "retriev"]):
            return "boosted because the section heading matches ingestion/indexing/retrieval intent"
        if p.endswith("readme.md") or p.startswith("docs/") or "architecture" in p:
            return "boosted as practical implementation/usage evidence for the how-to query"

    if name == "docs_mcp":
        if "mcp-docs" in p or "docs-server" in p or "docs_mcp" in p:
            return "boosted because this is the Docs MCP server source"
        if "mcp-packs" in p:
            return "demoted because the query asks about Docs MCP, not MCP Packs"

    if name == "packs_mcp":
        if "mcp-packs" in p:
            return "boosted because this is the MCP Packs/API-action runtime source"

    if name == "mcp_disambiguation":
        if taxonomy["source_type"] in {"architecture", "index"}:
            return "boosted as authoritative architecture/index evidence for MCP workflow disambiguation"
        if "mcp" in p or "mcp" in h or p.endswith("readme.md"):
            return "included to disambiguate Docs MCP server from MCP Packs runtime"

    if name == "troubleshooting":
        return "boosted as troubleshooting or operational evidence"

    if name == "release_history":
        return "ranked as supplementary release-history context"

    if getattr(intent, "wants_architecture", False) or name == "architecture":
        if "architecture" in p or "architecture" in h:
            return "boosted as architecture evidence for an architecture/project-structure query"
        if p.endswith("readme.md"):
            return "boosted as high-level overview evidence for a broad architecture query"
        if p.endswith("contributing.md"):
            return "boosted as project-structure and extension-point evidence"
    return "ranked by lexical/vector relevance with neutral source weighting"


def requirement_boost_reason(path: str | None, question: str, intent: Any) -> str | None:
    p = normalize_doc_path(path)
    taxonomy = project_source_taxonomy(p)
    if query_requests_artifact_sources(question) and taxonomy["source_type"] in {"research", "dogfood_artifact", "patch_review_artifact"}:
        return "explicitly requested research/dogfood/history artifact context"
    if has_project_structure_terms(question):
        if p.endswith("contributing.md"):
            return "required for project-structure coverage"
        if p.endswith("readme.md"):
            return "required for high-level project overview coverage"
    if getattr(intent, "wants_architecture", False):
        if "architecture" in p:
            return "required for architecture coverage"
        if p.endswith("readme.md"):
            return "required for overview coverage alongside architecture docs"
    return None


def attach_project_ranking_metadata(chunk: Any, *, base_score: float, final_score: float, original_rank: int, selected_rank: int, question: str, intent: Any, selected_by: str, diversity_relaxed: bool = False) -> Any:
    """Return chunk annotated with ranking diagnostics when it supports metadata."""
    metadata = getattr(chunk, "metadata", None)
    if metadata is None:
        metadata = {}
    elif isinstance(metadata, dict):
        metadata = dict(metadata)
    else:
        return chunk
    path = getattr(chunk, "path", None)
    heading_path = getattr(chunk, "heading_path", None)
    taxonomy = project_source_taxonomy(
        path,
        doc_scope=getattr(chunk, "doc_scope", None),
        module_path=getattr(chunk, "module_path", None),
    )
    reasons = [source_weight_reason(path, heading_path, intent)]
    boost = requirement_boost_reason(path, question, intent)
    if boost:
        reasons.append(boost)
    if getattr(intent, "broad", False):
        reasons.append("source diversity cap applied for this broad query")
    if selected_by == "broad_source_injection":
        reasons.append("included to satisfy broad-query source coverage")
    if diversity_relaxed:
        reasons.append("source diversity cap relaxed only after strict backfill could not fill the requested limit")
    ranking = {
        "query_intent": getattr(intent, "name", "general"),
        "base_score": base_score,
        "final_score": final_score,
        "original_rank": original_rank,
        "selected_rank": selected_rank,
        "source_weight_reason": reasons[0],
        "requirement_reason": boost,
        "selected_by": selected_by,
        "diversity_relaxed": diversity_relaxed,
        "reasons": reasons,
    }
    metadata["project_ranking"] = ranking
    metadata["project_source"] = taxonomy

    if hasattr(chunk, "model_copy"):
        return chunk.model_copy(update={"metadata": metadata})

    if dataclasses.is_dataclass(chunk):
        if any(field.name == "metadata" for field in dataclasses.fields(chunk)):
            return replace(chunk, metadata=metadata)
        return chunk

    try:
        setattr(chunk, "metadata", metadata)
        return chunk
    except Exception:
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
    q = (question or "").lower()
    asks_internals = any(term in q for term in ["source", "internals", "internal", "implementation", "bug", "todo", "fixme"])
    return asks_internals and not getattr(intent, "wants_how_to", False)


def find_replaceable_index(selected: list[Any]) -> int | None:
    for index in range(len(selected) - 1, -1, -1):
        if is_changelog_path(getattr(selected[index], "path", None)):
            return index
    seen: set[str] = set()
    for index in range(len(selected) - 1, -1, -1):
        path = normalize_doc_path(getattr(selected[index], "path", None))
        if path in seen:
            return index
        seen.add(path)
    return len(selected) - 1 if selected else None


def ensure_broad_query_sources(selected: list[Any], candidates: list[Any], *, question: str, intent: Any, limit: int | None) -> list[Any]:
    has_source_requirements = getattr(intent, "broad", False) or getattr(intent, "wants_docs_mcp", False) or getattr(intent, "wants_packs_mcp", False)
    if not has_source_requirements:
        return selected
    required_predicates = []
    if getattr(intent, "wants_architecture", False):
        required_predicates.append(lambda c: "architecture" in normalize_doc_path(getattr(c, "path", None)))
    if has_project_structure_terms(question):
        required_predicates.append(lambda c: normalize_doc_path(getattr(c, "path", None)).endswith("contributing.md"))
    if getattr(intent, "broad", False):
        required_predicates.append(is_readme_source)
    if getattr(intent, "wants_docs_mcp", False):
        required_predicates.append(is_specific_docs_mcp_source)
    if getattr(intent, "wants_packs_mcp", False):
        required_predicates.append(is_specific_packs_mcp_source)

    selected_ids = {id(c) for c in selected}
    for predicate in required_predicates:
        if any(predicate(c) for c in selected):
            continue
        candidate = next((c for c in candidates if predicate(c) and id(c) not in selected_ids), None)
        if candidate is None:
            continue
        if limit and len(selected) >= limit:
            replace_index = find_replaceable_index(selected)
            if replace_index is not None:
                selected_ids.discard(id(selected[replace_index]))
                selected[replace_index] = candidate
                selected_ids.add(id(candidate))
        else:
            selected.append(candidate)
            selected_ids.add(id(candidate))
    return selected[:limit] if limit else selected


def rerank_project_doc_chunks(chunks: list[Any], *, question: str, intent: Any, limit: int | None = None, broad_max_per_source: int = 2, narrow_max_per_source: int = 4) -> list[Any]:
    if not chunks:
        return []
    history_requested = query_requests_history(question)
    chunks = [
        chunk
        for chunk in chunks
        if (
            (getattr(chunk, "lifecycle_status", None) or "active") == "active"
            or history_requested
        )
        and not bool(getattr(chunk, "stale", False))
    ]
    if not chunks:
        return []
    scored = []
    score_by_id: dict[int, tuple[float, float, int]] = {}
    for index, chunk in enumerate(chunks):
        path = getattr(chunk, "path", None)
        base = chunk_base_score(chunk, index)
        score = base * source_weight_for_intent(path, getattr(chunk, "heading_path", None), intent) * source_requirement_boost(path, question, intent)
        description = str(getattr(chunk, "description", None) or "")
        query_terms = set(re.findall(r"[\w-]+", question.lower()))
        description_terms = set(re.findall(r"[\w-]+", description.lower()))
        description_overlap = query_terms & description_terms
        if description_overlap:
            score *= 1.0 + min(1.0, 0.2 * len(description_overlap))
        authority = str(getattr(chunk, "authority", None) or "")
        score *= {
            "source_of_truth": 1.5,
            "supporting": 1.0,
            "historical": 0.45,
            "generated": 0.3,
        }.get(authority, 1.0)
        if getattr(intent, "wants_code_symbols", False):
            if has_code_symbol_evidence(getattr(chunk, "content", ""), getattr(chunk, "title", None), getattr(chunk, "heading_path", None), path):
                score *= 2.5
            else:
                score *= 0.2
        noise = internal_noise_score(getattr(chunk, "content", ""))
        if noise >= 0.5 and getattr(intent, "wants_how_to", False) and not _query_allows_internal_noise(question, intent):
            score *= 0.2
        scored.append((score, index, chunk))
        score_by_id[id(chunk)] = (base, score, index)
    scored.sort(key=lambda row: (-row[0], row[1]))

    max_per_source = broad_max_per_source if getattr(intent, "broad", False) else narrow_max_per_source
    selected: list[Any] = []
    per_source_count: dict[str, int] = {}
    for _, index, chunk in scored:
        path = _source_key(chunk, index)
        if per_source_count.get(path, 0) >= max_per_source:
            continue
        selected.append(chunk)
        per_source_count[path] = per_source_count.get(path, 0) + 1
        if limit and len(selected) >= limit:
            break
    pre_injection_ids = {id(c) for c in selected}
    selected = ensure_broad_query_sources(selected, [chunk for _, _, chunk in scored], question=question, intent=intent, limit=limit)
    diversity_relaxed_ids: set[int] = set()
    if limit and len(selected) < limit:
        selected_ids = {id(c) for c in selected}
        selected_counts = Counter(_source_key(c) for c in selected)
        for _, index, chunk in scored:
            if len(selected) >= limit:
                break
            if id(chunk) not in selected_ids:
                source_key = _source_key(chunk, index)
                if selected_counts[source_key] >= max_per_source:
                    continue
                selected.append(chunk)
                selected_ids.add(id(chunk))
                selected_counts[source_key] += 1
        unique_candidate_sources = {_source_key(chunk, index) for _, index, chunk in scored}
        may_relax_diversity = not getattr(intent, "broad", False) or len(unique_candidate_sources) <= 1
        if len(selected) < limit and may_relax_diversity:
            for _, _, chunk in scored:
                if len(selected) >= limit:
                    break
                if id(chunk) not in selected_ids:
                    selected.append(chunk)
                    selected_ids.add(id(chunk))
                    diversity_relaxed_ids.add(id(chunk))
    annotated = []
    for selected_rank, chunk in enumerate(selected, start=1):
        base, score, original_rank = score_by_id.get(id(chunk), (chunk_base_score(chunk, selected_rank - 1), 0.0, selected_rank - 1))
        selected_by = "ranking"
        if id(chunk) not in pre_injection_ids and getattr(intent, "broad", False):
            selected_by = "broad_source_injection"
        annotated.append(attach_project_ranking_metadata(chunk, base_score=base, final_score=score, original_rank=original_rank, selected_rank=selected_rank, question=question, intent=intent, selected_by=selected_by, diversity_relaxed=id(chunk) in diversity_relaxed_ids))
    return annotated
