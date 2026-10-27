"""Compare experimental selectors through installed MCP and real OpenCode.

This is a source-witness experiment, not semantic answer certification. The
unchanged V40 regression corpus and the new multi-source corpus are separate
mixed projects. Gold is parsed only after all delivery calls for that corpus;
its bytes are hashed beforehand. The public legacy source packet is observed
after admission/upstream projection, before native selection and pagination.
Candidate quality failures are recorded, never relabelled as infrastructure
success. No answering model, provider billing, mocks or private selection calls.
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
import shutil
import statistics
import subprocess
import sys
import time
import traceback


POLICIES = (
    'preserve',
    'guarded-cover-v2',
    'guarded-obligation-v1',
    'guarded-constraint-v1',
    'guarded-combined-v1',
)
CORPORA = (
    ('v40', 'eval/prepared_model_comparison40', 'known development/regression'),
    ('new', 'eval/native_sufficiency_cases', 'new authored evaluation; not a blind population estimate'),
)
SOURCE_ATTRIBUTES = ('scope', 'version_binding', 'authority', 'instruction_trust',
                     'freshness', 'source_type')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def latency_summary(values):
    ordered = sorted(values)
    return {
        'calls': len(values),
        'total_ms': round(sum(values), 3),
        'median_ms': round(statistics.median(values), 3) if values else None,
        'p95_ms': round(ordered[max(0, (95 * len(ordered) + 99) // 100 - 1)], 3) if values else None,
        'interpretation': 'one sequential run; includes cold/warm order effects, not a latency benchmark',
    }


def packet_sources(text):
    packet = json.loads(text)
    assert isinstance(packet.get('sources'), list), packet
    return packet['sources']


def pool_intervals(rows, docs):
    """Independently bind admitted source text to original file coordinates."""
    intervals = {}
    for row in rows:
        path, snippet = row['path_or_url'], row['snippet']
        assert path in docs, ('source_outside_authorized_fixture', path)
        original = docs[path]
        first = row.get('line_start')
        assert type(first) is int and first > 0, row
        last = row.get('line_end') or first + max(0, len(snippet.splitlines()) - 1)
        lines = original.splitlines(keepends=True)
        window = ''.join(lines[first - 1:last])
        assert snippet in window, ('source_text_or_coordinates_changed', path, first, last)
        start = sum(map(len, lines[:first - 1])) + window.index(snippet)
        intervals.setdefault(path, []).append((start, start + len(snippet)))
        if row.get('content_sha256'):
            assert row['content_sha256'] == hashlib.sha256(snippet.encode()).hexdigest(), ('source_hash', path)
    return intervals


def acquired_report(cases, docs, replies, gold):
    records = []
    for case in cases:
        sources = packet_sources(replies[case['id']])
        intervals = pool_intervals(sources, docs)

        def covered(part):
            path = case['project_group'] + '/' + part['path']
            original = docs[path]
            lines = original.splitlines(keepends=True)
            start = sum(map(len, lines[:part['line_start'] - 1]))
            end = sum(map(len, lines[:part['line_end']]))
            while start < end and original[start].isspace():
                start += 1
            while end > start and original[end - 1].isspace():
                end -= 1
            cursor = start
            for left, right in sorted(intervals.get(path, [])):
                if right <= cursor:
                    continue
                if left > cursor:
                    break
                cursor = right
                if cursor >= end:
                    return True
            return cursor >= end

        facts = []
        for claim in gold[case['id']]['required_claims']:
            if not claim['witness_sets']:
                continue
            facts.append({'id': claim['id'], 'covered': any(
                all(covered(part) for part in group['parts']) for group in claim['witness_sets'])})
        records.append({'id': case['id'], 'facts': facts,
                        'all_documented': all(x['covered'] for x in facts) if facts else None,
                        'source_rows': len(sources),
                        'source_documents': len({x['path_or_url'] for x in sources}),
                        'absence_or_answer_quality_tested': False})
    return records


def verify_native(text, pool, reader):
    """Compare actual visible slices/provenance with the independent legacy pool."""
    binding = {}
    for line in text.splitlines():
        if line.startswith('Binding: '):
            binding = json.loads(line[len('Binding: '):])
            break
    for item in reader(text):
        index = int(item['ref'].split(':s')[1].split(':')[0]) - 1
        assert 0 <= index < len(pool)
        source = pool[index]
        assert item['path'] == source['path_or_url']
        assert item['full'] == len(source['snippet'])
        assert item['text'] == source['snippet'][item['a']:item['b']]
        assert item['start'] == source['line_start'] + source['snippet'][:item['a']].count('\n')
        assert item['end'] == item['start'] + max(0, len(item['text'].splitlines()) - 1)
        attributes = {**binding, **item['attributes']}
        for key in (*SOURCE_ATTRIBUTES, 'section'):
            if key in source:
                assert attributes.get(key) == source[key], ('source_provenance', key, source, attributes)


async def execute(args, cli, env, cases, root, arm, legacy, baseline, paginate=False):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from docmancer.docs.application.projection_tokenizer import projection_token_count

    settings = dict(env)
    settings.update(DOCATLAS_MCP_PRESENTATION='legacy' if arm == 'legacy' else 'opencode-v1',
                    DOCATLAS_NATIVE_SELECTION='preserve' if arm == 'legacy' else arm,
                    DOCATLAS_CONTEXT_COMPRESSION='off', DOCATLAS_MCP_TEXT_FALLBACK='1',
                    DOCATLAS_NATIVE_TRACE='1')
    for key in ('DOCATLAS_MINILM_MODEL_DIR', 'DOCATLAS_MCP_MODEL_VIEW'):
        settings.pop(key, None)
    calls, metrics, texts = 0, [], {}
    pagination = None
    params = StdioServerParameters(command=cli, args=['mcp', 'docs-serve'], env=settings)
    with (args.out / (arm + '-stderr.log')).open('w') as err:
        async with stdio_client(params, errlog=err) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=180)) as client:
                await client.initialize()
                tools = await client.list_tools()
                schema = next(t.inputSchema for t in tools.tools if t.name == 'get_docs_context')
                assert ('continuation' in schema['properties']) == (arm != 'legacy')

                async def call(request):
                    nonlocal calls
                    started = time.perf_counter()
                    response = await client.call_tool('get_docs_context', request)
                    elapsed = (time.perf_counter() - started) * 1000
                    calls += 1
                    return response, elapsed

                for case in cases:
                    request = {'question': case['question'], 'project_path': str(root), 'scope': 'project'}
                    response, elapsed = await call(request)
                    raw = response.model_dump(by_alias=True)
                    save(args.out / arm / (case['id'] + '.json'), raw)
                    assert not response.isError, raw
                    text = '\n'.join(x.text for x in response.content if x.type == 'text')
                    texts[case['id']] = text
                    meta = (raw.get('_meta') or {}).get('docatlas/native-delivery', {})
                    metrics.append({'id': case['id'], 'bytes': len(text.encode()), 'lines': len(text.splitlines()),
                                    'text_tokens': projection_token_count(text.encode()),
                                    'latency_ms': round(elapsed, 3), 'diagnostic': meta})
                    if arm == 'legacy':
                        packet_sources(text)
                    else:
                        assert len(text.encode()) <= 24_000 and len(text.splitlines()) <= 900
                        assert projection_token_count(text.encode()) <= 3_000
                        assert meta['minilm_applied'] is False and meta['policy'] == arm
                        assert 'not certified' in text.lower()
                        verify_native(text, packet_sources(legacy[case['id']]), baseline.visible_sources)

                if paginate:
                    case = cases[0]
                    request = {'question': case['question'], 'project_path': str(root), 'scope': 'project'}
                    response, _ = await call(request)
                    assert not response.isError
                    raw = response.model_dump(by_alias=True)
                    text = '\n'.join(x.text for x in response.content if x.type == 'text')
                    pool = packet_sources(legacy[case['id']])
                    verify_native(text, pool, baseline.visible_sources)
                    cursor = raw['_meta']['docatlas/native-delivery']['continuation']
                    original_cursor = cursor
                    assert original_cursor, 'pagination control must exercise a real continuation'
                    slices = baseline.visible_sources(text)
                    pages = 1
                    save(args.out / 'pages' / arm / '1.json', raw)
                    while cursor:
                        response, _ = await call(dict(request, continuation=cursor))
                        assert not response.isError, response
                        raw = response.model_dump(by_alias=True)
                        text = '\n'.join(x.text for x in response.content if x.type == 'text')
                        verify_native(text, pool, baseline.visible_sources)
                        assert projection_token_count(text.encode()) <= 3_000
                        assert len(text.encode()) <= 24_000 and len(text.splitlines()) <= 900
                        slices.extend(baseline.visible_sources(text))
                        pages += 1
                        assert pages <= 64
                        cursor = raw['_meta']['docatlas/native-delivery']['continuation']
                        save(args.out / 'pages' / arm / f'{pages}.json', raw)
                    groups = {}
                    for item in slices:
                        index = int(item['ref'].split(':s')[1].split(':')[0]) - 1
                        groups.setdefault(index, []).append(item)
                    assert len(groups) == len(pool)
                    for index, parts in groups.items():
                        parts.sort(key=lambda item: item['a'])
                        offset = 0
                        for part in parts:
                            assert part['a'] == offset
                            offset = part['b']
                        assert ''.join(x['text'] for x in parts) == pool[index]['snippet']
                    for override in ({'continuation': original_cursor + '0'},
                                     {'continuation': original_cursor, 'question': 'different question'},
                                     {'continuation': original_cursor, 'scope': 'all'}):
                        denied, _ = await call({**request, **override})
                        assert denied.isError
                    altered = root / pool[0]['path_or_url']
                    before = altered.read_bytes()
                    try:
                        altered.write_bytes(before + b'\nchanged after issuing continuation\n')
                        denied, _ = await call(dict(request, continuation=original_cursor))
                        assert denied.isError, 'stale continuation served changed source'
                    finally:
                        altered.write_bytes(before)
                    pagination = {'pages': pages, 'rows': len(groups), 'all_original_bytes_preserved': True,
                                  'forged_cursor_rejected': True, 'changed_question_rejected': True,
                                  'changed_scope_rejected': True, 'changed_source_rejected': True}
                    save(args.out / ('pagination-' + arm + '.json'), pagination)
    save(args.out / (arm + '-metrics.json'), metrics)
    return texts, metrics, calls, pagination


def score_boundary(cases, gold, acquired, reports, metrics):
    """Keep unknowns ungraded; report every missing independently authored claim."""
    acquired_map = {x['id']: {f['id']: f['covered'] for f in x['facts']} for x in acquired}
    report_maps = {arm: {x['id']: x for x in rows} for arm, rows in reports.items()}
    scorecards = {}
    for arm in POLICIES:
        rows, failures, losses = [], [], []
        metric_map = {x['id']: x for x in metrics[arm]}
        for case in cases:
            cid = case['id']
            record = report_maps[arm][cid]
            delivered = {x['id']: x['covered'] for x in record['facts']}
            claim_details = []
            for claim, value in delivered.items():
                present = acquired_map[cid][claim]
                status = 'delivered' if value else 'missing_before_native_selection' if not present else 'admitted_not_on_first_page'
                item = {'id': claim, 'acquired': present, 'delivered': value, 'status': status}
                claim_details.append(item)
                if not value:
                    failures.append({'case': cid, 'claim': claim, 'status': status})
                for control in ('preserve', 'guarded-cover-v2'):
                    prior = {x['id']: x['covered'] for x in report_maps[control][cid]['facts']}
                    if prior[claim] and not value:
                        losses.append({'control': control, 'case': cid, 'claim': claim})
            unknown = [x['id'] for x in gold[cid]['required_claims'] if not x['witness_sets']]
            rows.append({'id': cid, 'question': case['question'], 'answerability_label': case.get('answerability'),
                         'required_claims': claim_details, 'unsupported_claims_not_graded': unknown,
                         'all_documented': record['all_documented'],
                         'source_rows': record['source_rows'], 'source_documents': record['source_documents'],
                         'text_tokens': metric_map[cid]['text_tokens'],
                         'latency_ms': metric_map[cid]['latency_ms'],
                         'absence_or_answer_quality_tested': False})
        total_claims = sum(len(x['required_claims']) for x in rows)
        delivered_claims = sum(sum(c['delivered'] for c in x['required_claims']) for x in rows)
        acquired_claims = sum(sum(c['acquired'] for c in x['required_claims']) for x in rows)
        scorecards[arm] = {
            'source_witness_result': 'PASS' if delivered_claims == total_claims else 'FAIL',
            'first_page_retention_result': 'PASS' if not any(
                x['status'] == 'admitted_not_on_first_page' for x in failures) else 'FAIL',
            'baseline_non_regression_result': 'PASS' if not losses else 'FAIL',
            'final_answer_and_unknown_result': 'NOT_TESTED',
            'documented_claims': total_claims, 'acquired_claims': acquired_claims,
            'delivered_claims': delivered_claims,
            'complete_documented_cases': sum(x['all_documented'] is True for x in rows),
            'documented_cases': sum(bool(x['required_claims']) for x in rows),
            'fully_unsupported_cases_not_graded': sum(not x['required_claims'] for x in rows),
            'first_page_tokens': sum(x['text_tokens'] for x in rows),
            'source_rows': sum(x['source_rows'] for x in rows),
            'latency': latency_summary([x['latency_ms'] for x in rows]),
            'failures': failures, 'lost_control_claims': losses, 'cases': rows,
        }
    control_tokens = scorecards['preserve']['first_page_tokens']
    v2_tokens = scorecards['guarded-cover-v2']['first_page_tokens']
    for arm, score in scorecards.items():
        score['first_page_token_change_vs_preserve'] = score['first_page_tokens'] - control_tokens
        score['first_page_token_change_vs_v2'] = score['first_page_tokens'] - v2_tokens
        score['first_page_token_saving_pct_vs_preserve'] = round(100 * (1 - score['first_page_tokens'] / control_tokens), 3)
    return scorecards


def run_corpus(args, name, relative, label, baseline, runtime, state_helper):
    from docmancer.docs.application.projection_tokenizer import projection_token_count

    started = time.perf_counter()
    corpus = args.repo / relative
    # Hash bytes to freeze the oracle without parsing its expected facts.
    frozen_hashes = {name: hashlib.sha256((corpus / name).read_bytes()).hexdigest()
                     for name in ('questions.json', 'source_plan.json', 'gold_spans.json')}
    cases = json.loads((corpus / 'questions.json').read_text())['cases']
    assert len({x['id'] for x in cases}) == len(cases)
    families = json.loads((corpus / 'source_plan.json').read_text())['families']
    docs = {f['id'] + '/' + path: (corpus / 'sources' / f['id'] / path).read_bytes().decode('utf-8')
            for f in families for path in f['paths']}
    if name == 'v40':
        assert len(cases) == 40 and len(docs) == 15
    local = argparse.Namespace(**vars(args))
    local.out = args.out / name
    local.work = args.work / name
    local.out.mkdir()
    local.work.mkdir()
    root = local.work / 'project'
    runtime.write_project(root, docs)
    cli = str(Path(sys.executable).with_name('doc-atlas'))
    assert Path(cli).is_file()
    with runtime.isolated_service(local.work / 'state') as (service, config):
        install = subprocess.run([cli, 'install', 'opencode', '--project'], cwd=root, text=True, capture_output=True)
        assert install.returncode == 0, install.stderr
        registration = json.loads((root / 'opencode.json').read_text())['mcp']['servers']['docatlas']
        assert registration['environment']['DOCATLAS_MCP_PRESENTATION'] == 'opencode-v1'
        save(local.out / 'registration.json', registration)
        inventory = runtime.index_project(service, config, root)
        save(local.out / 'preparation.json', inventory)
        source_state = state_helper.source_state(root)
        db_state = state_helper.logical_state(inventory)
        replies, metrics, pagination, calls = {}, {}, {}, 0
        for arm in ('legacy', *POLICIES):
            reply, measured, n, paged = asyncio.run(execute(
                local, cli, dict(os.environ), cases, root, arm, replies.get('legacy'), baseline,
                paginate=name == 'v40' and arm != 'legacy'))
            replies[arm], metrics[arm] = reply, measured
            calls += n
            if paged:
                pagination[arm] = paged
        protocol = local.out / 'opencode-protocol.json'
        save(protocol, {'cli': cli, 'root': str(root), 'out': str(local.out), 'cases': cases,
                        'registration': registration, 'arms': list(POLICIES)})
        target = args.opencode / 'packages/core/test/docatlas-native-sufficiency.ts'
        shutil.copyfile(args.repo / 'eval/native_sufficiency_client.ts', target)
        run = subprocess.run(['bun', 'run', str(target)], cwd=args.opencode,
                             env={**os.environ, 'DOCATLAS_SUFFICIENCY_PROTOCOL': str(protocol)},
                             text=True, capture_output=True, timeout=1800)
        (local.out / 'opencode-stdout.log').write_text(run.stdout)
        (local.out / 'opencode-stderr.log').write_text(run.stderr)
        assert run.returncode == 0, run.stderr[-6000:]
        assert state_helper.source_state(root) == source_state
        assert state_helper.logical_state(inventory) == db_state
    # Evaluation-only source expectations are first opened at this boundary.
    assert frozen_hashes == {name: hashlib.sha256((corpus / name).read_bytes()).hexdigest()
                             for name in frozen_hashes}, 'evaluation inputs changed during delivery'
    gold = {x['id']: x for x in json.loads((corpus / 'gold_spans.json').read_text())['cases']}
    assert set(gold) == {x['id'] for x in cases}
    pool_report = acquired_report(cases, docs, replies['legacy'], gold)
    python_reports = {arm: baseline.witness_report(cases, docs, replies[arm], gold) for arm in POLICIES}
    normalized = json.loads((local.out / 'OPENCODE.json').read_text())
    assert normalized['model_calls'] == 0 and normalized['tool_calls'] == len(cases) * len(POLICIES)
    actual, client_metrics = {}, {}
    for arm in POLICIES:
        rows = [x for x in normalized['results'] if x['arm'] == arm]
        assert {x['id'] for x in rows} == {x['id'] for x in cases}
        actual[arm] = {x['id']: x['model_visible_text'] for x in rows}
        client_metrics[arm] = []
        for row in rows:
            text = row['model_visible_text']
            verify_native(text, packet_sources(replies['legacy'][row['id']]), baseline.visible_sources)
            tokens = projection_token_count(text.encode())
            assert tokens <= 3_000 and len(text.encode()) <= 24_000 and len(text.splitlines()) <= 900
            client_metrics[arm].append({'id': row['id'], 'text_tokens': tokens, 'latency_ms': row['latency_ms']})
    client_reports = {arm: baseline.witness_report(cases, docs, actual[arm], gold) for arm in POLICIES}
    result = {'corpus': name, 'corpus_description': label, 'questions': len(cases), 'documents': len(docs),
              'source_hashes': {path: hashlib.sha256(text.encode()).hexdigest() for path, text in docs.items()},
              'inputs_frozen_before_delivery': frozen_hashes,
              'question_file_sha256': frozen_hashes['questions.json'],
              'gold_file_sha256': frozen_hashes['gold_spans.json'],
              'pool_observation_boundary': 'legacy public docs_context after admission/upstream projection, before native selector/page renderer',
              'upstream_failure_localization': 'NOT_ESTABLISHED: missing_before_native_selection does not isolate retrieval, admission or upstream projection',
              'acquisition': pool_report,
              'python_stdio': score_boundary(cases, gold, pool_report, python_reports, metrics),
              'opencode': score_boundary(cases, gold, pool_report, client_reports, client_metrics),
              'pagination_integrity': pagination,
              'python_tool_calls': calls, 'opencode_tool_calls': normalized['tool_calls'],
              'answer_model_calls': 0, 'provider_usage': None,
              'model_answer_quality_tested': False, 'correct_unknown_tested': False,
              'source_and_sqlite_state_unchanged': True,
              'elapsed_seconds': round(time.perf_counter() - started, 3)}
    save(local.out / 'SUMMARY.json', result)
    return result


def markdown_report(result):
    lines = ['# Native evidence selection experiment', '',
             '**Infrastructure checks passed. Candidate source-witness results below are separate; final answers and correct unknowns were not tested.**', '',
             'All token counts are complete first MCP replies, not full dialogue usage. No answering model was called.', '']
    for corpus in result['corpora']:
        lines.extend([f"## {corpus['corpus']} — {corpus['questions']} questions, {corpus['documents']} documents", '',
                      '| Policy | Required claims delivered | Complete documented cases | First-page tokens | Source witness gate | Losses vs controls |',
                      '|---|---:|---:|---:|---|---:|'])
        for arm, score in corpus['opencode'].items():
            lines.append(f"| `{arm}` | {score['delivered_claims']}/{score['documented_claims']} | "
                         f"{score['complete_documented_cases']}/{score['documented_cases']} | "
                         f"{score['first_page_tokens']} | **{score['source_witness_result']}** | {len(score['lost_control_claims'])} |")
        lines.extend(['', '### Missing required source claims', ''])
        for arm, score in corpus['opencode'].items():
            missing = '; '.join(f"{x['case']}/{x['claim']} ({x['status']})" for x in score['failures']) or 'none'
            lines.append(f'- `{arm}`: {missing}')
        lines.extend(['', f"Calls: {corpus['python_tool_calls']} Python MCP + {corpus['opencode_tool_calls']} real OpenCode MCP. "
                      f"Elapsed: {corpus['elapsed_seconds']} seconds. Unsupported claims are explicitly ungraded.", ''])
    lines.extend(['## Evidence boundary', '',
                  '- Gold contains independently authored source spans; no selector accesses gold.',
                  '- The observed pool is legacy public docs_context after admission/upstream projection, before the native selector/page renderer.',
                  '- Missing-before-native-selection and admitted-but-not-on-first-page are reported separately; the latter includes selection and transport budget effects.',
                  '- A pre-native miss does not isolate upstream retrieval, admission or projection as its cause.',
                  '- All original text, coordinates, scope/version provenance, signed continuation and state invariants are checked.',
                  '- A PASS source-witness result is not proof of semantic sufficiency, global absence or lower provider cost.',
                  '- Detailed JSON contains every case, claim, raw reply, failure and call latency.', ''])
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repo', 'work', 'out', 'opencode'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    for name in ('repo', 'work', 'out', 'opencode'):
        setattr(args, name, getattr(args, name).resolve())
    args.out.mkdir(parents=True)
    args.work.mkdir(parents=True)
    try:
        import docmancer
        assert not Path(docmancer.__file__).resolve().is_relative_to(args.repo), 'installed wheel required'
        installed_package = Path(docmancer.__file__).resolve().parent
        product_hashes = {}
        for relative in ('mcp/evidence_selection.py', 'mcp/native_delivery.py'):
            installed_hash = hashlib.sha256((installed_package / relative).read_bytes()).hexdigest()
            repository_hash = hashlib.sha256((args.repo / 'docmancer' / relative).read_bytes()).hexdigest()
            assert installed_hash == repository_hash, ('installed_product_differs_from_checkout', relative)
            product_hashes[relative] = installed_hash
        save(args.out / 'PRODUCT_CHECKPOINT.json', {'head': os.environ.get('TESTED_SHA'),
                                                  'installed_matches_checkout': True,
                                                  'sha256': product_hashes})
        baseline = load('sufficiency_native_helpers', args.repo / 'eval/native_opencode_integration.py')
        runtime = load('sufficiency_fixture', args.repo / 'eval/evidence_quality_v2/runtime.py')
        state_helper = load('sufficiency_state', args.repo / 'eval/prepared_model_comparison40/run.py')
        results = [run_corpus(args, *corpus, baseline, runtime, state_helper) for corpus in CORPORA]
        result = {'head': os.environ.get('TESTED_SHA'), 'policies': list(POLICIES),
                  'installed_product_sha256': product_hashes,
                  'infrastructure_result': 'PASS', 'semantic_acceptance': 'NOT_TESTED',
                  'answer_model_calls': 0, 'provider_usage': None, 'corpora': results,
                  'python_tool_calls': sum(x['python_tool_calls'] for x in results),
                  'opencode_tool_calls': sum(x['opencode_tool_calls'] for x in results)}
        save(args.out / 'SUMMARY.json', result)
        report = markdown_report(result)
        (args.out / 'SCORECARD.md').write_text(report)
        print(report)
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a') as file:
                file.write(report)
    except Exception as exc:
        save(args.out / 'INFRASTRUCTURE_FAILURE.json', {'type': type(exc).__name__, 'message': str(exc),
                                                       'traceback': traceback.format_exc()})
        raise


if __name__ == '__main__':
    main()
