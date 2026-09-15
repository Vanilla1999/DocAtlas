"""Counterexamples outside frozen80; test retrieval attribution, not answers."""
from copy import deepcopy
import hashlib
import pytest
from section_scope import STAMP_KEYS
from relaxation import RelaxedBinder, camel_words, explicit_identity, label
from docmancer.docs.domain.evidence_qualification import qualify_evidence


def fixture(mode, doc, text, question, terms, exact):
    start = doc.index(text)
    raw = dict(content=text, char_start=start, char_end=start+len(text), path='api.md',
               project_identity='p', source_class='project_doc', freshness='current', index_freshness='synchronized',
               authority='source_of_truth', lifecycle_status='active', version='1',
               _source_snapshot_sha256='snapshot', _source_catalog_hash='catalog')
    source = dict(snippet=text, path_or_url='api.md', section='untrusted WorkQueue metadata',
                  _qualification_candidate=raw, _expected_project_identity='p')
    registry = {'api.md': dict(project='widgetlib', ref='1', repository='vendor/widgetlib', commit='abc123',
                              sha256=hashlib.sha256(doc.encode()).hexdigest())}
    binder = RelaxedBinder({'api.md':doc}, 'p', {'api.md':tuple(raw.get(k) for k in STAMP_KEYS)},
                           registry=registry, question=question, mode=mode)
    probe = dict(query_text=question, query_terms=terms, exact_terms=exact)
    return binder, source, probe


def check(f):
    b,s,p = f
    return b.qualify(qualify_evidence, p, s, query_id='query-original', visible_text=s['snippet'],
                     evidence_text=s['snippet'], candidate=s['_qualification_candidate'], expected_project_identity='p')


def catalog(question='When does WidgetLib run tasks after response?', exact=None):
    text='Tasks run after returning the response.'
    return fixture('catalog', '# Background processing\n'+text, text, question,
                   ['widgetlib','tasks','run','after','response'], exact or ['widgetlib'])


def spelling(heading='# Work Queues', question='Can WorkQueues run tasks in order?', mode='spelling'):
    text='Tasks run in order and stop after an exception.'
    return fixture(mode, heading+'\n'+text, text, question,
                   ['workqueues','tasks','run','order','exception'], ['workqueues'])


def one(text='A packet is the combination of a header and payload.', heading='## Packet'):
    return fixture('one_anchor', '# Transport\n'+heading+'\n'+text, text,
                   'Из каких компонентов состоит packet в Transport?',
                   ['каких','компонентов','состоит','packet','transport'], ['transport'])


def test_verified_catalog_not_repeated_in_body():
    f=catalog(); old=deepcopy(f[1]); q,proof=check(f)
    assert q.qualified and q.trace['catalog_context_used'] and f[1]==old
    assert 'catalog: widgetlib@1' in label(proof)


@pytest.mark.parametrize('question', ['What is the signature of WidgetLib?', 'Call WidgetLib()',
                                    'Explain class WidgetLib', 'Use `WidgetLib` here'])
def test_catalog_not_api_identity(question):
    assert not check(catalog(question))[0].qualified


def test_catalog_not_another_exact_identifier():
    assert not check(catalog(exact=['widgetlib','otherapi']))[0].qualified


@pytest.mark.parametrize('key,value', [('project_identity','foreign'),('version','2'),('_source_snapshot_sha256','x'),
    ('_source_catalog_hash','x'),('freshness','stale'),('index_freshness','old'),('stale',True),
    ('risk_flags',['unsafe']),('instruction_risk_flags',['unsafe']),('source_class','code')])
def test_hard_source_guards(key,value):
    f=catalog(); f[1]['_qualification_candidate'][key]=value
    assert not check(f)[0].qualified


def test_fake_library_metadata_not_used():
    f=catalog(); f[0].registry['api.md']['project']='otherlib'
    f[1]['_qualification_candidate']['library_id']='widgetlib'
    assert not check(f)[0].qualified


def test_manifest_digest_checked_at_construction():
    f=catalog(); b=f[0]; registry=deepcopy(b.registry); registry['api.md']['sha256']='wrong'
    with pytest.raises(ValueError):
        RelaxedBinder(b.documents,b.identity,b.stamps,registry=registry,question=b.question,mode='catalog')


def test_spaced_title_is_context_not_quote_rewrite():
    f=spelling(); q,p=check(f)
    assert q.qualified and q.trace['spelling_context_used']
    assert 'WorkQueues' not in f[1]['snippet']
    assert p['spellings']==[('WorkQueues','Work Queues')]


@pytest.mark.parametrize('heading', ['# Work Queue','# Other Queues','# Work Queues Extra',
    '# Work Queues\n## OtherQueues','# Work Queues\n## WorkQueue',
    '# API\n## Work Queues\nUnrelated.\n## OtherQueues'])
def test_spelling_does_not_merge_other_symbols(heading):
    assert not check(spelling(heading))[0].qualified


def test_code_spelling_is_not_relaxed():
    assert not check(spelling(question='What is the signature of `WorkQueues`?'))[0].qualified


def test_one_definitional_anchor():
    q,p=check(one())
    assert q.qualified and q.trace['one_anchor_used'] and q.trace['body_matched_terms']==['packet']


@pytest.mark.parametrize('text', ['Packet.', 'The packet button turns green after a click.',
                                 '## Packet', 'Read more about packet in another place.'])
def test_one_topical_word_is_not_definition(text):
    assert not check(one(text))[0].qualified


def test_definition_under_other_heading_not_rescued():
    assert not check(one(heading='## Message'))[0].qualified


def test_missing_distinct_scope_word_not_rescued():
    f=one(); f[2]['exact_terms']=['unrelated']; assert not check(f)[0].qualified


def test_smaller_window_requalified():
    f=one(); assert check(f)[0].qualified
    f[1]['snippet']='packet'; assert not check(f)[0].qualified


def test_forbidden_polarity_marker_kept():
    f=spelling(); f[2]['forbidden_evidence_terms']=['exception']; assert not check(f)[0].qualified


def test_boundaries_and_labels_are_literal():
    f=spelling(); f[1]['_qualification_candidate']['char_start']+=1
    assert not check(f)[0].qualified


def test_features_separate():
    assert not check(spelling(mode='catalog'))[0].qualified
    assert not check(spelling(mode='one_anchor'))[0].qualified


def test_camel_split_keeps_number_and_word_differences():
    assert camel_words('WorkQueues')==('work','queues')
    assert camel_words('WorkQueue')!=camel_words('WorkQueues')
    assert not camel_words('workqueues')
    assert not camel_words('WorkQueue2')


def test_heading_inside_fence_does_not_supply_alias():
    assert not check(spelling('# API\n```\n# Work Queues\n```'))[0].qualified
