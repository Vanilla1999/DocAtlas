"""Source-bound CommonMark representation; no query/gold-guided ownership."""
import hashlib

import pytest

from docmancer.core import structured_chunking as core
from experiments.retrieval_ablation.structure import commonmark_parents, source_structure_parser


def test_supported_atx_parents_and_child_prefixes_are_baseline_green():
    raw = '# Client\n\nintro\n\n## Client.alpha()\n\nThis method does not retry cancellation.\n'
    old_parents, old_children = core.chunk_markdown_parent_child(raw, 'source-one')
    with source_structure_parser():
        parents, children = core.chunk_markdown_parent_child(raw, 'source-one')
    assert parents == old_parents
    assert children == old_children


def test_setext_owner_is_not_changed_by_a_reference_to_another_api():
    raw = ('Client.alpha()\n==============\n\nThis method raises ErrAlpha on cancellation. See Client.beta().\n\n'
           'Client.beta()\n=============\n\nThis method does not raise ErrAlpha.\n')
    parents = commonmark_parents(raw, 'source-one')
    assert [p.title for p in parents] == ['Client.alpha()', 'Client.beta()']
    assert 'See Client.beta()' in parents[0].display_text
    assert 'does not raise' not in parents[0].display_text
    assert 'does not raise' in parents[1].display_text


def test_same_method_name_in_distinct_classes_has_distinct_source_owners():
    raw = '# ClassOne\n\nrun()\n-----\n\nfirst contract\n\n# ClassTwo\n\nrun()\n-----\n\nsecond contract\n'
    methods = [p for p in commonmark_parents(raw, 'source-one') if p.title == 'run()']
    assert [p.heading_path for p in methods] == [('ClassOne', 'run()'), ('ClassTwo', 'run()')]
    assert methods[0].logical_id != methods[1].logical_id


def test_code_html_quotes_and_list_headings_do_not_create_page_owners():
    raw = ('# Actual\n\n```md\n# Fenced\nFake\n====\n```\n\n'
           '    # IndentedCode\n\n<div>\n# HtmlExample\n</div>\n\n'
           '> # QuotedWarning\n> Do not retry.\n\n- # ListExample\n\n## Next\n\nreal body\n')
    assert [p.title for p in commonmark_parents(raw, 'source-one')] == ['Actual', 'Next']


def test_unicode_crlf_multiline_setext_and_missing_final_newline_keep_original_coordinates():
    raw = 'Введение\r\n\r\nMéthode\r\nalpha()\r\n======\r\n\r\nНе удаляй " /-S"; * не **.'
    parents = commonmark_parents(raw, 'source-one')
    assert parents[1].title == 'Méthode\nalpha()'
    assert ''.join(p.display_text for p in parents) == raw
    for parent in parents:
        assert raw[parent.char_start:parent.char_end] == parent.display_text
        assert raw.encode()[parent.byte_start:parent.byte_end].decode() == parent.display_text
        assert parent.source_content_hash == hashlib.sha256(raw.encode()).hexdigest()


def test_warning_lists_examples_and_exact_literals_survive_child_ingestion():
    raw = ('Client.alpha()\n==============\n\nThis method retries only if enabled.\n\n'
           '> Warning: do not retry cancellation.\n\n'
           '- First retain the original question.\n- Then preserve the condition.\n\n'
           '```python\npattern = " /-S"\nstar = "*"\ndouble_star = "**"\n```\n')
    with source_structure_parser():
        parents, children = core.chunk_markdown_parent_child(raw, 'source-one')
    assert children
    assert ''.join(c.display_text for c in children) == raw
    assert {c.parent_logical_id for c in children} == {parents[0].logical_id}
    assert all(raw[c.char_start:c.char_end] == c.display_text for c in children)
    assert all(c.retrieval_token_estimate <= 512 for c in children)


def test_heading_reorder_and_rename_preserve_owned_body_not_exact_rank():
    for names in [('Client.alpha()', 'Client.beta()'), ('Widget.nimbus()', 'Widget.zephyr()')]:
        blocks = [f'{name}\n{"=" * len(name)}\n\nThis method has contract {i}. See {names[1-i]}.\n\n'
                  for i, name in enumerate(names)]
        for ordered in (blocks, list(reversed(blocks))):
            parents = commonmark_parents(''.join(ordered), 'source-one')
            owned = {p.title: p.display_text for p in parents}
            for i, name in enumerate(names):
                assert f'contract {i}.' in owned[name]
                assert f'contract {1-i}.' not in owned[name]


def test_repeated_heading_occurrences_remain_distinct_and_source_bound():
    raw = 'API\n===\n\nfirst condition\n\nAPI\n===\n\nsecond condition\n'
    parents = commonmark_parents(raw, 'source-one')
    assert [p.occurrence for p in parents] == [1, 2]
    assert len({p.logical_id for p in parents}) == 2
    assert parents[0].char_end == parents[1].char_start


def test_parser_hook_invalidates_a_cache_from_the_other_representation_and_restores_on_failure():
    from experiments.retrieval_ablation.heading_hook import one_body_match_heading_context
    from docmancer.docs.domain import evidence_qualification as gate
    original_gate = gate.qualify_evidence
    with pytest.raises(ValueError, match='unsupported'):
        with one_body_match_heading_context(phase='unknown'):
            pass
    for phase in ('admission', 'final'):
        with one_body_match_heading_context(phase=phase) as phase_stats:
            gate.qualify_evidence({'query_terms': ['cancellation']}, query_id='q',
                                 visible_text='Cancellation is never retried.')
            assert phase_stats['phase'] == phase
            assert all(c['gained'] == c['lost'] == 0 for c in phase_stats['call_sites'].values())
        assert gate.qualify_evidence is original_gate
    with pytest.raises(RuntimeError, match='heading failure'):
        with one_body_match_heading_context() as stats:
            assert stats['changed_comparisons'] == 1
            assert gate.qualify_evidence is not original_gate
            for facts in ({'risk_flags': ['unsafe']}, {'freshness': 'stale'},
                          {'project_identity': 'foreign'}):
                rejected = gate.qualify_evidence(
                    {'query_terms': ['cancellation']}, query_id='q',
                    visible_text='Cancellation is never retried.',
                    candidate={'project_identity': 'repo', **facts},
                    expected_project_identity='repo')
                assert not rejected.qualified
            for body in ('Unrelated prose.', 'Cancellation is never retried.'):
                rejected = gate.qualify_evidence(
                    {'query_terms': ['client.alpha', 'cancellation'],
                     'exact_terms': ['client.alpha']}, query_id='q',
                    visible_text=body)
                assert not rejected.qualified
            assert sum(c['calls'] for c in stats['call_sites'].values()) == stats['qualification_calls']
            assert all(c['gained'] == c['lost'] == 0 for c in stats['call_sites'].values())
            raise RuntimeError('heading failure')
    assert gate.qualify_evidence is original_gate
    from docmancer.docs.domain.source_subject_binding import _document_structure
    original = core.parse_markdown_parents
    raw = 'API\n===\n\nbody contract\n'
    _document_structure.cache_clear()
    assert _document_structure(raw, 'source-one')[1][0].title == 'Document'
    with pytest.raises(RuntimeError, match='controlled failure'):
        with source_structure_parser():
            assert _document_structure(raw, 'source-one')[1][0].title == 'API'
            raise RuntimeError('controlled failure')
    assert core.parse_markdown_parents is original
    assert _document_structure(raw, 'source-one')[1][0].title == 'Document'
    _document_structure.cache_clear()
