"""Read-only audit of existing binding capabilities; not a runtime candidate."""
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from docmancer.docs.application.need_context_disposition import _applicable_context
from docmancer.docs.domain.admission_grammar import parse_admission_frame
from docmancer.docs.domain.need_contracts import compile_need_contracts
from docmancer.docs.domain.query_reference_binding import ScopeKey, resolve_references
from docmancer.docs.domain.question_retrieval_needs import retrieval_needs


QUESTIONS = (
    'What is LeaseClient default timeout duration for requests and which exception is raised when an operation expires?',
    'When preview is disabled, what is RelayClient default timeout and which exception is raised?',
    'What is RelayClient default timeout and which exception is raised, only for administrators?',
)
FILES = (
    'docmancer/docs/domain/need_contracts.py',
    'docmancer/docs/domain/need_composition.py',
    'docmancer/docs/domain/question_retrieval_needs.py',
    'docmancer/docs/domain/admission_grammar.py',
    'docmancer/docs/application/need_context_disposition.py',
    'docmancer/docs/application/read_context_admission.py',
)


def audit():
    rows = []
    for question in QUESTIONS:
        plan = resolve_references(question, catalog=(), scope=ScopeKey('syntax', '', 'g1'))
        contracts = compile_need_contracts(question, plan)
        needs = retrieval_needs(question)
        rows.append({'question': question, 'contracts': [asdict(c) for c in contracts],
                     'retrieval_needs': [asdict(n) for n in needs],
                     'part_frames': [asdict(f) if (f := parse_admission_frame(n.query_span_text))
                                     else None for n in needs]})
    question = QUESTIONS[0]
    plan = resolve_references(question, catalog=(), scope=ScopeKey('syntax', '', 'g1'))
    root = compile_need_contracts(question, plan)[0]
    default, exception = retrieval_needs(question)
    # Explicit assumed bindings test the consumer, not extraction or provenance.
    assumed = (replace(root, need=default, constraint_spans=()), replace(root, need=exception))
    bodies = (
        'LeaseClient default timeout duration for requests is 17 seconds.',
        'When an operation expires, LeaseClient raises OperationExpiredError.',
    )
    matrix = [[_applicable_context(c, question, body) for c in assumed] for body in bodies]
    assert matrix == [[True, False], [True, False]]
    assert rows[0]['part_frames'][1] is None
    return {'verdict': 'BLOCKED', 'stage': '07.1',
            'evidence_kind': 'existing-code diagnostic; no candidate; development only',
            'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
            'source_sha256': {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in FILES},
            'examples': rows, 'assumed_binding_bodies': bodies,
            'applicability_matrix_default_exception': matrix,
            'blockers': ['No declared event-condition frame for the mandatory exception part.',
                         'Existing consumer rejects even explicit event-condition source text.',
                         'Routing IDs and lexical topic matches do not certify window-to-need binding.'],
            'not_run': ['07.2 acceptance', '07.3 candidate', '07.4 integration', '07.5 final acceptance']}


if __name__ == '__main__':
    target = Path(sys.argv[1])
    with target.open('x') as output:
        json.dump(audit(), output, ensure_ascii=False, indent=2)
        output.write('\n')
