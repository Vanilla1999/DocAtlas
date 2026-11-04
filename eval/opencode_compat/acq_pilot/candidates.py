import hashlib,json,os,re,sys,time
from pathlib import Path
from docmancer.core.member_storage_policy import MemberStoragePolicy
from docmancer.core.member_read_store import MemberReadStore
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.lifecycle_policy import lifecycle_filters_for_intent,lifecycle_intent
import docmancer.retrieval.experimental_acquisition as EA
R=Path('/tmp/opencode/acq-pilot'); corpus=sys.argv[1]; variant=os.environ['DOCATLAS_EXPERIMENT_ACQUISITION']
home=Path('/home/viadmin/.local/share/docatlas-acq-pilot')/corpus/'docatlas-home'
project=Path('/tmp/opencode/semantic-signal-experiment/project') if corpus=='L0' else R/'L2-project'
store=MemberReadStore(MemberStoragePolicy(home,home/'mcp-members/members.db'))
oracle=json.loads(Path('/home/viadmin/StudioProjects/DocAtlas/eval/opencode_compat/acq_pilot/oracle.json').read_text())
identity='local:'+hashlib.sha256(str(project.resolve()).encode()).hexdigest()
allout=[]
for q in oracle['questions']:
    plan=build_documentation_query_plan(q['question'],lookup_queries=(q['search_question'],)).as_payload()
    filters={'project_path':str(project),'project_identity':identity,'source_class':{'in':['project_file']},**lifecycle_filters_for_intent(lifecycle_intent(q['question'])),'doc_scope':{'in':['project']}}
    lanes=[('original',q['question'],filters),('authority',q['question'],{**filters,'authority':'source_of_truth'}),('host_lookup',q['search_question'],filters)]
    result={'question_id':q['id'],'production_plan_reconstructed':plan,'plan_observation_gap':'public stdio trace records projection only; planner replay uses actual request inputs, not captured plan','lanes':[],'ordered_union_ids':[],'qualification_gap':'pre/post qualification not observed'}
    seen=set()
    for name,text,fil in lanes:
        sql,params=store._metadata_filter_sql(fil,promoted=True)
        expression='{title retrieval_text} : ('+' OR '.join('"'+t+'"' for t in re.findall(r'\w+',text))+')'
        with store._connect() as c:
            generation=store._active_generation_id(c)
            count=c.execute('SELECT count(*) FROM retrieval_children_fts JOIN retrieval_children AS sections ON sections.id=retrieval_children_fts.rowid WHERE retrieval_children_fts MATCH ? AND sections.generation_id=? '+sql,(expression,generation,*params)).fetchone()[0]
        EA.ACQUISITION_CANDIDATES=256;t=time.perf_counter(); rows=store._search_rows(text,256,filters=fil); elapsed=time.perf_counter()-t
        EA.ACQUISITION_CANDIDATES=20000;t=time.perf_counter(); full=store._search_rows(text,20000,filters=fil); fulltime=time.perf_counter()-t
        ids=[r['stable_chunk_id'] for r in rows]; fullids=[r['stable_chunk_id'] for r in full]
        for id in ids:
            if id not in seen: seen.add(id);result['ordered_union_ids'].append(id)
        result['lanes'].append({'lane':name,'text':text,'filters':fil,'active_generation':generation,'fts_expression':expression,'fts_scoped_count':count,'positive_or_locator_count':len(full),'ordered_ids':ids,'full_ordered_ids':fullids,'prefix_equal':ids==fullids[:len(ids)],'candidate_rows':rows,'full_rows':full,'seconds_256':elapsed,'seconds_full':fulltime})
        print(corpus,variant,q['id'],name,'fts',count,'positive',len(full),'prefix',ids==fullids[:len(ids)],flush=True)
    allout.append(result)
    (R/f'candidates-{corpus}-{variant}-{q["id"]}.json').write_text(json.dumps(result,ensure_ascii=False))
