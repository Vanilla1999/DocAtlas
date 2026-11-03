"""Read-only observation of the production acquisition stage; no stdio calls."""
import hashlib,json,os,sys,time
from pathlib import Path
from docmancer.core.member_storage_policy import MemberStoragePolicy
from docmancer.core.member_read_store import MemberReadStore
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.lifecycle_policy import lifecycle_filters_for_intent,lifecycle_intent
from docmancer.retrieval.experimental_acquisition import ACQUISITION_CANDIDATES, ACQUISITION_ESTIMATED_TOKENS, ACQUISITION_TEXT_BYTES, ACQUISITION_METHOD

ROOT=Path('/tmp/opencode/acq-pilot'); OUT=ROOT/'acquire-stage'
corpus=sys.argv[1]; variant=os.environ['DOCATLAS_EXPERIMENT_ACQUISITION']
project=Path('/tmp/opencode/semantic-signal-experiment/project') if corpus=='L0' else ROOT/'L2-project'
home=Path('/home/viadmin/.local/share/docatlas-acq-pilot')/corpus/'docatlas-home'
store=MemberReadStore(MemberStoragePolicy(home,home/'mcp-members/members.db'))
with store._connect() as conn: generation=store._active_generation_id(conn)
original_search=store._search_rows
original_expand=store._expand_row
events=[]
def observe_search(*args,**kwargs):
    t=time.perf_counter(); rows=original_search(*args,**kwargs)
    events.append({'stage':'sql_rows_before_acquisition','count':len(rows),'ordered_section_ids':[int(x['id']) for x in rows],'ordered_stable_ids':[x['stable_chunk_id'] for x in rows], 'estimated_tokens':sum(max(0,int(x['token_estimate'])) for x in rows),'text_bytes':sum(len(str(x['text']).encode('utf-8')) for x in rows),'seconds':time.perf_counter()-t})
    return rows
def observe_expand(*args,**kwargs):
    rows=original_expand(*args,**kwargs)
    events.append({'stage':'expansion','anchor_section_id':int(args[0]['id']),'returned_section_ids':[int(x['id']) for x in rows]})
    return rows
store._search_rows=observe_search
store._expand_row=observe_expand
oracle=json.loads(Path('/home/viadmin/StudioProjects/DocAtlas/eval/opencode_compat/acq_pilot/oracle.json').read_text())
identity='local:'+hashlib.sha256(str(project.resolve()).encode()).hexdigest()
for q in oracle['questions']:
    target=OUT/f'acquired-{corpus}-{variant}-{q["id"]}.json'
    if target.exists(): raise FileExistsError(f'refuse overwrite: {target}')
    plan=build_documentation_query_plan(q['question'],lookup_queries=(q['search_question'],)).as_payload()
    filters={'project_path':str(project),'project_identity':identity,'source_class':{'in':['project_file']},**lifecycle_filters_for_intent(lifecycle_intent(q['question'])),'doc_scope':{'in':['project']}}
    # P1 was observed in-process: the service's effective_expand is "none";
    # "none" or "page" therefore remains "none", not "page".
    effective_expand='none'
    lanes=[('original',q['question'],effective_expand,filters),('authority',q['question'],effective_expand or 'page',{**filters,'authority':'source_of_truth'}),('host_lookup',q['search_question'],'none',filters)]
    output={'corpus':corpus,'variant':variant,'question_id':q['id'],'active_generation':generation,'plan':plan,'plan_provenance':'production planner replay; actual P1 inputs and expand observed separately, not captured from 12 stdio calls','ordered_union_section_ids':[],'ordered_concat_section_ids':[],'lanes':[]}
    seen=set()
    for name,text,expand,fil in lanes:
        events.clear(); t=time.perf_counter(); chunks=store.acquire_candidates(text,expand=expand,filters=fil); elapsed=time.perf_counter()-t
        serialized=[chunk.model_dump(mode='json') for chunk in chunks]
        ids=[int(chunk.metadata['section_id']) for chunk in chunks]
        for id in ids:
            output['ordered_concat_section_ids'].append(id)
            if id not in seen:
                seen.add(id);output['ordered_union_section_ids'].append(id)
        after={'count':len(chunks),'estimated_tokens_from_rows':sum(max(0,int(x.metadata['token_estimate'])) for x in chunks),'text_bytes_from_rows':sum(len(x.text.encode('utf-8')) for x in chunks),'reported_acquisition':chunks[0].metadata.get('acquisition') if chunks else None}
        output['lanes'].append({'name':name,'arguments':{'text':text,'expand':expand,'filters':fil},'ceiling_constants':{'candidates':ACQUISITION_CANDIDATES,'estimated_tokens':ACQUISITION_ESTIMATED_TOKENS,'text_bytes':ACQUISITION_TEXT_BYTES,'method':ACQUISITION_METHOD},'before':list(events),'after':after,'ordered_section_ids':ids,'rows':serialized,'seconds':elapsed})
        print(corpus,variant,q['id'],name,'before',events[0]['count'] if events else None,'after',len(chunks),'tokens',after['estimated_tokens_from_rows'],'bytes',after['text_bytes_from_rows'],flush=True)
    target.write_text(json.dumps(output,ensure_ascii=False))
