"""Frozen public-corpus experiment; no gold or experimental policy in production.

A/B/lookup lanes call the real handler. C/D replay exactly A's application result
through the same projector and final validator. They are NOT end-to-end lanes.
All raw traces stay in an explicitly selected external output directory.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from contextlib import nullcontext
from copy import deepcopy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import random
import re
import subprocess
import sys
import time
import traceback
from unittest.mock import patch

from eval.evidence_quality_v2.cost import count_input, model_visible_text, percentiles
from eval.evidence_quality_v2.observer import observe_call
from eval.evidence_quality_v2.runtime import digest, index_project, isolated_service, save_json, write_project
from eval.evidence_quality_v2.semantic import assess_context

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def load_protocol() -> tuple[dict, list[dict], dict]:
    protocol = json.loads((HERE/'protocol.json').read_text())
    for filename, key in [('cases.json','cases_sha256'), ('source-manifest.json','source_sha256')]:
        if digest((HERE/filename).read_bytes()) != protocol[key]:
            raise ValueError(f'frozen {filename} identity changed')
    return protocol, json.loads((HERE/'cases.json').read_text())['cases'], json.loads((HERE/'source-manifest.json').read_text())


def documents_for(project: str, manifest: dict) -> dict[str, str]:
    documents = {}
    for row in manifest['sources']:
        if row['project'] != project:
            continue
        data = (HERE/'sources'/project/row['path']).read_bytes()
        if digest(data) != row['sha256']:
            raise ValueError('source manifest mismatch: '+row['path'])
        documents[row['path']] = data.decode('utf-8')
    if not documents:
        raise ValueError('project has no documents')
    return documents


def registry_for(project: str, manifest: dict) -> dict:
    return {row['path']: {'project_group': project, 'version': row['ref'], 'scope':'project',
                         'authority':'source_of_truth', 'lifecycle':'active'}
            for row in manifest['sources'] if row['project'] == project}


def lexical_candidates(candidates: list[dict], *, query_text: dict, **kwargs) -> list[dict]:
    """One eval-only relevance order; never adds candidates or changes their text."""
    tokens = set(re.findall(r'[\w]+', ' '.join(str(x) for x in query_text.values()).casefold()))
    return sorted(candidates, key=lambda s: (
        -len(tokens & set(re.findall(r'[\w]+', str(s.get('snippet') or '').casefold()))),
        str(s.get('path_or_url') or ''), s.get('line_start') or 0, s.get('line_end') or 0,
        str(s.get('snippet') or '')))


def lookup_variant(question: str, variant: str) -> list[str] | None:
    if variant == 'L-duplicate':
        return [question]  # duplicate of implicit query-original; the schema forbids repeated array items
    if variant == 'L-nearby':
        return ['deployment changelog maintenance']
    if variant == 'L-explicit':
        # Only the user's original characters; no expected path or answer leaks.
        identifiers = re.findall(r'`([^`]+)`|\b([\w]+(?:[._][\w]+)+)\b', question)
        text = ' '.join(a or b for a, b in identifiers)
        return [text] if text else [question]
    return None


def audit_payload(payload: dict, snapshot: dict, root: Path) -> list[str]:
    from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
    errors = validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800)
    for source in payload.get('sources') or []:
        path = (root / str(source.get('path_or_url') or '')).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            errors.append('source escapes the isolated corpus')
            continue
        text = path.read_text(encoding='utf-8')
        start, end = source.get('line_start'), source.get('line_end')
        snippet = str(source.get('snippet') or '')
        if type(start) is not int or type(end) is not int or start < 1 or end < start:
            errors.append('invalid source line range')
        elif snippet not in '\n'.join(text.splitlines()[start-1:end]):
            errors.append('source span does not occur inside claimed line range')
        if not snippet or snippet not in text:
            errors.append('noncontiguous or nonexistent source snippet')
        if payload.get('kind') == 'docs_context' and any(payload.get(k) is not False for k in ('answer_supported','answer_available','edit_ready')):
            errors.append('retrieval-only flag violation')
    return errors


def _stage_sources(rows: list[dict]) -> list[dict]:
    # Equal candidate IDs may name distinct projected windows. Occurrences stay
    # separate; this ID is solely an external assessment key, never a public ID.
    result = []
    seen = set()
    for index, row in enumerate(rows):
        source = deepcopy(row)
        source['path_or_url'] = source.get('path_or_url') or source.get('source_path')
        source['snippet'] = source.get('snippet') or source.get('display_text') or ''
        key = (source.get('path_or_url'), source.get('snippet'), source.get('line_start'), source.get('line_end'))
        if key in seen:
            continue
        seen.add(key)
        source['observed_evidence_id'] = source.get('evidence_id') or source.get('stable_chunk_id')
        source['evidence_id'] = f'observed-span-{index}'
        result.append(source)
    return result


def stage_assessment(case: dict, payload: dict, trace: dict, index: dict, registry: dict) -> dict:
    observations = {}
    stages = trace.get('stages', {})
    def score(name, rows, complete, boundary=None):
        result = assess_context(case, {'sources': _stage_sources(rows)}, registry)
        observations[name] = {'complete': complete, 'required_supported':result['required_supported'],
            'required_count':result['required_count'], 'context_sufficiency':result['context_sufficiency'],
            'boundary':boundary, 'claim_statuses': {k:v['status'] for k,v in result['claims'].items()}}
    score('index', index['rows'], True, 'complete selected corpus index, not the entire upstream project')
    for name, key, field in [('retrieval','retrieved_candidates','sources'), ('query_window','query_window','sources'),
                             ('ranking','rankings','after'), ('selection','expansions','before')]:
        calls = stages.get(key, [])
        score(name, [r for c in calls for r in c[field]], bool(calls) and all(c['complete'] for c in calls),
              'mixed lifecycle/deduplication/cap/budget; not a pure eligibility gate' if key=='query_window' else None)
    score('projection', payload.get('sources', []), True)
    # Fail closed: an unknown equivalence is not automatically an absent fact.
    first_loss = {}
    for claim in case['required_claims']:
        cid = claim['id']
        if observations['projection']['claim_statuses'][cid] == 'supported':
            first_loss[cid] = 'visible'
        elif not claim.get('witness_sets'):
            first_loss[cid] = 'source_not_established_in_selected_corpus'
        elif observations['index']['claim_statuses'][cid] != 'supported':
            first_loss[cid] = 'index_or_spanning_witness_needs_review'
        elif not observations['retrieval']['complete']:
            first_loss[cid] = 'unobserved'
        elif observations['retrieval']['claim_statuses'][cid] != 'supported':
            first_loss[cid] = 'retrieval_recognized_witness_loss_needs_review'
        elif observations['selection']['complete'] and observations['selection']['claim_statuses'][cid] == 'supported':
            first_loss[cid] = 'projection_recognized_witness_loss_needs_review'
        else:
            first_loss[cid] = 'after_retrieval_mixed_transition_needs_review'
    return {'stages':observations,'first_observed_loss':first_loss,
            'note':'Needs-review labels are not a proof of a production defect or true source absence.'}


def evaluate_row(case, variant, payload, trace, root, registry, index, elapsed, request):
    if payload.get('status') == 'failed':
        raise RuntimeError('public tool rejected request: '+str(payload.get('error')))
    assessment = assess_context(case,payload,registry)
    text = model_visible_text({'structuredContent':payload},'structured')
    literal = {}
    for claim in case['required_claims']:
        literal[claim['id']] = any(all(any(part['path']==s.get('path_or_url') and part['text'] in s.get('snippet','')
                for s in payload.get('sources',[])) for part in group['parts']) for group in claim.get('witness_sets',[]))
    return {'id':case['id'],'project':case['project_group'],'family':case['family'],'split':case['split'],
        'answerability':case['answerability'],'variant':variant,
        'execution':'frozen_projector_replay' if '-replay' in variant else 'real_handler_same_call',
        'request':request,'seconds':elapsed,'payload':payload,'assessment':assessment,
        'literal_required':literal,'size':count_input(text),'engineering_estimate':payload.get('estimated_tokens'),
        'safety_errors':audit_payload(payload,trace.get('snapshot',{}),root),
        'observer_counts':trace.get('observer_counts',{}),
        'stage_assessment':stage_assessment(case,payload,trace,index,registry)}


def summarize(rows: list[dict], protocol: dict) -> dict:
    result = {'schema_version':'evidence-quality-results-v2','rows':len(rows),
              'unseen_validation':'NOT_MEASURED','host_quality':'NOT_MEASURED',
              'variants':{},'paired':{},'source_kind':'selected real upstream Markdown, unchanged bytes'}
    for variant in protocol['variants']:
        subset = [r for r in rows if r['variant']==variant]
        if not subset:
            continue
        valid = [r for r in subset if 'error' not in r]
        primary = [r for r in valid if r['answerability']=='within_budget']
        sufficient = lambda r: r['assessment']['context_sufficiency']=='sufficient' and not r['safety_errors']
        summary = {'cases':len(subset),'operational_errors':len(subset)-len(valid),
            'within_budget':len([r for r in subset if r['answerability']=='within_budget']),
            'within_budget_sufficient':sum(sufficient(r) for r in primary),
            'sufficiency':dict(Counter(r['assessment']['context_sufficiency'] for r in valid)),
            'literal_full':sum(all(r['literal_required'].values()) for r in valid),
            'source_integrity_or_contract_violations':sum(bool(r['safety_errors']) for r in valid),
            'required_supported':sum(r['assessment']['required_supported'] for r in valid),
            'required_total':sum(r['assessment']['required_count'] for r in valid),
            'tokens':percentiles(r['size']['actual_tokens'] for r in valid),
            'bytes':percentiles(r['size']['utf8_bytes'] for r in valid),
            'latency_seconds':percentiles(r['seconds'] for r in valid),
            'slices':{}}
        for field in ('project','family','split','answerability'):
            summary['slices'][field] = {name:{'n':len(group),'sufficient':sum(sufficient(r) for r in group)}
                for name in sorted({r[field] for r in valid}) if (group:=[r for r in valid if r[field]==name])}
        result['variants'][variant] = summary
    baseline = {r['id']:r for r in rows if r['variant']=='A-current' and r['answerability']=='within_budget'}
    for variant in result['variants']:
        if variant=='A-current': continue
        pairs = [(baseline[r['id']],r) for r in rows if r['variant']==variant and r['id'] in baseline]
        def ok(r): return int('error' not in r and r['assessment']['context_sufficiency']=='sufficient' and not r['safety_errors'])
        groups = defaultdict(list)
        for a,b in pairs: groups[a['project']].append(ok(b)-ok(a))
        group_deltas=[sum(v)/len(v) for v in groups.values()]
        rng=random.Random(protocol['bootstrap']['seed'])
        samples=sorted(sum(rng.choices(group_deltas,k=len(group_deltas)))/len(group_deltas)
                       for _ in range(protocol['bootstrap']['resamples'])) if group_deltas else []
        ci=[samples[int(len(samples)*.025)],samples[min(len(samples)-1,int(len(samples)*.975))]] if samples else [None,None]
        result['paired'][variant]={'wins':[b['id'] for a,b in pairs if ok(b)>ok(a)],
            'losses':[b['id'] for a,b in pairs if ok(b)<ok(a)],'project_groups':len(groups),
            'mean_project_delta':sum(group_deltas)/len(group_deltas) if group_deltas else None,
            'cluster_bootstrap_95':ci,'comparative_outcome':'INCONCLUSIVE' if not samples or ci[0]<=0<=ci[1] else 'diagnostic_difference_only',
            'warning':'few related project groups; exposed tasks; no market or hidden validation claim'}
    return result


def run(output: Path, projects: list[str] | None = None, *, fixture_output: Path | None = None) -> dict:
    from docmancer.docs.application import docs_context_projection as projection
    from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
    from docmancer.docs.domain import documentation_query_plan
    protocol,cases,manifest = load_protocol()
    output=output.resolve()
    if output.is_relative_to(REPO): raise ValueError('raw fixture traces must be outside checkout')
    output.mkdir(parents=True,exist_ok=True)
    save_json(output/'environment.json',{'python':sys.version,'platform':platform.platform(),
        'executable':sys.executable,'code_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
        'protocol_sha256':digest((HERE/'protocol.json').read_bytes()),'packages':{n:importlib.metadata.version(n) for n in ['pydantic','mcp','tiktoken']},
        'mode':'lexical, no embeddings, no live provider','transport':'handler; installed stdio is a separate run'})
    rows=[]
    for project in sorted({c['project_group'] for c in cases}):
        if projects and project not in projects: continue
        fixture = fixture_output.resolve() if fixture_output is not None else output
        root=fixture/'corpus'/project
        documents=documents_for(project,manifest); registry=registry_for(project,manifest)
        if fixture_output is None:
            write_project(root,documents)
        with isolated_service(fixture/'state'/project) as (service,config):
            index=(json.loads((fixture/'ingest'/f'{project}.json').read_text())
                   if fixture_output is not None else index_project(service,config,root))
            save_json(output/'ingest'/f'{project}.json',index)
            for case in [c for c in cases if c['project_group']==project]:
                base_trace=None
                for variant in protocol['variants']:
                    request={'question':case['question'],'project_path':str(root),'scope':'all'}
                    lookups=lookup_variant(case['question'],variant)
                    if lookups is not None: request['lookup_queries']=lookups
                    try:
                        start=time.perf_counter()
                        if '-replay' in variant:
                            if not base_trace or len(base_trace['stages']['projector_inputs'])!=1:
                                raise RuntimeError('no complete same-call baseline projector input')
                            frozen=deepcopy(base_trace['stages']['projector_inputs'][0])
                            before=digest(json.dumps(frozen,sort_keys=True,default=str).encode())
                            manager=(patch.object(projection,'_facet_aware_candidates',lexical_candidates)
                                if variant.startswith('C-') else patch.object(projection,'_expand_selected_snippets',lambda sources,**kw:deepcopy(sources)))
                            with manager:
                                payload,snapshot=projection.project_docs_context(retrieval=frozen,max_tokens=800)
                                validation=validate_model_visible_projection(payload,snapshot=snapshot,max_tokens=800)
                            trace={'snapshot':snapshot,'observer_counts':{'retrieval_calls':0,'validation_calls':1},'stages':{},
                                   'replay_input_sha256':before,'baseline_request':request,'validation_errors':validation}
                        else:
                            manager=patch.object(documentation_query_plan,'build_project_retrieval_aliases',lambda *a,**kw:()) if variant=='B-no-canonical' else nullcontext()
                            with manager: payload,trace=observe_call(service,request)
                            if variant=='A-current': base_trace=deepcopy(trace)
                        elapsed=time.perf_counter()-start
                        save_json(output/'traces'/variant/f'{case["id"]}.json',trace)
                        save_json(output/'payloads'/variant/f'{case["id"]}.json',payload)
                        row=evaluate_row(case,variant,payload,trace,root,registry,index,elapsed,request)
                    except Exception as exc:
                        row={key:case[key] for key in ['id','family','split','answerability']}
                        row.update(project=project,variant=variant,error=f'{type(exc).__name__}: {exc}',request=request)
                        (output/f'{project}-errors.log').open('a').write(traceback.format_exc()+'\n')
                    rows.append(row)
                    save_json(output/'raw'/variant/f'{case["id"]}.json',row)
                print(project,case['id'],[(r['variant'],r.get('assessment',{}).get('context_sufficiency',r.get('error'))) for r in rows[-len(protocol['variants']):]],flush=True)
    summary=summarize(rows,protocol)
    save_json(output/'summary.json',summary)
    save_json(output/'rows.json',rows)
    print(json.dumps(summary['paired'],ensure_ascii=False,indent=2),flush=True)
    return summary


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--project',action='append')
    args=parser.parse_args()
    summary=run(args.output,args.project)
    return int(any(v['operational_errors'] or v['source_integrity_or_contract_violations'] for v in summary['variants'].values()))

if __name__=='__main__': raise SystemExit(main())
