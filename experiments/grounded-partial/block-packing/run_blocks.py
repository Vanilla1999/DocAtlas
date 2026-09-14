"""Two-lane English-only frozen projector replay. No model or retrieval calls."""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.metadata
import json
import lzma
from pathlib import Path
import re
import time
import zipfile

from structural_blocks import BlockIndex, installed as install_blocks
from relaxation import RelaxedBinder, installed as install_qualification, label
from section_scope import STAMP_KEYS, PREFIX
from docmancer.docs.application import docs_context_projection as projection
from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
from docmancer.docs.application.model_visible_projection_helpers import canonical_projection_bytes, estimate_projection_tokens
from docmancer.docs.application.projection_tokenizer import projection_token_count
from eval.evidence_quality_v2.semantic import assess_context


def sha(b): return hashlib.sha256(b).hexdigest()
def save(path,data): path.write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str)+'\n')
def spans(payload): return [(s['path_or_url'],s['snippet']) for s in payload.get('sources',[])]
def english(q): return re.search('[\u0400-\u04ff]',q) is None


def run(root, archive, output):
    output.mkdir(parents=True,exist_ok=False)
    started=time.monotonic()
    fixture=root/'eval/evidence_quality_v2'
    protocol=json.loads((fixture/'protocol.json').read_text())
    for path,key in [('cases.json','cases_sha256'),('source-manifest.json','source_sha256')]:
        expected=str(protocol[key]).removeprefix('sha256:')
        assert sha((fixture/path).read_bytes())==expected, path
    cases={c['id']:c for c in json.loads((fixture/'cases.json').read_text())['cases'] if english(c['question'])}
    manifest=json.loads((fixture/'source-manifest.json').read_text())
    with zipfile.ZipFile(archive) as z:
        inputs=json.loads(lzma.decompress(z.read('results/prior/inputs.json.xz')))
        prior={r['id']:r for r in json.loads(z.read('results/questions.json')) if r['mode']=='combined' and r['id'] in cases}
    assert len(cases)==len(prior)==67
    inputs={cid:inputs[cid] for cid in cases}
    (output/'inputs.json.xz').write_bytes(lzma.compress(json.dumps(inputs,ensure_ascii=False).encode()))
    documents,registries,indexes={},{},{}
    for group in sorted({c['project_group'] for c in cases.values()}):
        registry={r['path']:r for r in manifest['sources'] if r['project']==group}
        docs={p:(fixture/'sources'/group/p).read_text() for p in registry}
        assert all(sha(t.encode())==registry[p]['sha256'] for p,t in docs.items())
        documents[group],registries[group],indexes[group]=docs,registry,BlockIndex(docs)
        # Recreate only the frozen local corpus at the historical replay path.
        corpus=Path('/tmp/docatlas-continued-systemic/acceptance/full80_current/corpus')/group
        for path,text in docs.items():
            target=corpus/path; target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text)
    outcomes,events=[],[]
    for cid,case in cases.items():
        group=case['project_group']; frozen=inputs[cid]
        identity={c['project_identity'] for c in frozen['context_pack']};assert len(identity)==1
        stamps={}
        for c in frozen['context_pack']:
            stamp=tuple(c.get(k) for k in STAMP_KEYS);assert stamps.setdefault(c['path'],stamp)==stamp
        binder=RelaxedBinder(documents[group],next(iter(identity)),stamps,registry=registries[group],question=case['question'],mode='combined')
        for mode in ('control','blocks'):
            f=deepcopy(frozen); qevents=[];diagnostics={}
            begin=time.monotonic()
            with install_qualification(binder,qevents):
                if mode=='blocks':
                    with install_blocks(indexes[group],diagnostics):
                        payload,snapshot=projection.project_docs_context(retrieval=f)
                else:payload,snapshot=projection.project_docs_context(retrieval=f)
            elapsed=time.monotonic()-begin
            errors=validate_model_visible_projection(payload,snapshot=snapshot,max_tokens=800)
            for s in payload.get('sources',[]):
                path=s['path_or_url'];text=documents[group].get(path,'')
                a,b=s['line_start'],s['line_end']
                if not s['snippet'] or s['snippet'] not in '\n'.join(text.splitlines()[a-1:b]):errors.append('source line mismatch')
                candidates=[c for c in frozen['context_pack'] if c['path']==path and s['snippet'] in c['content']]
                if not candidates:errors.append('quote escaped unchanged candidate pool')
                if str(s['section']).startswith(PREFIX):
                    proof=binder.bind({**s,'_qualification_candidate':snapshot[s['evidence_id']]['source']})
                    if not proof or label(proof)!=s['section']:errors.append('section binding mismatch')
                if mode=='blocks' and not any(s['snippet']==c['content'][a:b] for c in candidates
                    for a,b in indexes[group].alternatives(c,c['content'])):
                    errors.append('output is not a complete registered structural alternative')
            assessment=assess_context(case,payload,{p:{'project_group':group,'version':r['ref'],'scope':'project',
                'authority':'source_of_truth','lifecycle':'active'} for p,r in registries[group].items()})
            tokens=projection.docs_context_budget_tokens(payload)
            if mode=='control':
                assert payload==prior[cid]['payload'], ('control payload',cid)
                assert tokens==prior[cid]['tokens'], ('control tokens',cid)
                assert assessment==prior[cid]['assessment'], ('control assessment',cid)
            outcomes.append({'id':cid,'question':case['question'],'mode':mode,'project_group':group,
                'answerability':case['answerability'],'input_sha256':sha(json.dumps(frozen,sort_keys=True).encode()),
                'payload':payload,'snapshot':snapshot,'tokens':tokens,'pinned_bpe_tokens':projection_token_count(canonical_projection_bytes(payload)),
                'byte_estimate_tokens':estimate_projection_tokens(payload),'assessment':assessment,
                'errors':errors,'elapsed_seconds':elapsed,'block_diagnostics':diagnostics,
                'projector_diagnostics':f['retrieval_diagnostics'].get('docs_context_projection')})
            events.append({'id':cid,'mode':mode,'qualification_events':qevents})
        print('block-replay',cid,flush=True)
    base={r['id']:r for r in outcomes if r['mode']=='control'}
    ok=lambda r:r['answerability']=='within_budget' and r['assessment']['context_sufficiency']=='sufficient'
    old={cid for cid,r in base.items() if ok(r)};assert len(old)==29
    summary={}
    for mode in ('control','blocks'):
        rows=[r for r in outcomes if r['mode']==mode]; successes={r['id'] for r in rows if ok(r)}
        summary[mode]={'sufficient':len(successes),'wins':sorted(successes-old),'losses':sorted(old-successes),
            'mean_tokens':sum(r['tokens'] for r in rows)/67,'max_tokens':max(r['tokens'] for r in rows),
            'mean_pinned_bpe_tokens':sum(r['pinned_bpe_tokens'] for r in rows)/67,
            'changed_payloads':[r['id'] for r in rows if r['payload']!=base[r['id']]['payload']],
            'changed_quotes':[r['id'] for r in rows if spans(r['payload'])!=spans(base[r['id']]['payload'])],
            'changed_controls':[r['id'] for r in rows if r['answerability']!='within_budget' and r['payload']!=base[r['id']]['payload']],
            'sufficient_controls':[r['id'] for r in rows if r['answerability']!='within_budget' and r['assessment']['context_sufficiency']=='sufficient'],
            'supported_claim_losses':[[r['id'],k] for r in rows for k,v in base[r['id']]['assessment']['claims'].items()
                if v['status']=='supported' and r['assessment']['claims'][k]['status']!='supported'],
            'literal_losses':[r['id'] for r in rows if not all(any(path==p and text in t for p,t in spans(r['payload'])) for path,text in spans(base[r['id']]['payload']))],
            'source_entries_above640':sum(len(s['snippet'])>640 for r in rows for s in r['payload'].get('sources',[])),
            'max_snippet_characters':max((len(s['snippet']) for r in rows for s in r['payload'].get('sources',[])),default=0),
            'audit_errors':sum(len(r['errors']) for r in rows),
            'source_count':sum(len(r['payload'].get('sources',[])) for r in rows)}
    validation={'questions':67,'positive_questions':35,'controls':32,'rows':134,'exact_archived_controls_reproduced':67,
        'input_archive_sha256':sha(archive.read_bytes()),'audit_errors':sum(len(r['errors']) for r in outcomes),
        'policy_sha256':sha((Path(__file__).parent/'structural_blocks.py').read_bytes()),
        'markdown_it_py':importlib.metadata.version('markdown-it-py'),'holdout_opened':False,'runtime_changed':False,
        'answer_model_run':False,'elapsed_seconds':time.monotonic()-started}
    for name,data in [('summary',summary),('validation',validation),('questions',outcomes)]:save(output/(name+'.json'),data)
    (output/'qualification-events.json.xz').write_bytes(lzma.compress(json.dumps(events,ensure_ascii=False,default=str).encode()))
    print(json.dumps(summary,indent=2),flush=True)
    assert not validation['audit_errors'], 'Artifacts preserved, but audit failed'


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path.cwd());parser.add_argument('--archive',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.root,args.archive,args.output)
