from docmancer.docs.application.context_query_probes import independent_query_probes


def _source(text):
    return {'snippet': text, 'source_class': 'project_doc', 'project_identity': 'repo',
            '_expected_project_identity': 'repo', 'retrieval_query_matches': {}}


def _plan(*texts):
    return {'queries': [{'query_id': f'query-lookup-{i}', 'origin': 'host_lookup', 'text': text}
                        for i, text in enumerate(texts, 1)]}


def test_independent_lookup_requires_its_distinctive_body_terms():
    plan = _plan('project architecture documentation', 'project testing documentation')
    result = independent_query_probes(_source('Project architecture documentation describes the layers.'), plan)
    assert set(result) == {'query-lookup-1'}
    assert result['query-lookup-1']['qualified'] is True


def test_independent_lookup_does_not_promote_one_generic_word():
    assert independent_query_probes(_source('Contributor configuration is stored locally.'), _plan('contributor overview')) == {}


def test_independent_lookup_preserves_exact_and_source_policy():
    plan = _plan('How does `EXACT_KEY` select storage?')
    assert independent_query_probes(_source('OTHER_KEY selects storage.'), plan) == {}
    source = _source('EXACT_KEY selects local storage.')
    assert independent_query_probes(source, plan)
    source['project_identity'] = 'another-repo'
    assert independent_query_probes(source, plan) == {}
    source['project_identity'] = 'repo'
    plan['queries'][0]['forbidden_evidence_terms'] = ['local']
    assert independent_query_probes(source, plan) == {}


def test_generated_aliases_are_not_invented_as_direct_public_coverage():
    plan = _plan('storage configuration')
    plan['queries'][0].update(origin='canonical_intent', public_parent_query_id='query-original')
    assert independent_query_probes(_source('Storage configuration is local.'), plan) == {}
