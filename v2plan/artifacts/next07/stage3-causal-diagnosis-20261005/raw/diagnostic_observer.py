"""Read-only runtime observer for existing native tests; no result replacement."""
import json
import os
from pathlib import Path
import sys

CURRENT = None
EVENTS = []
NAMES = {
    'project_context_pack', 'get_project_context', '_normalize_project_context',
    '_dedupe_and_guard', 'annotate_context_pack', '_augment_snippet_first_context',
    'get_docs_context', 'project_docs_context', '_subject_relation_groups',
    'rerank_project_doc_chunks', 'fit_stage_items', 'set_context_variants',
    'qualify_evidence', 'build_documentation_query_plan',
}
if os.environ.get('DIAGNOSTIC_FUNCTIONS'):
    NAMES = set(os.environ['DIAGNOSTIC_FUNCTIONS'].split(','))


def profile(frame, event, arg):
    if event != 'return' or '/docmancer/docs/' not in frame.f_code.co_filename:
        return
    name = frame.f_code.co_name
    if name not in NAMES:
        return
    values = frame.f_locals
    keys = {'question', 'context_pack', 'items', 'project_items', 'contamination',
            'deduplication', 'result', 'raw', 'retrieval', 'projection_diagnostics',
            'initially_ranked', 'query_plan', 'chunks', 'scored',
            'qualified_query_ids', 'query_matches', 'context_candidate_ids',
            'candidate', 'query', 'reason', 'stage', 'text', 'relation_groups',
            'source', 'sources', 'raw_snippet', 'candidate_sources', 'decision',
            'choices', 'groups', 'legacy', 'selected', 'limit', 'variant',
            'budget_tokens'}
    EVENTS.append({'node': CURRENT, 'file': frame.f_code.co_filename,
                   'line': frame.f_lineno, 'function': name,
                   'locals': {k: v for k, v in values.items() if k in keys},
                   'return': arg})
    if name == 'record':
        caller = frame.f_back
        EVENTS[-1]['caller'] = {'line': caller.f_lineno, 'locals': {
            k: v for k, v in caller.f_locals.items() if k in {
                'obligations', 'query_plan', 'selected_authoritative_public_ids',
                'new_components', 'novel_independent_public_ids', 'qualified_ids',
                'canonical_intent_query_ids', 'selected_canonical_ids', 'sources',
            }}}
    # Freeze now: later code can legitimately mutate dictionaries.
    EVENTS[-1] = json.loads(json.dumps(EVENTS[-1], default=repr, ensure_ascii=False))


def pytest_runtest_call(item):
    global CURRENT
    CURRENT = item.nodeid
    sys.setprofile(profile)


def pytest_runtest_teardown(item):
    sys.setprofile(None)
    with Path(os.environ['DIAGNOSTIC_OUTPUT']).open('a') as stream:
        for event in EVENTS:
            stream.write(json.dumps(event, ensure_ascii=False) + '\n')
    EVENTS.clear()
