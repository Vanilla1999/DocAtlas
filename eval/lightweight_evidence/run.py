"""Installed stdio evaluation under a shared hard 1,500,000,000-byte cgroup.

Original source witnesses, complete tool text and observed latency are measured.
No answering model or sufficiency autorater; unknown-answer correctness is NOT
inferred from an empty gold list. Frozen V40 + disclosed known L10 + fresh pilot.
"""
from __future__ import annotations
import argparse
import asyncio
from datetime import timedelta
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import statistics
import sys
import time

FIELDS = ('path_or_url', 'line_start', 'line_end', 'snippet', 'scope',
          'version_binding', 'authority', 'instruction_trust', 'evidence_id')


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def logical_state(path):
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as db:
        return hashlib.sha256('\n'.join(db.iterdump()).encode()).hexdigest()


def cgroup():
    root = Path('/sys/fs/cgroup')
    result = {n: (root/n).read_text().strip() for n in
              ('memory.max', 'memory.swap.max', 'memory.current', 'memory.peak', 'memory.events')
              if (root/n).exists()}
    if result.get('memory.max') != '1500000000' or result.get('memory.swap.max') != '0':
        raise RuntimeError('The experiment requires a real 1.5 GB/no-swap cgroup, not a claimed budget.')
    return result


def decode(reply):
    from docmancer.docs.application.section_compression import expand_sections
    text = '\n'.join(x['text'] for x in reply['content'] if x['type'] == 'text')
    if reply.get('isError'):
        return text, None, []
    packet = expand_sections(json.loads(text))
    assert packet.get('kind') == 'docs_context'
    return text, packet, packet.get('sources', [])


def source_spans(rows, docs):
    spans = {}
    for row in rows:
        path, text = row['path_or_url'], row['snippet']
        assert path in docs and text
        a, b = row['line_start'], row['line_end']
        lines = docs[path].splitlines(keepends=True)
        assert type(a) is int and type(b) is int and 1 <= a <= b <= len(lines)
        window = ''.join(lines[a-1:b])
        assert text in window, ('modified_original', path, a, b)
        start = sum(map(len, lines[:a-1])) + window.index(text)
        spans.setdefault(path, []).append((start, start+len(text)))
        assert row['scope'] == 'project'
    return spans


def covered(part, spans, docs):
    original = docs[part['path']]
    if 'quote' in part:
        assert original.count(part['quote']) == 1
        start = original.index(part['quote'])
        end = start + len(part['quote'])
    else:
        lines = original.splitlines(keepends=True)
        start = sum(map(len, lines[:part['line_start']-1]))
        end = sum(map(len, lines[:part['line_end']]))
    while start < end and original[start].isspace():
        start += 1
    while end > start and original[end-1].isspace():
        end -= 1
    for left, right in sorted(spans.get(part['path'], [])):
        if right <= start:
            continue
        if left > start:
            return False
        start = right
        if start >= end:
            return True
    return start >= end


def signature(row):
    return json.dumps([row.get(k) for k in FIELDS], sort_keys=True, ensure_ascii=False)


def read_data(repo, suite):
    base = repo / ('eval/prepared_model_comparison40' if suite == 'v40'
                   else 'eval/lightweight_evidence/' + suite)
    if suite == 'v40':
        cases = json.loads((base/'questions.json').read_text())['cases']
        families = json.loads((base/'source_plan.json').read_text())['families']
        docs = {f['id']+'/'+p: (base/'sources'/f['id']/p).read_text()
                for f in families for p in f['paths']}
        names = ('questions.json', 'source_plan.json', 'gold_spans.json')
    else:
        cases = json.loads((base/'questions.json').read_text())
        docs = json.loads((base/'sources.json').read_text())
        names = ('questions.json', 'sources.json', 'gold.json')
    hashes = {n: sha(base/n) for n in names}
    if suite != 'v40':
        assert hashes == json.loads((base/'freeze.json').read_text())['sha256']
    return base, cases, docs, hashes


def read_gold(base, suite, cases):
    if suite != 'v40':
        return json.loads((base/'gold.json').read_text())
    groups = {c['id']: c['project_group'] for c in cases}
    result = {}
    for case in json.loads((base/'gold_spans.json').read_text())['cases']:
        facts = []
        for claim in case['required_claims']:
            if not claim['witness_sets']:
                continue
            alternatives = [[{**p, 'path': groups[case['id']]+'/'+p['path']}
                             for p in group['parts']] for group in claim['witness_sets']]
            facts.append({'id': claim['id'], 'alternatives': alternatives})
        result[case['id']] = {'facts': facts}
    return result


