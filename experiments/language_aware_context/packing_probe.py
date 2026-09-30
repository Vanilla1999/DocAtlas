"""Paired DEVELOPMENT probe of one ordering intervention on viewed public tasks.

The original and lookup strings, corpus hashes, candidate/source limits, evidence
qualification and final DTO auditor are identical in both conditions. No live
planner, language hint, neighbor expansion, model answer or holdout is involved.
Raw traces are written only to a caller-supplied new directory, never committed.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager, nullcontext
from copy import deepcopy
import json
import os
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import patch

from .baseline_probe import environment, run, write_report
from .ci_diagnostic import TASKS, CLAIMS, claim_check
from .packing_experiment import REVISION, packing_experiment

MAX_EVENTS = 2048


def _span(source: Any) -> dict:
    from docmancer.docs.application.context_selection import attributable_query_ids
    source = source if isinstance(source, dict) else {}
    return {'path': source.get('path_or_url') or source.get('path'),
            'line_start': source.get('line_start'), 'line_end': source.get('line_end'),
            'snippet': source.get('snippet') or source.get('content') or '',
            'attributable_query_ids': sorted(attributable_query_ids((source,)))}


@contextmanager
def capture_packing_trace() -> Iterator[dict]:
    """Observe exact calls and decisions, without altering inputs or outputs.

    As with the adapter, this monkeypatch collector is process-local and must not
    run concurrently with other requests. Direct spans only, not hidden raw docs.
    """
    from docmancer.docs.application import _docs_context_projection_core as core
    from docmancer.docs.application import docs_context_projection as facade
    from docmancer.docs.application import joint_context_selection as joint
    from docmancer.docs.application import query_block_context as blocks
    from docmancer.docs.application import query_block_recovery as recovery
    from docmancer.docs.application.projection_decision_trace import ProjectionDecisionTrace

    trace: dict[str, Any] = {'events': [], 'omitted_events': 0}
    def append(row: dict) -> None:
        if len(trace['events']) < MAX_EVENTS:
            trace['events'].append(row)
        else:
            trace['omitted_events'] += 1

    preference = core._prefer_missing_baseline_candidate
    def capture_preference(candidates, selected, *args, **kwargs):
        before = [_span(c) for c in candidates[:3]]
        result = preference(candidates, selected, *args, **kwargs)
        append({'stage': 'baseline_preference', 'before_top3': before,
                'after_top3': [_span(c) for c in candidates[:3]],
                'selected': [_span(c) for c in selected]})
        return result

    decision_record = ProjectionDecisionTrace.record
    def capture_decision(self, stage, decision, reason, candidate, variant=None, **kwargs):
        result = decision_record(self, stage, decision, reason, candidate, variant, **kwargs)
        if stage == 'selection':
            append({'stage': 'selection', 'decision': decision, 'reason': reason,
                    'variant': _span(variant or candidate),
                    'budget_tokens': kwargs.get('budget_tokens')})
        return result

    def boundary(module, name):
        fn = getattr(module, name)
        def capture(*args, **kwargs):
            result = fn(*args, **kwargs)
            append({'stage': name, 'sources': [_span(s) for s in result[0].get('sources', [])]})
            return result
        return capture

    with ExitStack() as stack:
        stack.enter_context(patch.object(core, '_prefer_missing_baseline_candidate', capture_preference))
        stack.enter_context(patch.object(ProjectionDecisionTrace, 'record', capture_decision))
        for module, name in ((facade, '_run_core'), (joint, 'select_joint_context'),
                             (blocks, 'select_query_block_context'),
                             (recovery, 'select_query_block_recovery')):
            stack.enter_context(patch.object(module, name, boundary(module, name)))
        yield trace


def run_case(corpus: Path, spec: dict, request: dict, *, candidate: bool) -> dict:
    """Real handler. The adapter receives no corpus name, labels or answer text."""
    before = deepcopy(request)
    with (packing_experiment() if candidate else nullcontext()):
        with capture_packing_trace() as trace:
            result = run(corpus, spec, request)
    if before != request:
        raise RuntimeError('probe mutated its supplied request')
    result.update(packing_trace=trace, packing_intervention=REVISION if candidate else None,
                  python_hash_seed=os.getenv('PYTHONHASHSEED'),
                  independent_holdout=False, agent_evaluation='NOT_MEASURED',
                  planner_origin='manual_reviewed_development')
    return result


def run_suite(output: Path) -> int:
    from eval.evidence_quality_v2.run import documents_for, load_protocol
    from hashlib import sha256
    output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[2]
    _, _, manifest = load_protocol()
    rows = []
    for task_id, project, question, lookup in TASKS:
        documents = documents_for(project, manifest)
        spec = {'schema_version': 1, 'sources': [
            {'path': p, 'sha256': sha256(t.encode('utf-8')).hexdigest()}
            for p, t in sorted(documents.items())]}
        for variant, lookups in (('original_only', []), ('supplied_lookup', [lookup])):
            request = {'question': question, 'lookup_queries': lookups}
            for condition in ('baseline', 'candidate'):
                try:
                    observed = run_case(root / 'eval/evidence_quality_v2/sources' / project,
                        spec, deepcopy(request), candidate=condition == 'candidate')
                except Exception as exc:
                    observed = {'status': 'EXECUTION_ERROR', 'exception_type': type(exc).__name__,
                                'audit_errors': None, 'budget_tokens': None}
                path, clauses = CLAIMS['typer' if project == 'typer' else task_id]
                outcome = claim_check(observed, path, clauses)
                observed.update(task_id=task_id, variant=variant, condition=condition,
                                development_claim=outcome)
                name = f'{task_id}-{variant}-{condition}.json'
                write_report(output / name, observed)
                row = {'task_id': task_id, 'variant': variant, 'condition': condition,
                       'execution_status': observed['status'], 'claim_status': outcome['status'],
                       'budget_tokens': observed.get('budget_tokens'), 'artifact': name}
                rows.append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
    pairs = [dict(task_id=a['task_id'], variant=a['variant'],
                  baseline=a['claim_status'], candidate=b['claim_status'])
             for a, b in zip(rows[::2], rows[1::2], strict=True)]
    losses = [p for p in pairs if p['baseline'] == 'COMPLETE' and p['candidate'] != 'COMPLETE']
    errors = [r for r in rows if r['execution_status'] != 'EXECUTED']
    summary = {'schema_version': 1, 'evaluation_kind': 'packing_development_pairs',
               'environment': environment(), 'python_hash_seed': os.getenv('PYTHONHASHSEED'),
               'intervention': REVISION, 'rows': rows, 'pairs': pairs,
               'complete_claim_losses': losses, 'execution_errors': errors,
               'independent_holdout': False, 'agent_evaluation': 'NOT_MEASURED',
               'H1': None, 'H2': None, 'H3': None, 'product_activation': False,
               'note': 'Viewed tasks and manual queries: mechanism diagnostic, not A-E acceptance.'}
    write_report(output / 'summary.json', summary)
    return int(bool(losses or errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    return run_suite(parser.parse_args().output)


if __name__ == '__main__':
    raise SystemExit(main())
