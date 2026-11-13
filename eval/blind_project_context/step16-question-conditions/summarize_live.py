"""Reconcile recorded review and usage; no semantic keyword grader or model calls."""
import hashlib
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name):
    return json.loads((HERE / name).read_text())


def main():
    results = {r['id']: r for r in load('live/results.json')}
    review = load('live/review.json')
    rubric = {c['id']: c for c in load('rubric-v2.json')['cases']}
    assert len(results) == len(review['reviews']) == 8
    assert {r['trial'] for r in review['reviews']} == set(results)
    arms = {}
    quote_count = 0
    for arm in ['current', 'aspect-conditions-v1']:
        selected = [r for r in results.values() if r['arm'] == arm]
        assert len(selected) == 4
        items = {}
        errors = observations = 0
        for result in selected:
            row = next(r for r in review['reviews'] if r['trial'] == result['id'])
            expected = {i['id'] for i in rubric[result['case_id']]['items']}
            assert len(row['items']) == len(expected) and {i['id'] for i in row['items']} == expected
            export_path = HERE / 'live/exports' / (result['id'] + '.json')
            assert hashlib.sha256(export_path.read_bytes()).hexdigest() == result['export_sha256']
            assert (HERE / 'live/answers' / (result['id'] + '.md')).read_text() == result['answer'] + '\n'
            for item in row['items']:
                assert item['grade'] in ['full','partial','missing','contradicted','unknown']
                assert item['id'] not in items
                items[item['id']] = item
                if item['quote'] is not None:
                    assert item['quote'] in result['answer'], (result['id'], item['id'])
                    quote_count += 1
            for observation in row['secondary_observations']:
                assert observation['quote'] in result['answer']
            errors += len(row['erroneous_added_restrictions'])
            observations += len(row['secondary_observations'])
        sensitivity = {}
        for include in [False, True]:
            groups = review['scoring_groups_without_M7'] + ([review['sensitivity_additional_group']] if include else [])
            counts = Counter()
            for group in groups:
                grades = {items[i]['grade'] for i in group}
                grade = next(g for g in ['contradicted','unknown','missing','partial','full'] if g in grades)
                counts[grade] += 1
            sensitivity['with_M7' if include else 'without_M7'] = {
                'required_groups': len(groups), 'delivered_in_harness_read_result': len(groups),
                'retention': dict(counts), 'delivery_level': 'harness_transcript_not_raw_provider_body'}
        usage = {k: sum(r['harness_reported_provider_usage'][k] for r in selected) for k in ['input','output','reasoning']}
        usage['cache'] = {k: sum(r['harness_reported_provider_usage']['cache'][k] for r in selected) for k in ['read','write']}
        # Explicit convention retained from historical OpenCode accounting.
        usage['input_plus_cache_read'] = usage['input'] + usage['cache']['read']
        arms[arm] = {'sensitivity': sensitivity, 'erroneous_added_restrictions': errors,
                     'secondary_observations': observations, 'harness_reported_provider_usage': usage,
                     'abstention_J1': items['J1']['grade'],
                     'separate_positions': {i: items[i]['grade'] for i in review['separate_positions']}}
    summary = {'status':'DRAFT_NONBLIND_NOT_OWNER_APPROVED', 'arms':arms,
               'checks':{'review_trials':8,'review_positions':42,'exact_quotes':quote_count,
                         'raw_provider_capture':False,'generations_by_summarizer':0,'generated_answers':8},
               'usage_basis':'Sum of 16 assistant-message tokens, including input-loading turns; reconciled against 8 session totals. Harness-reported provider usage, not raw HTTP usage.',
               'cost_warning':'cost=0 is an exported field, not evidence of zero billing; cache warming/order were not controlled.'}
    (HERE / 'live/summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False))


if __name__ == '__main__':
    main()
