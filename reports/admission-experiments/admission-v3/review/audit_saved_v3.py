"""Independent stdlib saved-data audit only; never import/execute product/adapter/host."""
import hashlib
import json
import math
import re
from pathlib import Path
from collections import Counter

R = Path(__file__).resolve().parent.parent
REPO = Path('/tmp/opencode/docatlas-compact-review')
errors = []
checks = Counter()


def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def canonical(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def sha(x):
    return hashlib.sha256(x if isinstance(x, bytes) else x.encode('utf-8')).hexdigest()


def digest(x):
    return sha(canonical(x))


def ok(test, what, where):
    checks[what] += 1
    if not test:
        errors.append({'where': where, 'check': what})


def envelope(x):
    return {'path': x.get('path') or x.get('source') or x.get('url') or x.get('source_url'),
            'section': x.get('heading_path') or x.get('title'),
            'content': x.get('content') or x.get('display_text'),
            'snippet': x.get('snippet') or x.get('code'),
            'version': x.get('version_binding') or x.get('version') or x.get('requested_version')}


config = load(R/'EXECUTION_CONFIG.json')
cases = load(config['cases_file']) + config['additional_cases']
case_by_id = {x['id']: x for x in cases}
docs = {}
for x in load(config['corpus_file'])['documents']:
    docs.setdefault(x['document_group'], {})[x['path']] = x['content']
    ok(sha(x['content']) == x['utf8_sha256'], 'execution_corpus_hash', x['path'])
docs.update(config['additional_documents'])
bindings = {p.stem: load(p) for p in (R/'bindings').glob('*.json')}
prepares = {p.stem: load(p) for p in (R/'prepares').glob('*.json')}
publics = {}
public_verdicts = []
stable_state = {}


def group(c):
    return c.get('document_group', c.get('project'))


def ref_check(meta, reference, g, where):
    b = bindings[g]
    identity = 'local:' + sha(b['project'])
    source = reference['source']
    path = source['canonical_path']
    text = docs[g][path]
    a, z = reference['char_start'], reference['char_end']
    ok(reference['raw_document'] == text and type(a) is int and type(z) is int
       and 0 <= a < z <= len(text) and reference['text'] == text[a:z], 'raw_span', where)
    ok(source['content_sha256'] == sha(text) == b['document_hashes'][path], 'full_source_hash', where)
    ok(source['document_id'] == 'project_file:' + identity + ':' + path, 'document_identity', where)
    ok(source['scope'] == {'project_id': identity, 'version': '', 'snapshot_id': b['generation']}, 'scope_generation', where)
    ok(reference['project_doc_content_hash'] == 'sha256:' + sha(text), 'file_content_hash', where)
    member = reference['member_binding']
    catalog_hash = next(x['catalog_entry_hash'] for x in prepares[g]['documents'] if x['path'] == path)
    ok(member == {'doc_scope': 'project', 'module_path': '', 'catalog_entry_hash': catalog_hash}, 'catalog_member', where)
    for key in ('project_doc_catalog_entry_hash', '_source_catalog_hash'):
        if meta.get(key):
            ok(meta[key] == catalog_hash, 'catalog_metadata', where)
    if meta.get('source_class'):
        ok(meta['source_class'] in ('project_file', 'project_doc'), 'source_class', where)
    if meta.get('project_identity'):
        ok(meta['project_identity'] == identity, 'metadata_project', where)
    if meta.get('generation_id'):
        ok(meta['generation_id'] == b['generation'], 'metadata_generation', where)
    owner = reference.get('owner')
    if owner:
        s, e = owner['char_start'], owner['char_end']
        ok(0 <= owner['scope_start'] <= s < e <= owner['scope_end'] <= len(text)
           and text[s:e] == owner['text'] and owner['scope_start'] <= a < z <= owner['scope_end'],
           'structural_owner_bounds', where)
    return text, a, z


def native_key(q, body, meta, g):
    reference = meta['_reference_evidence']
    source = reference['source']
    scope = source['scope']
    member = reference['member_binding']
    return digest({'question': q, 'request_project_path': bindings[g]['project'], 'request_scope': 'project',
                   'source': {k: source[k] for k in ('document_id', 'canonical_path', 'content_sha256')},
                   'scope': {k: scope[k] for k in ('project_id', 'version', 'snapshot_id')},
                   'member': {k: member[k] for k in ('doc_scope', 'module_path', 'catalog_entry_hash')},
                   'file_content_hash': reference['project_doc_content_hash'],
                   'window_span': [reference['char_start'], reference['char_end']], 'window_sha256': sha(body)})


def pair_check(pair, text, where):
    a, z = pair['char_start'], pair['char_end']
    ok(text[a:z] == pair['text'] and text[pair['scalar_char_start']:pair['scalar_char_end']] == pair['scalar']
       and text[pair['label_char_start']:pair['label_char_end']] == pair['label'], 'scalar_pair_exact_spans', where)
    ok(bool(re.fullmatch(r'[0-9]+(?:[.,][0-9]+)?', pair['scalar'])) and pair['label'].isalpha(), 'scalar_pair_shape', where)
    ok(a == 0 or text[a-1].isspace(), 'maximal_scalar_start', where)
    tail = pair['label_char_end']
    if tail < len(text) and text[tail] in '.!?;:,':
        tail += 1
    ok(tail == len(text) or text[tail].isspace(), 'maximal_label_end', where)
    # Independent original-token context guard, using stored absolute operands.
    tokens = list(re.finditer(r'\S+', text))
    i = next((i for i, t in enumerate(tokens) if t.span() == (pair['scalar_char_start'], pair['scalar_char_end'])), None)
    ok(i is not None, 'whole_original_scalar_token', where)
    if i is not None:
        neighbors = tokens[max(0, i-1):i] + tokens[i+2:i+3]
        ok(not any(re.search(r'[=<>+*/\\^~\-−–—±×÷≤≥≠]', t[0]) for t in neighbors), 'original_neighbor_operator_veto', where)


def window_check(row, g, q, where):
    meta = row['metadata']
    ref = meta['_reference_evidence']
    text, a, z = ref_check(meta, ref, g, where)
    ok(row['span'] == [a,z] and row['text'] == text[a:z] and row['path'] == ref['source']['canonical_path']
       and row['binding'] == ref['source'] and row['text_sha256'] == sha(row['text']), 'candidate_window_identity', where)
    ok(row['id'] == digest([ref['source']['document_id'], a, z, row['text']]), 'candidate_id', where)
    root = meta['_reference_root_plan']
    ok(root['question'] == q and root['catalog_complete'] is True and root['scope'] == ref['source']['scope'], 'original_root_receipt_operands', where)
    trace = (meta.get('retrieval_query_matches') or {}).get('query-original') or {}
    if trace:
        ok(trace.get('query_text') == q and trace.get('query_origin') == 'original' and trace.get('relation') == 'direct', 'original_query_trace', where)
    admission = trace.get('literal_context_admission')
    if admission:
        ok(admission['coverage_credit'] is False and admission['generation_id'] == bindings[g]['generation']
           and admission['source_id'] == ref['source']['document_id'], 'admission_no_coverage_authority', where)
        for witness in admission['body_witnesses']:
            if witness.get('native_discovery_binding_sha256'):
                ok(witness['native_discovery_binding_sha256'] == native_key(q, row['text'], meta, g), 'native_fingerprint', where)
            if witness.get('kind') == 'scalar_label_original_candidate_v3':
                w1, w2 = witness['char_start'], witness['char_end']
                ok(a <= w1 < w2 <= z and witness['text'] == text[w1:w2]
                   and witness['relevance_unassessed'] is True and witness['numeric_condition_unassessed'] is True,
                   'scalar_witness_bound_unassessed', where)
                spans = {(p['scalar_char_start'], p['scalar_char_end']) for p in witness['query_scalar_label_pairs']}
                digit_tokens = {t.span() for t in re.finditer(r'\S+', q) if any(c.isdigit() for c in t[0])}
                ok(spans == digit_tokens and bool(spans), 'complete_query_digit_tokens', where)
                for p in witness['query_scalar_label_pairs']:
                    pair_check(p, q, where)
                for pair in witness['scalar_label_pairs']:
                    pair_check(pair['query'], q, where)
                    pair_check(pair['source'], text, where)
                    ok(w1 <= pair['source']['char_start'] < pair['source']['char_end'] <= w2
                       and pair['source']['label'].casefold() == pair['query']['label'].casefold(), 'local_scalar_pair_label_containment', where)


def immutable_row(row):
    return {k: row[k] for k in ('id','text','text_sha256','source','chunk_index','path','span','binding')}


def main():
    for path, value in config['frozen_files'].items():
        ok(sha(Path(path).read_bytes()) == value, 'execution_freeze_hash', path)
    freeze = load(R/'review/FREEZE.json')
    for path, value in freeze['sha256'].items():
        ok(sha((R/'review'/path).read_bytes()) == value, 'independent_freeze_hash', path)
    for case in load(R/'review/private/oracle.json')['cases']:
        for w in case['witnesses']:
            text=docs[case['project']][w['path']]
            a,z=w['char_start'],w['char_end']
            ok(text[a:z]==w['quote'] and sha(text)==w['document_sha256']
               and sha(w['quote'])==w['quote_sha256']
               and [text.count('\n',0,a)+1,text.count('\n',0,z-1)+1]==[w['line_start'],w['line_end']],
               'frozen_oracle_witness_coordinates_hashes',case['id'])
    source_identity = load(R/'SOURCE_IDENTITY.json')
    for path, value in source_identity['product_python_sha256'].items():
        ok(sha((REPO/path).read_bytes()) == value, 'product_after_run_hash', path)
    ok(source_identity['runtime_config_sha256'] == sha((R/'EXECUTION_CONFIG.json').read_bytes()), 'config_identity', 'SOURCE_IDENTITY')
    raw_hashes = load(R/'RAW_HASHES.json')
    inventory = {str(p.relative_to(R)) for folder in ('public','host','prepares','bindings','citation')
                 for p in (R/folder).rglob('*') if p.is_file()}
    ok(set(raw_hashes) == inventory, 'complete_raw_hash_inventory', 'RAW_HASHES')
    for path, value in raw_hashes.items():
        ok(sha((R/path).read_bytes()) == value, 'raw_artifact_hash', path)
    for g, b in bindings.items():
        p = prepares[g]
        ok(p['status'] == 'EXECUTED' and p['generation_id'] == b['generation']
           and p['indexed_paths'] == p['expected_paths'] == sorted(docs[g])
           and not p['excluded_or_failed_paths'] and not p['unexpected_paths'], 'prepare_finite_generation', g)
        ok(b['document_hashes'] == {path: sha(text) for path, text in docs[g].items()}, 'binding_allowlist', g)
        ok({x['path']:x['content_sha256'] for x in p['documents']} == b['document_hashes'], 'prepared_file_hashes', g)
    for path in sorted((R/'public').glob('*.json')):
        where = path.stem
        x = load(path)
        c = case_by_id[x['case_id']]
        g = group(c)
        b = bindings[g]
        publics[(x['case_id'],x['arm'])] = x
        ok(x['status'] == 'EXECUTED' and x['integrity_errors'] == [] and x['question'] == c['question'], 'public_execution_question', where)
        ok(x['request'] == {'question': c['question'],'project_path':b['project'],'scope':'project'}, 'public_request', where)
        state = x['state_before']
        ok(state == x['state_after'] and state['generation'] == b['generation'], 'state_read_unchanged', where)
        if g in stable_state:
            ok(state == stable_state[g], 'same_family_state_all_cases_arms', where)
        stable_state[g] = state
        expected_rows = sorted([[b['generation'], b['project']+'/'+p, text, sha(text), 'project_file:local:'+sha(b['project'])+':'+p] for p,text in docs[g].items()])
        ok(sorted(state['rows']) == expected_rows, 'stored_rows_expected_bytes', where)
        expected_files = {b['project']+'/'+p:sha(t) for p,t in docs[g].items()}
        expected_files[b['project']+'/docatlas.project-docs.yaml'] = prepares[g]['catalog_sha256']
        ok(state['files'] == expected_files, 'catalog_source_files_saved_state', where)
        payload = x['payload']
        ok(all(payload.get(k) is False for k in ('answer_supported','answer_available','edit_ready')), 'public_false_authority', where)
        sources = payload.get('sources') or []
        if sources:
            ok(payload.get('kind')=='docs_context' and payload.get('support_status')=='retrieval_only'
               and payload.get('context_available') is True,'public_retrieval_only_context_contract',where)
        ids = set()
        ranges = {}
        for item in sources:
            sid = item['evidence_id']
            ok(sid not in ids, 'unique_public_id', where)
            ids.add(sid)
            bound = x['validation_snapshot'][sid]
            ok(bound['projected_source'] == item, 'snapshot_projected_equality', where)
            original = bound['source']
            text, a, z = ref_check(original, original['_reference_evidence'], g, where)
            ok(item['content_sha256'] == digest(envelope(original)), 'canonical_envelope', where)
            ok(item['authority'] == 'source_of_truth' and item['scope'] == 'project'
               and item['version_binding'] == 'unversioned' and item['project_identity'] == 'local:'+sha(b['project']), 'public_source_authority_scope', where)
            snippet = item['snippet']
            positions = [m for m in range(a,z) if text.startswith(snippet,m) and m+len(snippet)<=z]
            positions = [m for m in positions if [text.count('\n',0,m)+1, text.count('\n',0,m+len(snippet)-1)+1] == [item['line_start'],item['line_end']]]
            ok(len(positions) == 1, 'unique_exact_snippet_line_span', where)
            if positions:
                ranges.setdefault(item['path_or_url'],[]).append([positions[0],positions[0]+len(snippet)])
        for pool in x['pools']:
            ok(pool['question'] == c['question'] and pool['selected_indices'] is None, 'observer_no_selection', where)
            for row in pool['complete_candidates']:
                window_check(row,g,c['question'],where)
            membership = []
            for row in pool['pool']:
                window_check(row,g,c['question'],where)
                membership.append(immutable_row(row))
            ords = [e['original_ordinal'] for e in pool['excluded']]
            ok(len(set(ords)) == len(ords) and all(immutable_row(e['candidate']) == immutable_row(pool['complete_candidates'][e['original_ordinal']]) for e in pool['excluded']), 'excluded_ordinals_identity',where)
            survivors = [immutable_row(row) for i,row in enumerate(pool['complete_candidates']) if i not in ords]
            ok(survivors == membership, 'complete_universe_partition',where)
            ok(len({(row['source'],row['chunk_index']) for row in pool['pool']}) == len(pool['pool']), 'pool_dedup',where)
        public_verdicts.append({'case_id':x['case_id'],'arm':x['arm'],'source_count':len(sources),'ranges':ranges})
    for c in cases:
        a,b = [publics[(c['id'], arm)] for arm in ('B1','V3')]
        ok(len(a['pools']) == len(b['pools']) == 1, 'admission_observation_boundary',c['id'])
        ok([immutable_row(r) for r in a['pools'][0]['complete_candidates']] == [immutable_row(r) for r in b['pools'][0]['complete_candidates']], 'B1_V3_complete_original_universe',c['id'])
        ok(publics[(c['id'],'DefaultOff')]['pools'] == [], 'default_observer_inactive',c['id'])
    host_verdicts = []
    for directory in sorted((R/'host').iterdir()):
        if not directory.is_dir():
            continue
        receipt = load(directory/'receipt.json')
        messages = load(directory/'messages.json')
        request = load(directory/'request.json')
        response = load(directory/'response.json')
        raw = (directory/'answer.raw.txt').read_bytes()
        answer = json.loads(raw)
        cid, arm = receipt['provenance']['case_id'], receipt['provenance']['arm']
        parent = config['citation_parent_by_case'].get(cid,config['citation_parent_arm']) if arm=='Citation' else arm
        x = publics[(cid,parent)]
        ok(receipt['execution']=='EXECUTED' and receipt['attempts']==1 and receipt['runner_retries']==0 and receipt['format_repairs']==0, 'single_host_execution',directory.name)
        ok(request['model'] == receipt['requested_model'] == source_identity['host_model'], 'frozen_host_model', directory.name)
        ok(response['data']['text'].encode('utf-8')==raw and load(directory/'answer.json')==answer,'raw_transport_parse_equality',directory.name)
        ok(request['prompt']=='Answer the following supplied conversation as the assistant. Return only the requested JSON. No tools, external context, or chain of thought.\nConversation JSON:\n'+canonical(messages), 'host_transport_wrapper',directory.name)
        ok(receipt['request_sha256']==digest(request) and receipt['provenance']['public_result_sha256']==digest(x), 'host_request_parent_hash',directory.name)
        ok(sha(messages[0]['content'])==receipt['provenance']['system_prompt_sha256'], 'host_prompt_hash',directory.name)
        inp=json.loads(messages[1]['content'])
        expected_sources=[{'source_id':s['evidence_id'],'text':s['snippet'],'provenance':{k:s[k] for k in ('path_or_url','scope','version_binding','line_start','line_end','project_identity','authority') if k in s}} for s in x['payload'].get('sources') or []]
        ok(inp['question']==case_by_id[cid]['question'], 'host_original_question',directory.name)
        if arm!='Citation':
            ok(set(answer)=={'status','answer','evidence','missing'} and answer['status']in ('complete','partial','insufficient')
               and type(answer['answer'])is str and type(answer['evidence'])is list and type(answer['missing'])is list
               and all(type(m)is str for m in answer['missing'])
               and all(set(e)=={'source_id','quote','supports'} and all(type(v)is str for v in e.values())for e in answer['evidence']),
               'base_answer_json_schema',directory.name)
            ok(inp=={'question':x['question'],'sources':expected_sources},'base_host_public_sources_only',directory.name)
            ok(messages[0]['content']==(R.parent/'admission-full-20261012/HOST_PROMPT_RU.txt').read_text(),'base_host_same_prompt',directory.name)
            sources={s['source_id']:s['text'] for s in inp['sources']}
            citation_fail=[e for e in answer['evidence'] if e['source_id'] not in sources or e['quote'] not in sources[e['source_id']]]
            host_verdicts.append({'case_id':cid,'arm':arm,'literal_citations':'FAIL' if citation_fail else ('PASS' if answer['evidence'] else 'N/A'),'citation_failures':citation_fail,'parsed_status':answer['status']})
        else:
            packet=load(R/'citation'/f'{cid}_packet.json')
            adapter_text = (R/'citation_adaptation.py').read_text()
            frozen_prompt = adapter_text.split("GENERATOR_PROMPT_RU = '''",1)[1].split("'''",1)[0]
            ok(messages[0]['content'] == frozen_prompt, 'citation_same_frozen_prompt', cid)
            ext=load(R/'citation'/f'{cid}_extracted.json')
            cost=load(R/'citation'/f'{cid}_cost.json')
            ok(packet['public_result_sha256']==digest(x) and packet['binding_sha256']==digest(bindings[group(case_by_id[cid])]),'citation_packet_binding',cid)
            ok(packet['prepared_sha256']==digest({k:v for k,v in packet.items() if k!='prepared_sha256'}), 'citation_packet_hash',cid)
            ok(inp==packet['model_input'] and ext['generator_output']==answer and ext['raw_answer_sha256']==sha(raw), 'citation_original_claims_input_raw',cid)
            ok(ext['prepared_sha256']==packet['prepared_sha256'] and ext['status']=='EXTRACTED' and ext['semantic_entailment']=='INDEPENDENT_REVIEW_REQUIRED', 'citation_extraction_shape',cid)
            ok(cost['parent_arm']==parent and cost['public_result_sha256']==digest(x),'citation_cost_parent',cid)
            ok([(s['source_id'],s['text']) for s in inp['sources']]==[(s['source_id'],s['text']) for s in expected_sources], 'citation_same_parent_public_content',cid)
            for s in inp['sources']:
                text=s['text']; f=packet['fragments'][s['source_id']]
                ok(s['length_codepoints']==len(text) and s['text_sha256']==sha(text) and ''.join(l['text'] for l in s['lines'])==text,'citation_lines_exact_cover',cid)
                for line in s['lines']:
                    ok(text[line['start']:line['end']]==line['text'],'citation_line_offsets',cid)
                ok(f['text']==text==f['raw_document'][f['char_start']:f['char_end']] and f['document_sha256']==sha(f['raw_document']),'citation_fragment_raw',cid)
                ok(f['source_envelope_sha256']==digest(f['source_envelope']),'citation_fragment_envelope',cid)
            ok(len(answer['claims'])==len(ext['claims']),'citation_claim_count',cid)
            for claim, output in zip(answer['claims'],ext['claims']):
                ok(claim['claim']==output['claim'] and len(claim['citations'])==len(output['citations']),'citation_claim_unchanged',cid)
                for c,o in zip(claim['citations'],output['citations']):
                    f=packet['fragments'][c['source_id']]; original=f['raw_document']; a=f['char_start']+c['start']; z=f['char_start']+c['end']; quote=f['text'][c['start']:c['end']]
                    ok(type(c['start']) is int and type(c['end']) is int and 0<=c['start']<c['end']<=len(f['text']), 'citation_coordinates',cid)
                    ok(o['source_id']==c['source_id'] and o['start']==c['start'] and o['end']==c['end'] and o['quote']==quote==original[a:z] and o['quote_sha256']==sha(quote),'citation_quote_literal',cid)
                    ok(o['document_char_range']==[a,z] and o['document_utf8_byte_range']==[len(original[:a].encode()),len(original[:z].encode())] and o['document_lf_line_range']==[original.count('\n',0,a)+1,original.count('\n',0,z-1)+1],'citation_absolute_coordinates',cid)
            ok((R/'citation'/cid/'raw_answer.bin').read_bytes()==raw and load(R/'citation'/cid/'extraction.json')==ext,'citation_saved_raw_unchanged',cid)
            host_verdicts.append({'case_id':cid,'arm':arm,'literal_citations':'PASS','citation_failures':[],'parsed_status':answer['status'],'coordinate_extraction':'PASS'})
    completion=load(R/'COMPLETION.json')
    ok(load(R/'RUN_RECEIPT.json')['config'] == config, 'run_config_unchanged', 'RUN_RECEIPT')
    ok(len(public_verdicts)==57 and len(host_verdicts)==28 and len(prepares)==7,'actual_saved_counts','ledger')
    current_ledger=load(R/'LEDGER.json')
    experiment_keys=tuple(completion['ledger'])
    ok(completion['ledger']=={k:current_ledger[k] for k in experiment_keys}==config['planned_workload']|{'errors':[]}, 'actual_ledger','ledger')
    costs=load(R/'COSTS_V3.json')
    for row in costs['rows']:
        if row['kind']=='context':
            x=publics[(row['case_id'],row['arm'])]
            ok(row['seconds']==x['elapsed_seconds'] and row['sources']==len(x['payload'].get('sources')or[]) and row['snippet_chars']==sum(len(s['snippet'])for s in x['payload'].get('sources')or[]),'context_cost_arithmetic',row['case_id'])
        elif row['kind']=='prepare':
            ok(row['seconds']==prepares[row['group']]['seconds'],'prepare_cost_arithmetic',row['group'])
        elif row['kind']=='host':
            d=R/'host'/f"{row['case_id']}_{row['arm']}"; receipt=load(d/'receipt.json'); req=load(d/'request.json')
            ok(row['seconds']==receipt['latency_seconds'] and row['submitted_prompt_chars']==len(req['prompt']) and row['submitted_prompt_utf8_bytes']==len(req['prompt'].encode()) and row['request_sha256']==digest(req),'host_actual_submitted_cost',d.name)
        elif row['kind']=='citation_reconstruction':
            c=load(R/'citation'/f"{row['case_id']}_cost.json")
            ok(row['seconds']==c['assembly_seconds']+c['reconstruction_seconds'],'citation_reconstruction_cost',row['case_id'])
    total=sum(row.get('seconds')or 0 for row in costs['rows'])
    ok(math.isclose(total,costs['observed_seconds_sum_lower_bound'],abs_tol=1e-9),'cost_total','costs')
    summaries={k:{'rows':sum(x['kind']==k for x in costs['rows']),'seconds':sum((x.get('seconds')or 0)for x in costs['rows'] if x['kind']==k)}for k in ('context','prepare','host','citation_reconstruction')}
    result={'errors':errors,'checks':dict(checks),'public':public_verdicts,'host':host_verdicts,'costs':summaries,'observed_seconds_sum_lower_bound':total,'whole_run_seconds':completion['runtime_seconds'],'execution_freeze_count':len(config['frozen_files']),'independent_freeze_count':len(freeze['sha256']),'product_source_count':len(source_identity['product_python_sha256']),'raw_hash_count':len(raw_hashes),'live_receipts_reexecuted':False,'supplementary_ledger_fields':{k:v for k,v in current_ledger.items() if k not in experiment_keys},'default_complete_universe_observer':'NOT_AVAILABLE: inactive by design'}
    (R/'review/RAW_AUDIT_V3.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'errors':errors,'counts':{'public':len(public_verdicts),'host':len(host_verdicts)},'costs':summaries},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
