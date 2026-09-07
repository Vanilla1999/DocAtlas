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

service = Path("docmancer/docs/application/_project_docs_service_part03.py")
service_text = service.read_text(encoding="utf-8")
old = '''        queries_by_origin: dict[str, list[list[Any]]] = {}
        for item in documentation_query_plan.queries:
            lane = supplemental_chunks_by_query.get(item.text)
            if lane:
                queries_by_origin.setdefault(item.origin, []).append(lane)
        candidates = select_context_candidates([
            [
                *queries_by_origin.get("exact_path", []),
                *queries_by_origin.get("exact_anchor", []),
            ],
            [[*authoritative_chunks, *chunks]],
            queries_by_origin.get("host_lookup", []),
            [
                *queries_by_origin.get("canonical_intent", []),
                *queries_by_origin.get("concept_alias", []),
                *queries_by_origin.get("retrieval_hint", []),
            ],
        ])
        candidates.sort(
            key=lambda chunk: not bool(
                (chunk.metadata or {}).get("retrieval_query_ids")
            )
        )
'''
new = '''        queries_by_origin: dict[str, list[list[Any]]] = {}
        audited_parent_lanes: list[list[Any]] = []
        generic_canonical_lanes: list[list[Any]] = []
        for item in documentation_query_plan.queries:
            lane = supplemental_chunks_by_query.get(item.text)
            if not lane:
                continue
            queries_by_origin.setdefault(item.origin, []).append(lane)
            if item.origin == "canonical_intent":
                if item.relation == "audited_rewrite" and item.public_parent_query_id:
                    audited_parent_lanes.append(lane)
                else:
                    generic_canonical_lanes.append(lane)
        candidates = select_context_candidates([
            [
                *queries_by_origin.get("exact_path", []),
                *queries_by_origin.get("exact_anchor", []),
            ],
            [[*authoritative_chunks, *chunks]],
            audited_parent_lanes,
            queries_by_origin.get("host_lookup", []),
            [
                *generic_canonical_lanes,
                *queries_by_origin.get("concept_alias", []),
                *queries_by_origin.get("retrieval_hint", []),
            ],
        ])
        # Audited rewrites are the only generated queries allowed to derive
        # coverage for a public parent. Their compact top witness must survive
        # aggregate admission before noisy recall-only lanes spend the same
        # bounded candidate budget. This changes admission order only; it does
        # not increase the internal budget or the public 3-source/800-token cap.
        audited_seed_ids = {
            str((lane[0].metadata or {}).get("stable_chunk_id") or "")
            for lane in audited_parent_lanes if lane
        }
        candidates.sort(
            key=lambda chunk: (
                str((chunk.metadata or {}).get("stable_chunk_id") or "") not in audited_seed_ids,
                not bool((chunk.metadata or {}).get("retrieval_query_ids")),
            )
        )
'''
assert service_text.count(old) == 1
service.write_text(service_text.replace(old, new, 1), encoding="utf-8")
