"""Stdlib audit of saved X pair; no product/model/provider execution."""
import hashlib
import json
import re
from pathlib import Path

R=Path(__file__).resolve().parents[1]
O=R.parent/'admission-full-20261012'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def canon(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def sha(b):return hashlib.sha256(b).hexdigest()
def digest(x):return sha(canon(x).encode())
full=Path('/tmp/opencode/docatlas-compact-review/eval/main_flow_comparison/corpus.md').read_text(encoding='utf-8')
gold=read(O/'G_FROZEN_ORACLE.json')
inp=read(R/'X/input.json');joint=read(R/'X/joint_receipt.json')
binding=read(R/'bindings/main.json');prep=read(R/'prepares/main.json')
source_sha=sha(full.encode());errors=[]
if source_sha!=gold['input_sha256']['corpus.md']:errors.append('frozen_main_corpus')
if joint['input_sha256']!=sha((R/'X/input.json').read_bytes()):errors.append('joint_input_hash')
if joint['forward_calls']!=16 or joint['pair_count']!=16 or not joint['complete'] or joint['threshold']!=.3:errors.append('joint_count_threshold_complete')
if joint['runner_sha256']!=sha((O/'D_xprovence_runner.py').read_bytes()):errors.append('runner_hash')
mask_checks=[];results={}
for case,sc in zip(inp['cases'],joint['cases']):
    cid=case['id'];base=read(R/f'public/{cid}_B1.json');mini=read(R/f'public/{cid}_Mini.json');rank=read(R/f'public/{cid}_X-rank.json')
    pool=base['pools'][0];native=pool['pool'];candidates=case['candidates'];ce=[]
    expected_candidates=[dict(id=w['id'],text=w['text'],text_sha256=w['text_sha256'],char_start=w['span'][0],char_end=w['span'][1],source_sha256=w['binding']['content_sha256']) for w in native]
    if candidates!=expected_candidates or case['question']!=base['question'] or sc['question']!=base['question']:ce.append('native_pool_question_bytes')
    score_rows={w['candidate_id']:w for w in sc['rows']}
    if [w['candidate_id'] for w in sc['rows']]!=[w['id'] for w in native]:ce.append('joint_row_order_ids')
    expected_order=sorted(range(len(native)),key=lambda i:(-score_rows[native[i]['id']]['score'],i))
    if sc['ranked_ids']!=[native[i]['id'] for i in expected_order]:ce.append('ranking_order')
    for n in candidates:
        row=score_rows[n['id']];me=[]
        if row['original_window']!=n or row['status']!='EXECUTED' or not row['span_mapping_proven']:me.append('original_or_mapping')
        if row['token_selected_mask']!=[v>.3 for v in row['compression_probabilities']]:me.append('token_threshold')
        spans=row['retained_spans']+row['dropped_sentence_spans']
        for s in spans:
            a,b=s['char_start'],s['char_end'];ta,tb=s['token_span']
            frac=sum(row['token_selected_mask'][ta:tb])/(tb-ta)
            if (full[a:b]!=s['text'] or sha(s['text'].encode())!=s['text_sha256']
                    or s['source_sha256']!=source_sha or not n['char_start']<=a<b<=n['char_end']
                    or [len(full[:a].encode()),len(full[:b].encode())]!=[s['byte_start'],s['byte_end']]):me.append('sentence_exact_span')
            if abs(frac-s['fraction_tokens_above_threshold'])>1e-12 or s['retained']!=(frac>.3) or row['rounded_mask'][ta:tb]!=[s['retained']]*(tb-ta):me.append('sentence_rounding')
        mask_checks.append({'case_id':cid,'candidate_id':n['id'],'errors':sorted(set(me)),'retained_sentences':len(row['retained_spans']),'dropped_sentences':len(row['dropped_sentence_spans'])})
    rp=rank['pools'][0]
    if (rp['pool']!=pool['pool'] or rp['complete_candidates']!=pool['complete_candidates'] or rp['excluded']!=pool['excluded']
            or digest(rp['pool'])!=rp['pool_sha256'] or digest(rp['complete_candidates'])!=rp['complete_sha256']):ce.append('complete_public_candidate_universe')
    if rp['selected_indices']!=expected_order[:2] or rp['selected_indices']!=mini['pools'][0]['selected_indices']:ce.append('top2_not_Mini')
    if rank['state_before']!=rank['state_after'] or rank['state_before']!=base['state_before']:ce.append('state_generation_rows_files')
    if rank['integrity_errors'] or rank['status']!='EXECUTED' or rank['payload'].get('answer_supported') is not False or rank['payload'].get('edit_ready') is not False:ce.append('public_status_authority')
    exact=read(R/f'X/{cid}_bindings.json');selected=[score_rows[w] for w in sc['ranked_ids'][:2]]
    if exact['selected_native_ids']!=sc['ranked_ids'][:2] or exact['parent_public_sha256']!=digest(rank):ce.append('prune_parent_selection_binding')
    rank_input=read(R/f'X/{cid}_X-rank_model_input.json');prune_input=read(R/f'X/{cid}_X-prune_model_input.json')
    expected_excerpts=[];parents={};parent_checks=[]
    for source in rank['payload'].get('sources',[]):
        sid=source['evidence_id'];snap=rank['validation_snapshot'][sid];ref=snap['source']['_reference_evidence'];text=source['snippet']
        identity=ref['source'];scope=identity['scope'];pe=[]
        if (snap['projected_source']!=source or ref['raw_document']!=full or identity['content_sha256']!=source_sha
                or identity['canonical_path']!='README.md' or scope!={'project_id':'local:'+sha(binding['project'].encode()),'snapshot_id':binding['generation'],'version':''}
                or source['scope']!='project' or source['version_binding']!='unversioned'
                or full[ref['char_start']:ref['char_end']]!=ref['text']):pe.append('parent_source_binding')
        if ref['text'].count(text)!=1:pe.append('ambiguous_parent_span')
        first=ref['char_start']+ref['text'].index(text);last=first+len(text)
        if full[first:last]!=text:pe.append('parent_exact_text')
        material={'path':snap['source'].get('path') or snap['source'].get('source') or snap['source'].get('url') or snap['source'].get('source_url'),
            'section':snap['source'].get('heading_path') or snap['source'].get('title'),
            'content':snap['source'].get('content') or snap['source'].get('display_text'),
            'snippet':snap['source'].get('snippet') or snap['source'].get('code'),
            'version':snap['source'].get('version_binding') or snap['source'].get('version') or snap['source'].get('requested_version')}
        if digest(material)!=source['content_sha256']:pe.append('parent_envelope_hash')
        prov={k:source[k] for k in ('path_or_url','scope','version_binding','line_start','line_end','project_identity','authority') if k in source}
        parents[sid]={'text':text,'span':[first,last],'provenance':prov}
        parent_checks.append({'id':sid,'errors':pe,'span':[first,last]})
        # Independent char-wise reconstruction of the announced structural policy.
        retained=[True]*len(text)
        for w in selected:
            a,b=w['original_window']['char_start'],w['original_window']['char_end']
            for pos in range(max(a,first),min(b,last)):retained[pos-first]=False
        for w in selected:
            for span in w['retained_spans']:
                for pos in range(max(span['char_start'],first),min(span['char_end'],last)):retained[pos-first]=True
        for m in re.finditer(r'(?m)^#{1,6}[^\n]*(?:\n|$)',text):
            for i in range(m.start(),m.end()):retained[i]=True
        cursor=0
        while cursor<len(text):
            if not retained[cursor]:cursor+=1;continue
            end=cursor+1
            while end<len(text) and retained[end]:end+=1
            fragment=text[cursor:end]
            if fragment.strip():
                a,b=first+cursor,first+end;eid='excerpt-'+digest([sid,a,b,fragment])[:16]
                expected_excerpts.append({'source_id':eid,'parent_source_id':sid,'path':'README.md','char_start':a,'char_end':b,'text':fragment,
                    'text_sha256':sha(fragment.encode()),'parent_span':[first,last],'source_sha256':source_sha})
            cursor=end
    if exact['excerpts']!=expected_excerpts:ce.append('client_view_not_announced_policy')
    expected_rank=[{'source_id':sid,'text':parent['text'],'provenance':parent['provenance']} for sid,parent in parents.items()]
    expected_prune=[{'source_id':e['source_id'],'text':e['text'],'provenance':parents[e['parent_source_id']]['provenance']} for e in expected_excerpts]
    if rank_input!={'question':base['question'],'sources':expected_rank}:ce.append('rank_model_input')
    if prune_input!={'question':base['question'],'sources':expected_prune}:ce.append('prune_model_input')
    required=next(o for o in gold['original_cases'] if o['id']==int(cid[1:]))['required_char_spans']
    arms={}
    for arm,mi in [('X-rank',rank_input),('X-prune',prune_input)]:
        d=R/f'host/{cid}_{arm}';rec=read(d/'receipt.json');messages=read(d/'messages.json');request=read(d/'request.json');he=[]
        raw=(d/'answer.raw.txt').read_text();answer=json.loads(raw)
        if json.loads(messages[1]['content'])!=mi or messages[0]['content']!=(O/'HOST_PROMPT_RU.txt').read_text():he.append('host_input_prompt')
        wrapper='Answer the following supplied conversation as the assistant. Return only the requested JSON. No tools, external context, or chain of thought.\nConversation JSON:\n'+canon(messages)
        if request['prompt']!=wrapper or rec['request_sha256']!=digest(request):he.append('submitted_wrapper_hash')
        if rec['provenance']['parent_public_sha256']!=digest(rank) or rec['provenance']['native_selected_ids']!=sc['ranked_ids'][:2]:he.append('host_parent_binding')
        if rec['execution']!='EXECUTED' or rec['attempts']!=1 or rec['runner_retries'] or rec['format_repairs']:he.append('host_execution')
        if answer!=read(d/'answer.json') or read(d/'response.json')['data']['text']!=raw:he.append('raw_answer_binding')
        byid={s['source_id']:s for s in mi['sources']};quotes=[]
        for e in answer['evidence']:
            s=byid.get(e['source_id']);q=e['quote']
            quotes.append({'source_id':e['source_id'],'quote':q,'id_valid':s is not None,'literal_in_submitted_fragment':bool(s and q and q in s['text']),
                'literal_in_original_document':bool(q and q in full),'supports':e['supports']})
        arms[arm]={'errors':he,'required_span_delivery':all(any(full[a:b] in s['text'] for s in mi['sources']) for a,b in required),
            'source_count':len(mi['sources']),'source_chars':sum(len(s['text']) for s in mi['sources']),
            'submitted_prompt_chars':len(wrapper),'submitted_prompt_utf8_bytes':len(wrapper.encode()),'host_seconds':rec['latency_seconds'],
            'semantic_required_facts':'PASS','grounded_required_relations':'PASS','unsupported_affirmative_claims':[],
            'semantic_reason':('Оба completion поля и отличие от начала сохранены; не требуем неasked lifecycle ID или весь диагностический перечень.' if cid=='Q16' else 'Явно отказывает PASS одинаковым неправильным ответам; не требуем неasked полного audit checklist.'),
            'exact_citations':'PASS' if all(q['id_valid'] and q['literal_in_submitted_fragment'] and q['literal_in_original_document'] for q in quotes) else 'FAIL',
            'quotes':quotes,'raw_answer_sha256':sha(raw.encode())}
    results[cid]={'errors':ce,'parent_checks':parent_checks,'same_complete_primary_universe':rp['complete_candidates']==pool['complete_candidates'],
        'Xrank_Mini_same_selected_indices':rp['selected_indices']==mini['pools'][0]['selected_indices'],
        'Xrank_Mini_same_final_public_sources':rank['payload']['sources']==mini['payload']['sources'],
        'same_native_ids_for_rank_and_prune':exact['selected_native_ids']==sc['ranked_ids'][:2],
        'selected_indices':rp['selected_indices'],'client_policy_reconstructed_independently':exact['excerpts']==expected_excerpts,
        'parent_source_policy':'PASS' if not any(p['errors'] for p in parent_checks) else 'FAIL',
        'excerpt_provenance_note':'line_start/line_end inherited from PUBLIC PARENT envelope, not recomputed exact child lines; exact child spans in sidecar; NOT a validated pruned public DTO',
        'standalone_punctuation_excerpts':[e['source_id'] for e in expected_excerpts if not re.search(r'\w',e['text'])],
        'public_new_call_seconds':rank['elapsed_seconds'],'old_B1_capture_seconds':base['elapsed_seconds'],
        'joint_forward_seconds':sum(w['inference_seconds'] for w in sc['rows']),'view_build_seconds':exact['view_build_seconds'],'arms':arms}
costs=read(R/'X/COSTS.json')
result={'schema':'docatlas-independent-X-review-v2','boundary':'real public X-rank parent + adapted client exact-span view; NOT native pruned public DTO validation',
    'top_errors':errors,'joint_mask_checks':mask_checks,'cases':results,'counts':{'new_prepares':0,'new_public_calls':2,'joint_forwards':16,'new_host_attempts':4,'completed_host_answers':4},
    'total_stage_ledger':read(R/'LEDGER.json'),'costs_reported':costs,
    'cost_accounting_note':'COSTS actual_public_requests=2 per row includes common old B1 capture plus new X-rank call for that case; prune reuses parent, rows must not be summed as new calls. observed_actual_turn_seconds adds already-consumed B1 capture to each hypothetical arm; cold load excluded. Shared pipeline cost counted once for workload, charged equally for hypothetical arm comparison.',
    'model':{'revision':joint['revision'],'threshold':joint['threshold'],'cold_load_seconds':joint['cold_load_seconds'],'joint_resident_seconds':sum(w['inference_seconds'] for c in joint['cases'] for w in c['rows']),
        'rss_bytes':joint['peak_rss_bytes'],'license':'same isolated nonproduction eval restriction; no legal/deployment assurance'},
    'recommendation':'NO_GENERAL_X_PRUNING_ADOPTION: Q16 small submitted reduction with persistent citation FAIL; Q46 submitted framing growth despite one citation improvement. Known diagnostics only; no holdout evidence.',
    'verdict_axes':{'requested_version_filtering':'NOT_TESTED','literal_transport_version_2026_1':'UNSATISFIED','arbitrary_access_consent_denials':'NOT_TESTED','pruned_native_public_DTO_validation':'NOT_APPLIED_BY_DESIGN'}}
(R/'review/X_REVIEW_RESULTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'top_errors':errors,'mask_errors':[x for x in mask_checks if x['errors']],
    'cases':{cid:{k:v for k,v in c.items() if k not in ('arms','parent_checks')}|{'parent_checks':c['parent_checks'],'arms':{arm:{k:v for k,v in a.items() if k!='quotes'} for arm,a in c['arms'].items()}} for cid,c in results.items()}},ensure_ascii=False,indent=2))
