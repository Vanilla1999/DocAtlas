"""Manual review of the eight completed L0 candidate sessions at one snapshot.

Never polls unfinished sessions. Future completed cases require fresh manual
grading; no policy/threshold/input changes are performed by this evaluator.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

from account_sessions import account, CASES
from grade_valid_baseline import REASONS

HERE=Path(__file__).resolve().parent
ROOT=Path('/tmp/opencode/terra-step10-prepared')
CORPORA=Path('/tmp/opencode/step8-corpora2')
SNAPSHOT={('L0',case) for case in CASES}
EVIDENCE={
 'T01-en':['`feat/<topic>` or `fix/<description>`','Run the full test suite before opening the PR.','Include tests for new connectors or fetchers where practical.'],
 'T01-ru':['`feat/<topic>` или `fix/<description>`','До открытия PR запустить полный набор тестов.','добавить тесты, где это практически возможно'],
 'T05-ru':['установленный wheel, реальный установщик проекта, MCP через stdio, SQLite и MiniLM','не автономные запуски OpenCode с моделью'],
 'T10-ru':['одного и того же исходного вопроса','Запустить оба режима из одинаковых состояний','Совпадение двух неверных ответов не считается PASS.'],
 'T15-en':['_meta` is dropped','the original source packet is therefore lost and the response’s short source references cannot be resolved'],
 'T19-ru':['локальным процессом Qdrant, принадлежащим DocAtlas','при необходимости загружая закреплённую версию','Останавливает управляемый процесс','Показывает PID, порт, URL, состояние процесса'],
}
REFERENCES={
 'T01':'ev-dc2112ec2f32298ae05568ea','T05':'ev-3a519fcbfb7616ce6bd0f390',
 'T10':'ev-1d1d4d4953794fbbc3282feb','T15':'ev-8ed9b9e1a3fd964b5c046518',
 'T19':'ev-5d1a7e5547416bdd471a9e6f',
}


def decode(packet):
    rows=packet.get('sources',[])
    if packet.get('source_columns'):
        cols=packet['source_columns']
        assert len(set(cols))==len(cols)
        rows=[dict(zip(cols,row,strict=True)) for row in rows]
    return [{**packet.get('source_context',{}),**row} for row in rows]


def merge(intervals):
    merged=[]
    for a,b in sorted(intervals):
        if merged and a<=merged[-1][1]:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
        else:merged.append((a,b))
    return merged


def main():
    # Reuse the project's offline tokenizer wrapper only for a labelled output
    # token proxy. Provider/session token totals remain the actual cost measure.
    sys.path.insert(0,str(HERE.parents[2]))
    from docmancer.docs.application.projection_tokenizer import projection_token_count
    data=account(ROOT,arm_filter='minimal-context',allowed_sessions=SNAPSHOT)
    assert len(data['sessions'])==8
    frozen=HERE.parent
    questions={q['id']:q for q in json.loads((frozen/'questions.json').read_text())['cases'] if q['id'] in CASES}
    assert all(q['split']=='dev' for q in questions.values())
    topics={q['topic_id'] for q in questions.values()}
    gold={t['topic_id']:t for t in json.loads((frozen/'oracle.json').read_text())['topics'] if t['topic_id'] in topics}
    wanted={f['fact_id'] for t in gold.values() for f in t['facts']}
    witnesses={w['fact_id']:w for w in json.loads((frozen/'witness-audit.json').read_text())['facts'] if w['fact_id'] in wanted}
    for row in data['sessions']:
        case,corpus=row['case'],row['corpus'];q=questions[case];topic=q['topic_id']
        project=CORPORA/(corpus+'-0')/'project'
        calls=[t for t in row['tool_trace'] if t['tool']=='docatlas_get_docs_context']
        assert len(calls)==1
        call=calls[0];arguments=call['state']['input'];raw=call['state']['output'];packet=json.loads(raw)
        sources=decode(packet);byref={s['ref']:s for s in sources}
        assert len(byref)==len(sources)
        rows_by_path={};coverage={};anomalies=[]
        for source in sources:
            path=source['path'];file=project/path
            assert file.resolve().is_relative_to(project.resolve()) and file.is_file()
            text=file.read_text();lines=text.splitlines(keepends=True)
            a,b=source['line_start'],source['line_end'];body=source['text']
            assert 1<=a<=b<=len(lines)
            span=''.join(lines[a-1:b]);offset=span.find(body)
            if offset<0:anomalies.append({'ref':source['ref'],'path':path,'reason':'not_verbatim'})
            assert offset>=0
            start=sum(len(line) for line in lines[:a-1])+offset
            coverage.setdefault(path,[]).append((start,start+len(body)))
            rows_by_path.setdefault(path,[]).append(source)
            assert source['authority']=='source_of_truth' and source['scope'] in ('project','module')
            assert source['project_identity'] and re.fullmatch('[0-9a-f]{64}',source['content_sha256'])
        coverage={p:merge(v) for p,v in coverage.items()}
        whole=[p for p,v in coverage.items() if len(v)==1 and v[0]==(0,len((project/p).read_text()))]
        exact=arguments.get('question')==q['question']
        checks={'frozen_question':q['question'],'actual_question':arguments.get('question'),'original_question_exact':exact,
                'deviation':None if exact else 'Extra surrounding quote characters; exact original-question contract violated. Not normalized or excused.',
                'frozen_search_question':q.get('search_question'),'actual_search_question':arguments.get('search_question'),
                'supplied_translation_exact':arguments.get('search_question')==q.get('search_question') if arguments.get('search_question') is not None else None,
                'translation_note':'Translation is optional; omission is recorded, not counted as an original-question mutation.'}
        assert exact or arguments.get('question')=='"'+q['question']+'"'
        row.update(question=q,tool_argument_contract=checks,source_text_anomalies=anomalies,
                   context_result={'status':packet.get('status'),'reason_code':packet.get('reason_code'),
                    'context_quality':packet.get('context_quality'),'source_selection':packet.get('source_selection'),
                    'more_context':packet.get('more_context'),'source_rows':len(sources),'source_documents':len(rows_by_path),
                    'whole_documents_delivered':whole,'unique_source_characters':sum(b-a for spans in coverage.values() for a,b in spans),
                    'actual_tool_output_o200k_tokens':projection_token_count(raw.encode()),
                    'source_file_sha256':{p:hashlib.sha256((project/p).read_bytes()).hexdigest() for p in rows_by_path}},
                   facts=[],unknown_cited_refs=sorted(set(re.findall(r'ev-[0-9a-f]+',row['final_answer']))-set(byref)))
        assert not row['unknown_cited_refs']
        for index,fact in enumerate(gold[topic]['facts']):
            stopped=packet.get('reason_code')=='context_emergency_stop'
            partial=topic=='T15' and index==0
            grade='FAIL' if stopped else 'PARTIAL' if partial else 'PASS'
            excerpt=None if stopped else EVIDENCE[case][index]
            if excerpt:assert excerpt in row['final_answer']
            witness_data=[];literal=False
            for w in witnesses[fact['fact_id']]['occurrences'][corpus]:
                file=project/w['path'];text=file.read_text();lines=text.splitlines(keepends=True)
                snippet=''.join(lines[w['line_start']-1:w['line_end']]);assert fact['quote'] in snippet
                quote_start=sum(len(s) for s in lines[:w['line_start']-1])+snippet.index(fact['quote'])
                covered=any(a<=quote_start and quote_start+len(fact['quote'])<=b for a,b in coverage.get(w['path'],[]))
                literal|=covered
                witness_data.append({**w,'text':snippet,'source_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'delivered_exact_quote':covered})
            citation=[]
            if not stopped:
                ref=REFERENCES[topic];assert ref in row['final_answer'];source=byref[ref]
                assert fact['quote'] in source['text'],(case,fact['fact_id'],ref)
                citation=[{'ref':ref,'path':source['path'],'line_start':source['line_start'],'line_end':source['line_end'],
                           'source_text':source['text'],'reason':'Issued reference resolves to exact source text containing the frozen required fact; final answer names the same path and supporting lines.'}]
            reason=('Final answer abstains after the explicit emergency stop; it does not state the required fact: '+fact['quote']) if stopped else REASONS[fact['fact_id']]
            if topic=='T01' and index==2:reason='Explicitly requires tests for new connectors/fetchers where practical.'
            row['facts'].append({**fact,'answer_grade':grade,'binary_pass':grade=='PASS','answer_excerpt':excerpt,
                'reason':reason,'citation_grade':'PASS' if citation else 'FAIL','citation_evidence':citation,
                'frozen_witnesses':witness_data,'literal_evidence_delivered':literal})
        row['grading_status']='independent manual review complete for this completed snapshot'
        row['answer_pass']=all(f['binary_pass'] for f in row['facts'])
        row['retrieval_status']='explicit_emergency_stop_no_source_delivery' if not sources else 'source_checked_native_delivery'
    facts=[f for r in data['sessions'] for f in r['facts']]
    baseline=json.loads((HERE/'baseline-valid.json').read_text())
    paired=[r for r in baseline['sessions'] if (r['corpus'],r['case']) in SNAPSHOT]
    pairedusage=Counter()
    for r in paired:pairedusage.update(r['usage'])
    data['summary'].update(partial=True,expected_full_sessions=16,reviewed_corpora=['L0'],facts_pass=sum(f['binary_pass'] for f in facts),
        facts_total=len(facts),facts_partial=sum(f['answer_grade']=='PARTIAL' for f in facts),
        citations_supported=sum(f['citation_grade']=='PASS' for f in facts),answers_pass=sum(r['answer_pass'] for r in data['sessions']),
        original_question_deviations=sum(not r['tool_argument_contract']['original_question_exact'] for r in data['sessions']),
        emergency_stops=sum(r['context_result']['reason_code']=='context_emergency_stop' for r in data['sessions']),
        seconds_sum=sum(r['receipt']['seconds'] for r in data['sessions']))
    data['comparison']={'fresh_full_baseline_sessions':16,'fresh_full_baseline_input_with_cache':169853,
        'fresh_full_baseline_facts':'42/46','matched_baseline_sessions':len(paired),'matched_baseline_usage':dict(pairedusage),
        'matched_baseline_facts_pass':sum(f['binary_pass'] for r in paired for f in r['facts']),
        'matched_baseline_facts_total':sum(len(r['facts']) for r in paired),
        'partial_candidate_input_with_cache':data['summary']['usage']['input_with_cache'],
        'matched_input_ratio':data['summary']['usage']['input_with_cache']/pairedusage['input_with_cache'],
        'comparison_limitation':'Partial L0 snapshot, not full 16-case result. Six exact-question deviations remain protocol failures; no strict unchanged-question experimental pass is claimed. Historical runs and failed setup costs are separate, never used as this denominator.'}
    data['grading_contract']=baseline['grading_contract']
    data['analysis_notes']=[
        'Many whole documents are delivered by conservative semantic selection and structural closure, not by filling a token budget. Receipts show counts and incomplete dependencies.',
        'Emergency-stop measured_tokens is the rejected candidate size, not tokens delivered to the answering model. The compact failure packet and actual provider usage are counted separately.',
        'The o200k tool-output count is an offline exact text-token proxy, not provider billable token accounting. Provider input/cache totals are authoritative for actual session accounting.',
        'No future/unfinished case was inspected; this fixed eight-case list was captured from completed receipts once. No polling, reruns, threshold changes or question normalization.',
        'Source bytes, spans, authority and identity presence checked independently; projection fingerprint presence is not independent reconstruction of its algorithm. Required fact references checked; extra advice not exhaustively graded.',
    ]
    (HERE/'candidate-partial.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    md=['# Candidate partial evaluation: eight completed L0 sessions','',
        '**Partial snapshot only. All eight L0 receipts were complete when inspected; L2 was not polled.**','',
        '## Actual results','', '```json',json.dumps(data['summary'],indent=2),'```','',
        '## Paired fresh baseline comparison','', '```json',json.dumps(data['comparison'],indent=2),'```','',
        'The final full-run denominator is the fresh baseline **169853 input+cache / 16 sessions**, not historical file-search measurements or denied-access attempts. For this partial snapshot, use only the matched L0 baseline subset.','',
        '## Contract and delivery findings','',
        'Six requests wrap the frozen original question in extra quote characters. This is an exact original-question contract deviation, not normalized away. T01-ru is one such case despite a correct final answer. Only T01-en and T05-ru preserve the exact question in this snapshot.',
        'T02-ru and T12-ru stop at measured candidate sizes 50110 and 50297 tokens; no source text is delivered and required facts fail. The rejection sizes are not model-input tokens. Other calls deliver many complete documents through selection plus structural closure, not budget filling. Successful packets explicitly report incomplete structural dependencies and unverified context quality.','',
        '| Case | Facts | Citation support | Input + cache | Context result | Exact question |',
        '|---|---:|---:|---:|---|---|']
    for r in data['sessions']:
        md.append(f"| {r['case']} | {sum(f['binary_pass'] for f in r['facts'])}/{len(r['facts'])} | {sum(f['citation_grade']=='PASS' for f in r['facts'])}/{len(r['facts'])} | {r['usage']['input_with_cache']} | {r['context_result']['reason_code'] or 'sources delivered'} | {r['tool_argument_contract']['original_question_exact']} |")
    for r in data['sessions']:
        md += ['',f"## L0/{r['case']}",'','Actual tool arguments: `'+json.dumps(r['tool_argument_contract'],ensure_ascii=False)+'`','',r['final_answer'],'']
        for f in r['facts']:md.append(f"- **{f['fact_id']}: {f['answer_grade']}; citation {f['citation_grade']}.** {f['reason']}")
        md += ['',f"Delivered {r['context_result']['source_rows']} source rows across {r['context_result']['source_documents']} documents; {len(r['context_result']['whole_documents_delivered'])} complete documents by exact character-span union. Raw native tool-output o200k proxy: {r['context_result']['actual_tool_output_o200k_tokens']} tokens."]
    md += ['','## Evidence and limits','',*data['analysis_notes'],'',
           'Portable JSON includes original tool traces, provider step/session accounting, exact final answers, per-fact reasons, referenced source text and witness hashes, delivery receipts, and exact original-question comparisons. No production/policy/input changes.','']
    (HERE/'candidate-partial.md').write_text('\n'.join(md))
    print(json.dumps({'summary':data['summary'],'comparison':data['comparison']},indent=2))


if __name__=='__main__':main()
