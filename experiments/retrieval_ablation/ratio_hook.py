"""Process-local remove-one control. Never install in a concurrent MCP server."""
from __future__ import annotations

import ast
from contextlib import contextmanager
import hashlib
import inspect
import sys


@contextmanager
def without_ratio_threshold(*, phase='all'):
    """Execute the real gate with exactly its ratio comparison removed.

    Do not turn a rejected return value into approval: retain the original body,
    reference/policy checks, exact identities, nonempty matches and typed admission.
    Missing parent exact terms keep the original ratio test: that identity field
    is traced but not independently rejected by the current legacy expression.
    AST shape must match exactly or the experiment refuses to run.
    """
    from docmancer.docs.domain import evidence_qualification as module

    if phase not in ('all', 'tagging', 'final'):
        raise ValueError('unsupported ratio intervention phase')

    original = module.qualify_evidence
    source = inspect.getsource(original)
    tree = ast.parse(source)
    expected = ast.dump(ast.parse('ratio >= required_ratio', mode='eval').body)
    stats = {'changed_comparisons': 0, 'qualification_calls': 0,
             'ratio_checks': 0, 'below_threshold_checks': 0,
              'parent_exact_preserved_checks': 0,
             'phase': phase, 'call_sites': {},
             'source_sha256': hashlib.sha256(source.encode()).hexdigest()}

    class RemoveRatio(ast.NodeTransformer):
        def visit_Compare(self, node):
            if ast.dump(node) != expected:
                return self.generic_visit(node)
            stats['changed_comparisons'] += 1
            return ast.copy_location(ast.Call(func=ast.Name(id='_ablation_ratio_check', ctx=ast.Load()),
                args=[ast.Name(id='ratio', ctx=ast.Load()),
                      ast.Name(id='required_ratio', ctx=ast.Load()),
                      ast.Name(id='missing_parent_exact', ctx=ast.Load())], keywords=[]), node)

    tree = RemoveRatio().visit(tree)
    if stats['changed_comparisons'] != 1:
        raise ValueError('ratio-only hook does not match the current production gate')

    active = True

    def ratio_check(ratio, required_ratio, missing_parent_exact):
        stats['ratio_checks'] += 1
        if not active:
            return ratio >= required_ratio
        if missing_parent_exact:
            stats['parent_exact_preserved_checks'] += 1
            return ratio >= required_ratio
        stats['below_threshold_checks'] += int(ratio < required_ratio)
        return True

    namespace = {**original.__globals__, '_ablation_ratio_check': ratio_check}
    exec(compile(ast.fix_missing_locations(tree), '<ablation-ratio-only>', 'exec'), namespace)
    changed = namespace['qualify_evidence']

    def invoke(*args, **kwargs):
        nonlocal active
        stats['qualification_calls'] += 1
        frame = inspect.currentframe().f_back
        try:
            caller = frame.f_code.co_name
            filename = frame.f_code.co_filename.replace('\\', '/')
            if 'docmancer/' in filename:
                filename = 'docmancer/' + filename.split('docmancer/', 1)[1]
            site = f'{filename}:{caller}:{frame.f_lineno}'
        finally:
            del frame
        prior = active
        active = (phase == 'all' or
                  (phase == 'tagging' and caller == '_tag_retrieval_query'
                   and filename.endswith('/reference_query_tagging.py')) or
                  (phase == 'final' and caller == '_requalify_visible_source'
                   and filename.endswith('/_docs_context_projection_core.py')))
        try:
            result = changed(*args, **kwargs)
            baseline = original(*args, **kwargs)
            counts = stats['call_sites'].setdefault(site, {'calls': 0, 'active_calls': 0,
                'gained': 0, 'lost': 0})
            counts['calls'] += 1
            counts['active_calls'] += int(active)
            counts['gained'] += int(result.qualified and not baseline.qualified)
            counts['lost'] += int(baseline.qualified and not result.qualified)
            return result
        finally:
            active = prior

    def aliases(function):
        for name, loaded in tuple(sys.modules.items()):
            if loaded is not None and name.startswith('docmancer.'):
                for key, value in tuple(vars(loaded).items()):
                    if value is function:
                        yield loaded, key

    for loaded, key in aliases(original):
        setattr(loaded, key, invoke)
    try:
        yield stats
    finally:
        # Includes aliases imported lazily during the handler, not only modules
        # that existed on entry. Exceptions must not leak the modified gate.
        for loaded, key in aliases(invoke):
            setattr(loaded, key, original)
