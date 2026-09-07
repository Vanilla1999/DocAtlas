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
    """Return conservative retrieval-only rewrites for one public host lookup.

    Rewrites never become public query IDs. They are allowed only for the
    documented get_docs_context flow when the lookup contains no negation or
    independent exact technical identity; qualification still happens against
    the model-visible source before parent coverage may be derived.
    """
    text = " ".join(str(lookup_text or "").strip().split())
    if not text or _HOST_LOOKUP_NEGATION_RE.search(text):
        return ()
    if technical_anchors(text):
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
ranking_text = ranking.read_text(encoding="utf-8")
old = '''        public_queries_by_id[id(chunk)] = {
            query_id for query_id in qualified_query_ids
            if query_matches[query_id].get("query_origin") in {
                "original", "host_lookup", "exact_anchor", "exact_path",
            }
        } if not exact_path_anchor else set()
'''
new = '''        # Parent coverage derived from an audited internal rewrite is stored
        # under the public query ID while retaining the rewrite's internal
        # origin in its trace. Public-lane diversity therefore follows the
        # stable public ID, not the witness origin metadata.
        public_queries_by_id[id(chunk)] = {
            query_id for query_id in qualified_query_ids
            if query_id == "query-original"
            or query_id.startswith(("query-lookup-", "query-anchor-", "query-path-"))
        } if not exact_path_anchor else set()
'''
assert ranking_text.count(old) == 1
ranking.write_text(ranking_text.replace(old, new, 1), encoding="utf-8")
