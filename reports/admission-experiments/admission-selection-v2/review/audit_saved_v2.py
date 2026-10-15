"""Stdlib saved-data audit only. Never imports/executes product or model code."""
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT.parent / 'admission-full-20261012'
REPO = Path('/tmp/opencode/docatlas-compact-review')

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def digest(obj):
    return sha(canonical(obj).encode('utf-8'))

oracle = read(ROOT/'review/oracle.json')
case_oracles = {c['id']: c for c in oracle['cases']}
case_inputs = {c['id']: c for c in read(ROOT/'review/cases.json')['cases']}
corpus = read(ROOT/'review/corpus.json')['documents']
docs = {d['path']: d['content'] for d in corpus}
groups = {d['path']: d['document_group'] for d in corpus}
bindings = {p.stem: read(p) for p in (ROOT/'bindings').glob('*.json')}
prepares = {p.stem: read(p) for p in (ROOT/'prepares').glob('*.json')}
public = {p.stem: read(p) for p in (ROOT/'public').glob('*.json')
          if p.stem.rsplit('_',1)[-1] in ('B1','Budget','Mini')}
group_cases = {c['id']: c['document_group'] for c in case_inputs.values()}
group_cases.update(Q16='main', Q46='main', OtherAPI='owner', unrelated='unrelated')
# Independent source bytes for synthetic families and original main corpus.
group_docs = defaultdict(dict)
for d in corpus:
    group_docs[d['document_group']][d['path']] = d['content']
group_docs['main']['README.md'] = (REPO/'eval/main_flow_comparison/corpus.md').read_text(encoding='utf-8')
# Diagnostic fixture source text is independently checked against original saved evidence below.
for group, cid in [('owner', 'OtherAPI'), ('unrelated', 'unrelated')]:
    for row in public[cid+'_B1']['state_before']['rows']:
        relative = str(Path(row[1]).relative_to(Path(bindings[group]['project'])))
        group_docs[group][relative] = row[2]

frozen = read(ROOT/'review/frozen_manifest.json')
freeze_errors = [name for name, entry in frozen['files'].items()
                 if sha((ROOT/'review'/name).read_bytes()) != entry['sha256']]
old_oracle = read(OLD/'G_FROZEN_ORACLE.json')
old_questions = json.loads((REPO/'eval/main_flow_comparison/questions_extra40.json').read_text())
old_corpus_errors = []
if sha(group_docs['main']['README.md'].encode()) != old_oracle['input_sha256']['corpus.md']:
    old_corpus_errors.append('original_main_corpus_hash')
if sha((REPO/'eval/main_flow_comparison/questions_extra40.json').read_bytes()) != old_oracle['input_sha256']['questions_extra40.json']:
    old_corpus_errors.append('original_diagnostic_questions_hash')

prepare_checks = {}
for group, p in prepares.items():
    errors = []
    b = bindings[group]
    expected = group_docs[group]
    if p['excluded_or_failed_paths'] or p['unexpected_paths'] or sorted(p['indexed_paths']) != sorted(expected):
        errors.append('indexed_paths')
    if p['generation_id'] != b['generation']:
        errors.append('generation')
    if b['document_hashes'] != {path: sha(text.encode()) for path, text in expected.items()}:
        errors.append('binding_file_hashes')
    if {d['path']: d['content_sha256'] for d in p['documents']} != b['document_hashes']:
        errors.append('prepare_file_hashes')
    prepare_checks[group] = {'errors': errors, 'generation': b['generation'], 'project': b['project'],
                             'source_hashes': b['document_hashes'], 'prepare_seconds': p['seconds']}

def witness_present(payload, wid):
    w = oracle['witnesses'][wid]
    return any(s['path_or_url'] == w['source_path'] and w['quote'] in s['snippet'] for s in payload.get('sources', []))

