"""Paired installed-MCP extension of the existing adaptive selection study.

Frozen V40, former New16, and N01--N08 are REGRESSION sets, not new holdouts.
No product mocks and no LLM calls. Gold is parsed only after public delivery.
First retrieval only: this is not a full-dialogue or provider-cost measurement.
"""
from __future__ import annotations
import argparse
import asyncio
from collections import Counter
from datetime import timedelta
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import statistics
import sys
import time

POLICIES = ("fixed", "adaptive-gap-b1-v1", "facet-max-v1", "facet-envelope-v1", "facet-guarded-v1", "facet-margin-envelope-v1")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def inputs(args):
    if args.suite != "fresh":
        helper = load("existing_adaptive_inputs", args.repo / "eval/adaptive_gap_integration.py")
        return helper.inputs(args)
    root = args.repo / "eval/fresh_dialogues/fixtures"
    cases = json.loads((root / "cases.json").read_text())["cases"]
    categories = {"N07": "partial", "N08": "unanswerable"}
    cases = [{**c, "project_group": "nacrerelay", "answerability": categories.get(c["id"], "within_budget")}
             for c in cases]
    docs = {p.relative_to(root / "project").as_posix(): p.read_text(encoding="utf-8")
            for p in (root / "project").rglob("*.md") if p.is_file()}
    return cases, {"nacrerelay": docs}


def request(case, root):
    result = {"question": case["question"], "project_path": str(root), "scope": "project"}
    for name in ("search_question", "lookup_queries"):
        if name in case:
            result[name] = case[name]
    return result