async def execute(args, env, root, docs, cases, arm, out, pool=None, endpoint=None,
                  compression_off=False, trace=True):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from docmancer.docs.application.projection_tokenizer import projection_token_count
    settings = dict(env)
    for name in ('DOCATLAS_CONTEXT_COMPRESSION', 'DOCATLAS_SECTION_SELECTION',
                 'DOCATLAS_SECTION_TOP_K', 'DOCATLAS_MCP_MODEL_VIEW'):
        settings.pop(name, None)
    settings.update(DOCATLAS_MINILM_MODEL_DIR='/model', DOCATLAS_MCP_TEXT_FALLBACK='1',
                    DOCATLAS_SECTION_WIRE_FORMAT='adaptive-v2',
                    DOCATLAS_LIGHT_SELECTION=arm if arm in {'minilm-window','qwen-rerank','qwen-select'} else 'off',
                    DOCATLAS_LIGHT_URL=endpoint or 'http://127.0.0.1:8099',
                    DOCATLAS_LIGHT_TRACE='1' if trace else '0')
    if arm == 'pool' or compression_off:
        settings['DOCATLAS_CONTEXT_COMPRESSION'] = 'off'
    if arm == 'fixed-five':
        settings.update(DOCATLAS_SECTION_SELECTION='fixed', DOCATLAS_SECTION_TOP_K='5')
    cli = str(Path(sys.executable).with_name('doc-atlas'))
    out.mkdir(parents=True, exist_ok=True)
    records = []
    log = out/'stderr.jsonl'
    with log.open('w') as err:
        params = StdioServerParameters(command=cli, args=['mcp','docs-serve'], env=settings)
        async with stdio_client(params, errlog=err) as (rd, wr):
            async with ClientSession(rd, wr, read_timeout_seconds=timedelta(seconds=180)) as client:
                await client.initialize()
                for case in cases:
                    start = time.monotonic()
                    response = await client.call_tool('get_docs_context',
                        {'question':case['question'],'project_path':str(root),'scope':'project'})
                    seconds = time.monotonic()-start
                    raw = response.model_dump(by_alias=True)
                    save(out/(case['id']+'.json'), raw)
                    text, packet, rows = decode(raw)
                    source_spans(rows, docs)
                    if pool is not None and not raw.get('isError'):
                        assert {signature(r) for r in rows}.issubset(pool[case['id']]), 'new/unbound source'
                    records.append({'id':case['id'],'question':case['question'],'tool_error':bool(response.isError),
                        'seconds':seconds,'text_tokens_o200k':projection_token_count(text.encode()),
                        'source_rows':len(rows),'source_signatures':[signature(r) for r in rows]})
                    print(json.dumps({'arm':arm,'case':case['id'],'seconds':round(seconds,3),
                                      'error':bool(response.isError)}, ensure_ascii=False), flush=True)
    receipts = []
    for line in log.read_text().splitlines():
        try:
            obj = json.loads(line)
            if obj.get('event') == 'docatlas_light_selection':
                receipts.append(obj['receipt'])
        except (ValueError, AttributeError):
            pass
    by_query = {r['question_sha256']:r for r in receipts}
    for record in records:
        record['selection_receipt'] = by_query.get(hashlib.sha256(record['question'].encode()).hexdigest())
    save(out/'measurements.json', records)
    return records