def bound_errors(ref, text, group):
    errors = []
    binding = ref.get('source') or {}
    scope = binding.get('scope') or {}
    path = binding.get('canonical_path')
    full = group_docs[group].get(path)
    a,b = ref.get('char_start'),ref.get('char_end')
    project_identity = 'local:' + sha(bindings[group]['project'].encode())
    if full is None or ref.get('raw_document') != full:
        errors.append('raw_document_or_allowlist')
    if full is not None and binding.get('content_sha256') != sha(full.encode()):
        errors.append('source_hash')
    if scope != {'project_id': project_identity, 'version': '', 'snapshot_id': bindings[group]['generation']}:
        errors.append('project_version_generation')
    if (type(a) is not int or type(b) is not int or full is None or not 0 <= a < b <= len(full)
            or text != full[a:b] or ref.get('text') != text):
        errors.append('exact_char_span')
    member = ref.get('member_binding') or {}
    if member.get('doc_scope') != 'project' or member.get('module_path') != '' or not member.get('catalog_entry_hash'):
        errors.append('member_binding')
    prepared_document = next((d for d in prepares[group]['documents'] if d['path']==path),{})
    if member.get('catalog_entry_hash') != prepared_document.get('catalog_entry_hash'):
        errors.append('catalog_member_hash')
    if str(ref.get('project_doc_content_hash','')).removeprefix('sha256:') != prepared_document.get('content_sha256'):
        errors.append('bound_file_content_hash')
    owner = ref.get('owner')
    if owner:
        oa,ob,sa,sb = [owner.get(k) for k in ['char_start','char_end','scope_start','scope_end']]
        if (full is None or any(type(x) is not int for x in [oa,ob,sa,sb])
                or not 0 <= sa <= oa <= ob <= sb <= len(full)
                or owner.get('text') != full[oa:ob] or not sa <= a < b <= sb):
            errors.append('structural_owner')
    return errors

