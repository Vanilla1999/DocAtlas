from pathlib import Path

# 1) Canonical agent contract: restore the established bootstrap wording.
p = Path('docmancer/templates/agent_contract.md')
text = p.read_text()
old = '1. Call `get_docs_context` with the original concrete `question` and `project_path` (or `library`). Independent questions need separate `get_docs_context` calls; never substitute a benchmark/evaluation or documentation-governance meta-question.'
new = '1. Call `get_docs_context` for bounded structured context with the original concrete `question` and `project_path` (or `library`). Independent questions need separate `get_docs_context` calls; never substitute a benchmark/evaluation or documentation-governance meta-question.'
if old not in text:
    raise SystemExit('canonical agent contract bootstrap sentence not found')
p.write_text(text.replace(old, new, 1))

# 2) Compact advertised tool metadata without changing runtime payload schemas.
p = Path('docmancer/mcp/_docs_server_tool_data.py')
text = p.read_text()
text = text.replace(
    '"description": "Second-call apply flag for action=\'clear_index\' only; omit for every other action.",',
    '"description": "Apply flag for clear_index only.",',
    1,
)
start = text.index('PUBLIC_ADVERTISED_DESCRIPTIONS: dict[str, str] = {')
end = text.index('\n\nPUBLIC_ADVERTISED_INPUT_SCHEMAS:', start)
compact = '''PUBLIC_ADVERTISED_DESCRIPTIONS: dict[str, str] = {
    "get_docs_context": (
        "Source-grounded documentation tool. One call = one concrete question. Pass the original request unchanged; "
        "never substitute a benchmark/evaluation or documentation-governance meta-question. For cross-module use "
        "scope=all without module filters; module_path always implies module scope. For module plus repo policy make two "
        "bounded calls (module then project). Lookups never authorize an answer or edit. hard_stop=true blocks edits."
    ),
    "prepare_docs": (
        "Call only from get_docs_context recommended_next_action or an explicit sync, refresh, index, or prefetch request. "
        "Honor approval; poll job_id with docs_status and retry unchanged only after success."
    ),
    "docs_status": (
        "Read-only status. Use when the user explicitly asks about health, freshness, indexing, or job progress, "
        "or to poll a returned prepare_docs job_id."
    ),
}'''
text = text[:start] + compact + text[end:]
replacements = {
    '"description": "Retrieval-only hypotheses for the same question. For cross-language, comparison, conditional, or multiple dependent facets, use 1–3 short lookups in the documentation language; simple single-facet questions need none. Keep the original question unchanged; preserve exact identifiers, versions, conditions, negation and comparison sides; never invent the expected answer or use guessed source names. Independent questions use separate calls."':
    '"description": "Same question only. For cross-language, comparison, conditional, or multiple dependent facets use 1–3 short lookups in the documentation language; simple single-facet questions need none. Keep the original question unchanged; preserve exact identifiers, versions, conditions, negation and comparison sides. Never batch independent questions, invent the expected answer, or use guessed source names."',
    '"description": "Omit for current project dependency queries so the current lockfile is resolved again. Set only for an explicitly requested exact/historical version; never carry a previous binding forward after a lockfile change."':
    '"description": "Current project: omit. Set only for an explicit exact/historical version; re-query after lockfile changes."',
    '"description": "Exact path; always implies module scope."':
    '"description": "Exact module path; always implies module scope."',
    '"description": "project: repo-level docs only; module: one module; all: repo-level plus modules in the same repository. module_path always limits to that module."':
    '"description": "project=repo-level docs only; module=one module; all=repo+modules; module_path limits to module."',
}
for old, new in replacements.items():
    if old not in text:
        raise SystemExit(f'advertised input description not found: {old[:70]}')
    text = text.replace(old, new, 1)
old_output = '''PUBLIC_ADVERTISED_OUTPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "get_docs_context": PUBLIC_GET_DOCS_CONTEXT_OUTPUT_SCHEMA,
}'''
new_output = '''PUBLIC_ADVERTISED_OUTPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "get_docs_context": {
        "type": "object", "required": ["status"], "properties": {
            "status": {"enum": ["ok", "truncated", "insufficient_evidence", "failed"]},
            "kind": {"enum": ["docs_answer", "docs_context", "patch_context"]},
            "estimated_tokens": {"type": "integer"},
            "context_quality": {"type": "object"},
            "read_next": {"type": "array", "maxItems": 1, "items": {"type": "object"}},
            "reason_code": {"type": "string"}, "operational_reason_code": {"type": "string"},
            "documentation_supported": {"type": "boolean"}, "investigation_allowed": {"type": "boolean"},
            "hard_stop": {"type": "boolean"}, "recovery_origin": {"type": "string"},
            "recovery_reason_code": {"type": "string"}, "recovery_disposition": {"type": "string"},
            "module_candidates": {"type": "array", "maxItems": 8, "items": {
                "type": "object", "required": ["module_path"],
                "properties": {"module_path": {"type": "string"}},
            }},
            "missing": {"type": "array", "maxItems": 5, "items": {"type": "string"}},
            "recommended_next_action": {"type": "object"},
        },
    },
}'''
if old_output not in text:
    raise SystemExit('advertised get_docs_context output schema block not found')
text = text.replace(old_output, new_output, 1)
p.write_text(text)

