"""User-visible regression on pinned upstream docs, without host lookup hints."""
from pathlib import Path

from eval.evidence_quality_v2.run import load_protocol, documents_for
from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
from docmancer.mcp.docs_server import call_docs_tool_payload
from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens

QUESTION = "Перечисли способы включить strict mode, включая field, annotation, config и validation call."


def test_original_direct_question_delivers_all_four_strict_mode_controls(tmp_path):
    _, _, manifest = load_protocol()
    documents = documents_for('pydantic', manifest)
    project = tmp_path / 'project'
    write_project(project, documents)
    # Read expected occurrences from immutable source, outside runtime arguments.
    lines = documents['docs/concepts/strict_mode.md'].splitlines()
    expected = ['\n'.join(lines[40:42]), lines[42], lines[43], lines[45]]
    with isolated_service(tmp_path / 'state') as (service, config):
        inventory = index_project(service, config, project)
        assert not inventory['excluded_or_failed_paths']
        result = call_docs_tool_payload('get_docs_context', {
            'question': QUESTION, 'project_path': str(project), 'scope': 'all',
        }, service)
    visible = '\n'.join(s['snippet'] for s in result.get('sources', []))
    assert all(fact in visible for fact in expected), {
        'missing': [fact for fact in expected if fact not in visible], 'payload': result,
    }
    assert result['answer_supported'] is False
    assert result['edit_ready'] is False
    assert len(result['sources']) <= 3
    assert docs_context_budget_tokens(result) <= 800