rows = {}
for name, r in sorted(public.items()):
    cid, arm = name.rsplit('_',1)
    group = group_cases[cid]
    errors = []
    if r['status'] != 'EXECUTED' or len(r['pools']) != 1:
        errors.append('execution_or_boundary_count')
    p = r['pools'][0]
    if digest(p['pool']) != p['pool_sha256'] or digest(p['complete_candidates']) != p['complete_sha256']:
        errors.append('candidate_receipt_hash')
    if r['state_before'] != r['state_after']:
        errors.append('per_call_state_changed')
    if r['state_before']['generation'] != bindings[group]['generation']:
        errors.append('state_generation')
    if cid in case_inputs and r['question'] != case_inputs[cid]['question']:
        errors.append('question_rewritten')
    if cid in ('Q16','Q46') and r['question'] != old_questions[int(cid[1:])-11][0]:
        errors.append('diagnostic_question_rewritten')
    if r['payload'].get('answer_supported') is not False or r['payload'].get('edit_ready') is not False:
        errors.append('authority_escalation')
    for row in r['state_before']['rows']:
        path = str(Path(row[1]).relative_to(Path(bindings[group]['project'])))
        if row[0] != bindings[group]['generation'] or row[2] != group_docs[group].get(path):
            errors.append('stored_source_content_generation')
        if sha(row[2].encode()) != bindings[group]['document_hashes'].get(path):
            errors.append('stored_source_hash')
        if r['state_before']['files'].get(row[1]) != sha(row[2].encode()):
            errors.append('source_file_hash')
    catalog_path = str(Path(bindings[group]['project'])/'docatlas.project-docs.yaml')
    if r['state_before']['files'].get(catalog_path) != prepares[group]['catalog_sha256']:
        errors.append('catalog_file_hash')
    pool_errors = []
    for i,w in enumerate(p['pool']):
        ref = w['metadata'].get('_reference_evidence') or {}
        e = bound_errors(ref,w['text'],group)
        if w['binding'] != ref.get('source') or w['span'] != [ref.get('char_start'),ref.get('char_end')]:
            e.append('row_binding_projection')
        if w['text_sha256'] != sha(w['text'].encode()) or w['id'] != digest([w['binding'].get('document_id'),*w['span'],w['text']]):
            e.append('native_identity_hash')
        trace = (w['metadata'].get('retrieval_query_matches') or {}).get('query-original') or {}
        if not (trace.get('qualified') is True or trace.get('literal_context_admission')):
            e.append('no_original_admission_trace')
        root = w['metadata'].get('_reference_root_plan') or {}
        if root.get('question')!=r['question'] or root.get('catalog_complete') is not True or root.get('scope')!=w['binding'].get('scope'):
            e.append('original_root_plan')
        admission=trace.get('literal_context_admission') or {}
        source=w['binding'];member=ref.get('member_binding') or {}
        material={'question':r['question'],'request_project_path':bindings[group]['project'],'request_scope':'project',
            'source':{key:source[key] for key in ['document_id','canonical_path','content_sha256']},
            'scope':{key:source['scope'][key] for key in ['project_id','version','snapshot_id']},
            'member':{key:member[key] for key in ['doc_scope','module_path','catalog_entry_hash']},
            'file_content_hash':ref.get('project_doc_content_hash'),'window_span':w['span'],'window_sha256':sha(w['text'].encode())}
        for witness in admission.get('body_witnesses',[]):
            receipt_hash=witness.get('native_discovery_binding_sha256')
            if receipt_hash and receipt_hash!=digest(material):e.append('native_discovery_fingerprint')
        if e: pool_errors.append({'index':i,'errors':e})
    excluded_ordinals = [e['original_ordinal'] for e in p['excluded']]
    if len(set(excluded_ordinals)) != len(excluded_ordinals):
        errors.append('duplicate_excluded_ordinal')
    for e in p['excluded']:
        i=e['original_ordinal']
        if not 0 <= i < len(p['complete_candidates']) or e['candidate'] != p['complete_candidates'][i]:
            errors.append('excluded_original_identity')
    unexcluded = [w for i,w in enumerate(p['complete_candidates']) if i not in set(excluded_ordinals)]
    if unexcluded != p['pool']:
        errors.append('pool_not_original_unexcluded_subsequence')
    selected = p['selected_indices']
    if arm == 'B1' and selected is not None:
        errors.append('B1_not_original_identity')
    if arm != 'B1' and (len(selected)>2 or len(set(selected))!=len(selected) or any(type(i) is not int or not 0<=i<len(p['pool']) for i in selected)):
        errors.append('selected_indices')
    source_errors=[]
    final_sources=[]
    for s in r['payload'].get('sources',[]):
        snap = r['validation_snapshot'].get(s['evidence_id'],{})
        original = snap.get('source') or {}
        ref=original.get('_reference_evidence') or {}
        e=bound_errors(ref,ref.get('text'),group)
        if snap.get('projected_source') != s:
            e.append('public_snapshot_equality')
        if s['path_or_url'] != (ref.get('source') or {}).get('canonical_path') or s.get('scope')!='project' or s.get('version_binding')!='unversioned':
            e.append('public_path_scope_version')
        if s.get('project_identity') != 'local:'+sha(bindings[group]['project'].encode()):
            e.append('public_project_identity')
        snippet=s['snippet']; full=group_docs[group].get(s['path_or_url'],'')
        start=ref.get('char_start',0);end=ref.get('char_end',0)
        if not snippet or snippet not in full[start:end]:
            e.append('final_snippet_not_exact_bound_source')
        occurrences=[]
        cursor=start
        while snippet and (pos:=full.find(snippet,cursor,end))>=0:
            se=pos+len(snippet)
            lines=[full.count('\n',0,pos)+1,full.count('\n',0,se)+(0 if snippet.endswith('\n') else 1)]
            occurrences.append({'span':[pos,se],'lines':lines})
            cursor=pos+1
        if not any(o['lines']==[s.get('line_start'),s.get('line_end')] for o in occurrences):
            e.append('declared_snippet_lines')
        material={'path':original.get('path') or original.get('source') or original.get('url') or original.get('source_url'),
                  'section':original.get('heading_path') or original.get('title'),
                  'content':original.get('content') or original.get('display_text'),
                  'snippet':original.get('snippet') or original.get('code'),
                  'version':original.get('version_binding') or original.get('version') or original.get('requested_version')}
        if s.get('content_sha256') != digest(material):
            e.append('public_envelope_hash')
        if e: source_errors.append({'evidence_id':s['evidence_id'],'errors':e})
        final_sources.append({'id':s['evidence_id'],'path':s['path_or_url'],'snippet_sha256':sha(snippet.encode()),'chars':len(snippet),'source_occurrences':occurrences})
    wids=[]
    if cid in case_oracles:
        wids=list(dict.fromkeys(w for f in case_oracles[cid]['required_facts'] for w in f['source_witnesses']))
    delivered=[w for w in wids if witness_present(r['payload'],w)]
    diagnostic_delivery=None
    if cid in ('Q16','Q46'):
        oo=next(x for x in old_oracle['original_cases'] if x['id']==int(cid[1:]))
        spans=oo['required_char_spans']
        full=group_docs['main']['README.md']
        diagnostic_delivery=all(any(full[a:b] in s['snippet'] for s in r['payload'].get('sources',[])) for a,b in spans)
    duplicate_groups=defaultdict(list)
    for i,w in enumerate(p['complete_candidates']):duplicate_groups[(w['source'],w['chunk_index'])].append((i,w))
    duplicates=[]
    for key, entries in duplicate_groups.items():
        if len(entries)>1:
            duplicates.append({'source':key[0],'chunk_index':key[1],'ordinals':[i for i,w in entries],
                'distinct_text_span_binding':len({digest([w['text'],w['span'],w['binding']]) for i,w in entries}),
                'distinct_full_rows':len({digest(w) for i,w in entries})})
    rows[name]={'case_id':cid,'arm':arm,'split':r['split'],'execution_errors':errors,'pool_errors':pool_errors,'source_errors':source_errors,
        'pool_count':len(p['pool']),'complete_count':len(p['complete_candidates']),'excluded_count':len(p['excluded']),
        'exclusion_reasons':dict(Counter(e['reason'] for e in p['excluded'])),'duplicates':duplicates,
        'selected_indices':selected,'selected_ids':None if selected is None else [p['pool'][i]['id'] for i in selected],
        'sources':final_sources,'source_count':len(final_sources),'snippet_chars':sum(s['chars'] for s in final_sources),
        'payload_utf8_bytes_with_diagnostics':len(canonical(r['payload']).encode()),
        'estimated_tokens_product_proxy':r['payload'].get('estimated_tokens'),
        'elapsed_seconds':r['elapsed_seconds'],'required_witness_ids':wids,'delivered_witness_ids':delivered,
        'missing_witness_ids':[w for w in wids if w not in delivered],
        'exact_witness_full_delivery':bool(wids) and len(delivered)==len(wids),
        'full_fact_groups_by_frozen_witnesses':sum(all(w in delivered for w in f['source_witnesses']) for f in case_oracles.get(cid,{}).get('required_facts',[])),
        'required_fact_group_count':len(case_oracles.get(cid,{}).get('required_facts',[])),
        'diagnostic_original_span_delivery':diagnostic_delivery,
        'context_available':r['payload'].get('context_available'),'current_contract':
            ('PASS' if not final_sources and r['payload'].get('context_available') is False and r['payload'].get('answer_supported') is False and r['payload'].get('edit_ready') is False else 'FAIL')
            if cid in ('OtherAPI','unrelated') or case_oracles.get(cid,{}).get('label')=='all_irrelevant' else 'NOT_APPLICABLE'}

