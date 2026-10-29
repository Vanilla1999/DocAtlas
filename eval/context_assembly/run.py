"""Installed MCP evaluation: 20 frozen new questions, five presentation policies.

Real MiniLM/retrieval/SQLite/stdio; no model-written sources or mocked evidence.
The controlled same-response comparison separates ephemeral ref token noise.
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
import statistics
import sys
import time

POLICIES = ('literal', 'grouped', 'table', 'grouped-table', 'adaptive')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def dataset(repo):
    return json.loads((repo / 'eval/context_assembly/questions20.json').read_text())


def sources(repo, family):
    base = repo / 'eval/prepared_model_comparison40/sources' / family
    return {p.relative_to(base).as_posix(): p.read_text(encoding='utf-8') for p in base.rglob('*.md')}


def worker(a):
    runtime = load('assembly_fixture_runtime', a.repo / 'eval/evidence_quality_v2/runtime.py')
    state = load('assembly_fixture_state', a.repo / 'eval/prepared_model_comparison40/run.py')
    from docmancer.mcp._docs_server_part01 import _run_async
    from docmancer.docs.application.section_compression import observe_section_compression
    folder = a.out / a.policy / a.family
    root = a.work / a.policy / a.family / 'project'
    runtime.write_project(root, sources(a.repo, a.family))
    with runtime.isolated_service(root.parent / 'state') as (service, config):
        inventory = runtime.index_project(service, config, root)
        save(folder / 'preparation.json', inventory)
        before = state.logical_state(inventory), state.source_state(root)
        os.environ.update(DOCATLAS_MINILM_MODEL_DIR='/model', DOCATLAS_MCP_TEXT_FALLBACK='1',
                          DOCATLAS_MCP_COMPACT_TEXT='1', DOCATLAS_MCP_MODEL_VIEW='off',
                          DOCATLAS_CONTEXT_ASSEMBLY=a.policy)
        # Main's selector and full-packet wire/budgets are intentionally untouched.
        with observe_section_compression() as observed:
            try:
                asyncio.run(_run_async(service))
            finally:
                save(folder / 'server.json', {'observations': observed,
                     'database_unchanged': before[0] == state.logical_state(inventory),
                     'files_unchanged': before[1] == state.source_state(root)})


def literal(view):
    # Independent oracle: do not use production decode_context for grading.
    import copy
    fmt = view.get('context_format', '')
    if not str(fmt).startswith('docatlas.assembled-'):
        return view
    kind = fmt[len('docatlas.assembled-'):-len('.v1')]
    assert kind in {'grouped', 'table', 'grouped-table'}
    value = copy.deepcopy(view)
    rows = value['sources']
    if kind in {'table', 'grouped-table'}:
        columns = value.pop('source_columns')
        assert len(set(columns)) == len(columns)
        assert all(isinstance(r, list) and len(r) == len(columns) for r in rows)
        rows = [dict(zip(columns, r, strict=True)) for r in rows]
    if kind in {'grouped', 'grouped-table'}:
        groups = value.pop('source_groups')
        decoded = []
        for row in rows:
            idx = row.pop('group')
            assert type(idx) is int and 0 <= idx < len(groups)
            assert not set(groups[idx]).intersection(row)
            decoded.append(dict(groups[idx], **row))
        rows = decoded
    prefix = (' Source objects inherit' if kind == 'grouped' else ' Each source array follows')
    notice, separator, legend = value['notice'].rpartition(prefix)
    assert separator and notice and legend
    value.update(sources=rows, notice=notice, context_format='docatlas.standalone-text.v1')
    return value


def source_rows(view):
    if view.get('context_format') == 'docatlas.standalone-text.v1':
        return [{**(view.get('source_context') or {}), **s} for s in view.get('sources', [])]
    # Explicit full-text fallback has a different machine schema.
    from docmancer.docs.application.section_compression import expand_sections
    p = expand_sections(view)
    return [{'path': s['path_or_url'], 'text': s['snippet'], 'ref': s['evidence_id'],
             **{k: v for k, v in s.items() if k not in {'path_or_url','snippet','evidence_id'}}}
            for s in p.get('sources', [])]


def verify_sources(view, docs):
    spans = {}
    for s in source_rows(view):
        p, text = s['path'], s['text']
        assert p in docs and isinstance(text, str) and text
        lines = docs[p].splitlines(keepends=True)
        a, b = s['line_start'], s['line_end']
        assert type(a) is int and type(b) is int and 1 <= a <= b <= len(lines)
        window = ''.join(lines[a-1:b])
        assert text in window, (p, a, b)
        lo = sum(map(len, lines[:a-1])) + window.index(text)
        spans.setdefault(p, []).append((lo, lo + len(text)))
        assert s.get('scope') == 'project'
        assert isinstance(s['ref'], str) and s['ref']
        assert s.get('source_uri', '').startswith('docatlas://source/')
    return spans


def covered(fact, spans, docs):
    p, q = fact['path'], fact['quote']
    assert docs[p].count(q) == 1, (p, q)
    cursor = docs[p].index(q)
    end = cursor + len(q)
    for left, right in sorted(spans.get(p, [])):
        if right <= cursor:
            continue
        if left > cursor:
            return False
        cursor = right
        if cursor >= end:
            return True
    return False


def stable(view):
    # Fresh server capabilities are intentionally session-local. Ignore only
    # ephemeral identity, NOT source bytes, trust/scope/version or ordering.
    return [{k: v for k, v in s.items() if k not in {'ref', 'source_uri', 'project_identity', 'content_sha256'}}
            for s in source_rows(view)]


async def execute(a):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from docmancer.docs.application.projection_tokenizer import projection_token_count as count
    cases = dataset(a.repo)['cases']
    records = []
    for policy in POLICIES:
        for family in dict.fromkeys(c['family'] for c in cases):
            folder = a.out / policy / family
            folder.mkdir(parents=True, exist_ok=True)
            params = StdioServerParameters(command=sys.executable,
                args=['-I', str(Path(__file__).resolve()), '--worker', '--repo', str(a.repo),
                      '--work', str(a.work), '--out', str(a.out), '--policy', policy, '--family', family],
                env=dict(os.environ))
            with (folder / 'stderr.log').open('w') as err:
                async with stdio_client(params, errlog=err) as streams:
                    async with ClientSession(*streams, read_timeout_seconds=timedelta(seconds=240)) as session:
                        await session.initialize()
                        for case in [c for c in cases if c['family'] == family]:
                            start = time.perf_counter()
                            r = await session.call_tool('get_docs_context', {
                                'question': case['question'], 'scope': 'project',
                                'project_path': str(a.work / policy / family / 'project')})
                            elapsed = time.perf_counter() - start
                            wire = r.model_dump(by_alias=True)
                            save(folder / f"{case['id']}-reply.json", wire)
                            assert r.structuredContent is None and not wire.get('_meta')
                            assert len(r.content) == 1 and r.content[0].type == 'text'
                            text = r.content[0].text
                            view = literal(json.loads(text))
                            save(folder / f"{case['id']}-literal.json", view)
                            spans = verify_sources(view, sources(a.repo, family)) if not r.isError else {}
                            facts = [f['id'] for f in case['required'] if covered(f, spans, sources(a.repo, family))]
                            record = {'id': case['id'], 'family': family, 'policy': policy,
                                      'error': bool(r.isError), 'seconds': elapsed,
                                      'tokens': count(text.encode()), 'facts': facts,
                                      'required': len(case['required']), 'format': json.loads(text).get('context_format'),
                                      'rows': len(source_rows(view))}
                            records.append(record)
                            print(json.dumps(record), flush=True)
                        # One typed unavailable-scope response per policy, not a
                        # short error masquerading as successful compression.
                        if family == 'black':
                            denied = await session.call_tool('get_docs_context', {
                                'question': cases[0]['question'], 'project_path': str(a.work / policy / family / 'project'),
                                'scope': 'module', 'module_path': 'absent'})
                            p = json.loads(denied.content[0].text)
                            assert p['status'] in {'failed', 'insufficient_evidence'} and not p.get('sources')
                            assert not str(p.get('context_format', '')).startswith('docatlas.assembled-')
                            save(folder / 'unavailable.json', p)
            state = json.loads((folder / 'server.json').read_text())
            assert state['files_unchanged'] and state['database_unchanged']
    return records


def compare(a, records):
    from docmancer.docs.application.context_assembly import assemble_context, render_layouts
    from docmancer.docs.application.projection_tokenizer import projection_token_count as count
    def canonical(v):
        return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    result = {'cases': [], 'new_questions': 20, 'stdio_get_context_calls': 105,
              'paid_model_calls': 0, 'provider_usage': None, 'answer_quality': 'NOT_TESTED',
              'cross_process_input_order_changes': [], 'own_input_order_checks': 0}
    for case in dataset(a.repo)['cases']:
        def get(policy):
            return json.loads((a.out / policy / case['family'] / f"{case['id']}-literal.json").read_text())
        base = get('literal')
        # Separate processes can produce different upstream tied-row orders.
        # Require identical source multisets across runs AND exact retention of
        # each run's own pre-assembly selected-evidence order from its receipt.
        base_set = Counter(canonical(r) for r in stable(base))
        key = hashlib.sha256(case['question'].encode()).hexdigest()
        for p in POLICIES:
            view = get(p)
            assert Counter(canonical(r) for r in stable(view)) == base_set, (case['id'], p, 'sources changed')
            state = json.loads((a.out / p / case['family'] / 'server.json').read_text())
            receipts = [r for r in state['observations'] if r['scoring_question_sha256'] == key]
            assert len(receipts) == 1
            assert [r['ref'] for r in source_rows(view)] == receipts[0]['selected_evidence_ids'], (case['id'], p, 'own input order changed')
            result['own_input_order_checks'] += 1
            if stable(view) != stable(base):
                result['cross_process_input_order_changes'].append({'id': case['id'], 'policy': p})
        assert all(next(r for r in records if r['id'] == case['id'] and r['policy'] == p)['facts'] ==
                   next(r for r in records if r['id'] == case['id'] and r['policy'] == 'literal')['facts'] for p in POLICIES)
        text = canonical(base)
        variants = render_layouts(text)
        costs, timings = {}, {}
        # Fixed response, including the SAME ephemeral refs, across all layouts.
        for p in POLICIES:
            samples = []
            for _ in range(5):
                start = time.perf_counter_ns()
                rendered = assemble_context(text, policy=p)
                samples.append((time.perf_counter_ns()-start)/1e6)
            restored = literal(json.loads(rendered))
            assert canonical(restored) == text
            costs[p] = count(rendered.encode())
            timings[p] = statistics.median(samples)
            save(a.out / 'paid-inputs' / f"{case['id']}-{p}.json", {
                'id': case['id'], 'policy': p, 'question': case['question'], 'context': rendered})
        assert costs['adaptive'] == min(costs.values())
        actual = assemble_context(text, policy='adaptive')
        winner = next(k for k, v in variants.items() if v == actual)
        result['cases'].append({'id': case['id'], 'costs': costs, 'assembly_ms': timings,
                                'winner': winner, 'exact_roundtrip': True, 'same_source_multisets_all_arms': True})
    result['policies'] = {}
    for p in POLICIES:
        rs = [r for r in records if r['policy'] == p]
        good = [r for r in rs if not r['error']]
        result['policies'][p] = {
            'same_ref_tokens': sum(c['costs'][p] for c in result['cases'] if not next(r for r in rs if r['id']==c['id'])['error']),
            'actual_wire_tokens_success': sum(r['tokens'] for r in good),
            'delivered_requirements': sum(len(r['facts']) for r in rs),
            'required': sum(r['required'] for r in rs), 'errors': sum(r['error'] for r in rs),
            'complete_cases': sum(len(r['facts']) == r['required'] for r in rs),
            'median_mcp_seconds': statistics.median(r['seconds'] for r in good) if good else None,
            'median_assembly_ms': statistics.median(c['assembly_ms'][p] for c in result['cases'])}
    result['records'] = records
    result['winner_counts'] = {p: sum(c['winner'] == p for c in result['cases']) for p in POLICIES[:-1]}
    result['note'] = 'Known facts only. Two partially unsupported questions are NOT proof of correct unknown answers. Cross-process input order variation is reported, never silently repaired; each output retains its own pre-assembly order.'
    save(a.out / 'RESULT.json', result)
    print(json.dumps({k:v for k,v in result.items() if k not in {'cases','records'}}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    for key in ('repo', 'work', 'out'):
        parser.add_argument('--'+key, type=Path, required=True)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--resume-recorded', action='store_true', help='Re-evaluate saved actual responses; no new retrieval or inference')
    parser.add_argument('--policy', choices=POLICIES)
    parser.add_argument('--family')
    a = parser.parse_args()
    if a.worker:
        worker(a)
        return
    import docmancer
    installed = Path(docmancer.__file__).resolve().parent
    assert not installed.is_relative_to(a.repo), 'installed wheel required'
    for name in ('context_assembly.py','standalone_text_view.py','section_compression.py','facet_selection.py'):
        assert (installed/'docs/application'/name).read_bytes() == (a.repo/'docmancer/docs/application'/name).read_bytes()
    source_root = a.repo / 'eval/prepared_model_comparison40/sources'
    for rel, sha in dataset(a.repo)['source_sha256'].items():
        assert hashlib.sha256((source_root/rel).read_bytes()).hexdigest() == sha, rel
    if a.resume_recorded:
        records = json.loads((a.out/'RECORDS.json').read_text())
        assert len(records) == 100
    else:
        save(a.out/'FROZEN.json', {'question_sha256': hashlib.sha256((a.repo/'eval/context_assembly/questions20.json').read_bytes()).hexdigest(),
                                 'source_sha256': dataset(a.repo)['source_sha256'], 'git_sha': os.environ.get('TESTED_SHA')})
        records = asyncio.run(execute(a))
        save(a.out/'RECORDS.json', records)
    compare(a, records)


if __name__ == '__main__':
    main()