# 3) Keep runtime lookup description semantically identical but compact.
p = Path('docmancer/mcp/_docs_server_shared.py')
text = p.read_text()
old = '''_GET_DOCS_CONTEXT_LOOKUP_DESCRIPTION = (
    "Same question only; keep the original question unchanged. For cross-language, comparison, conditional, or multiple dependent facets, add 1–3 short lookups in the documentation language; a simple single-facet question needs none. Preserve exact identifiers, versions, conditions, negation and comparison sides; never batch independent questions, invent the expected answer, or use guessed source names."
)'''
new = '''_GET_DOCS_CONTEXT_LOOKUP_DESCRIPTION = (
    "Same question only. For cross-language, comparison, conditional, or multiple dependent facets use 1–3 short lookups in the documentation language; simple single-facet questions need none. Keep the original question unchanged; preserve exact identifiers, versions, conditions, negation and comparison sides. Never batch independent questions, invent the expected answer, or use guessed source names."
)'''
if old not in text:
    raise SystemExit('runtime lookup description not found')
p.write_text(text.replace(old, new, 1))

# 4) Move lookup-priority policy to ranking owner so projection core remains bounded.
p = Path('docmancer/docs/application/context_candidate_ranking.py')
text = p.read_text()
marker = '\n\ndef _context_rank(\n'
helper = '''\n\ndef _prefer_missing_baseline_candidate(
    candidates: list[Any], selected: list[dict[str, Any]], public_query_ids: set[str],
    host_query_ids: set[str], canonical_query_ids: set[str],
) -> None:
    """Keep original/exact evidence ahead of expansion-only candidates."""
    if not host_query_ids:
        return
    selected_ids = qualified_query_ids(selected)
    missing_public = (public_query_ids - host_query_ids) - selected_ids
    protected = next((i for i, candidate in enumerate(candidates)
                      if qualified_query_ids((candidate,)) & missing_public), None)
    if protected is None:
        missing_canonical = canonical_query_ids - selected_ids
        protected = next((i for i, candidate in enumerate(candidates)
                          if qualified_query_ids((candidate,)) & missing_canonical
                          and not (qualified_query_ids((candidate,)) & host_query_ids)), None)
    if protected not in (None, 0):
        candidates.insert(0, candidates.pop(protected))
'''
if '_prefer_missing_baseline_candidate(' not in text:
    if marker not in text:
        raise SystemExit('ranking helper insertion marker not found')
    text = text.replace(marker, helper + marker, 1)
p.write_text(text)

p = Path('docmancer/docs/application/_docs_context_projection_core.py')
text = p.read_text()
old_import = 'from .context_candidate_ranking import _context_rank, _facet_aware_candidates, _fully_matched_query_ids'
new_import = 'from .context_candidate_ranking import _context_rank, _facet_aware_candidates, _fully_matched_query_ids, _prefer_missing_baseline_candidate'
if old_import not in text:
    raise SystemExit('ranking import not found')
text = text.replace(old_import, new_import, 1)
old = '''        # Host rewrites are expansion lanes. Preserve missing original/exact
        # evidence first, even when the same candidate also matches a host lookup.
        # Canonical-intent fallback is weaker: protect it only when it is baseline-only,
        # so a weak alias cannot outrank a stronger explicit lookup.
        if host_query_ids:
            selected_query_ids = qualified_query_ids(sources)
            missing_public_ids = (public_query_id_set - host_query_ids) - selected_query_ids
            protected_index = next((
                index for index, candidate in enumerate(prepared)
                if qualified_query_ids((candidate,)) & missing_public_ids
            ), None)
            if protected_index is None:
                missing_canonical_ids = canonical_intent_query_ids - selected_query_ids
                protected_index = next((
                    index for index, candidate in enumerate(prepared)
                    if (qualified_query_ids((candidate,)) & missing_canonical_ids)
                    and not (qualified_query_ids((candidate,)) & host_query_ids)
                ), None)
            if protected_index not in (None, 0):
                prepared.insert(0, prepared.pop(protected_index))
'''
new = '''        _prefer_missing_baseline_candidate(
            prepared, sources, public_query_id_set, host_query_ids, canonical_intent_query_ids,
        )
'''
if old not in text:
    raise SystemExit('inline baseline priority block not found')
p.write_text(text.replace(old, new, 1))

# 5) Formatting-only line reduction in model-visible projection.
p = Path('docmancer/docs/application/model_visible_projection.py')
text = p.read_text()
replacements = {
    '''DOCS_SOURCE_FIELDS = frozenset({
    "evidence_id", "path_or_url", "section", "snippet", "version_binding",
    "content_sha256",
})''': '''DOCS_SOURCE_FIELDS = frozenset({"evidence_id", "path_or_url", "section", "snippet",
                                "version_binding", "content_sha256"})''',
    '''PATCH_SOURCE_FIELDS = frozenset({
    "evidence_id", "path", "symbol_or_section", "authority",
    "instruction_trust", "scope", "version_binding", "content_sha256",
})''': '''PATCH_SOURCE_FIELDS = frozenset({"evidence_id", "path", "symbol_or_section", "authority",
                                 "instruction_trust", "scope", "version_binding", "content_sha256"})''',
    '''_OPTIONAL_INSUFFICIENT_KEYS = (
    "operational_status", "context_available", "disposition",
)''': '_OPTIONAL_INSUFFICIENT_KEYS = ("operational_status", "context_available", "disposition")',
}
for old, new in replacements.items():
    if old not in text:
        raise SystemExit('model-visible formatting block not found')
    text = text.replace(old, new, 1)
p.write_text(text)
