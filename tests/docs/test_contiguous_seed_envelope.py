"""Related quotes need their canonical intervening explanation, not more budget."""
from eval.evidence_quality_v2.run import audit_payload, documents_for, load_protocol
from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
from eval.evidence_quality_v2.observer import observe_call


def test_index_restriction_and_cause_arrive_together_in_first_packet(tmp_path):
    _, cases, manifest = load_protocol()
    case = next(c for c in cases if c['id'] == 'uv-04')
    root = tmp_path / 'project'
    write_project(root, documents_for('uv', manifest))
    with isolated_service(tmp_path / 'state') as (service, config):
        index_project(service, config, root)
        payload, trace = observe_call(service, {
            'question': case['question'], 'project_path': str(root), 'scope': 'all',
        })
    required = case['required_claims'][0]['witness_sets'][0]['parts'][0]['text']
    assert any(required in s['snippet'] for s in payload.get('sources', [])), payload
    assert audit_payload(payload, trace['snapshot'], root) == []
    assert payload['answer_supported'] is False and payload['edit_ready'] is False


def _seed(tmp_path):
    from unittest.mock import patch
    from docmancer.docs.application import joint_context_selection as joint
    _, cases, manifest = load_protocol()
    case = next(c for c in cases if c['id'] == 'uv-04')
    root = tmp_path / 'project'
    write_project(root, documents_for('uv', manifest))
    with isolated_service(tmp_path / 'state') as (service, config):
        index_project(service, config, root)
        with patch.object(joint, 'select_joint_context', side_effect=lambda p, b, r, **kw: (p, b)):
            p, t = observe_call(service, {'question': case['question'], 'project_path': str(root), 'scope': 'all'})
    return p, t['snapshot'], t['stages']['projector_inputs'][0], root


def test_envelope_keeps_every_byte_in_the_gap_and_original_occurrences(tmp_path):
    from copy import deepcopy
    from docmancer.docs.application.joint_seed_envelopes import seed_envelopes
    p, b, _, _ = _seed(tmp_path)
    before = deepcopy((p, b))
    options = seed_envelopes(p, b)
    assert options and len(options) <= 2
    for index, (row, source, kind) in options:
        raw = source['_reference_evidence']['raw_document']
        ref = source['_reference_evidence']
        assert row['snippet'] == raw[ref['char_start']:ref['char_end']]
        assert all(old['snippet'] in row['snippet'] for old in p['sources'])
        assert ref['owner'] is not None
        assert kind == 'seed_envelope'
    assert (p, b) == before


def test_single_seed_does_not_trigger_arbitrary_neighbor_expansion(tmp_path):
    from docmancer.docs.application.joint_seed_envelopes import seed_envelopes
    p, b, _, _ = _seed(tmp_path)
    p['sources'] = p['sources'][:1]
    assert seed_envelopes(p, b) == []


def test_envelope_must_not_erase_an_inherited_forbidden_gap(tmp_path):
    from docmancer.docs.application.joint_context_selection import select_joint_context
    p, b, r, root = _seed(tmp_path)
    for source in b.values():
        if not isinstance(source, dict) or not isinstance(source.get('source'), dict):
            continue
        for probe in source['source'].get('retrieval_query_matches', {}).values():
            probe['forbidden_evidence_terms'] = ['malicious package']
    out, bindings = select_joint_context(p, b, r, max_tokens=800)
    assert not any('malicious package' in s['snippet'] for s in out.get('sources', []))
    assert audit_payload(out, bindings, root) == []


def test_old_inspection_uri_survives_replacement_of_unissued_draft_locators(tmp_path):
    from unittest.mock import patch
    import json
    from docmancer.mcp.docs_server import read_docs_resource
    _, cases, manifest = load_protocol()
    case = next(c for c in cases if c['id'] == 'mkdocs-05')
    docs = documents_for('mkdocs', manifest)
    root = tmp_path / 'project'
    write_project(root, docs)
    request = {'question': case['question'], 'project_path': str(root), 'scope': 'all'}
    with isolated_service(tmp_path / 'state') as (service, config):
        index_project(service, config, root)
        # Force the old draft shape only on the first call. Otherwise early
        # delivery already supplies the rule and both calls issue the same
        # idempotent, single-use continuation: that is not a replacement test.
        with (patch('docmancer.docs.application.query_block_recovery.select_query_block_recovery',
                    side_effect=lambda p, b, r, **kw: (p, b)),
              patch('docmancer.docs.application.need_context_projection.precedence_context_variants',
                    side_effect=lambda *args, **kwargs: iter(()))):
            before, _ = observe_call(service, request)
        if before.get('read_next'):
            old = before['read_next'][0]
        else:
            source = next(s for s in before['sources'] if s.get('source_uri'))
            old = {'source_uri': source['source_uri'], 'path': source['path_or_url'],
                   'line_start': source['line_end'] + 1}
        after, trace = observe_call(service, request)
        fact = case['required_claims'][0]['witness_sets'][0]['parts'][0]['text']
        assert any(fact in s['snippet'] for s in after['sources'])
        assert audit_payload(after, trace['snapshot'], root) == []
        assert all(after[key] is False for key in ('answer_supported', 'answer_available', 'edit_ready'))
        if after.get('read_next'):
            new = after['read_next'][0]
        else:
            source = next(s for s in after['sources'] if s.get('source_uri'))
            new = {'source_uri': source['source_uri'], 'path': source['path_or_url'],
                   'line_start': source['line_end'] + 1}
        assert old['source_uri'] != new['source_uri'], 'scenario must actually replace a locator'
        previous_read = json.loads(read_docs_resource(old['source_uri'], service)['text'])
        assert previous_read['line_start'] == old['line_start']
        raw = docs[old['path']]
        assert previous_read['snippet'] in '\n'.join(raw.splitlines()[previous_read['line_start']-1:previous_read['line_end']])
        replay = json.loads(read_docs_resource(old['source_uri'], service)['text'])
        assert replay['status'] == 'source_unavailable'
        assert replay['reason_code'] == 'unknown_or_expired_reference'
        current_read = json.loads(read_docs_resource(new['source_uri'], service)['text'])
        assert current_read['line_start'] == new['line_start']
        raw = docs[new['path']]
        assert current_read['snippet'] in '\n'.join(
            raw.splitlines()[current_read['line_start']-1:current_read['line_end']])
        replay = json.loads(read_docs_resource(new['source_uri'], service)['text'])
        assert replay['status'] == 'source_unavailable'
        assert replay['reason_code'] == 'unknown_or_expired_reference'
