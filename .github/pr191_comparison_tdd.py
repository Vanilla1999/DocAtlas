from __future__ import annotations

import argparse, ast, hashlib, json
from pathlib import Path

NEW_TEST='tests/docs/test_comparison_relation_query_planning.py'
NEW_MANIFEST='tests/diagnostic_labels.comparison_relation_query_planning.json'
OLD_TEST='tests/docs/test_query_planning_budget_regressions.py'
OLD_MANIFEST='tests/diagnostic_labels.query_planning.json'


def replace_once(path, old, new):
    p=Path(path); text=p.read_text(encoding='utf-8')
    if text.count(old)!=1: raise AssertionError((path,text.count(old)))
    p.write_text(text.replace(old,new,1),encoding='utf-8')


def digest(module):
    tree=ast.parse(Path(module).read_text(encoding='utf-8')); nodes=[]
    for n in tree.body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith('test_'):
            nodes.append(f'{module}::{n.name}')
        elif isinstance(n,ast.ClassDef) and n.name.startswith('Test'):
            for m in n.body:
                if isinstance(m,(ast.FunctionDef,ast.AsyncFunctionDef)) and m.name.startswith('test_'):
                    nodes.append(f'{module}::{n.name}::{m.name}')
    return hashlib.sha256('\n'.join(sorted(nodes)).encode()).hexdigest()


def refresh_manifest(path,module):
    p=Path(path); d=json.loads(p.read_text(encoding='utf-8'))
    if module not in d['module_node_hashes']: raise AssertionError((path,module))
    d['module_node_hashes'][module]=digest(module)
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def write_tests():
    Path(NEW_TEST).write_text(r'''from docmancer.docs.application.evidence_selection import build_requirements
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan


def test_comparison_lookup_keeps_relation_semantics_in_cross_side_probe():
    question = "How do alpha documentation and beta documentation differ in retrieval scope and provenance?"
    plan = build_documentation_query_plan(
        question, requirements=build_requirements(question, profile="project_docs_answer")
    )
    relation = [q.text.casefold() for q in plan.queries if q.query_id.startswith("query-relation-")]
    assert len(relation) <= 4
    assert any(
        "alpha documentation beta documentation" in q
        and "different" in q and "separate" in q
        for q in relation
    )
    # Search vocabulary is relation-only; it must not inject a domain answer.
    assert not any(word in " ".join(relation) for word in ("manifest", "lockfile", "repository-owned"))
''',encoding='utf-8')
    Path(NEW_MANIFEST).write_text(json.dumps({
        'schema_version':1,'module_labels':{NEW_TEST:'behavioral'},'node_overrides':{},
        'module_node_hashes':{NEW_TEST:digest(NEW_TEST)}},indent=2)+'\n',encoding='utf-8')


def apply_fix():
    replace_once(
        'docmancer/docs/domain/documentation_query_plan.py',
        'value = f"{left_value} {right_value}".strip()\n                if value and supplemental_query_is_useful(value):',
        'value = f"{left_value} {right_value} different separate".strip()\n                if value and supplemental_query_is_useful(value):',
    )
    # The prior regression intentionally froze the old cross-side text. Update
    # only those assertions to keep the same <=4-slot contract while requiring
    # the newly preserved relation; the two axis probes remain unchanged.
    replace_once(
        OLD_TEST,
        '    assert "project documentation dependency documentation" in relation\n    assert "project documentation library documentation" in relation\n',
        '    assert "project documentation dependency documentation different separate" in relation\n    assert "project documentation library documentation different separate" in relation\n',
    )
    refresh_manifest(OLD_MANIFEST,OLD_TEST)


def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=('tests','fix'));a=p.parse_args()
    write_tests() if a.phase=='tests' else apply_fix()
if __name__=='__main__': main()
