"""Temporal/scenario diagnostic matrix. No conditions are removed or authorized."""
import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path

from docmancer.docs.domain.query_reference_binding import resolve_references, ScopeKey
from docmancer.docs.domain.need_contracts import compile_need_contracts
from docmancer.docs.domain.admission_grammar import parse_admission_frame
from docmancer.docs.application.need_context_disposition import _applicable_context


MATRIX = [
    ('temporal-en', 'temporal_question', 'When do QueueTasks run relative to returning the response?',
     'QueueTasks run only after the response has been sent.'),
    ('temporal-ru', 'temporal_question', 'Когда начинается lifespan teardown относительно connections и background tasks?',
     'The lifespan teardown will run once all connections have been closed, and any in-process background tasks have completed.'),
    ('temporal-ru-supported', 'temporal_question', 'Когда выполняются QueueTasks относительно отправки ответа?',
     'QueueTasks выполняются после отправки ответа.'),
    ('temporal-parsed-state-match', 'temporal_and_scenario', 'When do QueueTasks run relative to returning the response when preview is disabled?',
     'When preview is disabled, QueueTasks run after the response.'),
    ('temporal-parsed-state-wrong', 'temporal_and_scenario', 'When do QueueTasks run relative to returning the response when preview is disabled?',
     'When preview is enabled, QueueTasks run after the response.'),
    ('temporal-with-state', 'temporal_and_scenario', 'When do QueueTasks run when preview is disabled?',
     'When preview is disabled, QueueTasks run after the response.'),
    ('temporal-unless', 'temporal_and_exception', 'When do QueueTasks run unless preview is enabled?',
     'QueueTasks run after the response unless preview is enabled.'),
    ('scenario-default-match', 'state_condition', 'What is OrbitClient default timeout when preview is disabled?',
     'When preview is disabled, OrbitClient default timeout is 7 seconds.'),
    ('scenario-default-wrong-state', 'state_condition', 'What is OrbitClient default timeout when preview is disabled?',
     'When preview is enabled, OrbitClient default timeout is 7 seconds.'),
    ('scenario-default-missing-state', 'state_condition', 'What is OrbitClient default timeout when preview is disabled?',
     'OrbitClient default timeout is 7 seconds.'),
    ('scenario-default-wrong-subject', 'state_condition', 'What is OrbitClient default timeout when preview is disabled?',
     'When preview is disabled, OtherClient default timeout is 7 seconds.'),
    ('scenario-negated-state-match', 'negated_state_condition', 'What is OrbitClient default timeout when preview is not enabled?',
     'When preview is disabled, OrbitClient default timeout is 7 seconds.'),
    ('scenario-negated-state-wrong', 'negated_state_condition', 'What is OrbitClient default timeout when preview is not enabled?',
     'When preview is enabled, OrbitClient default timeout is 7 seconds.'),
    ('scenario-exception', 'exception_condition', 'What is OrbitClient default timeout except when preview is enabled?',
     'OrbitClient default timeout is 7 seconds except when preview is enabled.'),
    ('scenario-if-event', 'event_condition', 'If one QueueTasks function raises an exception, what happens to later tasks?',
     'If one QueueTasks function raises an exception, later tasks are not executed.'),
    ('scenario-if-event-wrong-polarity', 'event_condition', 'If one QueueTasks function raises an exception, what happens to later tasks?',
     'If one QueueTasks function raises an exception, later tasks are executed.'),
    ('quoted-marker', 'literal_identity', 'What does `when` mean?', 'The literal when is a parameter.'),
]


def inspect_contracts(question, body):
    plan = resolve_references(question, catalog=(), scope=ScopeKey('diagnostic', '', 'generation'),
                              catalog_complete=True, document_suffixes=frozenset())
    rows = []
    for contract in compile_need_contracts(question, plan):
        frame = parse_admission_frame(contract.need.query_span_text)
        rows.append({'need_id': contract.need.need_id, 'query_span': contract.need.query_span_text,
            'compiler_interpretation': contract.interpretation,
            'constraint_spans': [asdict(s) for s in contract.constraint_spans],
            'constraint_text': [question[s.start:s.end] for s in contract.constraint_spans],
            'parsed_frame': asdict(frame) if frame else None,
            'existing_applicability': _applicable_context(contract, question, body)})
    return rows


def run(input_path, output_dir):
    if output_dir.exists():
        raise FileExistsError(output_dir)
    matrix = [{'id': name, 'diagnostic_label': label, 'question': question, 'body': body,
               'contracts': inspect_contracts(question, body), 'diagnostic_only': True}
              for name, label, question, body in MATRIX]
    results = json.loads(input_path.read_text())
    temporal_ids = {'fastapi-01', 'fastapi-07', 'starlette-03'}
    frozen = []
    for case in results:
        if not any(layer['conditions'] for layer in case['layers']):
            continue
        frozen.append({'case_id': case['case_id'],
            'annotated_temporal_question': case['case_id'] in temporal_ids,
            'claims': case['claims'],
            'proposals': [{'proposal_id': layer['proposal_id'], 'conditions': layer['conditions'],
                           'topic_locality': layer['topic_locality'], 'native_read_reason': layer['native_read_reason'],
                           'corrected_reason': layer['corrected_reason']}
                          for layer in case['layers']]})
    temporal = [r for r in frozen if r['annotated_temporal_question']]
    summary = {'synthetic_pairs': len(matrix), 'frozen_cases_with_constraints': len(frozen),
        'temporal_case_ids': [r['case_id'] for r in temporal],
        'temporal_corrected_first_veto': dict(Counter(p['corrected_reason'] or 'admitted'
            for r in temporal for p in r['proposals'])),
        'note': 'Labels are post-hoc diagnostics only. No oracle-conditioned admission or replay with removed veto.'}
    output_dir.mkdir(parents=True)
    for filename, data in [('matrix.json', matrix), ('frozen_conditions.json', frozen), ('summary.json', summary)]:
        (output_dir / filename).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=Path('v2plan/artifacts/corrected-owner-1500/results.json'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.input, args.output)