def score(base, suite, docs, cases, hashes, records, out):
    assert hashes == {n:sha(base/n) for n in hashes}
    gold = read_gold(base, suite, cases)  # Expected witnesses parsed only after delivery.
    for record in records:
        _, _, rows = decode(json.loads((out/(record['id']+'.json')).read_text()))
        spans = source_spans(rows, docs)
        record['requirements'] = [{'id':f['id'],'covered':any(all(covered(p,spans,docs) for p in alt)
                                  for alt in f['alternatives'])} for f in gold[record['id']]['facts']]
        record['complete_documented'] = (all(f['covered'] for f in record['requirements'])
                                        if record['requirements'] else None)
        record['answer_correctness'] = 'NOT_TESTED'
        record.pop('source_signatures', None)
    successful = [r['seconds'] for r in records if not r['tool_error']]
    return {'cases':records,'requirements':sum(len(r['requirements']) for r in records),
            'covered':sum(sum(f['covered'] for f in r['requirements']) for r in records),
            'documented_cases':sum(bool(r['requirements']) for r in records),
            'complete_cases':sum(r['complete_documented'] is True for r in records),
            'tokens_all_replies_including_errors':sum(r['text_tokens_o200k'] for r in records),
            'tool_errors':sum(r['tool_error'] for r in records),
            'applied':sum(bool((r.get('selection_receipt') or {}).get('applied')) for r in records),
            'median_success_seconds':statistics.median(successful) if successful else None,
            'latency_interpretation':'one ordered CPU run, not a production benchmark'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--group',choices=['baseline','qwen-rerank','qwen-select'],required=True)
    args=parser.parse_args()
    args.repo=args.repo.resolve(); args.out.mkdir(parents=True,exist_ok=True)
    import docmancer
    installed=Path(docmancer.__file__).resolve().parent
    assert not installed.is_relative_to(args.repo), 'must run installed wheel'
    files=['docs/application/section_compression.py','docs/application/lightweight_selection.py']
    product={f:sha(installed/f) for f in files}
    assert product=={f:sha(args.repo/'docmancer'/f) for f in files}
    save(args.out/'CHECKPOINT.json',{'head':os.environ.get('TESTED_SHA'),'product':product,
                                  'cgroup':cgroup(),'group':args.group})
    runtime=load('lightweight_fixture',args.repo/'eval/evidence_quality_v2/runtime.py')
    arms=['main','fixed-five','minilm-window'] if args.group=='baseline' else [args.group]
    results=[]; calls=0
    for suite in ['l10','fresh','v40']:
        base,cases,docs,hashes=read_data(args.repo,suite)
        output=args.out/suite;output.mkdir()
        root=output/'project'; runtime.write_project(root,docs)
        before={p:sha(root/p) for p in docs}
        with runtime.isolated_service(output/'state') as (service,config):
            inventory=runtime.index_project(service,config,root)
            assert not inventory['excluded_or_failed_paths'] and not inventory['unexpected_paths']
            save(output/'preparation.json',inventory)
            state=logical_state(inventory['storage_path'])
            initial=asyncio.run(execute(args,dict(os.environ),root,docs,cases,'pool',output/'pool'))
            calls+=len(cases)
            assert not any(r['tool_error'] for r in initial), 'pool acquisition failed'
            pool={r['id']:set(r['source_signatures']) for r in initial}
            measured={}
            for arm in arms:
                measured[arm]=asyncio.run(execute(args,dict(os.environ),root,docs,cases,arm,output/arm,pool))
                calls+=len(cases)
            if suite=='l10' and args.group!='baseline':
                # Public integration controls, no private-helper/unit assertions.
                control=asyncio.run(execute(args,dict(os.environ),root,docs,cases[:1],'main',output/'fallback-control',pool))
                fallback=asyncio.run(execute(args,dict(os.environ),root,docs,cases[:1],args.group,output/'unavailable',pool,endpoint='http://127.0.0.1:1'))
                disabled=asyncio.run(execute(args,dict(os.environ),root,docs,cases[:1],args.group,output/'disabled',pool,compression_off=True))
                calls+=3
                assert fallback[0]['source_signatures']==control[0]['source_signatures']
                assert not fallback[0]['selection_receipt']['applied']
                assert set(disabled[0]['source_signatures'])==pool[cases[0]['id']]
                assert disabled[0]['selection_receipt'] is None
                save(output/'FALLBACK.json',{'unavailable_preserves_main':True,'explicit_off_preserved':True})
            assert state==logical_state(inventory['storage_path'])
            assert before=={p:sha(root/p) for p in docs}
        scores={'pool':score(base,suite,docs,cases,hashes,initial,output/'pool')}
        scores.update({a:score(base,suite,docs,cases,hashes,r,output/a) for a,r in measured.items()})
        results.append({'suite':suite,'input_hashes':hashes,'documents':len(docs),'questions':len(cases),
                        'arms':scores,'sources_and_sqlite_unchanged':True})
        save(output/'SUMMARY.json',results[-1])
        save(args.out/'PROGRESS.json',results)
    save(args.out/'SUMMARY.json',{'head':os.environ.get('TESTED_SHA'),'group':args.group,'corpora':results,
        'public_mcp_calls':calls,'cgroup':cgroup(),'paid_provider_calls':0,'provider_usage':None,
        'paid_answers':'NOT_TESTED','unknown_answers':'NOT_TESTED',
        'boundary':'installed public stdio MCP; not actual OpenCode/provider; coverage is not answer grading'})


if __name__=='__main__':
    main()
