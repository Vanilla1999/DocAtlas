"""Finalize notified 16-session measurement; offline only, no model calls.

Preserves prior manual reviews and adds the three final censored L2 cases.
Does not modify the measured wheel, frozen inputs, model policy or any runner.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path

from account_sessions import account

HERE=Path(__file__).resolve().parent
ROOT=Path('/tmp/opencode/terra-step10-prepared')
LAST={('L2',case) for case in ('T12-ru','T15-en','T19-ru')}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def summary(rows):
    usage=Counter()
    for r in rows:usage.update(r['usage'])
    facts=[f for r in rows for f in r['facts']]
    return {'sessions':len(rows),'final_answers_emitted':sum(bool(r['final_answer']) for r in rows),
        'censored':sum(bool(r['receipt']['censored']) for r in rows),
        'facts_pass':sum(f['binary_pass'] for f in facts),'facts_total':len(facts),
        'facts_partial':sum(f['answer_grade']=='PARTIAL' for f in facts),
        'citations_supported':sum(f['citation_grade']=='PASS' for f in facts),
        'answers_pass':sum(r['answer_pass'] for r in rows),'usage':dict(usage),
        'usage_is_lower_bound':any(r['receipt']['censored'] for r in rows),
        'seconds_sum':round(sum(r['receipt']['seconds'] for r in rows),2),
        'seconds_min':min(r['receipt']['seconds'] for r in rows),'seconds_max':max(r['receipt']['seconds'] for r in rows)}


def main():
    prior_path=HERE/'candidate-partial-13.json'
    previous=json.loads(prior_path.read_text())
    assert len(previous['sessions'])==13
    additional=account(ROOT,allow_incomplete=True,arm_filter='minimal-context',allowed_sessions=LAST)
    assert len(additional['sessions'])==3
    baseline=json.loads((HERE/'baseline-valid.json').read_text())
    baseline_by_key={(r['corpus'],r['case']):r for r in baseline['sessions']}
    for row in additional['sessions']:
        original=baseline_by_key[row['corpus'],row['case']]
        assert row['receipt']['censored'] and row['receipt']['timeout_seconds']==900
        assert not row['final_answer'] and row['session_outcome']=='interrupted'
        assert not any(t['tool']=='docatlas_get_docs_context' for t in row['tool_trace'])
        q=original['question'];assert q['split']=='dev'
        row.update(question=q,answer_pass=False,grading_status='manual terminal-timeout review complete',
            retrieval_status='no_completed_context_result_recorded_before_censorship',usage_is_lower_bound=True,
            tool_argument_contract={'frozen_question':q['question'],'actual_question':None,'original_question_exact':None,
                'deviation':'Unknown: no in-flight get_docs_context arguments in saved completed-tool events. Exact preservation is not established.'},
            context_result={'status':None,'reason_code':'external_session_timeout','source_rows':0,'source_documents':0,
                'source_selection':None,'note':'No completed context result recorded; this does not mean server inference never started.'},
            unknown_cited_refs=[],facts=[])
        for fact in original['facts']:
            row['facts'].append({'fact_id':fact['fact_id'],'quote':fact['quote'],'answer_grade':'FAIL',
                'binary_pass':False,'answer_excerpt':None,
                'reason':'Censored at 900 seconds with no final answer. Required fact not answered: '+fact['quote'],
                'citation_grade':'FAIL','citation_reason':'No final answer or supporting citation emitted before timeout.',
                'citation_evidence':[],'literal_evidence_delivered':False})
    rows=previous['sessions']+additional['sessions']
    assert len(rows)==len({(r['corpus'],r['case']) for r in rows})==16
    assert {(r['corpus'],r['case']) for r in rows}==set(baseline_by_key)
    # Carry portable independent witness text into timeout grades as well; none
    # was delivered to these interrupted agent sessions.
    for row in rows:
        if row['receipt']['censored']:
            gold={f['fact_id']:f for f in baseline_by_key[row['corpus'],row['case']]['facts']}
            for fact in row['facts']:
                fact['frozen_witnesses']=[{**w,'observed_in_tool_output':False} for w in gold[fact['fact_id']]['frozen_witnesses']]
    overall=summary(rows);assert overall['facts_total']==46
    bycorpus={c:summary([r for r in rows if r['corpus']==c]) for c in ('L0','L2')}
    baseline_total=summary(baseline['sessions'])
    baseline_corpora={c:summary([r for r in baseline['sessions'] if r['corpus']==c]) for c in ('L0','L2')}
    assert baseline_total['usage']['input_with_cache']==169853 and baseline_total['facts_pass']==42
    limitations=[
        'All 16 assigned cases remain in the denominator, including eight censored failures. No survivor-only quality score.',
        'Censored session metadata records more provider tokens than interrupted step_finish streams. Use persisted session totals and preserve both ledgers; unfinished work may add unrecorded cost. Emitted tool counts also omit in-flight operations.',
        'Six observed L0 questions have additional surrounding quotes, violating exact original-question preservation. Two L0 questions are exact. Eight L2 in-flight arguments are unavailable in saved completed-tool events, so exact preservation is unobservable.',
        'The L0 comparison is a matched completed-trajectory operational comparison, not a clean exact-question-compliant experiment for all cases. Quote deviations are not normalized away.',
        'The full input ratio is a recorded lower bound, not a cost-saving claim. L2 has no final answers and its shorter recorded provider traffic is not successful context compression.',
        'Many whole source documents were delivered through semantic selection and structural closure, not token-budget filling. Two L0 emergency stops blocked the selected context before source delivery.',
        'Source bodies were independently checked against frozen bytes/spans. content_sha256 is a canonical projection-material digest, not sha256(snippet). Presence/syntax was checked; projection-digest reconstruction is not claimed.',
        'Required fact and supporting citation grades do not exhaustively grade extra advice. All material qualifiers are required; partial facts count as zero. The same final-answer rule is used in both fresh arms.',
        'No new agent/model/product calls, no completion polling, no wheel/input/policy/threshold changes. Historical and invalid setup attempts are separate.',
    ]
    candidate={'schema_version':1,'complete_evaluation':True,'source_root':str(ROOT),'arm':'minimal-context',
        'summary':overall,'by_corpus':bycorpus,'original_question_contract':{'exact':2,'deviations':6,'unobservable':8},
        'grading_contract':baseline['grading_contract'],'limitations':limitations,
        'prior_review_sha256':sha(prior_path),'baseline_review_sha256':sha(HERE/'baseline-valid.json'),
        'sessions':rows}
    (HERE/'candidate.json').write_text(json.dumps(candidate,ensure_ascii=False,indent=2)+'\n')
    paired=[]
    for row in rows:
        base=baseline_by_key[row['corpus'],row['case']]
        paired.append({'corpus':row['corpus'],'case':row['case'],
            'baseline_facts_pass':sum(f['binary_pass'] for f in base['facts']),
            'candidate_facts_pass':sum(f['binary_pass'] for f in row['facts']),'required_facts':len(row['facts']),
            'baseline_input_with_cache':base['usage']['input_with_cache'],
            'candidate_recorded_input_with_cache':row['usage']['input_with_cache'],
            'candidate_censored':row['receipt']['censored'],
            'candidate_original_question_exact':row['tool_argument_contract']['original_question_exact'],
            'candidate_context_reason':row['context_result']['reason_code']})
    comparison={'schema_version':1,'fresh_baseline':baseline_total,'candidate':overall,
        'paired_by_corpus':{c:{'baseline':baseline_corpora[c],'candidate':bycorpus[c],
            'input_with_cache_ratio':bycorpus[c]['usage']['input_with_cache']/baseline_corpora[c]['usage']['input_with_cache'],
            'ratio_is_lower_bound':bycorpus[c]['usage_is_lower_bound'],
            'interpretation':'Matched completed-trajectory comparison; exact-question deviations remain.' if c=='L0' else 'All eight candidate answers timed out. Lower recorded input does not establish savings; incomplete cost and zero task completion.'} for c in ('L0','L2')},
        'full_input_with_cache_ratio_lower_bound':overall['usage']['input_with_cache']/169853,
        'facts_difference':overall['facts_pass']-42,'candidate_original_question_contract':candidate['original_question_contract'],
        'conclusion':'Measured candidate does not meet the quality or token-efficiency objective: 16/46 versus 42/46 facts; recorded total input+cache is higher even with eight censored failures. L0 alone spends 6.16x matched baseline input+cache and delivers fewer facts. No claim of cost savings is supported.',
        'historical_separate':{'invalid_baseline_and_initial_candidate':'failed-attempts.json / failed-attempts.md',
            'earlier_step9_study':'../STEP9_GAP_RESOLUTION_RU.md (historical; not the denominator; not independently regraded here)',
            'fresh_comparison_only':True},
        'artifact_sha256':{'candidate.json':sha(HERE/'candidate.json'),'baseline-valid.json':sha(HERE/'baseline-valid.json'),
            'failed-attempts.json':sha(HERE/'failed-attempts.json')},'limitations':limitations,'paired_cases':paired}
    (HERE/'comparison.json').write_text(json.dumps(comparison,ensure_ascii=False,indent=2)+'\n')
    md=['# Final candidate evaluation: all 16 sessions','',
        '**16/46 required facts; 17/46 supporting fact citations; 5/16 fully answered cases.** Eight L2 sessions censored at 900 seconds count as failed answers, not exclusions. Two completed L0 sessions returned an emergency stop and no sources.','',
        '## Recorded accounting','', '```json',json.dumps(overall,indent=2),'```','',
        'Persisted session metadata supplies the most complete recorded usage on censored runs. Their event streams omit a final step, so totals are lower bounds; both ledgers remain in JSON. Input, cache-read, output and reasoning are separately reported.','',
        '## Per-case outcomes','',
        '| Corpus/case | Facts | Citation support | Input + cache | Censored | Exact question |',
        '|---|---:|---:|---:|---|---|']
    for row in rows:
        md.append(f"| {row['corpus']}/{row['case']} | {sum(f['binary_pass'] for f in row['facts'])}/{len(row['facts'])} | {sum(f['citation_grade']=='PASS' for f in row['facts'])}/{len(row['facts'])} | {row['usage']['input_with_cache']} | {row['receipt']['censored']} | {row['tool_argument_contract']['original_question_exact']} |")
    for row in rows:
        md += ['',f"## {row['corpus']}/{row['case']}",'',row['question']['question'],'',
            row['final_answer'] or '**No final answer: censored at 900 seconds.**','',
            'Question contract: '+json.dumps(row['tool_argument_contract'],ensure_ascii=False),'']
        for fact in row['facts']:
            md.append(f"- **{fact['fact_id']}: {fact['answer_grade']}; citation {fact['citation_grade']}.** {fact['reason']}")
    md += ['','## Boundaries and limitations','',*limitations,'',
        '`candidate.json` preserves actual final answers, traces, source/witness excerpts, per-fact reasons, question comparisons and usage ledgers. No source digest is equated with a raw-snippet hash.','']
    (HERE/'candidate.md').write_text('\n'.join(md))
    md=['# Step 10: fresh baseline versus measured candidate','',comparison['conclusion'],'',
        '| Arm/subset | Facts | Full answers | Input | Cache read | Input + cache | Output | Censored |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for name,s in [('Fresh baseline, all16',baseline_total),('Candidate, all16',overall),
                   ('Fresh baseline, L0',baseline_corpora['L0']),('Candidate, L0',bycorpus['L0']),
                   ('Fresh baseline, L2',baseline_corpora['L2']),('Candidate, L2',bycorpus['L2'])]:
        u=s['usage'];md.append(f"| {name} | {s['facts_pass']}/{s['facts_total']} | {s['answers_pass']}/{s['sessions']} | {u['input']} | {u['cache_read']} | {u['input_with_cache']} | {u['output']} | {s['censored']} |")
    ratio=comparison['full_input_with_cache_ratio_lower_bound']
    md += ['',f"Full-run recorded input+cache ratio: **at least {ratio:.3f}×** the fresh baseline's **169853 tokens / 16 sessions**. Both arms report zero reasoning tokens and zero cache-write tokens. Censored usage remains a lower bound, not a zero-cost result.",'',
        '## Matched L0 result', '',
        '**16/23 versus 21/23 facts; 354608 versus 57522 input+cache tokens (6.165×).** All eight candidate L0 trajectories completed, so this is the meaningful matched operational comparison. It still has six exact-question contract violations. Candidate L0 time sums to 823.21 seconds; the eight measured durations are 72.34–173.37 seconds.', '',
        '## L2 censorship', '',
        'All eight L2 candidate sessions timed out at approximately 900 seconds, emitted no final answers and deliver 0/23 required facts. They remain in the 46-fact denominator. Lower recorded L2 input than the baseline is not evidence of efficiency: no task completed, and unrecorded in-flight work may increase cost. The saved completed-tool stream contains no context result or original get_docs_context arguments for these sessions.', '',
        '## Contract and source findings', '',
        'Six L0 requests added surrounding quote characters to the frozen question. T01-en and T05-ru preserved it exactly; L2 preservation is unobservable from saved events. These deviations are reported as protocol failures, not normalized or excused.',
        'Whole-document delivery is explained by conservative semantic membership plus structural closure, not filling a token budget. Successful L0 packets explicitly reported unverified context and incomplete structural dependencies. T02 and T12 emergency stops rejected candidate packets of 50110 and 50297 tokens; those rejected sizes are not delivered model-input usage.',
        'Independent checks compare source text with frozen file spans and citation references with issued source rows. Public content_sha256 is a projection-material fingerprint; no sha256(snippet) equality was assumed.', '',
        '## Historical/setup accounting stays separate', '',
        'The denied-access baseline and unprepared initial candidate are in `failed-attempts.{json,md}`. Older step9 measurements are historical and are not this comparison denominator. The fresh valid baseline is `baseline-valid.{json,md}`; final candidate details are `candidate.{json,md}`. Earlier partial snapshots remain preserved.', '',
        'No policy, threshold, source, question, measured wheel or agent runner was changed during grading. No additional model/product calls were made. The same manual final-answer rule applies to both fresh arms; partial facts count as zero. Supporting citations do not repair omissions in final prose.','']
    (HERE/'comparison.md').write_text('\n'.join(md))
    print(json.dumps({'candidate':overall,'baseline':baseline_total,'ratio_lower_bound':ratio,'candidate_by_corpus':bycorpus},indent=2))


if __name__=='__main__':main()