comparisons={}
for cid in sorted({r['case_id'] for r in rows.values()}):
    base=public[cid+'_B1'];bp=base['pools'][0]
    state_same=all(public[cid+'_'+a]['state_before']==base['state_before'] for a in ['Budget','Mini'])
    same_pool=all(public[cid+'_'+a]['pools'][0]['pool']==bp['pool'] for a in ['Budget','Mini'])
    same_complete=all(public[cid+'_'+a]['pools'][0]['complete_candidates']==bp['complete_candidates'] for a in ['Budget','Mini'])
    same_excluded=all(public[cid+'_'+a]['pools'][0]['excluded']==bp['excluded'] for a in ['Budget','Mini'])
    comparisons[cid]={'same_pool':same_pool,'same_complete_sequence':same_complete,'same_excluded_ordinals':same_excluded,'same_source_state_across_arms':state_same,
        'Budget_Mini_same_selected_set':set(rows[cid+'_Budget']['selected_ids'])==set(rows[cid+'_Mini']['selected_ids']),
        'Budget_Mini_same_public_sources_bytes_order':public[cid+'_Budget']['payload'].get('sources',[])==public[cid+'_Mini']['payload'].get('sources',[]),
        'Mini_lost_B1_witnesses':sorted(set(rows[cid+'_B1']['delivered_witness_ids'])-set(rows[cid+'_Mini']['delivered_witness_ids'])),
        'Budget_lost_B1_witnesses':sorted(set(rows[cid+'_B1']['delivered_witness_ids'])-set(rows[cid+'_Budget']['delivered_witness_ids']))}

