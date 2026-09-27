"""Complete host lookup matches must precede partial topical cross-matches.

These are selection-order tests, not semantic proof or an expanded source budget.
"""
from copy import deepcopy

import pytest

from docmancer.docs.application.context_candidate_ranking import _facet_aware_candidates
from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens
from docmancer.mcp.docs_server import call_docs_tool_payload
from tests.docs.test_question_frame_paraphrase_e2e import _service


def candidate(name, ratios, score):
    return {
        'path': f'docs/{name}.md', 'content': name,
        'source_class': 'project_doc', 'project_identity': 'fixture',
        'authority': 'source_of_truth',
        'retrieval_query_matches': {
            query_id: {'qualified': True, 'match_ratio': ratio,
                       'query_text': query_id, 'query_origin': 'host_lookup',
                       'lexical_score': score}
            for query_id, ratio in ratios.items()
        },
    }


def test_complete_missing_host_match_beats_multiple_partial_votes():
    partial = candidate('overview', {'h1': 0.5, 'h2': 0.5}, 100)
    exact = candidate('operation', {'h1': 1.0}, 1)
    inputs = [partial, exact]
    before = deepcopy(inputs)
    ranked = _facet_aware_candidates(inputs, query_text={'h1': 'setup', 'h2': 'query'},
                                    required_query_ids={'h1', 'h2'}, host_query_ids={'h1', 'h2'})
    assert ranked[0] == exact
    assert inputs == before, 'Ordering must not rewrite qualification or scores'


def test_completed_direction_cannot_outvote_the_still_missing_direction():
    old = candidate('old-operation', {'h1': 1.0, 'h2': 0.5}, 100)
    missing = candidate('new-operation', {'h2': 1.0}, 1)
    ranked = _facet_aware_candidates([old, missing], query_text={'h1': 'setup', 'h2': 'query'},
                                    required_query_ids={'h2'}, host_query_ids={'h1', 'h2'})
    assert ranked[0] == missing


def test_non_host_ranking_keeps_its_existing_order():
    partial = candidate('overview', {'h1': 0.5, 'h2': 0.5}, 100)
    exact = candidate('operation', {'h1': 1.0}, 1)
    ranked = _facet_aware_candidates([partial, exact], query_text={'h1': 'setup', 'h2': 'query'},
                                    required_query_ids={'h1', 'h2'}, host_query_ids=set())
    assert ranked[0] == partial


@pytest.mark.parametrize('product', ['Lumen', 'Orion'])
def test_three_requested_commands_survive_real_index(product, tmp_path, monkeypatch):
    project = tmp_path / 'project'
    project.mkdir()
    command = product.lower()
    facts = [
        f'Run `{command} setup` to create the configuration and database.',
        f'Run `{command} ingest ./notes` to index local files.',
        f'Run `{command} query "topic"` to search the index.',
    ]
    (project / 'README.md').write_text(f'# {product}\n\n{product} indexes local documentation.\n')
    (project / 'commands.md').write_text(
        f'# {product} commands\n\n' + '\n\n'.join(
            f'## Step {i}\n\n{fact}' for i, fact in enumerate(facts, 1)) + '\n')
    (project / 'docatlas.project-docs.yaml').write_text(
        'schema_version: 1\ndocuments:\n' + ''.join(
            f'  - path: {path}\n    role: runbook\n    scope: project\n'
            f'    description: {product} local workflow.\n    authority: source_of_truth\n'
            '    status: active\n    impact: track\n'
            for path in ('README.md', 'commands.md')))
    service = _service(tmp_path, monkeypatch)
    assert service.sync_project_docs(str(project), with_vectors=False).status == 'success'
    payload = call_docs_tool_payload('get_docs_context', {
        'question': f'How do I set up {product}, ingest local files, and query the index?',
        'lookup_queries': [f'{product} setup', f'{product} ingest local files', f'{product} query index'],
        'project_path': str(project), 'scope': 'project',
    }, service)
    visible = '\n'.join(row['snippet'] for row in payload.get('sources', []))
    assert all(fact in visible for fact in facts), {'missing': [f for f in facts if f not in visible], 'payload': payload}
    assert payload['answer_supported'] is False
    assert payload['edit_ready'] is False
    assert len(payload['sources']) <= 3
    assert docs_context_budget_tokens(payload) <= 800
