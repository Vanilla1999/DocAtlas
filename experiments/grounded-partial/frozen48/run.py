"""Bounded offline diagnosis; gold is confined to explicitly named oracle lanes."""
import argparse
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import gzip
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
from unittest.mock import patch

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import DocsJobTracker, LibraryDocsService
from docmancer.docs.application import docs_context_projection as projection
from docmancer.docs.application._docs_context_payload import _payload
from docmancer.docs.application.model_visible_projection import _docs_source, _snapshot_entry, canonical_projection_bytes, docs_context_budget_tokens
from docmancer.docs.application.projection_tokenizer import projection_token_count
from docmancer.docs.domain.evidence_qualification import qualify_evidence
from docmancer.docs.domain.query_terms import documentation_query_terms, documentation_exact_terms, documentation_technical_anchors
from eval.evidence_quality_v2.run import load_protocol, registry_for, documents_for, audit_payload, stage_assessment, lexical_candidates
from eval.evidence_quality_v2.observer import observe_call
from eval.evidence_quality_v2.semantic import assess_context


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--replay-from',type=Path)
    cli=parser.parse_args(); out=cli.output.resolve(); assert not out.exists();out.mkdir(parents=True)
    _, cases, manifest=load_protocol()
    previous={r['id']:r for r in json.loads((cli.fixture/'rows.json').read_text())}
    misses={k for k,r in previous.items() if r['answerability']=='within_budget' and r['assessment']['context_sufficiency']!='sufficient'}
    assert len(misses)==15
    rows=[];bases={};cache={}
    save=lambda path,value:path.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n')
    save(out/'protocol.json',json.loads(Path(__file__).with_name('protocol.json').read_text()))

    def parts(case):return [p for claim in case['required_claims'] for p in claim['witness_sets'][0]['parts']]
    def hit(case,candidate):
        meta=candidate or {};path=meta.get('path_or_url') or meta.get('path') or meta.get('project_doc_path') or meta.get('source_path')
        start,end=meta.get('line_start'),meta.get('line_end')
        if not isinstance(start,int):
            span=meta.get('line_span') or [];start,end=span if len(span)==2 else (None,None)
        return any(path==p['path'] and isinstance(start,int) and isinstance(end,int) and start<=p['line_end'] and end>=p['line_start'] for p in parts(case))
    def qualifier(case,soft=False,subject=False):
        def call(probe,**kw):
            r=qualify_evidence(probe,**kw)
            eligible=bool(r.trace.get('body_matched_terms')) if soft else kw['query_id']=='query-original' and hit(case,kw.get('candidate'))
            if eligible and r.reason=='insufficient_visible_match' and (subject or not r.trace.get('missing_exact_terms')) and not r.trace.get('missing_parent_exact_terms'):
                trace={**r.trace,'oracle_subject_binding':list(r.trace.get('missing_exact_terms') or ()) if subject else [],'qualified':True,'qualification_reason':'TEST_ONLY_soft' if soft else 'TEST_ONLY_gold_relevance'}
                return replace(r,qualified=True,covered_query_ids=(kw['query_id'],),coverage_kind='direct',reason=trace['qualification_reason'],trace=trace)
            return r
        return call
    def patched(stack,fn):
        for module in list(sys.modules.values()):
            if module and getattr(module,'__name__','').startswith('docmancer.') and getattr(module,'qualify_evidence',None) is qualify_evidence:
                stack.enter_context(patch.object(module,'qualify_evidence',fn))
    def record(case,variant,payload,snapshot,root,trace=None,index=None):
        registry=registry_for(case['project_group'],manifest)
        row={'id':case['id'],'question':case['question'],'answerability':case['answerability'],'variant':variant,'payload':payload,
             'assessment':assess_context(case,payload,registry),'audit_errors':audit_payload(payload,snapshot,root),
             'actual_tokens':projection_token_count(canonical_projection_bytes(payload)),'admission_tokens':docs_context_budget_tokens(payload)}
        if trace:
            row['stages']=stage_assessment(case,payload,trace,index,registry)
            name=f'{case["id"]}-{variant}.json.gz';(out/name).write_bytes(gzip.compress(json.dumps(trace,ensure_ascii=False,default=str).encode(),mtime=0));row['trace']=name
        rows.append(row);save(out/'results.json',rows)
        print(variant,case['id'],row['assessment']['context_sufficiency'],row['actual_tokens'],row['audit_errors'],flush=True)
        return row
    if cli.replay_from:
        rows.extend(r for r in json.loads((cli.replay_from/'results.json').read_text()) if r['variant'] in {'baseline','soft','oracle_qualification'})
        bases=json.loads((cli.replay_from/'inputs.json').read_text())
        for case in cases:
            for item in (bases.get(case['id']) or {}).get('context_pack',[]):cache.setdefault((case['project_group'],item.get('path')),deepcopy(item))
    for project in ([] if cli.replay_from else sorted({c['project_group'] for c in cases})):
        root=cli.fixture/'corpus'/project
        for path,body in documents_for(project,manifest).items():assert (root/path).read_text()==body
        state=out/project;state.mkdir();db=state/'index.db'
        with sqlite3.connect(f'file:{cli.fixture/"state"/project/"index.db"}?mode=ro',uri=True) as source:
            with sqlite3.connect(db) as target:source.backup(target)
        os.environ.update(DOCATLAS_HOME=str(state/'home'),DOCATLAS_OFFLINE='1',DOCATLAS_AUTO_VECTORS='0')
        config=DocmancerConfig();config.index.db_path=str(db);config.index.extracted_dir=str(state/'extracted')
        service=LibraryDocsService(config=config,config_source='explicit',registry=LibraryRegistry(str(db)),agent=DocmancerAgent(config=config),job_tracker=DocsJobTracker())
        index=json.loads((cli.fixture/'ingest'/f'{project}.json').read_text())
        for case in [c for c in cases if c['project_group']==project]:
            args={'question':case['question'],'project_path':str(root),'scope':'all'}
            payload,trace=observe_call(service,args)
            span=lambda p:[(s['path_or_url'],s['snippet']) for s in p.get('sources',[])]
            assert span(payload)==span(previous[case['id']]['payload']),case['id']
            record(case,'baseline',payload,trace['snapshot'],root,trace,index)
            bases[case['id']]=deepcopy(trace['stages']['projector_inputs'][-1]) if trace['stages']['projector_inputs'] else None
            for inp in trace['stages']['projector_inputs']:
                for item in inp.get('context_pack',[]):cache.setdefault((project,item.get('path')),deepcopy(item))
            with ExitStack() as stack:
                patched(stack,qualifier(case,soft=True));payload,trace=observe_call(service,args)
            record(case,'soft',payload,trace['snapshot'],root,trace,index)
            if case['id'] in misses:
                with ExitStack() as stack:
                    patched(stack,qualifier(case));payload,trace=observe_call(service,args)
                record(case,'oracle_qualification',payload,trace['snapshot'],root,trace,index)
    for case in [c for c in cases if c['answerability']=='within_budget']:
        root=cli.fixture/'corpus'/case['project_group'];base=bases[case['id']]
        # Pure frozen-input order control, with zero annotation input to ranking.
        with patch.object(projection,'_facet_aware_candidates',lexical_candidates):
            payload,snapshot=projection.project_docs_context(retrieval=deepcopy(base))
        record(case,'lexical_replay',payload,snapshot,root)
        known=[];public=[];snapshot={}
        for part in parts(case):
            raw=deepcopy(cache[(case['project_group'],part['path'])]); lines=(root/part['path']).read_text().splitlines()
            body='\n'.join(lines[part['line_start']-1:part['line_end']]);assert part['text'] in body
            raw.update(content=body,display_text=body,line_start=part['line_start'],line_end=part['line_end'],retrieval_query_matches={},retrieval_query_ids=[],project_ranking={})
            raw['document_data']={**raw.get('document_data',{}),'content':body}
            with sqlite3.connect(cli.fixture/'state'/case['project_group']/'index.db') as db:
                section=db.execute('SELECT title,anchor FROM retrieval_children WHERE source_path=? AND line_start<=? AND line_end>=? ORDER BY line_start DESC LIMIT 1',(part['path'],part['line_start'],part['line_start'])).fetchone()
            assert section,(case['id'],part)
            raw.update(title=section[0],heading_path=section[1])
            raw['section']={**raw.get('section',{}),'title':section[0],'heading_path':section[1]}
            for key in ['snippet','code']:raw.pop(key,None)
            raw['source']={**raw.get('source',{}),'title':section[0]}
            for k in ['char_start','char_end','stable_chunk_id','parent_logical_id','display_content_hash']:raw.pop(k,None)
            q=case['question'];probe={'query_text':q,'query_origin':'original','relation':'direct','query_terms':list(documentation_query_terms(q)),
                'exact_terms':list(dict.fromkeys([*(x.normalized_value for x in documentation_exact_terms(q)),*(x.casefold() for x in documentation_technical_anchors(q))]))}
            qual=qualify_evidence(probe,query_id='query-original',visible_text=part['path']+'\n'+body,evidence_text=body,candidate=raw,expected_project_identity=raw['project_identity'])
            raw['retrieval_query_matches']={'query-original':dict(qual.trace)};raw['retrieval_query_ids']=['query-original'] if qual.qualified else []
            known.append(raw)
            s=_docs_source(raw,display_snippet=body);s.update(project_identity=raw['project_identity'],authority=raw['authority'],scope=raw['doc_scope'],line_start=part['line_start'],line_end=part['line_end'])
            public.append(s);snapshot[s['evidence_id']]=_snapshot_entry(raw,s)
        payload=_payload(public,query_plan={'queries':[],'broad_context_only':True})
        record(case,'gold_dto',payload,snapshot,root)
        fragments=projection._qualified_fragments
        def full_block(source,**kw):
            candidates=fragments(source,**kw)
            text=kw['raw_snippet'].strip()
            if len(text)<=3000:
                whole={**source,'snippet':text,'line_start':kw['source_line_start'],'line_end':kw['source_line_start']+kw['raw_snippet'].rstrip().count('\n')}
                whole=projection._requalify_visible_source(whole,query_text=kw['query_text'])
                if set(whole.get('retrieval_query_ids',[])) & kw['query_ids']:candidates.insert(0,whole)
            return candidates
        with patch.object(projection,'_qualified_fragments',full_block):
            payload,snapshot=projection.project_docs_context(retrieval=deepcopy(base))
        record(case,'full_block_replay',payload,snapshot,root)
        def whole_only(source,**kw):
            values=full_block(source,**kw)
            return [max(values,key=lambda x:len(x['snippet']))] if values else []
        with patch.object(projection,'_qualified_fragments',whole_only):
            payload,snapshot=projection.project_docs_context(retrieval=deepcopy(base))
        record(case,'whole_only_replay',payload,snapshot,root)
        inp=deepcopy(base);inp['context_pack']=deepcopy(known)
        with ExitStack() as stack:
            patched(stack,qualifier(case,subject=True))
            stack.enter_context(patch.object(projection,'_qualified_fragments',whole_only))
            payload,snapshot=projection.project_docs_context(retrieval=inp)
        record(case,'oracle_complete_replay',payload,snapshot,root)
        if case['id'] not in misses:continue
        rank=projection._facet_aware_candidates
        def priority(values,**kw):return sorted(rank(values,**kw),key=lambda x:not hit(case,x))
        with patch.object(projection,'_facet_aware_candidates',priority):
            payload,snapshot=projection.project_docs_context(retrieval=deepcopy(base))
        record(case,'oracle_priority',payload,snapshot,root)
        for mode in ['window','window_qualification','window_subject','window_subject_full']:
            oracle=mode!='window'
            inp=deepcopy(base);inp['context_pack']=deepcopy(known)
            with ExitStack() as stack:
                if oracle:patched(stack,qualifier(case,subject='subject' in mode))
                if mode.endswith('_full'):stack.enter_context(patch.object(projection,'_qualified_fragments',whole_only))
                payload,snapshot=projection.project_docs_context(retrieval=inp)
            row=record(case,'oracle_'+mode,payload,snapshot,root);row['window_original_traces']=[x['retrieval_query_matches'] for x in known]
    save(out/'results.json',rows)
    save(out/'inputs.json',bases)
    save(out/'summary.json',{variant:{'sufficient':sum(r['assessment']['context_sufficiency']=='sufficient' and not r['audit_errors'] for r in rows if r['variant']==variant and r['answerability']=='within_budget'),
        'cases':sum(r['variant']==variant and r['answerability']=='within_budget' for r in rows)} for variant in sorted({r['variant'] for r in rows})})

if __name__=='__main__':main()
