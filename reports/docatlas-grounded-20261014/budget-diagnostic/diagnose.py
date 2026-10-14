"""Installed MCP/SQLite diagnostic, not a product selector or a unit test.

Usage: installed-python -I diagnose.py --repo CHECKOUT --work FRESH_DIR --output FRESH_DIR
Gold is opened only in the separate diagnostic budget-return observer, after
the product has decided its output. No product arguments/results are replaced.
"""
import argparse
from contextlib import redirect_stderr
from copy import deepcopy
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    for key in ('repo', 'work', 'output'):
        parser.add_argument('--' + key, type=Path, required=True)
    args = parser.parse_args()
    repo, work, out = args.repo.resolve(), args.work.resolve(), args.output.resolve()
    if work.exists() or out.exists():
        raise ValueError('fresh work/output required')
    work.mkdir(mode=0o700, parents=True)
    out.mkdir(parents=True)
    sys.path.insert(0, str(repo / 'eval/heuristic_removal'))
    from receipts import save, sha, database, files, integrity, deadline
    from run import load_dataset, source_directory
    from trace_two_losses import BoundaryObserver
    runtime = load('fixture_runtime', repo / 'eval/evidence_quality_v2/runtime.py')
    import docmancer
    from docmancer.mcp.docs_server import call_docs_tool_payload
    from docmancer.docs.application.query_trace import query_trace
    from docmancer.docs.application.experimental_context_finalization import (
        _rebuild, recheck_experimental_context, check_experimental_context_budget,
        experimental_context_cost, validate_model_visible_projection,
    )
    from docmancer.docs.application.projection_tokenizer import projection_token_count
    origin = Path(docmancer.__file__).resolve()
    assert not origin.is_relative_to(repo) and origin.is_relative_to(Path(sys.prefix))
    pinned = [p for directory in ('docmancer', 'eval/heuristic_removal', 'eval/prepared_model_comparison40')
              for p in (repo / directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    pinned += [repo / 'uv.lock', repo / 'pyproject.toml', Path(__file__).resolve(), repo / 'eval/evidence_quality_v2/runtime.py']
    inputs = {str(p.relative_to(repo)): sha(p.read_bytes()) for p in sorted(set(pinned))}
    installed = {str(p.relative_to(origin.parent)): sha(p.read_bytes()) for p in origin.parent.rglob('*')
                 if p.is_file() and '__pycache__' not in p.parts}
    assert all(installed[name.removeprefix('docmancer/')] == digest
               for name, digest in inputs.items() if name.startswith('docmancer/'))
    save(out / 'FREEZE.json', dict(code_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
        inputs_sha256=inputs, installed_files_sha256=installed, origin=str(origin), python=sys.version,
        dependencies={d.metadata['Name']: d.version for d in importlib.metadata.distributions()},
        config=dict(cap=12000, calls=4, prepares=2, wall_seconds=600, call_seconds=120,
                    offline=True, models=0, pairs='off/on; identical root/generation/state'),
        authorization='User request: current-head P03/E01 diagnostic and feasibility, no product changes'))
    data = repo / 'eval/prepared_model_comparison40'
    cases, families = load_dataset(data)
    selected = [c for c in cases if c['id'] in ('V40-P03', 'V40-E01')]
    results = []

    def measure(payload):
        wire = json.dumps(payload, ensure_ascii=False).encode()
        return dict(utf8_bytes=len(wire), utf8_div4=math.ceil(len(wire)/4),
                    codec_tokens=projection_token_count(wire), cost=experimental_context_cost(payload),
                    wire_sha256=sha(wire))

    def breakdown(payload):
        # Exact additive byte attribution by empty-snippet and empty-sources
        # counterfactuals. Token deltas are ordered counterfactuals, not byte shares.
        empty_text = deepcopy(payload)
        for row in empty_text['sources']:
            row['snippet'] = ''
        envelope = {**empty_text, 'sources': []}
        base, metadata, full = map(measure, (envelope, empty_text, payload))
        common = {k: v for k, v in payload['sources'][0].items() if k != 'snippet'
                  and all(row.get(k) == v and k in row for row in payload['sources'])} if payload['sources'] else {}
        normalized = deepcopy(payload)
        normalized['source_defaults'] = common
        for row in normalized['sources']:
            for key in common:
                del row[key]
        restored = deepcopy(normalized)
        defaults = restored.pop('source_defaults')
        restored['sources'] = [{**defaults, **row} for row in restored['sources']]
        assert restored == payload
        save(out / (current_id + '-normalized-diagnostic.json'), normalized)
        return dict(full=full, envelope=base, empty_snippets=metadata,
            byte_parts=dict(envelope=base['utf8_bytes'], source_metadata=metadata['utf8_bytes']-base['utf8_bytes'],
                            escaped_snippets=full['utf8_bytes']-metadata['utf8_bytes']),
            ordered_codec_deltas=dict(envelope=base['codec_tokens'], source_metadata=metadata['codec_tokens']-base['codec_tokens'],
                                      escaped_snippets=full['codec_tokens']-metadata['codec_tokens']),
            raw_snippets=dict(utf8_bytes=sum(len(row['snippet'].encode()) for row in payload['sources']),
                              standalone_codec_tokens=sum(projection_token_count(row['snippet'].encode()) for row in payload['sources'])),
            top_level_fields={k: measure({k: v}) for k, v in payload.items() if k != 'sources'},
            common_fields=common, normalized=measure(normalized), lossless_roundtrip=True,
            compatibility='New source_defaults schema requires negotiated decoder. Not backward-compatible as a drop-in.')

    class Observer(BoundaryObserver):
        def profile(self, frame, event, result):
            super().profile(frame, event, result)
            if event != 'return' or self.active is None:
                return
            name = frame.f_code.co_name
            if name == 'recheck_experimental_context' and frame.f_back.f_code.co_name != 'enforce_experimental_context_budget':
                payload, snapshot = result
                from docmancer.docs.application.projection_decision_trace import _flow_row
                self.emit('source_recheck.output', count=len(payload.get('sources', [])), rows=[
                    dict(public=row, binding=_flow_row(row, snapshot[row['evidence_id']]['source'])) for row in payload.get('sources', [])])
            if name != 'enforce_experimental_context_budget':
                return
            local = frame.f_locals
            # Same-call real validators need live request-owned discovery receipts.
            # Only independent copies are rebuilt; returned product DTO is untouched.
            payload, snapshot, retrieval = deepcopy((local['payload'], local['snapshot'], local['retrieval']))
            evaluator = load('independent_oracle', data / 'evaluate.py')
            gold = next(c for c in json.loads((data / 'gold_spans.json').read_text())['cases'] if c['id'] == current_id)
            prepared = dict(root=str(root), sources={})
            for path, text in documents.items():
                raw = text.encode()
                offsets = [0]
                for line in text.splitlines(keepends=True):
                    offsets.append(offsets[-1] + len(line))
                prepared['sources'][path] = dict(raw=raw, content=text, sha256=sha(raw), line_offsets=offsets, errors=[])
            verified, intervals, errors = evaluator._source_rows(payload, prepared)
            before_gold = evaluator._gold(case, gold, prepared, intervals)
            wanted = []
            for row, check in zip(payload['sources'], verified):
                if any(part['path'] == check['relative_path'] and any(a < prepared['sources'][part['path']]['line_offsets'][part['line_end']]
                    and b > prepared['sources'][part['path']]['line_offsets'][part['line_start']-1]
                    for a, b in check['guaranteed_coverage_intervals'])
                    for claim in before_gold['claims'] for witness in claim['witness_sets'] for part in witness['parts']):
                    wanted.append(row)
            diagnostic, binding = _rebuild(payload, snapshot, retrieval, wanted, reason='budget_limited')
            validation_errors = validate_model_visible_projection(diagnostic, snapshot=binding)
            checked, checked_binding = recheck_experimental_context(diagnostic, binding, retrieval, restore_native=False)
            assert checked == diagnostic and set(checked_binding) == set(binding)
            check_experimental_context_budget(checked)
            _, witness_intervals, witness_errors = evaluator._source_rows(checked, prepared)
            final_rows, final_intervals, final_errors = evaluator._source_rows(result[0], prepared)
            save(out / (current_id + '-feasible-packet.json'), checked)
            self.diagnostic = dict(before_gold=before_gold, original_final_gold=evaluator._gold(case, gold, prepared, final_intervals),
                projection_errors=validation_errors, source_errors=errors + witness_errors + final_errors,
                feasible_gold=evaluator._gold(case, gold, prepared, witness_intervals), feasible=measure(checked),
                selected_whole_ids=[r['evidence_id'] for r in wanted], real_recheck_pass=True, real_budget_checker_pass=True,
                public_budget=breakdown(result[0]), prebudget=measure(payload),
                feasibility_is_not_product_improvement=True)

    with deadline(600):
        for family in families:
            for case in [c for c in selected if c['project_group'] == family['id']]:
                current_id = case['id']
                root = work / family['id'] / 'project'
                documents = {name: (source_directory(data, family['id']) / name).read_text() for name in family['paths']}
                runtime.write_project(root, documents)
                with runtime.isolated_service(work / family['id'] / 'state') as (service, config):
                    with deadline(180):
                        inventory = runtime.index_project(service, config, root)
                    save(out / (current_id + '-preparation.json'), dict(root=str(root), inventory=inventory))
                    initial_db, initial_files = database(inventory['storage_path']), files(root)
                    pair = {}
                    for arm in ('off', 'on'):
                        os.environ.update(DOCATLAS_EXPERIMENT_CONTEXT_MAX_TOKENS='12000', HF_HUB_OFFLINE='1')
                        arguments = dict(question=case['question'], project_path=str(root), scope='project')
                        observer = Observer(out / 'boundaries')
                        old_profile = sys.getprofile()
                        stderr = io.StringIO()
                        try:
                            with redirect_stderr(stderr), query_trace(arm == 'on'), deadline(120):
                                if arm == 'on':
                                    sys.setprofile(observer.profile)
                                pair[arm] = call_docs_tool_payload('get_docs_context', arguments, service)
                        finally:
                            sys.setprofile(old_profile)
                        save(out / (current_id + '-' + arm + '-public.json'), pair[arm])
                        assert not integrity(pair[arm], root, documents)['errors']
                        assert database(inventory['storage_path']) == initial_db and files(root) == initial_files
                        if arm == 'on':
                            assert not observer.errors and len(observer.events) > 0
                            save(out / (current_id + '-trace.json'), dict(events=observer.events, errors=observer.errors))
                            results.append(dict(case_id=current_id, observer_output_exact_equal=pair['off'] == pair['on'],
                                off=measure(pair['off']), on=measure(pair['on']), read_only=True,
                                diagnostic=observer.diagnostic, observer_events=len(observer.events)))
    assert all(sha((repo / p).read_bytes()) == digest for p, digest in inputs.items())
    save(out / 'MEASUREMENTS.json', dict(cases=results, frozen_inputs_unchanged=True, contexts=4, prepares=2,
        extra_live_diagnostic_rechecks=2, model_calls=0, boundary='installed public in-process MCP; not stdio/client/production'))


if __name__ == '__main__':
    main()