def worker(args):
    import yaml
    from docmancer.mcp._docs_server_part01 import _run_async, call_docs_tool_payload
    from docmancer.docs.application.section_compression import observe_section_compression
    runtime = load("facet_fixture", args.repo / "eval/evidence_quality_v2/runtime.py")
    helper = load("facet_state", args.repo / "eval/prepared_model_comparison40/run.py")
    cases, families = inputs(args)
    root, out = args.work / args.family / "project", args.out / args.family
    runtime.write_project(root, families[args.family])
    if args.suite == "fresh":
        # Match the frozen runner: project marker is not a documentation entry.
        marker = args.repo / "eval/fresh_dialogues/fixtures/project/pyproject.toml"
        (root / "pyproject.toml").write_bytes(marker.read_bytes())
    catalog_path = root / "docatlas.project-docs.yaml"
    catalog = yaml.safe_load(catalog_path.read_text())
    catalog["documentation_languages"] = {p: ["en"] for p in families[args.family] if p.endswith('.md')}
    catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    with runtime.isolated_service(args.work / args.family / "state") as (service, config):
        inventory = runtime.index_project(service, config, root)
        before = helper.logical_state(inventory), helper.source_state(root)
        os.environ.update(DOCATLAS_CONTEXT_COMPRESSION="off", DOCATLAS_CONTEXT_ABSTENTION="off")
        for case in (c for c in cases if c["project_group"] == args.family):
            original = call_docs_tool_payload("get_docs_context", request(case, root), service)
            assert original.get("kind") == "docs_context" and original.get("sources"), original
            save(out / (case["id"] + "-baseline.json"), original)
        os.environ.update(DOCATLAS_CONTEXT_COMPRESSION="minilm-sections-v1",
            DOCATLAS_MINILM_MODEL_DIR=str(args.model), DOCATLAS_MCP_TEXT_FALLBACK="1",
            DOCATLAS_MCP_MODEL_VIEW="1", DOCATLAS_SECTION_TOP_K="5",
            DOCATLAS_SECTION_UNITS="markdown-owner-v1" if args.policy.startswith("facet-") else "legacy",
            DOCATLAS_SECTION_WIRE_FORMAT="v1", DOCATLAS_SECTION_SELECTION=args.policy,
            HF_HUB_OFFLINE="1")
        with observe_section_compression() as observations:
            try:
                asyncio.run(_run_async(service))
            finally:
                peak = Path('/sys/fs/cgroup/memory.peak')
                save(out / 'server.json', {'observations': observations,
                    'database_unchanged': before[0] == helper.logical_state(inventory),
                    'files_unchanged': before[1] == helper.source_state(root),
                    'rss_peak_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                    'container_peak_bytes': int(peak.read_text()) if peak.exists() else None})


async def client(args):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from docmancer.docs.application.section_compression import expand_sections
    from docmancer.docs.application.model_context_view import resolve_model_reference
    from docmancer.docs.interfaces.host_context import extract_tool_payload
    import tiktoken
    encoder = tiktoken.get_encoding('o200k_base')
    cases, families = inputs(args)
    records, prompts = [], []
    for family in families:
        folder = args.out / family
        folder.mkdir(parents=True)
        root = args.work / family / 'project'
        params = StdioServerParameters(command=sys.executable, args=[
            '-I', str(Path(__file__).resolve()), '--worker', '--family', family,
            '--suite', args.suite, '--policy', args.policy, '--repo', str(args.repo),
            '--work', str(args.work), '--out', str(args.out), '--model', str(args.model)], env=dict(os.environ))
        with (folder / 'stderr.log').open('w') as err:
          async with stdio_client(params, errlog=err) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=180)) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert {t.name for t in tools.tools} == {'docs_status', 'get_docs_context', 'prepare_docs'}
                status = await session.call_tool('docs_status', {'action':'project', 'project_path':str(root), 'include_language':True})
                assert not status.isError
                save(folder / 'language.json', status.model_dump(by_alias=True))
                for case in (c for c in cases if c['project_group'] == family):
                    req = request(case, root)
                    started = time.monotonic()
                    response = await session.call_tool('get_docs_context', req)
                    elapsed = time.monotonic() - started
                    raw = response.model_dump(by_alias=True)
                    save(folder / (case['id'] + '-response.json'), raw)
                    assert not response.isError, raw
                    assert len(response.content) == 1 and response.content[0].type == 'text'
                    text = response.content[0].text
                    display = json.loads(text)
                    packet = extract_tool_payload(response)
                    expanded = expand_sections(packet)
                    assert display['context_format'] == 'docatlas.model-context.v1'
                    assert expanded.get('answer_supported') is False
                    baseline = json.loads((folder / (case['id'] + '-baseline.json')).read_text())
                    admitted = {r['evidence_id']:r for r in baseline['sources']}
                    assert all(r == admitted[r['evidence_id']] for r in expanded['sources'])
                    for item, row in zip(display['sources'], expanded['sources'], strict=True):
                        assert item['text'] == row['snippet']
                        assert resolve_model_reference(display, raw['_meta'], item['ref']) == row
                    save(folder / (case['id'] + '-expanded.json'), expanded)
                    (folder / (case['id'] + '-wire.json')).write_text(text, encoding='utf-8')
                    machine = json.dumps(packet, ensure_ascii=False, separators=(',', ':'))
                    records.append({'case_id':case['id'], 'family':family,
                        'answerability':case['answerability'], 'question':case['question'],
                        'search_question':req.get('search_question'), 'tokens':len(encoder.encode(text)),
                        'machine_tokens':len(encoder.encode(machine)), 'rows':len(expanded['sources']),
                        'seconds':elapsed, 'source_rows_exact':True})
                    prompts.append({'case_id':case['id'], 'question':case['question'], 'context':text,
                        'instruction':'Answer only from the supplied evidence, in the question language. Cite exact source refs. Preserve conditions and exceptions. State unsupported parts explicitly.'})
                    print(json.dumps({'case_id':case['id'], 'tokens':records[-1]['tokens'], 'seconds':round(elapsed,3)}), flush=True)
        server = json.loads((folder / 'server.json').read_text())
        assert server['database_unchanged'] and server['files_unchanged']
        relevant = [r for r in records if r['family'] == family]
        assert len(server['observations']) == len(relevant)
        for record, obs in zip(relevant, server['observations'], strict=True):
            assert obs['selection_policy'] == args.policy
            assert obs['scoring_question_sha256'] == sha((record['search_question'] or record['question']).encode())
            record.update(selected_groups=obs['selected_sections'], forward_passes=obs['forward_passes'],
                input_pair_tokens=obs['input_pair_tokens'], cutoff=obs.get('adaptive_cutoff'),
                probe_count=obs.get('facet_selection',{}).get('probe_count',1))
    save(args.out / 'DELIVERY.json', {'records':records, 'search_calls':len(records),
        'baseline_calls':len(records), 'preparations':len(families), 'answer_model_calls':0})
    (args.out / 'PROMPTS.jsonl').write_text(''.join(json.dumps(p,ensure_ascii=False)+'\n' for p in prompts),encoding='utf-8')
    return records


