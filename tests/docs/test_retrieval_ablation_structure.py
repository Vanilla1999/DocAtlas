"""Format and owner controls; synthetic mechanisms, not retrieval quality."""
import hashlib
from copy import deepcopy

import pytest

from docmancer.core.structured_chunking import parse_markdown_parents
from experiments.retrieval_ablation.structure import canonical_markdown


def test_setext_binding_stays_with_its_declaration_not_a_linked_neighbor():
    raw = ('Alpha.wait\n----------\n\nThis method does not cancel work. See `Beta.wait`.\n\n'
           'Beta.wait\n---------\n\nThis method cancels work.\n')
    result = canonical_markdown(raw)
    parents = parse_markdown_parents(result['text'], 'source')
    assert [p.title for p in parents] == ['Alpha.wait', 'Beta.wait']
    assert 'does not cancel' in parents[0].display_text
    assert 'This method cancels' not in parents[0].display_text
    assert result['raw_sha256'] == hashlib.sha256(raw.encode()).hexdigest()
    assert result['canonical_sha256'] == hashlib.sha256(result['text'].encode()).hexdigest()
    assert result['citation_space'] == 'canonical_project_extract'


def test_commonmark_fence_does_not_invent_an_api_owner():
    raw = ('# Real.wait\n\n````python\n```` not a closing fence\n# Fake.wait\nprint(" /-S **")\n````\n\nStill the real method.\n')
    canonical = canonical_markdown(raw)['text']
    parents = parse_markdown_parents(canonical, 'source')
    assert [p.title for p in parents] == ['Real.wait']
    assert 'print(" /-S **")' in canonical


@pytest.mark.parametrize('name', ['Alpha', 'Zeta', 'Ωmega'])
def test_renaming_and_reordering_preserve_source_owner(name):
    sections = [f'{name}.read\n-----------\n\nThis method preserves `*`, `**` and ` /-S`.\n',
                '# Other.read\n\nThis method has the opposite rule.\n']
    for sequence in (sections, list(reversed(sections))):
        result = canonical_markdown('\n'.join(sequence))
        parents = parse_markdown_parents(result['text'], 'source')
        assert f'{name}.read' in [p.title for p in parents]
        owner = next(p for p in parents if p.title == f'{name}.read')
        assert 'preserves `*`, `**` and ` /-S`' in owner.display_text
        assert 'opposite rule' not in owner.display_text


def test_same_owner_assembly_adds_condition_without_foreign_api(tmp_path):
    from tests.docs.test_retrieval_ablation_packet import indexed_case
    from experiments.retrieval_ablation.adapters import native_diagnostic
    from experiments.retrieval_ablation.packet import _prepare
    from experiments.retrieval_ablation.structure import bounded_bundle
    text = ('# Alpha.wait\n\nAlpha.wait has a retry budget. ' +
            'The operation has a documented lifecycle. ' * 12 +
            '\n\nDo not restart cancelled work.\n\n# Beta.wait\n\nAlways restart cancelled work.\n')
    with indexed_case(tmp_path, {'methods.md': text}) as (store, docs, filters, _):
        native = native_diagnostic(store, ['Alpha.wait retry budget'], filters=filters, sources=docs, raw_limit=1)
        prepared, _, _ = _prepare(store, native, docs, 'Alpha.wait retry budget', [])
        before = deepcopy(prepared)
        bundle, trace = bounded_bundle(*prepared[0])
        assert prepared == before
        visible = '\n'.join(original['content'] for _, original in bundle)
        assert 'Do not restart cancelled work.' in visible
        assert '# Alpha.wait' in visible
        assert 'Beta.wait' not in visible and 'Always restart' not in visible
        assert trace['neighbor_reads'] <= 2
        for _, original in bundle:
            ref = original['_reference_evidence']
            assert original['content'] == text[ref['char_start']:ref['char_end']]


@pytest.mark.parametrize('raw', [
    '# Header\n\n- A list\n  - nested `**`\n\nWarning: do not remove ` /-S`.\n',
    '# Класс\r\n\r\nИмя.read\r\n---------\r\n\r\nThis method keeps **literal** spaces.\r\n',
    '````python\nFake.owner\n==========\nprint("\\t * **")\n````\n',
    '# Class One\n\n## read\n\nFirst.\n\n# Class Two\n\n## read\n\nSecond.\n',
])
def test_canonical_copy_mapping_preserves_every_non_markup_byte(raw):
    result = canonical_markdown(raw)
    for row in result['copied_spans']:
        a, b = row['raw_span']
        x, y = row['canonical_span']
        assert raw[a:b] == result['text'][x:y]
    # Applying only the declared transformations reconstructs the artifact.
    reconstructed, position = [], 0
    for row in result['edits']:
        a, b = row['raw_span']
        assert raw[a:b] == row['raw_text']
        reconstructed += [raw[position:a], row['canonical_text']]
        position = b
    reconstructed.append(raw[position:])
    assert ''.join(reconstructed) == result['text']


@pytest.mark.parametrize('raw', ['<div>\n# Hidden.owner\n</div>\n',
    'First line\nsecond line\n-----------\n', '```\nunterminated\n'])
def test_unsupported_representation_fails_closed(raw):
    with pytest.raises(ValueError, match='BLOCKED_REPRESENTATION'):
        canonical_markdown(raw)


