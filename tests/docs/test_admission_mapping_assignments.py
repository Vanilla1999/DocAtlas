"""Respectively binds two ordered source lists; no variable names in grammar."""
import pytest
from tests.docs.test_admission_relation_witnesses import qualify
from tests.docs._reference_binding_fixtures import capture_reference_case, visible
from tests.docs.test_admission_meaning import demand

EN = 'Which variables set routing for channel-a, channel-b and all channels?'
RU = 'Какие переменные задают routing для channel-a, channel-b и all channels?'
BODY = '`ROUTE_X`, `ROUTE_Y`, `ROUTE_ANY` set the routing to be used for `channel-a`, `channel-b`, or all channels respectively.'


@pytest.mark.parametrize('question', [EN, RU])
def test_actual_compiler_and_local_assignment_preserve_all_domains(question):
    frame = demand(question)
    assert frame.operator == 'mapping'
    targets = [s for s in frame.arguments if s.role == 'target']
    assert [s.text for s in targets] == ['channel-a', 'channel-b', 'all channels']
    result = qualify(question, BODY)
    assert result.qualified and result.trace.get('admission_route') == 'typed_local', result.trace


@pytest.mark.parametrize('bad', [
    '`ROUTE_X`, `ROUTE_Y` set routing for channel-a, channel-b and all channels respectively.',
    '`ROUTE_X`, `ROUTE_Y`, `ROUTE_ANY` set routing for channel-a, channel-b and private channels respectively.',
    '`ROUTE_X`, `ROUTE_Y`, `ROUTE_ANY` set routing for channel-a, channel-b and all channels.',
    '`ROUTE_X`, `ROUTE_Y`, `ROUTE_ANY` set encoding for channel-a, channel-b and all channels respectively.',
    'Routing variables are listed for channel-a, channel-b and all channels. Other values are mapped respectively.',
])
def test_unbound_or_incomplete_correspondence_is_rejected(bad):
    assert not qualify(EN, bad).qualified


def test_a_different_property_and_different_variable_names_transfer():
    q = 'Which variables control compression for images and text?'
    body = '`IMAGE_FORMAT` and `TEXT_FORMAT` control compression for images and text respectively.'
    assert qualify(q, body).qualified


def test_mapping_question_does_not_prescribe_the_answer_variables():
    first = qualify(EN, BODY)
    second = qualify(EN, BODY.replace('ROUTE_X', 'FOO').replace('ROUTE_Y', 'BAR').replace('ROUTE_ANY', 'BAZ'))
    assert first.qualified and second.qualified


def test_native_assignment_reaches_the_final_packet(tmp_path):
    cap = capture_reference_case(tmp_path, {'Guide.md': '# Routing\n\n'+BODY}, RU)
    assert 'ROUTE_X' in visible(cap) and 'ROUTE_Y' in visible(cap) and 'respectively' in visible(cap)


def test_changed_explicit_scope_is_not_equivalent():
    from docmancer.docs.domain.admission_meaning import same_supported_meaning
    assert not same_supported_meaning(demand(EN), demand(EN.replace('all channels', 'some channels')))


def test_duplicate_domain_spellings_do_not_hide_an_unrequested_domain():
    q = 'Which variables set routing for channel-a and `channel-a`?'
    body = '`ONE` and `TWO` set routing for channel-a and channel-b respectively.'
    assert not qualify(q, body).qualified


@pytest.mark.parametrize('text', [
    '```text\n'+BODY+'\n```',
    BODY.replace('set the routing', 'do not set the routing'),
    BODY.replace('`ROUTE_Y`', '`ROUTE_X`'),
    'When preview is enabled, '+BODY,
])
def test_assignment_requires_current_asserted_body_and_applicable_condition(text):
    assert not qualify(EN, text).qualified


def test_assignment_direction_comes_from_source_not_the_question():
    assert qualify(EN, BODY.replace('`channel-a`, `channel-b`', '`channel-b`, `channel-a`')).qualified


def test_semantic_crop_recomputes_instead_of_reusing_high_overlap():
    from docmancer.docs.domain.evidence_qualification import qualify_evidence
    from tests.docs.test_admission_relation_witnesses import probe
    old = qualify(EN, BODY)
    query = {**probe(EN), **old.trace, '_admission_demands': [{'matched': True}]}
    # Keep every identity and most words; only the asserted assignment is gone.
    current = 'Which variables set routing for channel-a, channel-b and all channels? This is the glossary topic.'
    result = qualify_evidence(query, query_id=query['query_id'], visible_text=current,
        evidence_text=current, candidate={'project_identity': 'repo'}, expected_project_identity='repo')
    assert not result.qualified
    assert '_admission_demands' not in result.trace
