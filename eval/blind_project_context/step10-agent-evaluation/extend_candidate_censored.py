"""Grade the five newly notified terminal L2 timeout receipts, without polling.

Reuses the immutable eight-case manual review. No model calls or source-hash
shortcut: content_sha256 is a projection digest, not sha256(snippet).
"""
from collections import Counter
import hashlib
import json
from pathlib import Path

from account_sessions import account

HERE=Path(__file__).resolve().parent
ROOT=Path('/tmp/opencode/terra-step10-prepared')
NEW={('L2',case) for case in ('T01-en','T01-ru','T02-ru','T05-ru','T10-ru')}


def main():
    previous_path=HERE/'candidate-partial.json'
    previous=json.loads(previous_path.read_text())
    assert len(previous['sessions'])==8
    recent=account(ROOT,allow_incomplete=True,arm_filter='minimal-context',allowed_sessions=NEW)
    assert len(recent['sessions'])==5
    questions={q['id']:q for q in json.loads((HERE.parent/'questions.json').read_text())['cases'] if ('L2',q['id']) in NEW}
    topics={q['topic_id'] for q in questions.values()}
    gold={t['topic_id']:t for t in json.loads((HERE.parent/'oracle.json').read_text())['topics'] if t['topic_id'] in topics}
    for row in recent['sessions']:
        assert row['receipt']['censored'] and row['receipt']['timeout_seconds']==900
        assert not row['final_answer'] and not row['completed_trajectory']
        assert row['session_outcome']=='interrupted'
        assert not any(t['tool']=='docatlas_get_docs_context' for t in row['tool_trace'])
        q=questions[row['case']];assert q['split']=='dev'
        row.update(question=q,answer_pass=False,grading_status='manual terminal-timeout review complete',
            retrieval_status='no_completed_context_result_recorded_before_censorship',
            usage_is_lower_bound=True,
            tool_argument_contract={'frozen_question':q['question'],'actual_question':None,'original_question_exact':None,
                'deviation':'Unknown: in-flight get_docs_context arguments are not present in the saved completed-tool event stream. Do not infer exact preservation or extra quotes from other sessions.'},
            context_result={'status':None,'reason_code':'external_session_timeout','source_rows':0,
                'source_documents':0,'source_selection':None,
                'note':'No completed docs_context payload recorded. This does not establish that server inference did not run; the interrupted scan and in-flight tool invocation are not fully represented in emitted completed-tool events.'},
            unknown_cited_refs=[],facts=[])
        for fact in gold[q['topic_id']]['facts']:
            row['facts'].append({**fact,'answer_grade':'FAIL','binary_pass':False,'answer_excerpt':None,
                'reason':'Session censored after 900 seconds with no final answer. Required fact not answered: '+fact['quote'],
                'citation_grade':'FAIL','citation_reason':'No final answer or source citation was emitted before censorship.',
                'citation_evidence':[],'literal_evidence_delivered':False})
    rows=previous['sessions']+recent['sessions']
    facts=[f for r in rows for f in r['facts']]
    totals=Counter()
    for row in rows:totals.update(row['usage'])
    baseline=json.loads((HERE/'baseline-valid.json').read_text())
    keys={(r['corpus'],r['case']) for r in rows}
    paired=[r for r in baseline['sessions'] if (r['corpus'],r['case']) in keys]
    paired_totals=Counter()
    for row in paired:paired_totals.update(row['usage'])
    summary={'terminal_receipts':len(rows),'completed_answers':sum(r['completed_trajectory'] for r in rows),
        'censored_timeouts':len(recent['sessions']),'expected_full_sessions':16,
        'facts_pass':sum(f['binary_pass'] for f in facts),'facts_total':len(facts),
        'facts_partial':sum(f['answer_grade']=='PARTIAL' for f in facts),
        'citations_supported':sum(f['citation_grade']=='PASS' for f in facts),
        'answers_pass':sum(r['answer_pass'] for r in rows),
        'usage_recorded_lower_bound':dict(totals),
        'original_question_deviations_observed':6,'original_question_exact_observed':2,
        'original_question_unobservable':5,'emergency_stops':2,
        'seconds_sum':sum(r['receipt']['seconds'] for r in rows)}
    comparison={'fresh_full_baseline_input_with_cache':169853,'fresh_full_baseline_sessions':16,
        'fresh_full_baseline_facts':'42/46','matched_baseline_sessions':len(paired),
        'matched_baseline_usage':dict(paired_totals),
        'matched_baseline_facts_pass':sum(f['binary_pass'] for r in paired for f in r['facts']),
        'matched_baseline_facts_total':sum(len(r['facts']) for r in paired),
        'candidate_recorded_input_with_cache_lower_bound':totals['input_with_cache'],
        'matched_input_ratio_lower_bound':totals['input_with_cache']/paired_totals['input_with_cache'],
        'limitation':'Only 13 terminal receipts included; three unnotified/unread cases are absent, not assumed failures. Five censored cases count as failed answers, and their recorded cost is a lower bound. Six exact-question deviations remain protocol failures. Historical and setup-invalid runs are separate.'}
    result={'schema_version':1,'partial':True,'source_root':str(ROOT),
        'snapshot':'L0 eight completed cases plus terminal L2 T01-en/T01-ru/T02-ru/T05-ru/T10-ru timeouts',
        'prior_evaluation_sha256':hashlib.sha256(previous_path.read_bytes()).hexdigest(),
        'grading_contract':previous['grading_contract'],'summary':summary,'comparison':comparison,'sessions':rows,
        'source_hash_method':'Delivered source bodies were checked against independent frozen file spans; content_sha256 was checked for projection-fingerprint presence, not compared with sha256(snippet). Independent raw-file SHA values are separately labelled. Projection-digest reconstruction is not claimed.',
        'limitations':[
            'No new model/product calls. Fixed terminal-receipt snapshot; no completion polling.',
            'For all five censored sessions, persisted session token totals exceed the interrupted JSONL step totals. Accounting uses the larger persisted session ledger and preserves both, without claiming reconciliation. Unrecorded in-flight work and emitted tool counts remain lower bounds.',
            'A censored session without final text fails every required fact and citation, regardless of exit/status or server work underway.',
            'An unrecorded in-flight request is not evidence that no scan occurred or that its original question was exact.',
            'All previous successful-case grading is preserved byte-for-byte in the prior artifact and reused without inference or retuning.',
        ]}
    (HERE/'candidate-partial-13.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    md=['# Candidate terminal snapshot: 13 of 16 receipts','',
        '**16/37 facts; 17/37 supporting fact citations. Five 900-second L2 timeouts count as failed answers.**','',
        'The eight previously reviewed L0 cases are unchanged. Newly reviewed terminal receipts: L2 T01-en, T01-ru, T02-ru, T05-ru, T10-ru. Each has session outcome `interrupted`, a censored receipt, no final text and no completed context tool result. No outstanding sessions were polled.','',
        'The interrupted JSONL streams omit usage present in persisted session metadata. This artifact uses the more complete session totals, preserving the smaller step-event totals and flagging the mismatch rather than claiming reconciliation.','',
        '## Recorded usage and outcomes','', '```json',json.dumps(summary,indent=2),'```','',
        '## Fresh paired comparison','', '```json',json.dumps(comparison,indent=2),'```','',
        'Use the matched 13-case baseline for this snapshot. Final aggregation must use the full fresh **169853 input+cache / 16** baseline, not historical runs. A lower token cost on a timed-out case would not establish efficiency: no answer was produced and in-flight cost can be missing.','',
        '## Exact-question and source checks','',
        'The six observed L0 quote-wrapping deviations remain failures of exact original-question preservation. For the five censored L2 calls, in-flight get_docs_context arguments are absent from the saved completed-tool stream: preservation is **unobservable**, not PASS or a guessed deviation.',
        result['source_hash_method'],'',
        '## New per-fact grades','']
    for row in recent['sessions']:
        md += [f"### {row['corpus']}/{row['case']}",'',f"No final answer. Receipt: {row['receipt']['seconds']} seconds; censored at 900 seconds. Recorded input+cache: {row['usage']['input_with_cache']} (lower bound).",'']
        for fact in row['facts']:md.append(f"- **{fact['fact_id']}: FAIL; citation FAIL.** {fact['reason']}")
        md.append('')
    md += ['## Limits','',*result['limitations'],'']
    (HERE/'candidate-partial-13.md').write_text('\n'.join(md))
    print(json.dumps({'summary':summary,'comparison':comparison},indent=2))


if __name__=='__main__':main()
