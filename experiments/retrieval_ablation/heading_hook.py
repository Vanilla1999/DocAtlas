"""Diagnostic one-body-match heading control; never a production policy."""
from contextlib import contextmanager
import ast
import hashlib
import inspect
import sys


@contextmanager
def one_body_match_heading_context(*, phase='all'):
    if phase not in ('all', 'admission', 'final'):
        raise ValueError('unsupported heading intervention phase')
    from docmancer.docs.domain import evidence_qualification as gate
    original = gate.qualify_evidence
    source = inspect.getsource(original)
    tree = ast.parse(source)
    expected = ast.dump(ast.parse('len(body_matched) >= 2', mode='eval').body)
    changes = []

    class Change(ast.NodeTransformer):
        def visit_Compare(self, node):
            if ast.dump(node) == expected:
                changes.append(node)
                return ast.copy_location(ast.parse('len(body_matched) >= 1', mode='eval').body, node)
            return self.generic_visit(node)

    tree = Change().visit(tree)
    if len(changes) != 1:
        raise ValueError('heading hook does not match production gate')
    namespace = dict(original.__globals__)
    exec(compile(ast.fix_missing_locations(tree), '<ablation-heading-one-match>', 'exec'), namespace)
    changed = namespace['qualify_evidence']
    stats = {'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
             'changed_comparisons': 1, 'qualification_calls': 0,
             'call_sites': {},
             'phase': phase,
             'kind': 'diagnostic_heading_two_to_one_body_match'}

    def invoke(*args, **kwargs):
        stats['qualification_calls'] += 1
        frame = inspect.currentframe().f_back
        try:
            chain = []
            for _ in range(3):
                if frame is None:
                    break
                filename = frame.f_code.co_filename.replace('\\', '/')
                for prefix in ('docmancer/', 'experiments/'):
                    if prefix in filename:
                        filename = prefix + filename.split(prefix, 1)[1]
                        break
                chain.append(f'{filename}:{frame.f_code.co_name}:{frame.f_lineno}')
                frame = frame.f_back
            site = ' <- '.join(chain)
        finally:
            del frame
        active = (phase == 'all' or
                  (phase == 'admission' and ':prepare:' in site) or
                  (phase == 'final' and ':pack:' in site))
        result = changed(*args, **kwargs) if active else original(*args, **kwargs)
        baseline = original(*args, **kwargs)
        counts = stats['call_sites'].setdefault(site, {
            'calls': 0, 'baseline_qualified': 0, 'intervention_qualified': 0,
            'gained': 0, 'lost': 0})
        counts['calls'] += 1
        counts['baseline_qualified'] += int(baseline.qualified)
        counts['intervention_qualified'] += int(result.qualified)
        counts['gained'] += int(result.qualified and not baseline.qualified)
        counts['lost'] += int(baseline.qualified and not result.qualified)
        return result

    def aliases(function):
        for name, module in tuple(sys.modules.items()):
            if module is not None and name.startswith(('docmancer.', 'experiments.retrieval_ablation.')):
                for key, value in tuple(vars(module).items()):
                    if value is function:
                        yield module, key

    for module, key in aliases(original):
        setattr(module, key, invoke)
    try:
        yield stats
    finally:
        for module, key in aliases(invoke):
            setattr(module, key, original)