score_checks={}
for stage in ['calibration','evaluation']:
    receipt=read(ROOT/f'scores/{stage}_receipt.json');inputs=read(ROOT/f'scores/{stage}_input.json')
    errors=[]
    if receipt['input_sha256']!=sha((ROOT/f'scores/{stage}_input.json').read_bytes()):errors.append('input_hash')
    if receipt['status']!='SCORED' or receipt['truncation'] is not False:errors.append('status_truncation')
    for inp,sco in zip(inputs,receipt['cases']):
        cid=inp['id'];pool=public[cid+'_B1']['pools'][0]
        if inp['pool']!=pool['pool'] or inp['complete_candidates']!=pool['complete_candidates'] or inp['id']!=sco['id'] or sco['pool_sha256']!=pool['pool_sha256']:errors.append(cid+':input_identity')
        if [s['id'] for s in sco['rows']]!=[s['id'] for s in pool['pool']] or [s['index'] for s in sco['rows']]!=list(range(len(pool['pool']))):errors.append(cid+':score_rows')
        expected_order=sorted(range(len(sco['rows'])),key=lambda i:(-sco['rows'][i]['score'],i))
        if sco['order']!=expected_order or rows[cid+'_Mini']['selected_indices']!=expected_order[:2] or rows[cid+'_Budget']['selected_indices']!=list(range(len(pool['pool'])))[:2]:errors.append(cid+':selection')
        if any(s['tokens']>512 for s in sco['rows']):errors.append(cid+':overflow')
    if len(inputs)!=len(receipt['cases']) or receipt['forwards']!=sum(len(c['pool']) for c in inputs):errors.append('counts')
    score_checks[stage]={'errors':errors,'forwards':receipt['forwards'],'cold_load_seconds':receipt['cold_load_seconds'],
        'wall_seconds':receipt['wall_seconds'],'resident_forward_seconds':sum(s['seconds'] for c in receipt['cases'] for s in c['rows']),
        'rss_bytes':receipt['rss_bytes'],'model_revision':receipt['revision']}

host_checks={}
for directory in sorted((ROOT/'host').iterdir()):
    if not directory.is_dir():continue
    if directory.name not in public:continue
    name=directory.name;pub=public[name];rec=read(directory/'receipt.json')
    messages=read(directory/'messages.json');request=read(directory/'request.json')
    mi=json.loads(messages[1]['content']);errors=[]
    expected_sources=[{'source_id':s['evidence_id'],'text':s['snippet'],'provenance':{key:s[key] for key in ('path_or_url','scope','version_binding','line_start','line_end','project_identity','authority') if key in s}} for s in pub['payload'].get('sources',[])]
    if mi!={'question':pub['question'],'sources':expected_sources}:errors.append('not_exact_public_host_input')
    if messages[0]['content']!=(OLD/'HOST_PROMPT_RU.txt').read_text():errors.append('generator_prompt')
    expected_prompt='Answer the following supplied conversation as the assistant. Return only the requested JSON. No tools, external context, or chain of thought.\nConversation JSON:\n'+canonical(messages)
    if request.get('prompt')!=expected_prompt or rec['request_sha256']!=digest(request):errors.append('transport_prompt_hash')
    if rec['provenance']['public_result_sha256']!=digest(pub):errors.append('public_result_binding')
    if rec['attempts']!=1 or rec['runner_retries']!=0 or rec['format_repairs']!=0:errors.append('retries_or_repairs')
    quotes=[];answer=None
    if (directory/'answer.raw.txt').exists():
        raw=(directory/'answer.raw.txt').read_text();answer=json.loads(raw)
        if answer!=read(directory/'answer.json'):errors.append('raw_parsed_answer_disagree')
        if read(directory/'response.json')['data']['text']!=raw:errors.append('endpoint_answer_disagree')
        source_byid={s['source_id']:s for s in mi['sources']}
        for e in answer['evidence']:
            source=source_byid.get(e['source_id'])
            full=group_docs[group_cases[pub['case_id']]].get((source or {}).get('provenance',{}).get('path_or_url'),'')
            quotes.append({'source_id':e['source_id'],'quote':e['quote'],'supports':e['supports'],'id_valid':source is not None,
                'literal_in_submitted_fragment':bool(source and e['quote'] and e['quote'] in source['text']),
                'literal_in_original_document':bool(e['quote'] and e['quote'] in full),
                'whitespace_normalized_only':bool(source and e['quote'] not in source['text'] and ' '.join(e['quote'].split()) in ' '.join(source['text'].split()))})
    host_checks[name]={'execution':rec['execution'],'errors':errors,'answer_status':None if answer is None else answer['status'],
        'quotes':quotes,'exact_citation_verdict':'UNKNOWN' if answer is None else ('PASS' if all(q['id_valid'] and q['literal_in_submitted_fragment'] and q['literal_in_original_document'] for q in quotes) else 'FAIL'),
        'quote_count':len(quotes),'submitted_prompt_utf8_bytes':len(request['prompt'].encode()),'submitted_prompt_chars':len(request['prompt']),
        'source_text_chars':sum(len(s['text']) for s in mi['sources']),'host_latency_seconds':rec.get('latency_seconds'),
        'started_unix':rec.get('started_unix'),'raw_answer_sha256':sha((directory/'answer.raw.txt').read_bytes()) if answer is not None else None}

