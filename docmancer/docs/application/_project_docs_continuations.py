"""Bounded structural continuations for project-document retrieval.

These helpers preserve provenance only; final source and admission checks
still belong to the existing qualification and projection pipeline.
"""
from __future__ import annotations

from typing import Any


def _starts_markdown_list_item(text: str) -> bool:
    value = str(text or "").lstrip()
    if value.startswith(("- ", "+ ", "* ")):
        return True
    first = value.split(None, 1)[0] if value else ""
    return len(first) > 1 and first[:-1].isdigit() and first[-1] in ".)"


def _structured_continuation_route(anchor: Any, candidate: Any) -> str | None:
    """Return a provenance-only continuation route for adjacent retrieval chunks."""
    left = anchor.metadata or {}
    right = candidate.metadata or {}
    left_span = left.get("char_span") or ()
    right_span = right.get("char_span") or ()
    left_parent = str(left.get("parent_logical_id") or "")
    right_parent = str(right.get("parent_logical_id") or "")
    if (
        len(left_span) != 2 or len(right_span) != 2
        or right_span[0] != left_span[1]
        or not left_parent or left_parent != right_parent
        or candidate.source != anchor.source
    ):
        return None
    left_atom = str(left.get("atom_id") or "")
    right_atom = str(right.get("atom_id") or "")
    if left_atom and left_atom == right_atom:
        return "same_atom_continuation"
    if (
        str(left.get("atom_type") or "") == "list"
        and str(right.get("atom_type") or "") == "list"
        and not _starts_markdown_list_item(str(getattr(candidate, "text", "") or ""))
    ):
        return "same_list_item_continuation"
    return None


def _qualify_same_atom_continuations(chunks: list[Any], query_id: str) -> list[Any]:
    """Carry one qualified canonical probe into its immediate structural continuation.

    Same-atom children retain the historical route. A packed list fragment may
    also bridge an atom-id change only when source/parent spans are contiguous
    and the next list chunk does not start a new list item. This is provenance,
    not semantic proof, and never derives public/original query coverage.
    """
    result = list(chunks)
    anchors = []
    for chunk in result:
        metadata = chunk.metadata or {}
        trace = (metadata.get("retrieval_query_matches") or {}).get(query_id) or {}
        span = metadata.get("char_span") or ()
        if trace.get("qualified") is True and len(span) == 2:
            anchors.append(chunk)
    for anchor in anchors:
        anchor_meta = anchor.metadata or {}
        for index, candidate in enumerate(result):
            route = _structured_continuation_route(anchor, candidate)
            if route is None:
                continue
            metadata = candidate.metadata or {}
            matches = dict(metadata.get("retrieval_query_matches") or {})
            current = dict(matches.get(query_id) or {})
            if current.get("qualified") is True:
                continue
            anchor_trace = dict(
                (anchor_meta.get("retrieval_query_matches") or {}).get(query_id) or {}
            )
            if anchor_trace.get("qualified") is not True:
                continue
            derived = dict(anchor_trace)
            derived.update({
                "qualified": True,
                "qualification_reason": route,
                "qualification_route": route,
                "coverage_kind": "derived",
                "coverage_kinds": ["derived"],
                "derived_from_stable_chunk_id": str(anchor_meta.get("stable_chunk_id") or ""),
                "matched_terms": [],
                "body_matched_terms": [],
                "match_ratio": 0.0,
            })
            matches[query_id] = derived
            updated = dict(metadata)
            updated["retrieval_query_matches"] = matches
            updated["retrieval_query_ids"] = tuple(
                key for key, value in matches.items() if value.get("qualified") is True
            )
            result[index] = candidate.model_copy(update={"metadata": updated})
            break
    return result
def _merge_same_atom_continuations(
    chunks: list[Any], query_id: str, *, max_chars: int = 1024,
) -> list[Any]:
    """Reassemble one immediate structured continuation within the existing cap."""
    result = list(chunks)
    remove: set[int] = set()
    for index, anchor in enumerate(tuple(result)):
        if index in remove:
            continue
        metadata = dict(anchor.metadata or {})
        trace = (metadata.get("retrieval_query_matches") or {}).get(query_id) or {}
        span = metadata.get("char_span") or ()
        if trace.get("qualified") is not True or len(span) != 2:
            continue
        for other_index, candidate in enumerate(result):
            if other_index == index or other_index in remove:
                continue
            route = _structured_continuation_route(anchor, candidate)
            if route is None:
                continue
            other = candidate.metadata or {}
            other_trace = (other.get("retrieval_query_matches") or {}).get(query_id) or {}
            other_span = other.get("char_span") or ()
            if (
                other_trace.get("qualification_route") != route
                or other_trace.get("qualified") is not True
                or len(other_span) != 2
            ):
                continue
            text = f"{anchor.text}{candidate.text}"
            if len(text) > max_chars:
                continue
            metadata["char_span"] = [span[0], other_span[1]]
            for field in ("byte_span", "line_span"):
                left = metadata.get(field) or ()
                right = other.get(field) or ()
                if len(left) == 2 and len(right) == 2:
                    metadata[field] = [left[0], right[1]]
            metadata["reassembled_from_stable_chunk_ids"] = [
                str(metadata.get("stable_chunk_id") or ""),
                str(other.get("stable_chunk_id") or ""),
            ]
            metadata["display_token_estimate"] = int(metadata.get("display_token_estimate") or 0) + int(other.get("display_token_estimate") or 0)
            metadata["token_estimate"] = int(metadata.get("token_estimate") or 0) + int(other.get("token_estimate") or 0)
            result[index] = anchor.model_copy(update={"text": text, "metadata": metadata})
            remove.add(other_index)
            break
    return [chunk for index, chunk in enumerate(result) if index not in remove]
