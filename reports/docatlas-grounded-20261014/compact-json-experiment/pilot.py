"""Paired installed stdio MCP experiment. Gold is read only after delivery.

The server harness toggles only the host serializer flag at the entry to each
original public request. Production server/selection/storage/validators run
unchanged; all observation is passive. Fresh work/output directories required.
"""
import argparse
import asyncio
from copy import deepcopy
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def support(repo):
    sys.path.insert(0, str(repo / 'eval/heuristic_removal'))
    import receipts
    from run import load_dataset, source_directory
    from trace_two_losses import BoundaryObserver
    return receipts, load_dataset, source_directory, BoundaryObserver


def worker(args):
    r, dataset, source_directory, BaseObserver = support(args.repo)
    runtime = load('fixture_runtime', args.repo / 'eval/evidence_quality_v2/runtime.py')
    from docmancer.mcp._docs_server_part01 import _run_async
    from docmancer.docs.application.context_json import serialize_context_json
    from docmancer.docs.application.projection_tokenizer import projection_token_count
    cases, families = dataset(args.repo / 'eval/prepared_model_comparison40')
    family = next(f for f in families if f['id'] == args.family)
    case = next(c for c in cases if c['id'] == args.case)
    order = ['A', 'C'] if case['id'] == 'V40-P03' else ['C', 'A']
    root = args.work / family['id'] / 'project'
    documents = {name: (source_directory(args.repo / 'eval/prepared_model_comparison40', family['id']) / name).read_text()
                 for name in family['paths']}
    runtime.write_project(root, documents)
    # Prove byte-for-byte copy, not newline-normalized fixture substitution.
    assert all((root / name).read_bytes() == (source_directory(args.repo / 'eval/prepared_model_comparison40', family['id']) / name).read_bytes()
               for name in documents)
    with runtime.isolated_service(args.work / family['id'] / 'state') as (service, config):
        inventory = runtime.index_project(service, config, root)
        initial_db, initial_files = r.database(inventory['storage_path']), r.files(root)
        r.save(args.output / (case['id'] + '-preparation.json'), dict(root=str(root), inventory=inventory,
               snapshots=r.snapshots(inventory, root, documents), files=initial_files))
        os.environ.update(DOCATLAS_EXPERIMENT_CONTEXT_MAX_TOKENS='12000', DOCATLAS_MCP_TEXT_FALLBACK='1', HF_HUB_OFFLINE='1')

        class Observer(BaseObserver):
            def emit(self, stage, **fields):
                super().emit(stage, **deepcopy(fields))

            def profile(self, frame, event, result):
                name, module = frame.f_code.co_name, frame.f_globals.get('__name__', '')
                public = name == 'call_docs_tool_payload' and module == 'docmancer.mcp._docs_server_part01'
                if public and event == 'call' and frame.f_locals.get('name') == 'get_docs_context':
                    if self.calls >= len(order):
                        raise ValueError('unexpected extra context call')
                    self.arm = order[self.calls]
                    os.environ['DOCATLAS_EXPERIMENT_COMPACT_CONTEXT_JSON'] = '1' if self.arm == 'C' else '0'
                    self.started, self.cpu_started = time.perf_counter(), time.process_time()
                finishing = public and event == 'return' and self.active is not None
                if finishing:
                    wall, cpu = time.perf_counter() - self.started, time.process_time() - self.cpu_started
                if self.active is not None and event == 'return' and module.startswith('docmancer.'):
                    if name == 'experimental_context_cost' and frame.f_back.f_code.co_name == 'enforce_experimental_context_budget':
                        wire = serialize_context_json(frame.f_locals['payload']).encode()
                        tokens = projection_token_count(wire)
                        self.emit('budget.wire', sha256=r.sha(wire), bytes=len(wire), codec_tokens=tokens,
                                  utf8_div4=math.ceil(len(wire) / 4), cost=result,
                                  exact=result == max(tokens, math.ceil(len(wire) / 4)))
                super().profile(frame, event, result)
                if finishing:
                    checks = r.integrity(result, root, documents)
                    read_only = r.database(inventory['storage_path']) == initial_db and r.files(root) == initial_files
                    r.save(args.output / (case['id'] + '-' + self.arm + '-server.json'), dict(
                        payload=result, integrity=checks, read_only=read_only,
                        wall_seconds=wall, cpu_seconds=cpu, trace_errors=self.errors,
                        events=self.events, arm=self.arm, flag=os.environ['DOCATLAS_EXPERIMENT_COMPACT_CONTEXT_JSON']))
                    assert not self.errors and not checks['errors'] and read_only

        observer = Observer(args.output / (case['id'] + '-boundaries'))
        threading.setprofile(observer.profile)
        try:
            asyncio.run(_run_async(service))
        finally:
            threading.setprofile(None)