freeze=read(ROOT/'FROZEN_SELECTION.json')
freeze_before_host=all(freeze['timestamp_unix']<r['started_unix'] for r in host_checks.values())
old_unrelated=read(OLD/'B1_unrelated_public_model_input.json')['sources'][0]['text']
old_ledger=read(OLD/'live-B1-controls/public-call-ledger.json')
old_unrelated_row=next(r for r in old_ledger if r.get('request',{}).get('question')=='Как DocAtlas отправляет сообщения через квантовый канал?')
old_owner_row=next(r for r in old_ledger if r.get('request',{}).get('question')=='How does OtherAPI handle packet delivery during recovery?')
old_owner_project=Path(old_owner_row['request']['project_path'])
old_owner_docs={str(Path(s[1]).relative_to(old_owner_project)):s[2] for s in old_owner_row['state_before']['rows']}
old_unrelated_comparison={'full_text_equal':old_unrelated==group_docs['unrelated']['docs/fixture.md'],
    'text_sha256':sha(old_unrelated.encode()),'old_path':old_unrelated_row['payload']['sources'][0]['path_or_url'],
    'current_path':'docs/fixture.md','path_equal':old_unrelated_row['payload']['sources'][0]['path_or_url']=='docs/fixture.md',
    'classification':'SAME QUESTION/TEXT; CHANGED RELATIVE PATH AND REAL PROJECT/GENERATION BINDINGS, NOT EXACT OLD FIXTURE REPLAY'}
result={'audit_mode':'STDLIB_SAVED_DATA_ONLY_NO_RUNTIME','frozen_file_hash_errors':freeze_errors,'old_corpus_errors':old_corpus_errors,
    'prepares':prepare_checks,'public':rows,'comparisons':comparisons,'scores':score_checks,'host':host_checks,
    'freeze_k':freeze['k'],'freeze_precedes_all_host_attempts':freeze_before_host,'old_unrelated_comparison':old_unrelated_comparison,
    'old_OtherAPI_comparison':{'all_five_relative_paths_and_full_text_equal':old_owner_docs==group_docs['owner'],
        'old_emitted_owner_text_equal':old_owner_row['payload']['sources'][0]['snippet']==public['OtherAPI_B1']['payload']['sources'][0]['snippet']},
    'counts':{'public':len(rows),'host_attempts':len(host_checks),'host_completed':sum(h['execution']=='EXECUTED' for h in host_checks.values()),
        'model_forwards':sum(s['forwards'] for s in score_checks.values()),'prepares':len(prepares)},
    'issues':{'public_errors':{k:{a:v[a] for a in ['execution_errors','pool_errors','source_errors'] if v[a]} for k,v in rows.items() if any(v[a] for a in ['execution_errors','pool_errors','source_errors'])},
        'host_binding_errors':{k:v['errors'] for k,v in host_checks.items() if v['errors']},
        'citation_failures':{k:v['quotes'] for k,v in host_checks.items() if v['exact_citation_verdict']=='FAIL'}}}
(ROOT/'review/RAW_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'counts':result['counts'],'frozen_errors':freeze_errors,'old_corpus_errors':old_corpus_errors,
    'prepare_errors':{k:v['errors'] for k,v in prepare_checks.items() if v['errors']},'score_errors':{k:v['errors'] for k,v in score_checks.items() if v['errors']},
    'public_errors':result['issues']['public_errors'],'host_binding_errors':result['issues']['host_binding_errors'],
    'citation_failures':result['issues']['citation_failures'],'comparisons':comparisons},ensure_ascii=False,indent=2))