def test_matrix_replays_exact_pool_and_uses_same_physical_path(tmp_path):
    from tests.docs.test_retrieval_ablation_packet import input_fixture
    from experiments.retrieval_ablation.run import _matrix_fixture
    text = ('Alpha.wait\n----------\n\nAlpha.wait has a retry budget. ' +
            'The operation has a documented lifecycle. '*12 +
            '\n\nDo not restart cancelled work.\n\nBeta.wait\n---------\n\nAlways restart cancelled work.\n')
    corpus, spec, protocol = input_fixture(tmp_path, {'methods.md': text})
    protocol['raw_hits'] = 1
    results = _matrix_fixture(corpus, spec, {'question': 'Alpha.wait retry budget'}, protocol)
    assert set(results) == {'A', 'B', 'D_L', 'E_G_L'}
    assert all(r['execution_status'] == 'EXECUTED' and r['audit_errors'] == [] for r in results.values())
    assert results['A']['controlled_project_path'] == results['B']['controlled_project_path']
    assert results['B']['saved_native_pool'] == results['D_L']['saved_native_pool'] == results['E_G_L']['saved_native_pool']
    assert results['D_L']['pre_gate_input_sha256'] == results['E_G_L']['pre_gate_input_sha256']
    assert results['D_L']['search_count'] == results['E_G_L']['search_count'] == 0
    assert 'Do not restart' not in str(results['B']['model_visible_packet'])
    assert 'Do not restart' in str(results['D_L']['model_visible_packet'])
    assert 'Always restart' not in str(results['D_L']['model_visible_packet'])
    assert any(t['status'] == 'ASSEMBLED' for t in results['D_L']['assembly_trace'])


def test_oversized_atomic_assembly_is_omitted_without_cutting(tmp_path):
    from tests.docs.test_retrieval_ablation_packet import indexed_case
    from experiments.retrieval_ablation.adapters import native_diagnostic
    from experiments.retrieval_ablation.packet import pack_native
    text = '# Alpha.wait\n\nAlpha.wait retry budget.\n\n' + ('Do not retry cancellation. '*160) + '\n'
    with indexed_case(tmp_path, {'methods.md':text}) as (store, docs, filters, _):
        native = native_diagnostic(store, ['Alpha.wait retry budget'], filters=filters, sources=docs, raw_limit=1)
        result = pack_native(store, native, sources=docs, question='Alpha.wait retry budget', assembly=True)
        assert result['model_visible_packet']['status'] == 'insufficient_evidence'
        assert result['assembly_trace'][0]['status'] == 'OVERSIZED_OR_POLICY_REJECTED_ATOMIC_BUNDLE'


def test_source_without_owner_does_not_invent_assembly(tmp_path):
    from tests.docs.test_retrieval_ablation_packet import indexed_case, _native
    from experiments.retrieval_ablation.packet import pack_native
    with indexed_case(tmp_path, {'notes.md':'The retry budget is three.\n\nCancellation remains terminal.\n'}) as (s,d,f,_):
        result = pack_native(s, _native(s,d,f), sources=d, question='retry budget', assembly=True)
        assert all(t['status'] == 'NO_STRUCTURAL_OWNER_SEED_ONLY' for t in result['assembly_trace'])
        assert all(t['neighbor_reads'] == 0 for t in result['assembly_trace'])


def test_disjoint_required_heading_remains_a_separate_counted_quote(tmp_path):
    from tests.docs.test_retrieval_ablation_packet import indexed_case
    from experiments.retrieval_ablation.adapters import native_diagnostic
    from experiments.retrieval_ablation.packet import pack_native
    text = ('# Alpha.wait\n\nUnrelated introduction.\n\nAnother separate block.\n\n'
            'Alpha.wait has a retry budget. ' + 'The operation has a documented lifecycle. '*12 +
            '\n\nDo not restart cancelled work.\n')
    with indexed_case(tmp_path, {'methods.md': text}) as (store, docs, filters, _):
        native = native_diagnostic(store, ['Alpha.wait retry budget'], filters=filters, sources=docs, raw_limit=1)
        result = pack_native(store, native, sources=docs, question='Alpha.wait retry budget', assembly=True)
        packet = result['model_visible_packet']
        assert len(packet['sources']) == 2
        assert packet['sources'][0]['snippet'] == '# Alpha.wait'
        assert 'Unrelated introduction.' not in packet['sources'][1]['snippet']
        assert packet['sources'][0]['line_end'] < packet['sources'][1]['line_start']
        limited = pack_native(store, native, sources=docs, question='Alpha.wait retry budget', assembly=True, source_entries=1)
        assert limited['model_visible_packet']['status'] == 'insufficient_evidence'


@pytest.mark.parametrize('separator', ['\u2028', '\u2029', '\x85', '\r'])
def test_incompatible_line_boundaries_cannot_erase_source_declarations(separator):
    # Python splitlines and CommonMark disagree on these boundaries. The
    # unchanged index/audit coordinate system cannot safely represent them.
    raw = f'Preamble{separator}still prose.\n\nOwner.read\n----------\n\nDo not mutate.\n'
    with pytest.raises(ValueError, match='BLOCKED_REPRESENTATION'):
        canonical_markdown(raw)
