from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

TEST = "tests/docs/test_same_atom_continuation_chain.py"
MANIFEST = "tests/diagnostic_labels.same_atom_continuation_chain.json"


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise AssertionError(f"{path}: expected one replacement, got {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def node_digest(module: str) -> str:
    tree = ast.parse(Path(module).read_text(encoding="utf-8"))
    nodes = [
        f"{module}::{node.name}"
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ]
    return hashlib.sha256("\n".join(sorted(nodes)).encode()).hexdigest()


def write_tests() -> None:
    Path(TEST).write_text(r'''from docmancer.core.models import RetrievedChunk
from docmancer.docs.application._project_docs_service_part03 import (
    _merge_same_atom_continuations,
    _qualify_same_atom_continuations,
)


def _three_chunks():
    common = {
        "parent_logical_id": "parent-1",
        "atom_id": "atom-1",
        "project_identity": "project:test",
        "source_class": "project_file",
    }
    return [
        RetrievedChunk(
            source="docs/workflow.md", chunk_index=1,
            text="If evidence is insufficient, continue locally ", score=3,
            metadata={
                **common, "stable_chunk_id": "child-1", "char_span": [0, 44],
                "retrieval_query_matches": {"query-intent-1": {
                    "qualified": True, "relation": "host_lookup",
                }},
                "retrieval_query_ids": ("query-intent-1",),
            },
        ),
        RetrievedChunk(
            source="docs/workflow.md", chunk_index=2,
            text="with source/tests while keeping the documentary claim ", score=2,
            metadata={
                **common, "stable_chunk_id": "child-2", "char_span": [44, 97],
                "retrieval_query_matches": {"query-intent-1": {"qualified": False}},
                "retrieval_query_ids": (),
            },
        ),
        RetrievedChunk(
            source="docs/workflow.md", chunk_index=3,
            text="unproved. Stop before an edit when hard_stop=true.", score=1,
            metadata={
                **common, "stable_chunk_id": "child-3", "char_span": [97, 147],
                "retrieval_query_matches": {"query-intent-1": {"qualified": False}},
                "retrieval_query_ids": (),
            },
        ),
    ]


def test_qualification_propagates_across_all_contiguous_children_of_one_atom():
    rows = _qualify_same_atom_continuations(_three_chunks(), "query-intent-1")
    assert [
        row.metadata["retrieval_query_matches"]["query-intent-1"].get("qualified")
        for row in rows
    ] == [True, True, True]
    assert rows[1].metadata["retrieval_query_matches"]["query-intent-1"]["coverage_kind"] == "derived"
    assert rows[2].metadata["retrieval_query_matches"]["query-intent-1"]["coverage_kind"] == "derived"


def test_reassembly_consumes_the_entire_contiguous_chain_within_existing_cap():
    qualified = _qualify_same_atom_continuations(_three_chunks(), "query-intent-1")
    rows = _merge_same_atom_continuations(qualified, "query-intent-1")
    assert len(rows) == 1
    assert rows[0].text == (
        "If evidence is insufficient, continue locally with source/tests while keeping "
        "the documentary claim unproved. Stop before an edit when hard_stop=true."
    )
    assert rows[0].metadata["char_span"] == [0, 147]
    assert rows[0].metadata["reassembled_from_stable_chunk_ids"] == [
        "child-1", "child-2", "child-3",
    ]


def test_reassembly_does_not_cross_into_the_next_atom():
    chunks = _three_chunks()
    chunks.append(RetrievedChunk(
        source="docs/workflow.md", chunk_index=4, text="Next unrelated rule.", score=.5,
        metadata={
            "parent_logical_id": "parent-1", "atom_id": "atom-2",
            "project_identity": "project:test", "source_class": "project_file",
            "stable_chunk_id": "child-4", "char_span": [147, 167],
            "retrieval_query_matches": {"query-intent-1": {"qualified": False}},
            "retrieval_query_ids": (),
        },
    ))
    qualified = _qualify_same_atom_continuations(chunks, "query-intent-1")
    rows = _merge_same_atom_continuations(qualified, "query-intent-1")
    assert [row.text for row in rows] == [
        "If evidence is insufficient, continue locally with source/tests while keeping "
        "the documentary claim unproved. Stop before an edit when hard_stop=true.",
        "Next unrelated rule.",
    ]
''', encoding="utf-8")
    payload = {
        "schema_version": 1,
        "module_labels": {TEST: "behavioral"},
        "node_overrides": {},
        "module_node_hashes": {TEST: node_digest(TEST)},
    }
    Path(MANIFEST).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def apply_fix() -> None:
    path = "docmancer/docs/application/_project_docs_service_part03.py"
    old_qualify = '''def _qualify_same_atom_continuations(chunks: list[Any], query_id: str) -> list[Any]:\n    """Carry one qualified canonical probe across a physically split atom.\n\n    Parent/atom identity plus contiguous source spans are structural provenance,\n    not semantic inference.  This keeps a sentence/list item split by the child\n    chunk hard limit available to projection without deriving public/original\n    query coverage or adding another retrieval call.\n    """\n    result = list(chunks)\n    anchors = []\n    for chunk in result:\n        metadata = chunk.metadata or {}\n        trace = (metadata.get("retrieval_query_matches") or {}).get(query_id) or {}\n        span = metadata.get("char_span") or ()\n        if trace.get("qualified") is True and len(span) == 2:\n            anchors.append(chunk)\n    for anchor in anchors:\n        anchor_meta = anchor.metadata or {}\n        anchor_span = anchor_meta.get("char_span") or ()\n        atom_id = str(anchor_meta.get("atom_id") or "")\n        parent_id = str(anchor_meta.get("parent_logical_id") or "")\n        if not atom_id or not parent_id or len(anchor_span) != 2:\n            continue\n        for index, candidate in enumerate(result):\n            metadata = candidate.metadata or {}\n            span = metadata.get("char_span") or ()\n            if (\n                len(span) != 2 or span[0] != anchor_span[1]\n                or str(metadata.get("atom_id") or "") != atom_id\n                or str(metadata.get("parent_logical_id") or "") != parent_id\n                or candidate.source != anchor.source\n            ):\n                continue\n            matches = dict(metadata.get("retrieval_query_matches") or {})\n            current = dict(matches.get(query_id) or {})\n            if current.get("qualified") is True:\n                continue\n            anchor_trace = dict(\n                (anchor_meta.get("retrieval_query_matches") or {}).get(query_id) or {}\n            )\n            if anchor_trace.get("qualified") is not True:\n                continue\n            derived = dict(anchor_trace)\n            derived.update({\n                "qualified": True,\n                "qualification_reason": "same_atom_continuation",\n                "qualification_route": "same_atom_continuation",\n                "coverage_kind": "derived",\n                "coverage_kinds": ["derived"],\n                "derived_from_stable_chunk_id": str(anchor_meta.get("stable_chunk_id") or ""),\n                "matched_terms": [],\n                "body_matched_terms": [],\n                "match_ratio": 0.0,\n            })\n            matches[query_id] = derived\n            metadata = dict(metadata)\n            metadata["retrieval_query_matches"] = matches\n            metadata["retrieval_query_ids"] = tuple(\n                key for key, value in matches.items() if value.get("qualified") is True\n            )\n            result[index] = candidate.model_copy(update={"metadata": metadata})\n            break\n    return result\n'''
    new_qualify = '''def _qualify_same_atom_continuations(chunks: list[Any], query_id: str) -> list[Any]:\n    """Carry qualification through every contiguous child of one structured atom.\n\n    Propagation is structural only: same source, parent, atom and exact adjacent\n    char spans.  It creates derived canonical retrieval context, never public or\n    original-query coverage.  Source eligibility is rechecked later at visible\n    projection, independently from this lexical continuation.\n    """\n    result = list(chunks)\n    changed = True\n    while changed:\n        changed = False\n        for anchor in tuple(result):\n            anchor_meta = anchor.metadata or {}\n            anchor_trace = dict(\n                (anchor_meta.get("retrieval_query_matches") or {}).get(query_id) or {}\n            )\n            anchor_span = anchor_meta.get("char_span") or ()\n            atom_id = str(anchor_meta.get("atom_id") or "")\n            parent_id = str(anchor_meta.get("parent_logical_id") or "")\n            if (\n                anchor_trace.get("qualified") is not True\n                or not atom_id or not parent_id or len(anchor_span) != 2\n            ):\n                continue\n            for index, candidate in enumerate(result):\n                metadata = candidate.metadata or {}\n                span = metadata.get("char_span") or ()\n                if (\n                    len(span) != 2 or span[0] != anchor_span[1]\n                    or str(metadata.get("atom_id") or "") != atom_id\n                    or str(metadata.get("parent_logical_id") or "") != parent_id\n                    or candidate.source != anchor.source\n                ):\n                    continue\n                matches = dict(metadata.get("retrieval_query_matches") or {})\n                current = dict(matches.get(query_id) or {})\n                if current.get("qualified") is True:\n                    continue\n                derived = dict(anchor_trace)\n                derived.update({\n                    "qualified": True,\n                    "qualification_reason": "same_atom_continuation",\n                    "qualification_route": "same_atom_continuation",\n                    "coverage_kind": "derived",\n                    "coverage_kinds": ["derived"],\n                    "derived_from_stable_chunk_id": str(anchor_meta.get("stable_chunk_id") or ""),\n                    "matched_terms": [],\n                    "body_matched_terms": [],\n                    "match_ratio": 0.0,\n                })\n                matches[query_id] = derived\n                updated = dict(metadata)\n                updated["retrieval_query_matches"] = matches\n                updated["retrieval_query_ids"] = tuple(\n                    key for key, value in matches.items() if value.get("qualified") is True\n                )\n                result[index] = candidate.model_copy(update={"metadata": updated})\n                changed = True\n                break\n    return result\n'''
    replace_once(path, old_qualify, new_qualify)

    old_merge = '''def _merge_same_atom_continuations(\n    chunks: list[Any], query_id: str, *, max_chars: int = 1024,\n) -> list[Any]:\n    """Reassemble one forward split of a qualified structured atom.\n\n    The merge is source-contiguous and identity-bound.  It does not join\n    paragraphs/atoms or create public-query coverage; it only restores text that\n    child chunking split inside one atom.\n    """\n    result = list(chunks)\n    remove: set[int] = set()\n    for index, anchor in enumerate(tuple(result)):\n        if index in remove:\n            continue\n        metadata = dict(anchor.metadata or {})\n        trace = (metadata.get("retrieval_query_matches") or {}).get(query_id) or {}\n        span = metadata.get("char_span") or ()\n        atom_id = str(metadata.get("atom_id") or "")\n        parent_id = str(metadata.get("parent_logical_id") or "")\n        if trace.get("qualified") is not True or not atom_id or not parent_id or len(span) != 2:\n            continue\n        for other_index, candidate in enumerate(result):\n            if other_index == index or other_index in remove:\n                continue\n            other = candidate.metadata or {}\n            other_trace = (other.get("retrieval_query_matches") or {}).get(query_id) or {}\n            other_span = other.get("char_span") or ()\n            if (\n                other_trace.get("qualification_route") != "same_atom_continuation"\n                or other_trace.get("qualified") is not True\n                or len(other_span) != 2 or other_span[0] != span[1]\n                or str(other.get("atom_id") or "") != atom_id\n                or str(other.get("parent_logical_id") or "") != parent_id\n                or candidate.source != anchor.source\n            ):\n                continue\n            text = f"{anchor.text}{candidate.text}"\n            if len(text) > max_chars:\n                continue\n            metadata["char_span"] = [span[0], other_span[1]]\n            for field in ("byte_span", "line_span"):\n                left = metadata.get(field) or ()\n                right = other.get(field) or ()\n                if len(left) == 2 and len(right) == 2:\n                    metadata[field] = [left[0], right[1]]\n            metadata["reassembled_from_stable_chunk_ids"] = [\n                str(metadata.get("stable_chunk_id") or ""),\n                str(other.get("stable_chunk_id") or ""),\n            ]\n            metadata["display_token_estimate"] = int(metadata.get("display_token_estimate") or 0) + int(other.get("display_token_estimate") or 0)\n            metadata["token_estimate"] = int(metadata.get("token_estimate") or 0) + int(other.get("token_estimate") or 0)\n            result[index] = anchor.model_copy(update={"text": text, "metadata": metadata})\n            remove.add(other_index)\n            break\n    return [chunk for index, chunk in enumerate(result) if index not in remove]\n'''
    new_merge = '''def _merge_same_atom_continuations(\n    chunks: list[Any], query_id: str, *, max_chars: int = 1024,\n) -> list[Any]:\n    """Reassemble the full contiguous qualified chain of one structured atom.\n\n    The merge remains source/parent/atom/span bound and stops at ``max_chars``.\n    It cannot cross a semantic atom and does not create public-query coverage.\n    """\n    result = list(chunks)\n    remove: set[int] = set()\n    for index in range(len(result)):\n        if index in remove:\n            continue\n        while True:\n            anchor = result[index]\n            metadata = dict(anchor.metadata or {})\n            trace = (metadata.get("retrieval_query_matches") or {}).get(query_id) or {}\n            span = metadata.get("char_span") or ()\n            atom_id = str(metadata.get("atom_id") or "")\n            parent_id = str(metadata.get("parent_logical_id") or "")\n            if (\n                trace.get("qualified") is not True\n                or not atom_id or not parent_id or len(span) != 2\n            ):\n                break\n            next_index = None\n            for other_index, candidate in enumerate(result):\n                if other_index == index or other_index in remove:\n                    continue\n                other = candidate.metadata or {}\n                other_trace = (other.get("retrieval_query_matches") or {}).get(query_id) or {}\n                other_span = other.get("char_span") or ()\n                if (\n                    other_trace.get("qualification_route") == "same_atom_continuation"\n                    and other_trace.get("qualified") is True\n                    and len(other_span) == 2 and other_span[0] == span[1]\n                    and str(other.get("atom_id") or "") == atom_id\n                    and str(other.get("parent_logical_id") or "") == parent_id\n                    and candidate.source == anchor.source\n                ):\n                    next_index = other_index\n                    break\n            if next_index is None:\n                break\n            candidate = result[next_index]\n            other = candidate.metadata or {}\n            other_span = other.get("char_span") or ()\n            text = f"{anchor.text}{candidate.text}"\n            if len(text) > max_chars:\n                break\n            metadata["char_span"] = [span[0], other_span[1]]\n            for field in ("byte_span", "line_span"):\n                left = metadata.get(field) or ()\n                right = other.get(field) or ()\n                if len(left) == 2 and len(right) == 2:\n                    metadata[field] = [left[0], right[1]]\n            previous_ids = list(metadata.get("reassembled_from_stable_chunk_ids") or ())\n            if not previous_ids:\n                previous_ids.append(str(metadata.get("stable_chunk_id") or ""))\n            child_id = str(other.get("stable_chunk_id") or "")\n            if child_id and child_id not in previous_ids:\n                previous_ids.append(child_id)\n            metadata["reassembled_from_stable_chunk_ids"] = previous_ids\n            metadata["display_token_estimate"] = int(metadata.get("display_token_estimate") or 0) + int(other.get("display_token_estimate") or 0)\n            metadata["token_estimate"] = int(metadata.get("token_estimate") or 0) + int(other.get("token_estimate") or 0)\n            result[index] = anchor.model_copy(update={"text": text, "metadata": metadata})\n            remove.add(next_index)\n    return [chunk for index, chunk in enumerate(result) if index not in remove]\n'''
    replace_once(path, old_merge, new_merge)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("tests", "fix"))
    args = parser.parse_args()
    write_tests() if args.mode == "tests" else apply_fix()
    print(f"chain TDD {args.mode} complete")


if __name__ == "__main__":
    main()
