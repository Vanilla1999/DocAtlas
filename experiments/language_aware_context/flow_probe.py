"""Observe the existing frozen flow case; never change its witnesses or runtime."""
from __future__ import annotations
import argparse
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch
from .baseline_probe import environment, write_report
from .packing_experiment import packing_experiment
from .packing_probe import capture_packing_trace


def run_probe(output: Path) -> None:
    from eval.project_context_quality_v2_protocol import evaluate_case, load_cases
    from eval.evidence_quality_v2.observer import observe_call
    from scripts import run_project_docs_self_host_gate as gate
    output.mkdir(parents=True, exist_ok=False)
    case = next(row for row in load_cases() if row['id'] == 'v2-natural-request-flow')
    original_call = gate._call_with_snapshot
    for condition in ('baseline', 'packing'):
        observed = []
        def collect(arguments, service):
            with patch.object(gate, '_call_with_snapshot', original_call):
                with capture_packing_trace() as packing:
                    payload, trace = observe_call(service, arguments)
            observed.append({'arguments': arguments, 'payload': payload,
                             'trace': trace, 'packing_trace': packing})
            return {**payload, 'diagnostics': trace['bounded_diagnostics']}, trace['snapshot']
        with (packing_experiment() if condition == 'packing' else nullcontext()):
            with patch.object(gate, '_call_with_snapshot', collect):
                report = gate.run(cases=(gate.LiveCase(
                    case_id=case['id'], question=case['question'], relevant_paths=(),
                    lookup_queries=tuple(case['lookup_queries']), scope=case['scope'],
                ),), negative_cases=())
        verdict = evaluate_case(case, report['results'][0]['payload'])
        write_report(output / (condition + '.json'), {
            'environment': environment(), 'condition': condition, 'case': case,
            'report': report, 'observed': observed, 'verdict': verdict,
            'independent_holdout': False, 'production_activation': False,
        })
        print(condition, [(o['id'], o['met']) for o in verdict['obligations']], flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run_probe(parser.parse_args().output)
    return 0  # Observation completed; verdicts are NOT converted into a PASS claim.


if __name__ == '__main__':
    raise SystemExit(main())