async def client(args):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from docmancer.docs.application.projection_tokenizer import projection_token_count
    r, dataset, _, _ = support(args.repo)
    cases, families = dataset(args.repo / 'eval/prepared_model_comparison40')
    rows = []
    for case_id in ('V40-P03', 'V40-E01'):
        case = next(c for c in cases if c['id'] == case_id)
        order = ['A', 'C'] if case_id == 'V40-P03' else ['C', 'A']
        params = StdioServerParameters(command=sys.executable, args=[
            '-I', str(Path(__file__).resolve()), '--worker', '--repo', str(args.repo),
            '--work', str(args.work), '--output', str(args.output),
            '--family', case['project_group'], '--case', case_id], env=dict(os.environ))
        root = args.work / case['project_group'] / 'project'
        with (args.output / (case_id + '-stderr.log')).open('w') as stderr:
            async with stdio_client(params, errlog=stderr) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    assert 'get_docs_context' in {t.name for t in tools.tools}
                    for arm in order:
                        start = time.perf_counter()
                        result = await session.call_tool('get_docs_context', dict(question=case['question'], project_path=str(root), scope='project'))
                        wall = time.perf_counter() - start
                        assert not result.isError and len(result.content) == 1 and result.content[0].type == 'text'
                        text = result.content[0].text
                        raw, payload = text.encode('utf-8'), json.loads(text)
                        expected = json.dumps(payload, ensure_ascii=False, **({'separators': (',', ':')} if arm == 'C' else {}))
                        assert text == expected  # Actual delivered text, not a counterfactual.
                        (args.output / (case_id + '-' + arm + '-dto.txt')).write_bytes(raw)
                        r.save(args.output / (case_id + '-' + arm + '-mcp-result.json'), result.model_dump(mode='json'))
                        tokens, byte_cost = projection_token_count(raw), math.ceil(len(raw) / 4)
                        assert max(tokens, byte_cost) <= 12000
                        server = json.loads((args.output / (case_id + '-' + arm + '-server.json')).read_text())
                        assert server['payload'] == payload
                        trials = [e for e in server['events'] if e['stage'] == 'budget.wire']
                        assert trials and all(e['exact'] for e in trials)
                        assert any(e['sha256'] == r.sha(raw) for e in trials)
                        rows.append(dict(case_id=case_id, arm=arm, windows=len(payload['sources']), utf8_bytes=len(raw),
                            utf8_div4=byte_cost, codec_tokens=tokens, full_cost=max(tokens, byte_cost), wire_sha256=r.sha(raw),
                            client_wall_seconds=wall, server_wall_seconds=server['wall_seconds'], cpu_seconds=server['cpu_seconds'],
                            integrity=not server['integrity']['errors'], read_only=server['read_only'],
                            serialized_trials=len(trials), exact_trials=True, exact_final_wire=True))
    return rows


