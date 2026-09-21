"""Source-local relations, both answers, independent lanes and hard negatives."""
from dataclasses import asdict
import pytest
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.evidence_qualification import qualify_evidence
from docmancer.docs.domain.query_terms import documentation_query_terms, query_constraint_roles
from tests.docs._reference_binding_fixtures import capture_reference_case, visible

CASES = [
    ('Which takes precedence: nav title or page title?',
     'Что имеет приоритет: nav title или page title?',
     'The nav title takes precedence over the page title.',
     'The page title overrides the nav title.', 'precedence'),
    ('When do QueueTasks run relative to response delivery?',
     'Когда выполняется QueueTasks относительно response delivery?',
     'QueueTasks execute after response delivery.',
     'QueueTasks run before response delivery.', 'temporal_order'),
    ('Can a handler for QueueHub be synchronous?',
     'Может ли handler для QueueHub быть синхронной?',
     'A handler for QueueHub can be synchronous.',
     'A handler for QueueHub must be asynchronous.', 'callable_form'),
    ('Which ways enable strict mode?', 'Какие способы включают strict mode?',
     'Strict mode can be enabled in these ways:\n\n- Use a per-call option.\n- Set a model configuration.',
     'To enable strict mode, use these methods:\n\n1. Apply a field setting.\n2. Select a validation option.', 'enumeration'),
    ('How do transport keys map to protocols?', 'Как transport keys сопоставляются с protocols?',
     '| Transport key | Protocol |\n|---|---|\n| `ALPHA_KEY` | scheme-a |\n| `BETA_KEY` | scheme-b |',
     'Transport keys map to protocols as follows:\n\n- `FIRST_KEY` -> scheme-x\n- `LAST_KEY` -> scheme-y', 'mapping'),
]


def probe(question, origin='retrieval_need'):
    plan = build_documentation_query_plan(question)
    query = next(q for q in plan.queries if q.origin == origin)
    roles = query_constraint_roles(query.text)
    return {**asdict(query), 'query_text': query.text, 'query_origin': query.origin,
            'query_terms': list(documentation_query_terms(query.text)),
            'exact_terms': list(roles.hard_exact), 'bound_subjects': list(roles.bound_subjects)}


def qualify(question, body, origin='retrieval_need', candidate=None):
    data = probe(question, origin)
    return qualify_evidence(data, query_id=data['query_id'], visible_text=body,
        evidence_text=body, candidate={'project_identity': 'repo', **(candidate or {})},
        expected_project_identity='repo')


@pytest.mark.parametrize('english,russian,body,opposite,operator', CASES)
@pytest.mark.parametrize('language', ['en', 'ru'])
@pytest.mark.parametrize('answer', ['first', 'other'])
def test_local_relation_not_question_word_overlap(english, russian, body, opposite, operator, language, answer):
    text = body if answer == 'first' else opposite
    result = qualify(english if language == 'en' else russian, text)
    assert result.qualified and result.trace.get('admission_route') == 'typed_local', result.trace
    spans = result.trace['need_witness_spans']
    assert spans and all(0 <= a < b <= len(text) and text[a:b].strip() for a, b in spans)


@pytest.mark.parametrize('question,body', [
    ('Which has priority: command option or config file?', 'A config file takes precedence over a command option.'),
    ('When does Cleanup run relative to transaction commit?', '- Cleanup executes before transaction commit.'),
    ('Is a normal handler allowed?', 'A normal handler is not allowed; an async handler is required.'),
    ('Which options configure retry policy?', 'Retry policy is configured using these options:\n\n- Select an interval.\n- Choose a limit.'),
    ('How do input fields correspond to output fields?', '| Input fields | Output fields |\n|---|---|\n| old_name | new_name |'),
])
def test_new_lexical_family_and_markdown_layout(question, body):
    result = qualify(question, body)
    assert result.qualified and result.trace.get('admission_route') == 'typed_local', result.trace


@pytest.mark.parametrize('question,body', [
    (CASES[0][0], 'The nav title and page title glossary discusses precedence and titles.'),
    (CASES[0][0], 'The nav title is described. Other title overrides the page title.'),
    (CASES[1][0], 'QueueTasks are mentioned. OtherTasks execute after response delivery.'),
    (CASES[1][0], 'QueueTasks and response delivery order are listed in a glossary.'),
    (CASES[2][0], 'A handler for OtherHub can be synchronous. QueueHub is also documented.'),
    (CASES[2][0], 'A handler for QueueHub can be asynchronous.'),
    (CASES[2][0], 'QueueHub handler synchronous asynchronous glossary.'),
    (CASES[3][0], 'Strict mode is a feature. Other mode can be enabled in these ways:\n\n- Set a flag.'),
    (CASES[3][0], '# Strict mode ways\n\n- [Options](options.md)\n- [Methods](methods.md)'),
    (CASES[3][0], 'Strict mode can be disabled in these ways:\n\n- Set an option.'),
    (CASES[4][0], 'Transport keys and protocols:\n\n- `ALPHA_KEY`\n- `BETA_KEY`'),
    (CASES[4][0], '| Transport key | Error code |\n|---|---|\n| A | B |\n\nProtocols are described elsewhere.'),
])
@pytest.mark.parametrize('origin', ['original', 'retrieval_need'])
def test_keyword_salad_wrong_role_and_unrelated_sentence_never_prove_relation(question, body, origin):
    assert not qualify(question, body, origin).qualified


@pytest.mark.parametrize('question,body', [(c[0], c[2]) for c in CASES])
@pytest.mark.parametrize('source', [
    {'project_identity': 'foreign'}, {'freshness': 'stale'}, {'risk_flags': ['unsafe']},
])
def test_relation_does_not_override_source_policy(question, body, source):
    assert not qualify(question, body, candidate=source).qualified


@pytest.mark.parametrize('question,body', [(c[0], c[2]) for c in CASES[:3]])
def test_missing_or_opposite_condition_does_not_answer_conditional_question(question, body):
    question = question.rstrip('?') + ' when preview is disabled?'
    assert not qualify(question, body).qualified
    assert not qualify(question, 'When preview is enabled, ' + body).qualified
    result = qualify(question, 'When preview is disabled, ' + body)
    assert result.qualified and result.trace.get('admission_route') == 'typed_local', result.trace


@pytest.mark.parametrize('question,_,body,__,operator', CASES)
def test_native_pipeline_keeps_real_need_and_false_answer_flags(tmp_path, question, _, body, __, operator):
    cap = capture_reference_case(tmp_path, {'Guide.md': '# Reference\n\n' + body + '\n'}, question)
    assert cap['public_payload'].get('sources'), cap['public_payload']
    traces = [trace for row in cap['projection_attempts'][-1]['snapshot'].values()
              for trace in row['source'].get('retrieval_query_matches', {}).values()]
    assert any(t.get('qualified') and t.get('admission_route') == 'typed_local'
               and t.get('need_relation') == operator for t in traces)
    assert all(cap['public_payload'][key] is False for key in ('answer_supported', 'answer_available', 'edit_ready'))
