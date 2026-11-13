import json
import statistics
import hashlib
import subprocess
from pathlib import Path
from collections import Counter

OUT=Path('/tmp/opencode/terra-step8')
r=json.loads((OUT/'analysis.json').read_text())
manual=json.loads((OUT/'manual-review.json').read_text())
summary={'schema_version':1,'model':'openai/gpt-6.1-terra#low','groups':{},'cases':[]}
for x in r:
    key='/'.join([x['corpus'],x['arm'],x['case']])
    review=manual['answers'][key]
    assert len(review['facts'])==x['facts_total'],key
    x['answer_facts_full']=sum(review['facts'])
    calls=[n for f in x['flow'] for n in f['nested_calls']]
    retrieval=[n for n in calls if n['tool']=='docatlas.get_docs_context']
    continuations=[n for n in retrieval if n.get('input',{}).get('portion',1)>1]
    x['retrieval_calls']=len(retrieval)
    x['continuation_calls']=len(continuations)
    valid_continuations=0
    for call in continuations:
        args=call['input']; token=args['continuation_token']
        earlier=[f for f in x['flow'] if (f.get('more_context') or {}).get('continuation_token')==token and (f.get('more_context') or {}).get('next_portion')==args['portion']]
        valid=False
        for previous in earlier:
            old=[n['input'] for n in previous['nested_calls'] if n['tool']=='docatlas.get_docs_context']
            if not old:continue
            clean=lambda a:{k:v for k,v in a.items() if k not in ['portion','continuation_token']}
            if clean(old[0])==clean(args):valid=True
        valid_continuations+=valid
    info={k:x[k] for k in ['case','arm','corpus','session','seconds','steps','usage','input_including_cache','tool_output_tokens','facts_total','evidence_count','answer_facts_full','retrieval_calls','continuation_calls']}
    info.update(full_answer=x['answer_facts_full']==x['facts_total'],manual_notes=review['notes'],first_lookup=bool(retrieval and retrieval[0]['input'].get('lookup_queries')),language_preflight=any(n['tool']=='docatlas.docs_status' and n['input'].get('include_language') for n in calls),search_questions=[n['input']['search_question'] for n in retrieval if n['input'].get('search_question')],valid_continuations=valid_continuations,source_anomalies=x['source_anomalies'],unseen_cited_refs=x['unseen_cited_refs'],code_errors=sum(f['code_error'] for f in x['flow']),tool_truncations=sum(f['truncated'] for f in x['flow']))
    # Verify the stream's accounting against the server's aggregate, and model selection.
    state=json.loads((OUT/x['corpus']/x['arm']/(x['case']+'.session.json')).read_text())['data']
    assert state['model']=={'id':'gpt-6.1-terra','providerID':'openai','variant':'low'},key
    for k in ['input','output','reasoning']:assert state['tokens'][k]==x['usage'][k],key
    assert state['tokens']['cache']['read']==x['usage']['cache_read'],key
    info['reported_cost']=state['cost']
    summary['cases'].append(info)
for arm in ['docatlas','search','clarified']:
    for corpus in ['L0','L2','all']:
        a=[x for x in summary['cases'] if x['arm']==arm and (corpus=='all' or x['corpus']==corpus)]
        n=len(a)
        keys=['input_including_cache','tool_output_tokens','evidence_count','answer_facts_full','facts_total','steps','seconds','retrieval_calls','continuation_calls','valid_continuations','code_errors','tool_truncations']
        sums={k:sum(x[k] for x in a) for k in keys}
        totals={k:sum(x['usage'][k] for x in a) for k in ['input','cache_read','cache_write','output','reasoning']}
        summary['groups'][f'{corpus}/{arm}']={'sessions':n,'full_answers':sum(x['full_answer'] for x in a),'totals':sums,'usage':totals,'means':{k:v/n for k,v in sums.items()},'median_input':statistics.median(x['input_including_cache'] for x in a)}
summary['limitations']=['Dev diagnostic; 8 case wordings, 7 themes, 2 corpora; not independent holdout or a full regression gate.', 'One stochastic run per arm/case. No confidence intervals.', 'Manual final-answer grading is strict component coverage; partial but useful answers are not false claims. It is not a blinded external judge.', 'File search is agent-driven glob/grep/read on the same frozen corpus, not a public web search.', 'The shipped skill is supplied in the system prompt. Automatic skill discovery/activation is not tested.', 'Both arms have the same 12-step budget but not the same token cap; this measures actual spending by the two workflows.', 'Code Mode is enabled for MCP; its formatting and schema overhead are included.', 'OpenCode CLI adds outer quotation marks to the user message. Models sometimes strip those cosmetic quotes; the question meaning and identifiers were retained.', 'Reported cost is zero with empty model price metadata; that is unavailable pricing, not evidence that requests were free.', 'Timing is observational; runs shared CPU/network and four clarified diagnostics partly overlapped the main pair runs.', 'Index preparation, infrastructure attempts before model execution and this reviewer work are excluded from per-answer usage.', 'Clarified diagnostics were chosen after observed gaps and change translation+sequencing together; no causal attribution to one instruction.']
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps(summary['groups'],ensure_ascii=False,indent=2))