def score(args, rows):
    # No gold/evaluator import in worker or client; only after all four responses.
    r, dataset, source_directory, _ = support(args.repo)
    data = args.repo / 'eval/prepared_model_comparison40'
    evaluator = load('independent_oracle', data / 'evaluate.py')
    golds = json.loads((data / 'gold_spans.json').read_text())['cases']
    cases, families = dataset(data)
    for row in rows:
        case = next(c for c in cases if c['id'] == row['case_id'])
        family = next(f for f in families if f['id'] == case['project_group'])
        prepared = dict(root=str(args.work / family['id'] / 'project'), sources={})
        for name in family['paths']:
            raw = (source_directory(data, family['id']) / name).read_bytes()
            text = raw.decode('utf-8')
            offsets = [0]
            for line in text.splitlines(keepends=True):
                offsets.append(offsets[-1] + len(line))
            prepared['sources'][name] = dict(raw=raw, content=text, sha256=r.sha(raw), line_offsets=offsets, errors=[])
        payload = json.loads((args.output / (row['case_id'] + '-' + row['arm'] + '-dto.txt')).read_bytes())
        verified, intervals, errors = evaluator._source_rows(payload, prepared)
        gold = next(g for g in golds if g['id'] == row['case_id'])
        row['oracle'] = evaluator._gold(case, gold, prepared, intervals)
        row['source_errors'] = errors
        r.save(args.output / (row['case_id'] + '-' + row['arm'] + '-oracle.json'), dict(
            oracle=row['oracle'], verified_rows=verified, source_errors=errors))
    comparisons = []
    for case_id in ('V40-P03', 'V40-E01'):
        a, c = [json.loads((args.output / (case_id + '-' + arm + '-server.json')).read_text()) for arm in ('A', 'C')]
        stage = 'project_docs_context.output'
        ap, cp = [[e for e in s['events'] if e['stage'] == stage][-1]['rows'] for s in (a, c)]
        assert ap == cp  # Full admitted ordered pool, values and bindings identical.
        pool = [v['public'] for v in ap]
        selected = [{v['evidence_id']: v for v in s['payload']['sources']} for s in (a, c)]
        for packet in selected:
            assert all(v == next(p for p in pool if p['evidence_id'] == key) for key, v in packet.items())
        def changes(left, right):
            changed = []
            for position, v in enumerate(pool, 1):
                key = v['evidence_id']
                if key not in right or key in left:
                    continue
                trials = {}
                for arm, packet in (('A', a), ('C', c)):
                    costs = [e for e in packet['events'] if e['stage'] == 'budget.cost' and (e.get('option') or {}).get('evidence_id') == key]
                    trials[arm] = costs
                changed.append(dict(position=position, window=v, trials=trials,
                                    reason='same whole window, different exact full-DTO trial cost; first-fit retained earlier windows'))
            return changed
        comparisons.append(dict(case_id=case_id, pool_count=len(pool), pool_order_values_bindings_equal=True,
            selected_rows_unchanged=True, added=changes(selected[0], selected[1]), removed=changes(selected[1], selected[0])))
    return comparisons


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('repo', 'work', 'output'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--family')
    parser.add_argument('--case')
    args = parser.parse_args()
    args.repo, args.work, args.output = args.repo.resolve(), args.work.resolve(), args.output.resolve()
    if args.worker:
        return worker(args)
    assert not args.work.exists() and not args.output.exists(), 'fresh work/output required'
    args.work.mkdir(mode=0o700, parents=True)
    args.output.mkdir(parents=True)
    r, _, _, _ = support(args.repo)
    import docmancer
    origin = Path(docmancer.__file__).resolve()
    assert origin.is_relative_to(Path(sys.prefix)) and not origin.is_relative_to(args.repo)
    files = [p for directory in ('docmancer', 'eval/heuristic_removal', 'eval/prepared_model_comparison40')
             for p in (args.repo / directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files += [args.repo / 'uv.lock', args.repo / 'pyproject.toml', args.repo / 'eval/evidence_quality_v2/runtime.py', Path(__file__).resolve()]
    inputs = {str(p.relative_to(args.repo)): r.sha(p.read_bytes()) for p in sorted(set(files))}
    installed = {str(p.relative_to(origin.parent)): r.sha(p.read_bytes()) for p in origin.parent.rglob('*')
                 if p.is_file() and '__pycache__' not in p.parts}
    assert all(installed[name.removeprefix('docmancer/')] == digest for name, digest in inputs.items() if name.startswith('docmancer/'))
    r.save(args.output / 'FREEZE.json', dict(head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        inputs_sha256=inputs, installed_files_sha256=installed, origin=str(origin), python=sys.version,
        dependencies={d.metadata['Name']: d.version for d in importlib.metadata.distributions()},
        config=dict(cap=12000, calls=4, prepares=2, order={'V40-P03': ['A', 'C'], 'V40-E01': ['C', 'A']},
                    models=0, offline=True, wall_seconds=600, transport='installed stdio MCP with real Python SDK client',
                    switch='DOCATLAS_EXPERIMENT_COMPACT_CONTEXT_JSON', default=False),
        dirty_diff=subprocess.check_output(['git', 'diff', '--', 'docmancer'], text=True)))
    with r.deadline(600):
        rows = asyncio.run(client(args))
    comparisons = score(args, rows)
    assert all(r.sha((args.repo / p).read_bytes()) == digest for p, digest in inputs.items())
    pilot_pass = all(row['oracle']['all_documented_claims_covered'] and not row['source_errors']
                     and row['integrity'] and row['read_only'] for row in rows if row['arm'] == 'C')
    r.save(args.output / 'MEASUREMENTS.json', dict(rows=rows, comparisons=comparisons,
        C_pilot_pass=pilot_pass, V40='ELIGIBLE_NOT_RUN' if pilot_pass else 'NOT_RUN_PILOT_FAIL',
        B='BLOCKED_UNCHANGED', contexts=4, prepares=2, frozen_inputs_unchanged=True,
        timing='single observation per arm with identical passive profiling; not an uninstrumented benchmark'))


if __name__ == '__main__':
    main()
