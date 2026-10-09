"""Lexical project ranking without topic-derived boosts or source promotion."""
from __future__ import annotations

import dataclasses
from dataclasses import replace
from typing import Any

from docmancer.docs.domain.lifecycle_policy import lifecycle_allows, lifecycle_intent
from docmancer.docs.domain.documentation_query_plan import technical_anchors
from docmancer.docs.domain.literal_context_admission import admit_original_literal_context


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
        context_candidate_ids: frozenset[int] = frozenset(),
        finite_member_paths: frozenset[str] | None = None,
        retain_found_windows: bool = False) -> list[Any]:
    lifecycle = lifecycle_intent_value or lifecycle_intent(question)
    scored = []
    for index, chunk in enumerate(chunks):
        if finite_member_paths is not None and getattr(chunk, "path", None) not in finite_member_paths:
            continue
        if bool(getattr(chunk, "stale", False)) or not lifecycle_allows({
            "lifecycle_status": getattr(chunk, "lifecycle_status", None) or "active",
        }, lifecycle):
            continue
        if finite_member_paths is None and not source_lane_allowed(getattr(chunk, "path", None), question,
                                   impact_policy=getattr(chunk, "impact_policy", None)):
            continue
        metadata = getattr(chunk, "metadata", None) or {}
        matches = metadata.get("retrieval_query_matches") or {}
        qualified = {str(key) for key, trace in matches.items()
            if isinstance(trace, dict) and trace.get("qualified") is True}
        literal_context = None
        if not qualified:
            literal_context = admit_original_literal_context(
                question=question,
                evidence_text=str(getattr(chunk, "content", None) or getattr(chunk, "text", "") or ""),
                candidate={**metadata, "path": getattr(chunk, "path", None) or metadata.get("project_doc_path"),
                           "stale": bool(getattr(chunk, "stale", False))},
                lifecycle_intent=lifecycle,
            )
        # Rank cannot repair failed qualification. A distinct literal body
        # admission is recomputed from source bytes and confers no query credit.
        # The explicit context-candidate channel still reaches downstream guards.
        if "retrieval_query_matches" in metadata and not qualified and literal_context is None and id(chunk) not in context_candidate_ids:
            continue
        public = {key for key in qualified if key == "query-original"
                  or key.startswith("query-lookup-")}
        if retain_found_windows and not public and literal_context is None:
            continue
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
        if relaxed and not public - covered and not retain_found_windows:
            continue
        selected.append(attach_project_ranking_metadata(chunk, base_score=score,
            final_score=score, original_rank=index, selected_rank=len(selected) + 1,
            question=question, intent=intent, selected_by="ranking", diversity_relaxed=relaxed))
        covered.update(public)
        counts[key] = counts.get(key, 0) + 1
        if limit and len(selected) >= limit and not retain_found_windows:
            break
    return selected
class _UnsupportedFoundWindowRetention(ValueError):
    """A synchronous retention invocation did not complete its behavior contract."""


def _retention_arguments(signature, args, kwargs):
    from copy import deepcopy
    bound = signature.bind(*args, **kwargs)
    bound.apply_defaults()
    values = dict(bound.arguments)
    values.update(values.get('kwargs', {}))
    positional = values.get('args', ())
    root = values.get('project_path', values.get('root', positional[0] if len(positional) > 1 else None))
    question = values.get('question', values.get('query', positional[-1] if positional else None))
    excluded = {'self', 'args', 'kwargs', 'project_path', 'root', 'question', 'query',
                'lookup_queries', 'retain_found_windows', '_retention_ack', '_retained_results', '_control_chunks'}
    inputs = deepcopy({key: value for key, value in values.items() if key not in excluded})
    binding = (str(root) if root is not None else None, question,
               tuple(values.get('lookup_queries', ())), inputs, values.get('retain_found_windows') is True)
    sinks = tuple(values.get(key) for key in ('_retained_results', '_control_chunks'))
    return binding, sinks


