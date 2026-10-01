from pathlib import Path

from docmancer.docs.project import ProjectMetadataReader
from docmancer.docs.domain.project_doc_ranking import source_lane_allowed
from docmancer.docs.domain.lifecycle_policy import lifecycle_allows, lifecycle_intent

REPO = Path(__file__).resolve().parents[1]


def test_retired_answer_protocol_is_not_current_authority():
    metadata = ProjectMetadataReader().read(REPO)
    assert metadata.docs_catalog_valid
    entries = {row.path: row for row in metadata.docs_candidates}
    old = entries['eval/project_answer_surface_v1/README.md']
    assert (old.authority, old.lifecycle_status, old.impact_policy) == ('historical', 'superseded', 'search_only')
    assert (entries['docs/adr/0002-context-retrieval-vs-answer-proof.md'].authority,
            entries['docs/adr/0002-context-retrieval-vs-answer-proof.md'].lifecycle_status) == ('historical', 'superseded')
    for path in ('docs/adr/0003-context-first-project-reads.md', 'docs/mcp-docs-server.md',
                 'eval/project_context_quality/README.md'):
        assert (entries[path].authority, entries[path].lifecycle_status) == ('source_of_truth', 'active')
    assert entries['docs/source-continuation.md'].doc_scope == 'module'
    assert entries['docs/source-continuation.md'].module_path == 'docmancer'
    for path in ('.hermes/plans/2026-07-20-natural-language-library-retrieval.md',
                 'docs/analysis/context7-style-project-chat-regression.md'):
        assert entries[path].authority == 'supporting'
        assert not source_lane_allowed(path, 'What is the current public MCP contract?')
    assert entries['roadmap/README.md'].lifecycle_status == 'active'


def test_retired_protocol_has_lifecycle_notice_and_current_links():
    text = (REPO / 'eval/project_answer_surface_v1/README.md').read_text()
    assert 'Status: superseded' in text
    assert '../../docs/adr/0003-context-first-project-reads.md' in text
    assert '../project_context_quality/README.md' in text
    assert 'not the current operational contract' in text


def test_existing_history_routing_preserves_retired_protocol():
    path = 'eval/project_answer_surface_v1/README.md'
    question = 'What did the historical project-answer surface v1 evaluation protocol freeze?'
    assert source_lane_allowed(path, question)
    assert not source_lane_allowed(path, 'How do current project reads return context?')
    assert lifecycle_intent(question) == 'historical'
    assert lifecycle_allows({'lifecycle_status': 'superseded'}, lifecycle_intent(question))
    assert not lifecycle_allows({'lifecycle_status': 'superseded'}, 'current')
