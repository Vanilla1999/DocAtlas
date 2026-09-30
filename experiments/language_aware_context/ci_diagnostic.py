"""Run reviewed development questions through the real handler and save raw DTOs.

No profile, expansion, agent response or independent holdout is simulated here.
A missing answer is a measurement, not a reason to change the source or query.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path


TASKS = (
    ('typer-mixed', 'typer',
     'Как записать только отрицательное имя boolean option: важен ли пробел перед /?',
     'declare only negative name boolean option is space before slash significant'),
    ('typer-ru', 'typer',
     'Как записать только отрицательное имя логического параметра: важен ли пробел перед косой чертой?',
     'declare only negative name boolean option is space before slash significant'),
    ('typer-en', 'typer',
     'How to declare only the negative name for a boolean option: is the space before / significant?',
     'declare only negative name boolean option is space before slash significant'),
    ('httpx-default', 'httpx',
     'Какое поведение timeout по умолчанию в HTTPX: сколько секунд и какое исключение?',
     'HTTPX default timeout how many seconds which exception'),
    ('httpx-disable-client', 'httpx',
     'Как отключить all timeouts для HTTPX Client: какой аргумент передать?',
     'disable all timeouts HTTPX Client which argument to pass'),
)
# Labels are read only AFTER retrieval. They must never enter planner/ingestion.
CLAIMS = {
    'typer': ('docs/tutorial/parameter-types/bool.md', (
        'only *CLI option* names to set the `False` value',
        'use a space and a single `/` and pass the negative name after')),
    'httpx-default': ('docs/advanced/timeouts.md', (
        'default behavior', 'TimeoutException', '5 seconds', 'network inactivity')),
    'httpx-disable-client': ('docs/advanced/timeouts.md', (
        'httpx.Client(timeout=None)', 'Disable all timeouts by default')),
}


def claim_check(result: dict, path: str, clauses: tuple[str, ...]) -> dict:
    """One complete relationship requires one canonical quote, not keyword union.

    This is a narrow, preregistered DEVELOPMENT check, not a general semantic judge.
    Its precondition is the real handler's canonical/source/budget audit.
    """
    if (not isinstance(path, str) or not path or not isinstance(clauses, tuple)
            or not clauses or any(not isinstance(c, str) or not c for c in clauses)
            or len(set(clauses)) != len(clauses)):
        raise ValueError('invalid required-claim clauses')
    budget = result.get('budget_tokens')
    if (result.get('status') != 'EXECUTED' or result.get('audit_errors') != []
            or type(budget) is not int or not 0 <= budget <= 800):
        return {'status': 'NOT_EVALUABLE', 'quality_evidence': False}
    sources = result.get('payload', {}).get('sources')
    if not isinstance(sources, list):
        return {'status': 'NOT_EVALUABLE', 'quality_evidence': False}
    quotes = [s['snippet'] for s in sources if isinstance(s, dict)
              and s.get('path_or_url') == path and isinstance(s.get('snippet'), str)]
    complete = any(all(c in quote for c in clauses) for quote in quotes)
    partial = any(c in quote for quote in quotes for c in clauses)
    return {'status': 'COMPLETE' if complete else 'PARTIAL' if partial else 'ABSENT',
            'quality_evidence': True, 'criterion': 'one_canonical_quote_all_clauses'}


def run_suite(output: Path) -> int:
    from .baseline_probe import environment, run, write_report
    from eval.evidence_quality_v2.run import documents_for, load_protocol

    # Refuse to overwrite prior evidence. A failed suite remains inspectable.
    output.mkdir(parents=True, exist_ok=False)
    env = environment()
    root = Path(__file__).resolve().parents[2]
    if not env.get('git_revision'):
        raise RuntimeError('a full checkout with a known revision is required')
    _, _, manifest = load_protocol()
    rows = []
    for task_id, project, question, lookup in TASKS:
        # documents_for checks the source manifest's pinned byte hashes.
        documents = documents_for(project, manifest)
        spec = {'schema_version': 1, 'sources': [
            {'path': path, 'sha256': sha256(text.encode()).hexdigest()}
            for path, text in sorted(documents.items())]}
        corpus = root / 'eval/evidence_quality_v2/sources' / project
        for variant, lookups in (('original_only', []), ('supplied_lookup', [lookup])):
            request = {'question': question, 'lookup_queries': lookups}
            try:
                observed = run(corpus, spec, request)
            except Exception as exc:
                observed = {'status': 'EXECUTION_ERROR',
                            'exception_type': type(exc).__name__, 'message': str(exc),
                            'audit_errors': None, 'budget_tokens': None,
                            'environment': env}
            path, clauses = CLAIMS['typer' if project == 'typer' else task_id]
            observation = claim_check(observed, path, clauses)
            observed.update(task_id=task_id, variant=variant,
                            development_claim=observation,
                            planner_origin='manual_reviewed_development',
                            independent_holdout=False, agent_evaluation='NOT_MEASURED')
            name = f'{task_id}-{variant}.json'
            write_report(output / name, observed)
            rows.append({'task_id': task_id, 'variant': variant,
                         'execution_status': observed['status'],
                         'claim_status': observation['status'],
                         'budget_tokens': observed.get('budget_tokens'), 'artifact': name})
    manifest_out = {'schema_version': 1, 'evaluation_kind': 'real_handler_development',
                    'environment': env, 'rows': rows, 'independent_holdout': False,
                    'agent_evaluation': 'NOT_MEASURED', 'H1': None, 'H2': None, 'H3': None,
                    'note': 'Supplied lookups are not live planning or a profile ablation.'}
    write_report(output / 'summary.json', manifest_out)
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    # A missed fact is expected diagnostic data; a runtime/audit failure is not.
    return 1 if any(r['execution_status'] != 'EXECUTED' for r in rows) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    return run_suite(args.output)


if __name__ == '__main__':
    raise SystemExit(main())
