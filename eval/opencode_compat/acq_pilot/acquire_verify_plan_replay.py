import json
from pathlib import Path
from docmancer.docs.application.evidence_requirements import build_requirements
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.lifecycle_policy import lifecycle_intent
from docmancer.retrieval.query_planning import extract_document_locator
R=Path('/tmp/opencode/acq-pilot');D=R/'acquire-stage'
questions=json.loads(Path('/home/viadmin/StudioProjects/DocAtlas/eval/opencode_compat/acq_pilot/oracle.json').read_text())['questions']
out=[]
for q in questions:
    locator=extract_document_locator(q['question'])
    requirements=build_requirements(q['question'],required_evidence_paths=(locator,) if locator else (),required_target_paths=(),profile='project_document_answer' if locator else 'project_docs_answer')
    full=build_documentation_query_plan(q['question'],lookup_queries=(q['search_question'],),explicit_path=locator,requirements=requirements).as_payload()
    saved=json.loads((D/f'acquired-L0-v0-{q["id"]}.json').read_text())
    out.append({'question_id':q['id'],'locator':locator,'production_requirement_lifecycle':requirements.lifecycle_intent,'diagnostic_lifecycle':lifecycle_intent(q['question']),'requirements_aware_plan':full,'saved_plan_equal':saved['plan']==full})
result={'source_path':'docmancer/docs/application/_project_context_service_part01.py:58-84,93-100; _project_docs_service_part03.py:107-130,213-218,239-246,268-279; retrieval/_dispatch_part01.py:105-110,156-160','observation':'P1 actual input expand, filters and row order recorded in ../acquire-observed-L0-v0-P1.json; this file is production-function replay, not a claim of original trace capture','questions':out}
(D/'plan-replay-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print([(x['question_id'],x['locator'],x['production_requirement_lifecycle'],x['diagnostic_lifecycle'],x['saved_plan_equal']) for x in out])
