"""Six fixed logical lanes; unchanged queries/retrieval/budget and frozen scorer."""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.util
import json
import lzma
from pathlib import Path
import sys
from unittest.mock import patch
from relaxation import RelaxedBinder, MODES, installed, label
from section_scope import STAMP_KEYS, PREFIX
from docmancer.docs.application import docs_context_projection as projection
from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens
from eval.evidence_quality_v2.run import load_protocol, documents_for, registry_for, audit_payload
from eval.evidence_quality_v2.semantic import assess_context

HERE=Path(__file__).resolve().parent


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str)+'\n')


def spans(payload):
    return [(s['path_or_url'],s['snippet']) for s in payload.get('sources',[])]


def main():
    p=argparse.ArgumentParser(); p.add_argument('--output',type=Path,required=True); a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    spec=importlib.util.spec_from_file_location('prior_scope_runner',HERE.parent/'section-scope/run.py')
    prior=importlib.util.module_from_spec(spec); spec.loader.exec_module(prior)
    with patch.object(sys,'argv',['run.py','--output',str(a.output/'prior')]):
        prior.main()
    prior_rows=json.loads((a.output/'prior/questions.json').read_text())
    inputs=json.loads(lzma.decompress((a.output/'prior/inputs.json.xz').read_bytes()))
    _,cases,manifest=load_protocol(); cases={c['id']:c for c in cases}
    outcomes=[{**r,'mode':'scope' if r['mode']=='scope_requalify' else 'current'}
              for r in prior_rows if r['mode'] in {'scope_requalify','current'}]
    scopes={r['id']:r for r in outcomes if r['mode']=='scope'}
    assert sum(r['answerability']=='within_budget' and r['assessment']['context_sufficiency']=='sufficient'
               for r in scopes.values())==35
    all_events=[]
    for cid,frozen in inputs.items():
        case=cases[cid]; group=case['project_group']
        documents=documents_for(group,manifest)
        registry={r['path']:r for r in manifest['sources'] if r['project']==group}
        identities={c['project_identity'] for c in frozen['context_pack']}; assert len(identities)==1
        stamps={}
        for c in frozen['context_pack']:
            stamp=tuple(c.get(k) for k in STAMP_KEYS)
            assert stamps.setdefault(c['path'],stamp)==stamp
        for mode in MODES:
            binder=RelaxedBinder(documents,next(iter(identities)),stamps,
                                 registry=registry,question=case['question'],mode=mode)
            retrieval,events=deepcopy(frozen),[]
            with installed(binder,events):
                payload,snapshot=projection.project_docs_context(retrieval=retrieval)
            root=Path('/tmp/docatlas-continued-systemic/acceptance/full80_current/corpus')/group
            errors=audit_payload(payload,snapshot,root); proofs=[]
            for s in payload.get('sources',[]):
                if not any(s['path_or_url']==c['path'] and s['snippet'] in c['content'] for c in frozen['context_pack']):
                    errors.append('quote escaped unchanged candidate pool')
                if str(s['section']).startswith(PREFIX):
                    proof=binder.bind({**s,'_qualification_candidate':snapshot[s['evidence_id']]['source']})
                    if not proof or label(proof)!=s['section']:
                        errors.append('visible contextual binding failed revalidation')
                    proofs.append({'evidence_id':s['evidence_id'],'proof':proof})
            if any(payload.get(k) is not False for k in ('answer_supported','answer_available','edit_ready')):
                errors.append('context became answer/edit authorization')
            if docs_context_budget_tokens(payload)>800 or len(payload.get('sources',[]))>3:
                errors.append('full DTO or source budget exceeded')
            outcomes.append({'id':cid,'question':case['question'],'project_group':group,'mode':mode,
                             'answerability':case['answerability'],'payload':payload,'snapshot':snapshot,
                             'tokens':docs_context_budget_tokens(payload),
                             'assessment':assess_context(case,payload,registry_for(group,manifest)),
                             'audit_errors':errors,'binding_records':proofs,
                             'rescues':dict(Counter(e['stage'] for e in events if e['scope_proof']))})
            all_events.append({'id':cid,'mode':mode,'events':events})
        print('bounded-relaxation',cid,flush=True)
    assert len(outcomes)==480
    good=lambda r:r['answerability']=='within_budget' and r['assessment']['context_sufficiency']=='sufficient'
    bases={m:{r['id']:r for r in outcomes if r['mode']==m} for m in ('current','scope')}
    success={m:{cid for cid,r in base.items() if good(r)} for m,base in bases.items()}
    summary={}
    for mode in ('current','scope',*MODES):
        lane=[r for r in outcomes if r['mode']==mode]; ok={r['id'] for r in lane if good(r)}
        control_sufficient=[r['id'] for r in lane if r['answerability']!='within_budget'
                            and r['assessment']['context_sufficiency']=='sufficient']
        claim_losses=[]
        for r in lane:
            for key,value in scopes[r['id']]['assessment']['claims'].items():
                if value['status']=='supported' and r['assessment']['claims'][key]['status']!='supported':
                    claim_losses.append([r['id'],key])
        groups=sorted({cases[c]['project_group'] for c in ok-success['current']})
        summary[mode]={'sufficient':len(ok),'wins_vs34':sorted(ok-success['current']),
            'wins_vs35':sorted(ok-success['scope']),'losses_vs35':sorted(success['scope']-ok),
            'winning_projects_vs34':groups,'sufficient_controls':control_sufficient,
            'changed_controls_vs_scope':[r['id'] for r in lane if r['answerability']!='within_budget'
                                         and r['payload']!=scopes[r['id']]['payload']],
            'changed_payload_vs_scope':[r['id'] for r in lane if r['payload']!=scopes[r['id']]['payload']],
            'changed_spans_vs_scope':[r['id'] for r in lane if spans(r['payload'])!=spans(scopes[r['id']]['payload'])],
            'literal_losses_vs_scope':[r['id'] for r in lane if not all(any(p==p2 and s in s2 for p2,s2 in spans(r['payload']))
                                          for p,s in spans(scopes[r['id']]['payload']))],
            'supported_claim_losses_vs_scope':claim_losses,'mean_tokens':sum(r['tokens'] for r in lane)/80,
            'max_tokens':max(r['tokens'] for r in lane),'audit_errors':sum(len(r['audit_errors']) for r in lane),
            'screening_passed':len(ok)>=36 and len(groups)>=2 and not (success['scope']-ok)
                and not claim_losses and not control_sufficient and not any(r['audit_errors'] for r in lane)}
    validation={'logical_rows':480,'questions':80,'positives':48,'controls':32,
                'prior_native_baseline_reproduction':'separate verified workflow step',
                'prior_factorial_controls_reproduced':320,'prior_scope_dtos_reproduced':240,
                'new_policy_dtos':320,'audit_errors':sum(len(r['audit_errors']) for r in outcomes),
                'holdout_opened':False,'answer_model_run':False,'production_changed':False,
                'policy_sha256':hashlib.sha256((HERE/'relaxation.py').read_bytes()).hexdigest(),
                'documents_sha256':json.loads((a.output/'prior/validation.json').read_text())['documents_sha256']}
    for name,data in [('questions',outcomes),('summary',summary),('validation',validation)]:
        save(a.output/(name+'.json'),data)
    (a.output/'events.json.xz').write_bytes(lzma.compress(json.dumps(all_events,ensure_ascii=False).encode()))
    print('BOUNDED_RELAXATION_SUMMARY',json.dumps(summary,ensure_ascii=False),flush=True)
    assert validation['audit_errors']==0


if __name__=='__main__':
    main()