class _RetentionCompletion:
    """Private call-local behavior check; not permissions or evidence provenance.

    Ordinary wrappers cannot complete another receiver's invocation or substitute
    a different result/sink. Arbitrary Python access to internals is not a security
    boundary. No token or completion data is accepted from returned wire metadata.
    """
    def __init__(self, producer, receiver, binding, sinks):
        self.producer, self.receiver, self.binding, self.sinks = producer, receiver, binding, sinks
        self.active, self.completed = True, False
        self.result = self.snapshot = self.sink_snapshots = None

    def check(self, producer, receiver, binding, sinks):
        if not self.active or self.completed:
            raise _UnsupportedFoundWindowRetention('closed or already completed retention invocation')
        if producer is not self.producer or receiver is not self.receiver or binding != self.binding or not binding[-1]:
            raise _UnsupportedFoundWindowRetention('completion belongs to a different retention invocation')
        if any(left is not right for left, right in zip(sinks, self.sinks, strict=True)):
            raise _UnsupportedFoundWindowRetention('retention output sink was substituted')

    def complete(self, result, producer, receiver, binding, sinks):
        from copy import deepcopy
        self.check(producer, receiver, binding, sinks)
        self.result, self.snapshot = result, deepcopy(result)
        self.sink_snapshots = deepcopy(sinks)
        self.completed = True

    def validate(self, result):
        if not self.active or not self.completed or result is not self.result or result != self.snapshot:
            raise _UnsupportedFoundWindowRetention('returned result did not complete this retention invocation')
        if self.sinks != self.sink_snapshots:
            raise _UnsupportedFoundWindowRetention('completed retention output sink was changed')

    def close(self):
        self.active = False
        self.producer = self.receiver = self.result = self.snapshot = self.sink_snapshots = None
        self.binding = ()
        self.sinks = ()


def _found_window_retention_producer(function):
    """Complete only the actual invocation's result, after normal return."""
    from functools import wraps
    import inspect
    signature = inspect.signature(function)
    @wraps(function)
    def produce(*args, **kwargs):
        token = kwargs.get('_retention_ack')
        # Ordinary calls and deliberate unacknowledged calls retain their input
        # contract; only an ACK-bearing retention invocation needs a snapshot.
        if token is None or kwargs.get('retain_found_windows') is not True:
            return function(*args, **kwargs)
        binding, sinks = _retention_arguments(signature, args, kwargs)
        if binding[-1] and token is not None:
            if type(token) is not _RetentionCompletion:
                raise _UnsupportedFoundWindowRetention('invalid retention completion token')
            receiver = args[0] if 'self' in signature.parameters else None
            token.check(function, receiver, binding, sinks)
        result = function(*args, **kwargs)
        if binding[-1] and token is not None:
            token.complete(result, function, receiver, binding, sinks)
        return result
    return produce


def _invoke_found_window_retention(function, *args, **kwargs):
    """Each delegation owns a fresh token, closed on success and exceptions."""
    import inspect
    if kwargs.get('retain_found_windows') is not True:
        return function(*args, **kwargs)
    parent = kwargs.get('_retention_ack')
    if parent is not None and (type(parent) is not _RetentionCompletion or not parent.active or parent.completed):
        raise _UnsupportedFoundWindowRetention('closed or invalid parent retention completion')
    token = None
    try:
        kwargs = {**kwargs, '_retention_ack': None}
        try:
            binding, sinks = _retention_arguments(inspect.signature(function), args, kwargs)
        except (TypeError, ValueError) as exc:
            raise _UnsupportedFoundWindowRetention('facade lacks the explicit completion interface') from exc
        token = _RetentionCompletion(inspect.unwrap(getattr(function, '__func__', function)),
                                     getattr(function, '__self__', None), binding, sinks)
        kwargs['_retention_ack'] = token
        result = function(*args, **kwargs)
        token.validate(result)
        return result
    finally:
        if token is not None:
            token.close()
