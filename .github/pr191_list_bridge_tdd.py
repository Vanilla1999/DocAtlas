from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

TEST = "tests/docs/test_list_item_continuation_bridge.py"
MANIFEST = "tests/diagnostic_labels.list_item_continuation_bridge.json"


def replace_function(path: str, name: str, next_name: str, replacement: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    start = text.index(f"def {name}(")
    end = text.index(f"\ndef {next_name}(", start)
    p.write_text(text[:start] + replacement.rstrip() + "\n\n" + text[end + 1:], encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise AssertionError(f"{path}: expected one replacement, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def node_digest(module: str) -> str:
    tree = ast.parse(Path(module).read_text(encoding="utf-8"))
    nodes = [
        f"{module}::{node.name}"
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
    ]
    return hashlib.sha256("\n".join(sorted(nodes)).encode()).hexdigest()


def write_tests() -> None:
    Path(TEST).write_text(r'''from docmancer.core.models import RetrievedChunk
from docmancer.docs.application._docs_context_projection_core import _requalify_visible_source
from docmancer.docs.application._project_docs_service_part03 import (
    _merge_same_atom_continuations,
    _qualify_same_atom_continuations,
)


def _cross_atom_list_chunks(next_text="documentary claim unproved. Stop before an edit when hard_stop=true.\n6. Next independent rule."):
    common = {
        "parent_logical_id": "parent-1",
        "project_identity": "project:test",
        "source_class": "project_file",
        "atom_type": "list",
    }
    return [
        RetrievedChunk(
            source="docs/workflow.md", chunk_index=4,
            text="5. If evidence is insufficient, continue locally with source/tests while keeping the ",
            score=2,
            metadata={
                **common, "atom_id": "atom-left", "stable_chunk_id": "child-left",
                "char_span": [100, 181],
                "retrieval_query_matches": {"query-intent-1": {
                    "qualified": True, "relation": "host_lookup",
                }},
                "retrieval_query_ids": ("query-intent-1",),
            },
        ),
        RetrievedChunk(
            source="docs/workflow.md", chunk_index=5, text=next_text, score=1,
            metadata={
                **common, "atom_id": "atom-right", "stable_chunk_id": "child-right",
                "char_span": [181, 181 + len(next_text)],
                "retrieval_query_matches": {"query-intent-1": {"qualified": False}},
                "retrieval_query_ids": (),
            },
        ),
    ]


def test_cross_atom_list_fragment_continues_current_item_when_next_chunk_has_no_marker():
    rows = _qualify_same_atom_continuations(_cross_atom_list_chunks(), "query-intent-1")
    trace = rows[1].metadata["retrieval_query_matches"]["query-intent-1"]
    assert trace["qualified"] is True
    assert trace["qualification_route"] == "same_list_item_continuation"
    assert trace["coverage_kind"] == "derived"


def test_cross_atom_list_fragment_reassembles_for_projection_without_changing_cap():
    qualified = _qualify_same_atom_continuations(_cross_atom_list_chunks(), "query-intent-1")
    rows = _merge_same_atom_continuations(qualified, "query-intent-1")
    assert len(rows) == 1
    assert "documentary claim unproved" in rows[0].text
    assert "hard_stop=true" in rows[0].text
    assert "6. Next independent rule." in rows[0].text
    assert rows[0].metadata["reassembled_from_stable_chunk_ids"] == ["child-left", "child-right"]


def test_cross_atom_list_bridge_never_starts_at_a_new_list_marker():
    rows = _qualify_same_atom_continuations(
        _cross_atom_list_chunks("6. Next independent rule."), "query-intent-1"
    )
    trace = rows[1].metadata["retrieval_query_matches"]["query-intent-1"]
    assert trace["qualified"] is False
    assert len(_merge_same_atom_continuations(rows, "query-intent-1")) == 2


def test_cross_atom_list_continuation_still_rechecks_source_policy():
    source = {
        "path_or_url": "docs/workflow.md", "section": "Workflow",
        "snippet": "documentary claim unproved. Stop before unsafe edits.",
        "catalog_role": "runbook",
        "retrieval_query_matches": {"query-intent-1": {
            "qualified": True, "relation": "host_lookup",
            "qualification_route": "same_list_item_continuation",
            "coverage_kind": "derived", "coverage_kinds": ["derived"],
            "query_text": "insufficient evidence documentation workflow",
        }},
        "retrieval_query_ids": ["query-intent-1"],
        "_independent_query_plan": {"queries": [{
            "query_id": "query-intent-1", "text": "insufficient evidence documentation workflow",
            "origin": "canonical_intent",
        }]},
        "_qualification_candidate": {
            "project_identity": "project:other", "source_class": "project_doc",
            "freshness": "current", "index_freshness": "synchronized",
            "risk_flags": [], "lifecycle_status": "active",
        },
        "_expected_project_identity": "project:test",
        "_lifecycle_intent": "current",
    }
    visible = _requalify_visible_source(source, query_text={
        "query-original": "What should the agent do if evidence is insufficient?",
        "query-intent-1": "insufficient evidence documentation workflow",
    })
    trace = visible["retrieval_query_matches"]["query-intent-1"]
    assert trace["qualified"] is False
    assert trace["qualification_reason"] == "wrong_project_identity"
''', encoding="utf-8")
    Path(MANIFEST).write_text(json.dumps({
        "schema_version": 1,
        "module_labels": {TEST: "behavioral"},
        "node_overrides": {},
        "module_node_hashes": {TEST: node_digest(TEST)},
    }, indent=2) + "\n", encoding="utf-8")


def apply_fix() -> None:
    service = "docmancer/docs/application/_project_docs_service_part03.py"
    qualify = r'''def _starts_markdown_list_item(text: str) -> bool:
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
    return result'''
    replace_function(service, "_qualify_same_atom_continuations", "_merge_same_atom_continuations", qualify)

    merge = r'''def _merge_same_atom_continuations(
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
    return [chunk for index, chunk in enumerate(result) if index not in remove]'''
    replace_function(service, "_merge_same_atom_continuations", "_qualify_candidate_lookups", merge)

    replace_once(
        "docmancer/docs/application/_docs_context_projection_core.py",
        'trace.get("qualification_route") == "same_atom_continuation"',
        'trace.get("qualification_route") in {"same_atom_continuation", "same_list_item_continuation"}',
    )
    replace_once(
        "docmancer/docs/application/context_candidate_ranking.py",
        'trace.get("qualification_route") == "same_atom_continuation"',
        'trace.get("qualification_route") in {"same_atom_continuation", "same_list_item_continuation"}',
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("tests", "fix"))
    args = parser.parse_args()
    write_tests() if args.phase == "tests" else apply_fix()


if __name__ == "__main__":
    main()