def assess(args, records):
    cases, families = inputs(args)
    corpus = args.repo / 'eval/prepared_model_comparison40'
    oracle = load('facet_independent_oracle', corpus / 'evaluate.py')
    gold_path = (corpus / 'gold_spans.json' if args.suite == 'v40' else
                 args.repo / ('eval/adaptive_gap_holdout/gold.json' if args.suite == 'holdout' else 'eval/fresh_dialogues/oracle/gold.json'))
    gold = {g['id']:g for g in json.loads(gold_path.read_text())['cases']}
    results = []
    for record in records:
        case = next(c for c in cases if c['id'] == record['case_id'])
        root = args.work / record['family'] / 'project'
        prepared = {'root':str(root), 'sources':{}}
        for path,text in families[record['family']].items():
            offsets = [0]
            for line in text.splitlines(keepends=True): offsets.append(offsets[-1]+len(line))
            prepared['sources'][path] = {'raw':text.encode(), 'content':text,
                'sha256':sha(text.encode()), 'line_offsets':offsets, 'errors':[]}
        payload = json.loads((args.out / record['family'] / (case['id']+'-expanded.json')).read_text())
        _, intervals, errors = oracle._source_rows(payload, prepared)
        if args.suite == 'v40':
            coverage = oracle._gold(case, gold[case['id']], prepared, intervals)
        else:
            item = gold[case['id']]
            facts = (item.get('required_facts',[]) if args.suite == 'fresh' else
                     [{'id':str(n), 'witnesses':[{'path':item['path'],'text':q}]} for n,q in enumerate(item['witnesses'])])
            checked = []
            for fact in facts:
                covered = True
                for w in fact['witnesses']:
                    original = prepared['sources'][w['path']]['content']
                    assert original.count(w['text']) == 1
                    start = original.index(w['text'])
                    if 'line_start' in w:
                        lines = original.splitlines()
                        assert w['text'] in '\n'.join(lines[w['line_start']-1:w['line_end']])
                    covered &= not oracle._uncovered(start,start+len(w['text']),intervals.get(w['path'],[]))
                checked.append({'id':fact['id'],'covered':bool(covered)})
            coverage = {'all_documented_claims_covered':all(f['covered'] for f in checked),
                        'facts':checked,'errors':[]}
        valid = not errors and not coverage.get('errors')
        passed = valid and (not payload['sources'] if case['answerability']=='unanswerable' else coverage['all_documented_claims_covered'])
        results.append({**record,'integrity':valid,'passed':bool(passed),'coverage':coverage,'errors':errors})
    summary = {'head':os.environ.get('TESTED_SHA'), 'suite':args.suite, 'policy':args.policy,
        'cases':len(results), 'counts':{kind:{'total':sum(r['answerability']==kind for r in results),
            'pass':sum(r['passed'] for r in results if r['answerability']==kind)}
            for kind in ('within_budget','partial','unanswerable')},
        'documented_pass':sum(r['passed'] for r in results if r['answerability']!='unanswerable'),
        'documented_total':sum(r['answerability']!='unanswerable' for r in results),
        'failed_documented_ids':[r['case_id'] for r in results if not r['passed'] and r['answerability']!='unanswerable'],
        'integrity_pass':sum(r['integrity'] for r in results), 'tokens_sum':sum(r['tokens'] for r in results),
        'tokens_mean':statistics.mean(r['tokens'] for r in results),
        'seconds_median':statistics.median(r['seconds'] for r in results),
        'k_histogram':dict(Counter(r['selected_groups'] for r in results)),
        'forward_passes':sum(r['forward_passes'] for r in results),
        'budget_limited':[r['case_id'] for r in results if (r.get('cutoff') or {}).get('budget_limited')],
        'first_retrieval_only':True, 'answer_model_calls':0, 'provider_usage':None,
        'completeness_judge':False, 'default_rollout':False}
    save(args.out / 'ASSESSMENTS.json',results)
    save(args.out / 'SUMMARY.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
    assert all(r['integrity'] for r in results), 'source integrity regression'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('repo','work','out','model'): p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--suite',choices=('v40','holdout','fresh'),required=True)
    p.add_argument('--policy',choices=POLICIES,required=True)
    p.add_argument('--worker',action='store_true'); p.add_argument('--family')
    args=p.parse_args()
    for key in ('repo','work','out','model'): setattr(args,key,getattr(args,key).resolve())
    if args.worker:
        worker(args); return
    import docmancer
    product=Path(docmancer.__file__).resolve().parent
    assert not product.is_relative_to(args.repo), 'installed wheel required'
    assert all(f.read_bytes()==(args.repo/'docmancer'/f.relative_to(product)).read_bytes() for f in product.rglob('*.py'))
    assert not args.work.exists() and not args.out.exists()
    args.work.mkdir(parents=True,mode=0o700); args.out.mkdir(parents=True)
    frozen={str(f.relative_to(args.repo)):sha(f.read_bytes())
        for directory in ('eval/prepared_model_comparison40','eval/adaptive_gap_holdout','eval/fresh_dialogues')
        for f in (args.repo/directory).rglob('*') if f.is_file() and '__pycache__' not in f.parts}
    save(args.out/'FREEZE.json',{'head':os.environ.get('TESTED_SHA'),'inputs':frozen,'policy':args.policy})
    records=asyncio.run(client(args))
    assess(args,records)
    assert all(sha((args.repo/f).read_bytes())==h for f,h in frozen.items())


if __name__=='__main__': main()
