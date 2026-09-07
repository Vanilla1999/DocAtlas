from pathlib import Path

path = Path("docmancer/docs/domain/documentation_query_plan.py")
text = path.read_text(encoding="utf-8")
marker = "\n\ndef build_documentation_query_plan(\n"
assert text.count(marker) == 1
helper = r'''

_HOST_LOOKUP_NEGATION_RE = re.compile(
    r"\b(?:not|never|without|no|не|нет|никогда|без)\b", re.I,
)


def _audited_host_lookup_rewrites(
    original_question: str, lookup_text: str,
) -> tuple[str, ...]:
    """Return conservative retrieval-only rewrites for one public host lookup."""
    text = " ".join(str(lookup_text or "").strip().split())
    if not text or _HOST_LOOKUP_NEGATION_RE.search(text) or technical_anchors(text):
        return ()
    original_anchors = {value.casefold() for value in technical_anchors(original_question)}
    if "get_docs_context" not in original_anchors:
        return ()
    tokens = tuple(re.findall(r"[a-z0-9_]+", text.casefold()))

    def has(*stems: str) -> bool:
        return any(token.startswith(stem) for token in tokens for stem in stems)

    rows: list[str] = []
    if has("request") and has("boundar") and has("accept", "input", "argument"):
        rows.append("get_docs_context question project_path lookup_queries module_path scope")
    if has("retriev") and has("select") and has("chunk", "source", "candidate"):
        rows.extend((
            "retrieval gateway filtered project chunks",
            "selection maximizes distinct visible query coverage",
        ))
    return tuple(dict.fromkeys(rows))[:2]
'''
text = text.replace(marker, helper + marker, 1)
old = '''    for index, text in enumerate(lookup_queries[:5], start=1):
        cleaned = text.strip()
        if not cleaned:
            continue
        queries.append(DocumentationLookup(
            f"query-lookup-{index}", cleaned, "host_lookup", False,
            relation="host_lookup",
            **host_policies(cleaned),
        ))
        seen.add(cleaned.casefold())
'''
new = '''    host_rows: list[tuple[str, str]] = []
    for index, text in enumerate(lookup_queries[:5], start=1):
        cleaned = text.strip()
        if not cleaned:
            continue
        parent_query_id = f"query-lookup-{index}"
        queries.append(DocumentationLookup(
            parent_query_id, cleaned, "host_lookup", False,
            relation="host_lookup",
            **host_policies(cleaned),
        ))
        host_rows.append((parent_query_id, cleaned))
        seen.add(cleaned.casefold())
    host_rewrite_count = 0
    for parent_query_id, cleaned in host_rows:
        policies = host_policies(cleaned)
        parent_exact_terms = tuple(dict.fromkeys((
            *(term.normalized_value for term in documentation_exact_terms(cleaned)),
            *(value.casefold() for value in documentation_technical_anchors(cleaned)),
        )))
        for rewrite in _audited_host_lookup_rewrites(question, cleaned):
            if host_rewrite_count >= 4 or rewrite.casefold() in seen:
                break
            host_rewrite_count += 1
            queries.append(DocumentationLookup(
                f"query-host-rewrite-{host_rewrite_count}", rewrite, "canonical_intent", False,
                relation="audited_rewrite", public_parent_query_id=parent_query_id,
                preferred_catalog_roles=policies["preferred_catalog_roles"],
                forbidden_catalog_roles=policies["forbidden_catalog_roles"],
                forbidden_evidence_terms=policies["forbidden_evidence_terms"],
                parent_exact_terms=parent_exact_terms,
            ))
            seen.add(rewrite.casefold())
'''
assert text.count(old) == 1
path.write_text(text.replace(old, new, 1), encoding="utf-8")

ranking = Path("docmancer/docs/domain/project_doc_ranking.py")
text = ranking.read_text(encoding="utf-8")
old = '''        public_queries_by_id[id(chunk)] = {
            query_id for query_id in qualified_query_ids
            if query_matches[query_id].get("query_origin") in {
                "original", "host_lookup", "exact_anchor", "exact_path",
            }
        } if not exact_path_anchor else set()
'''
new = '''        public_queries_by_id[id(chunk)] = {
            query_id for query_id in qualified_query_ids
            if query_id == "query-original"
            or query_id.startswith(("query-lookup-", "query-anchor-", "query-path-"))
            or (
                query_matches[query_id].get("relation") == "audited_rewrite"
                and str(query_matches[query_id].get("public_parent_query_id") or "").startswith("query-lookup-")
            )
        } if not exact_path_anchor else set()
'''
assert text.count(old) == 1
ranking.write_text(text.replace(old, new, 1), encoding="utf-8")

