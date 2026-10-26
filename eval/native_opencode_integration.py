"""Installed CLI/MCP and actual pinned OpenCode adapter; no answering model.

The SAME fifteen frozen documents are one catalog project, not five isolated
projects. First ten questions are unchanged. Gold is opened only after delivery.
Three arms isolate old JSON, readable paging, and lexical-first readable paging.
No source/SQLite/retrieval/selection mocks, private model endpoints or paid calls.
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
import re
import shutil
import subprocess
import sys


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def visible_sources(text):
    """Independent reader of delivered text, not the production decoder/meta."""
    pattern = re.compile(r'^SOURCE \[([^\]]+)\] ("(?:[^"\\]|\\.)*")(?: L(\d+)-L(\d+))? chars=(\d+):(\d+)/(\d+)\nAttributes: ([^\n]*)\nTEXT\n', re.M)
    result, offset = [], 0
    while match := pattern.search(text, offset):
        ref, path, first, last, a, b, full, attributes = match.groups()
        a, b, full = int(a), int(b), int(full)
        assert 0 <= a < b <= full
        body = text[match.end():match.end()+b-a]
        assert len(body) == b-a and text[match.end()+b-a:].startswith("\nEND SOURCE\n")
        result.append(dict(ref=ref, path=json.loads(path), start=int(first) if first else None,
                           end=int(last) if last else None, a=a, b=b, full=full, text=body,
                           attributes=json.loads(attributes)))
        offset = match.end() + len(body) + len("\nEND SOURCE\n")
    return result


def witness_report(cases, docs, texts, gold):
    records = []
    for case in cases:
        rows = visible_sources(texts[case['id']])
        intervals = {}
        for row in rows:
            assert row['path'] in docs
            original = docs[row['path']]
            # Every body slice must be verbatim in the unchanged source.
            assert row['text'] in original
            assert row['start'] and row['end'] >= row['start']
            window = ''.join(original.splitlines(keepends=True)[row['start']-1:row['end']])
            assert row['text'] in window, (case['id'], row['path'], row['start'], row['end'])
            offset = sum(len(line) for line in original.splitlines(keepends=True)[:row['start']-1]) + window.index(row['text'])
            intervals.setdefault(row['path'],[]).append((offset,offset+len(row['text'])))

        def covered_part(part):
            path = case['project_group']+'/'+part['path']
            original = docs[path]
            lines = original.splitlines(keepends=True)
            a = sum(map(len,lines[:part['line_start']-1]))
            b = sum(map(len,lines[:part['line_end']]))
            while a < b and original[a].isspace(): a += 1
            while b > a and original[b-1].isspace(): b -= 1
            cursor = a
            for start,end in sorted(intervals.get(path,[])):
                if end <= cursor: continue
                if start > cursor: break
                cursor = end
                if cursor >= b: return True
            return cursor >= b
        facts = []
        for claim in gold[case['id']]['required_claims']:
            alternatives = claim['witness_sets']
            if not alternatives:
                continue
            covered = any(all(covered_part(part) for part in group['parts']) for group in alternatives)
            facts.append({'id':claim['id'], 'covered':covered})
        records.append({'id':case['id'], 'facts':facts, 'all_documented':all(f['covered'] for f in facts) if facts else None,
                        'absence_or_answer_quality_tested':False,
                        'source_rows':len(rows), 'source_documents':len({r['path'] for r in rows})})
    return records


async def execute(args, cli, env, cases, root, arm):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from docmancer.docs.application.projection_tokenizer import projection_token_count
    settings = dict(env)
    settings['DOCATLAS_MCP_PRESENTATION'] = 'legacy' if arm == 'legacy' else 'opencode-v1'
    if arm == 'delivery-only':
        settings.pop('DOCATLAS_NATIVE_SELECTION', None)  # exercise actual installed default
    else:
        settings['DOCATLAS_NATIVE_SELECTION'] = 'lexical-v1'
    settings['DOCATLAS_CONTEXT_COMPRESSION'] = 'off'
    settings['DOCATLAS_MCP_TEXT_FALLBACK'] = '1'
    settings['DOCATLAS_NATIVE_TRACE'] = '1'
    for key in ('DOCATLAS_MINILM_MODEL_DIR', 'DOCATLAS_MCP_MODEL_VIEW'):
        settings.pop(key, None)
    calls, records, texts = 0, [], {}
    params = StdioServerParameters(command=cli, args=['mcp','docs-serve'], env=settings)
    with (args.out/(arm+'-stderr.log')).open('w') as err:
      async with stdio_client(params, errlog=err) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=180)) as client:
            await client.initialize()
            tools = await client.list_tools()
            schema = next(t.inputSchema for t in tools.tools if t.name == 'get_docs_context')
            assert ('continuation' in schema['properties']) == (arm != 'legacy')
            for case in cases:
                request = {'question':case['question'], 'project_path':str(root), 'scope':'project'}
                response = await client.call_tool('get_docs_context', request); calls += 1
                raw = response.model_dump(by_alias=True)
                save(args.out/arm/(case['id']+'.json'),raw)
                assert not response.isError, raw
                text = '\n'.join(x.text for x in response.content if x.type == 'text')
                texts[case['id']] = text
                meta = (raw.get('_meta') or {}).get('docatlas/native-delivery',{})
                records.append({'id':case['id'], 'bytes':len(text.encode()), 'lines':len(text.splitlines()),
                                'text_tokens':projection_token_count(text.encode()), 'diagnostic':meta})
                if arm != 'legacy':
                    assert len(text.encode()) <= 24_000 and len(text.splitlines()) <= 900
                    assert projection_token_count(text.encode()) <= 3_000
                    assert meta['minilm_applied'] is False
                    assert meta['policy'] == ('preserve' if arm == 'delivery-only' else 'lexical-v1')
                    assert 'not certified' in text.lower()
            if arm == 'delivery-only':
                # Consume ONE real query's explicit pages and prove all original
                # source bytes remain reachable; no silently dropped fragments.
                case = cases[0]; request = {'question':case['question'], 'project_path':str(root), 'scope':'project'}
                first = json.loads((args.out/arm/(case['id']+'.json')).read_text())
                cursor = first['_meta']['docatlas/native-delivery']['continuation']
                original_cursor = cursor
                all_slices = visible_sources(texts[case['id']]); pages = 1
                while cursor:
                    response = await client.call_tool('get_docs_context', dict(request,continuation=cursor)); calls += 1
                    assert not response.isError, response
                    raw = response.model_dump(by_alias=True)
                    text = '\n'.join(c.text for c in response.content if c.type == 'text')
                    all_slices += visible_sources(text)
                    pages += 1
                    assert pages <= 64
                    cursor = raw['_meta']['docatlas/native-delivery']['continuation']
                    save(args.out/'pages'/f'{pages}.json',raw)
                legacy = json.loads((args.out/'legacy'/(case['id']+'.json')).read_text())
                source_packet = json.loads(legacy['content'][0]['text'])
                groups = {}
                for row in all_slices:
                    number = int(row['ref'].split(':s')[1].split(':')[0])-1
                    groups.setdefault(number,[]).append(row)
                assert len(groups) == len(source_packet['sources'])
                for number, parts in groups.items():
                    parts.sort(key=lambda x:x['a']); offset=0
                    for part in parts:
                        assert part['a']==offset
                        offset=part['b']
                    assert ''.join(p['text'] for p in parts)==source_packet['sources'][number]['snippet']
                # Forgery and changed scope fail before retrieving under the new
                # arguments. Old cursor never authorizes other roots/scopes.
                for override in ({'continuation':original_cursor+'0'},
                                 {'continuation':original_cursor,'question':'different question'},
                                 {'continuation':original_cursor,'scope':'all'}):
                    denied=await client.call_tool('get_docs_context',{**request,**override});calls+=1
                    assert denied.isError
                altered = root/source_packet['sources'][0]['path_or_url']
                before = altered.read_bytes()
                try:
                    altered.write_bytes(before+b'\nchanged after issuing continuation\n')
                    denied=await client.call_tool('get_docs_context',dict(request,continuation=original_cursor));calls+=1
                    assert denied.isError, 'stale continuation served changed source'
                finally:
                    altered.write_bytes(before)
                save(args.out/'pagination.json',{'pages':pages,'rows':len(groups),'all_original_bytes_preserved':True,
                    'forged_cursor_rejected':True,'changed_question_rejected':True,'changed_scope_rejected':True,
                    'changed_source_rejected':True})
    save(args.out/(arm+'-metrics.json'),records)
    return texts,calls


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('repo','work','out','opencode'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    for name in ('repo','work','out','opencode'):setattr(args,name,getattr(args,name).resolve())
    args.out.mkdir(parents=True);args.work.mkdir(parents=True)
    import docmancer
    assert not Path(docmancer.__file__).resolve().is_relative_to(args.repo), 'installed wheel required'
    cli=str(Path(sys.executable).with_name('doc-atlas'));assert Path(cli).is_file()
    corpus=args.repo/'eval/prepared_model_comparison40'
    cases=json.loads((corpus/'questions.json').read_text())['cases'][:10]
    families=json.loads((corpus/'source_plan.json').read_text())['families']
    docs={f['id']+'/'+p:(corpus/'sources'/f['id']/p).read_text() for f in families for p in f['paths']}
    assert len(docs)==15
    root=args.work/'project'
    runtime=load('native_fixture',args.repo/'eval/evidence_quality_v2/runtime.py')
    helper=load('native_state',corpus/'run.py')
    runtime.write_project(root,docs)
    with runtime.isolated_service(args.work/'state') as (service,config):
        # Normal install command, not a manually assumed optimized environment.
        install=subprocess.run([cli,'install','opencode','--project'],cwd=root,text=True,capture_output=True)
        assert install.returncode==0,install.stderr
        registration=json.loads((root/'opencode.json').read_text())['mcp']['servers']['docatlas']
        assert registration['environment']['DOCATLAS_MCP_PRESENTATION']=='opencode-v1'
        save(args.out/'registration.json',registration)
        inventory=runtime.index_project(service,config,root)
        source_state=helper.source_state(root);db_state=helper.logical_state(inventory)
        save(args.out/'preparation.json',inventory)
        replies,calls={},0
        for arm in ('legacy','delivery-only','ranked'):
            replies[arm],n=asyncio.run(execute(args,cli,dict(os.environ),cases,root,arm));calls+=n
        # Actual OpenCode v2.1.2 native MCP adapter + ToolOutput. No model API.
        config_path=args.out/'opencode-protocol.json'
        save(config_path,{'cli':cli,'root':str(root),'out':str(args.out),'cases':cases,'registration':registration})
        target=args.opencode/'packages/core/test/docatlas-native-integration.ts'
        shutil.copyfile(args.repo/'eval/native_opencode_client.ts',target)
        upstream_env={**os.environ,'DOCATLAS_PROTOCOL':str(config_path)}
        run=subprocess.run(['bun','run',str(target)],cwd=args.opencode,env=upstream_env,
                           text=True,capture_output=True,timeout=600)
        (args.out/'opencode-stdout.log').write_text(run.stdout)
        (args.out/'opencode-stderr.log').write_text(run.stderr)
        assert run.returncode==0,run.stderr[-5000:]
        assert helper.source_state(root)==source_state
        assert helper.logical_state(inventory)==db_state
    gold={x['id']:x for x in json.loads((corpus/'gold_spans.json').read_text())['cases']}
    normalized=json.loads((args.out/'OPENCODE.json').read_text())['results']
    actual={arm:{row['id']:row['model_visible_text'] for row in normalized if row['arm']==arm}
            for arm in ('delivery-only','ranked')}
    result={'head':os.environ.get('TESTED_SHA'),'provider_usage':None,'answer_model_calls':0,
            'model_answer_quality_tested':False,'python_stdio_calls':calls,'one_catalog_documents':15,
            'arms':{arm:witness_report(cases,docs,replies[arm],gold) for arm in ('delivery-only','ranked')},
            'opencode_arms':{arm:witness_report(cases,docs,actual[arm],gold) for arm in ('delivery-only','ranked')}}
    save(args.out/'SUMMARY.json',result)
    print(json.dumps(result,indent=2))
    assert all(r['all_documented'] for boundary in ('arms','opencode_arms')
               for arm in ('delivery-only','ranked') for r in result[boundary][arm] if r['facts']), 'first page missing documented evidence'


if __name__=='__main__':main()
