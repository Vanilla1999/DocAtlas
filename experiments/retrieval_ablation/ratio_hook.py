"""Process-local remove-one control. Never install in a concurrent MCP server."""
from __future__ import annotations

import ast
from contextlib import contextmanager
import hashlib
import inspect
import sys


@contextmanager
def without_ratio_threshold():
    """Execute the real gate with exactly its ratio comparison removed.

    Do not turn a rejected return value into approval: retain the original body,
    reference/policy checks, exact identities, nonempty matches and typed admission.
    Missing parent exact terms keep the original ratio test: that identity field
    is traced but not independently rejected by the current legacy expression.
    AST shape must match exactly or the experiment refuses to run.
    """
    from docmancer.docs.domain import evidence_qualification as module

    original = module.qualify_evidence
    source = inspect.getsource(original)
    tree = ast.parse(source)
    expected = ast.dump(ast.parse('ratio >= required_ratio', mode='eval').body)
    stats = {'changed_comparisons': 0, 'qualification_calls': 0,
             'ratio_checks': 0, 'below_threshold_checks': 0,
             'parent_exact_preserved_checks': 0,
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

    def ratio_check(ratio, required_ratio, missing_parent_exact):
        stats['ratio_checks'] += 1
        if missing_parent_exact:
            stats['parent_exact_preserved_checks'] += 1
            return ratio >= required_ratio
        stats['below_threshold_checks'] += int(ratio < required_ratio)
        return True

    namespace = {**original.__globals__, '_ablation_ratio_check': ratio_check}
    exec(compile(ast.fix_missing_locations(tree), '<ablation-ratio-only>', 'exec'), namespace)
    changed = namespace['qualify_evidence']

    def invoke(*args, **kwargs):
        stats['qualification_calls'] += 1
        return changed(*args, **kwargs)

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