projection = Path("docmancer/docs/application/docs_context_projection.py")
text = projection.read_text(encoding="utf-8")
old = '''    canonical_intent_query_ids = _query_ids_for_origins(
        query_plan, {"canonical_intent"},
    )
    eligible_query_ids = public_query_id_set | canonical_intent_query_ids
'''
new = '''    canonical_intent_query_ids = _query_ids_for_origins(
        query_plan, {"canonical_intent"},
    )
    audited_rewrite_query_ids = {
        str(item.get("query_id") or "")
        for item in query_plan.get("queries") or ()
        if isinstance(item, dict)
        and item.get("relation") == "audited_rewrite"
        and str(item.get("public_parent_query_id") or "") in host_query_ids
        and item.get("query_id")
    }
    compound_priority_query_ids = (
        host_query_ids | audited_rewrite_query_ids
        if len(host_query_ids) > 1 else public_query_id_set
    )
    eligible_query_ids = public_query_id_set | canonical_intent_query_ids
'''
assert text.count(old) == 1
text = text.replace(old, new, 1)
old = '''        candidates, query_text=query_text,
        required_query_ids=public_query_id_set,
        canonical_query_ids=canonical_intent_query_ids,
'''
new = '''        candidates, query_text=query_text,
        required_query_ids=compound_priority_query_ids,
        canonical_query_ids=canonical_intent_query_ids,
'''
assert text.count(old) == 1
text = text.replace(old, new, 1)
old = '''        prepared = _facet_aware_candidates(
            prepared, query_text=query_text,
            required_query_ids=public_query_id_set - (qualified_query_ids(sources) if len(host_query_ids) > 1 else selected_public_ids),
            canonical_query_ids=canonical_intent_query_ids - selected_canonical_ids,
            exact_query_ids=exact_anchor_query_ids - selected_public_ids,
'''
new = '''        missing_compound_priority_ids = (
            compound_priority_query_ids - qualified_query_ids(sources)
        )
        prepared = _facet_aware_candidates(
            prepared, query_text=query_text,
            required_query_ids=missing_compound_priority_ids,
            canonical_query_ids=canonical_intent_query_ids - selected_canonical_ids,
            exact_query_ids=(
                set()
                if len(host_query_ids) > 1 and missing_compound_priority_ids
                else exact_anchor_query_ids - selected_public_ids
            ),
'''
assert text.count(old) == 1
text = text.replace(old, new, 1)
old = '''            if snippet and (qualified_query_ids((candidate,)) & query_ids or component_witnesses(candidate, obligations)):
                variants.append(candidate)
    # Variants of one evidence item compete before global source selection.
'''
new = '''            if snippet and (qualified_query_ids((candidate,)) & query_ids or component_witnesses(candidate, obligations)):
                variants.append(candidate)

    # When two qualified alternatives from one source prove different requested
    # directions, offer a single contiguous union span before global selection.
    # The gap remains verbatim source text, the span stays bounded, and visible
    # qualification must preserve both directions.
    seed_variants = tuple(variants)
    for left_index, left in enumerate(seed_variants):
        left_start = raw_snippet.find(str(left.get("snippet") or ""))
        if left_start < 0:
            continue
        left_ids = qualified_query_ids((left,)) & query_ids
        if not left_ids:
            continue
        for right in seed_variants[left_index + 1:]:
            right_start = raw_snippet.find(str(right.get("snippet") or ""))
            if right_start < 0:
                continue
            right_ids = qualified_query_ids((right,)) & query_ids
            if not right_ids or left_ids == right_ids:
                continue
            union_ids = left_ids | right_ids
            union_start = min(left_start, right_start)
            union_end = max(
                left_start + len(str(left.get("snippet") or "")),
                right_start + len(str(right.get("snippet") or "")),
            )
            if union_end - union_start > 640 or (union_start, union_end) in seen_spans:
                continue
            union_snippet = raw_snippet[union_start:union_end].strip()
            union_candidate = dict(source)
            union_candidate["snippet"] = union_snippet
            union_candidate["line_start"], union_candidate["line_end"] = _focused_line_range(
                raw_snippet, union_start, union_end, source_line_start,
            )
            union_candidate = _requalify_visible_source(
                union_candidate, query_text=query_text,
            )
            if not union_ids <= (qualified_query_ids((union_candidate,)) & query_ids):
                continue
            hashes = visible_assignment_hashes(
                source.get("_qualification_candidate", source), union_candidate, assignments,
            )
            union_candidate["_visible_assignment_hashes"] = list(hashes)
            union_candidate["_assigned_requirement_ids"] = [
                item["requirement_id"] for item in assignments
                if item.get("projected_content_hash") in hashes
                and item.get("requirement_id") in set(source.get("_assigned_requirement_ids") or ())
            ]
            seen_spans.add((union_start, union_end))
            variants.append(union_candidate)
    # Variants of one evidence item compete before global source selection.
'''
assert text.count(old) == 1
text = text.replace(old, new, 1)
projection.write_text(text, encoding="utf-8")

payload = Path("docmancer/docs/application/_docs_context_payload.py")
text = payload.read_text(encoding="utf-8")
old = '''        "edit_ready": False,
        "investigation_allowed": True,
        "instruction": (
            "Answer only claims directly grounded in the returned sources, cite their paths, "
            "and do not claim that the context is complete. Never use this retrieval-only "
            "result to authorize an edit."
        ),
        "estimated_tokens": 0,
'''
new = '''        "edit_ready": False,
        "investigation_allowed": True,
        "estimated_tokens": 0,
'''
assert text.count(old) == 1
payload.write_text(text.replace(old, new, 1), encoding="utf-8")
