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







