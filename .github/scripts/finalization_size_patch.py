from pathlib import Path

path = Path("docmancer/docs/application/docs_context_projection.py")
text = path.read_text(encoding="utf-8")
replacements = {
'''    # When two qualified alternatives from one source prove different requested
    # directions, offer a single contiguous union span before global selection.
    # The gap remains verbatim source text, the span stays bounded, and visible
    # qualification must preserve both directions.
''': '''    # Offer one bounded verbatim union span when it preserves both directions.
''',
'''            union_end = max(
                left_start + len(str(left.get("snippet") or "")),
                right_start + len(str(right.get("snippet") or "")),
            )
''': '''            union_end = max(left_start + len(str(left.get("snippet") or "")),
                            right_start + len(str(right.get("snippet") or "")))
''',
'''            union_candidate["line_start"], union_candidate["line_end"] = _focused_line_range(
                raw_snippet, union_start, union_end, source_line_start,
            )
''': '''            union_candidate["line_start"], union_candidate["line_end"] = _focused_line_range(
                raw_snippet, union_start, union_end, source_line_start)
''',
'''            union_candidate = _requalify_visible_source(
                union_candidate, query_text=query_text,
            )
''': '''            union_candidate = _requalify_visible_source(union_candidate, query_text=query_text)
''',
'''            hashes = visible_assignment_hashes(
                source.get("_qualification_candidate", source), union_candidate, assignments,
            )
''': '''            hashes = visible_assignment_hashes(
                source.get("_qualification_candidate", source), union_candidate, assignments)
''',
'''            union_candidate["_assigned_requirement_ids"] = [
                item["requirement_id"] for item in assignments
                if item.get("projected_content_hash") in hashes
                and item.get("requirement_id") in set(source.get("_assigned_requirement_ids") or ())
            ]
''': '''            union_candidate["_assigned_requirement_ids"] = [
                item["requirement_id"] for item in assignments if item.get("projected_content_hash") in hashes
                and item.get("requirement_id") in set(source.get("_assigned_requirement_ids") or ())]
''',
'''    # Variants of one evidence item compete before global source selection.
    # Prefer a bounded, structurally complete contiguous span when coverage is
    # otherwise equivalent, so a shorter mid-sentence prefix cannot consume the
    # slot and later block a safe expansion under the same 800-token budget.
''': '''    # Prefer structurally complete variants when coverage is otherwise equal.
''',
}
for old, new in replacements.items():
    assert old in text, old
    text = text.replace(old, new, 1)
text = text.replace("                variants.append(candidate)\n\n    # Offer one bounded", "                variants.append(candidate)\n    # Offer one bounded", 1)
path.write_text(text, encoding="utf-8")
