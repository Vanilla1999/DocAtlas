"""Audit-classifier controls, not product/gold replacements."""
import ast
import json

from p0_structural_classification import classify_node


def main():
    cases = [
        ("{'timeout': 'deadline'}", False),
        ("{'close menu': closeMenu}", False),
        ("{'timeout': source.deadline}", False),
        ("{'query': source.query}", True),
        ("{'query': query}", True),
        ("{'query': translated_query}", False),
        ("{'sources': list(packet.sources)}", True),
        ("{'permission': True, 'run': True}", False),
        ("{'scope': source.scope, 'freshness': source.freshness}", True),
        ("Literal['project', 'module', 'all']", True),
        ("['run', 'execute', 'invoke']", False),
        ("query.startswith('run ')", False),
    ]
    rows = []
    for expression, expected in cases:
        tree = ast.parse(expression, mode="eval")
        parent = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        node = tree.body.slice if isinstance(tree.body, ast.Subscript) else tree.body
        decision = classify_node(node, path="unreviewed/module.py", assignment=[], parent=parent)
        assert (decision is not None) == expected, expression
        rows.append({"expression": expression, "technical_candidate": decision is not None})
    print(json.dumps({"checks": rows, "passed": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
