from __future__ import annotations

import argparse, ast, hashlib, json
from pathlib import Path

TEST='tests/docs/test_residual_paraphrase_query_planning.py'
MANIFEST='tests/diagnostic_labels.residual_paraphrase_query_planning.json'


def replace_once(path, old, new):
    p=Path(path); text=p.read_text(encoding='utf-8')
    if text.count(old)!=1: raise AssertionError((path,text.count(old)))
    p.write_text(text.replace(old,new,1),encoding='utf-8')


def digest(module):
    tree=ast.parse(Path(module).read_text(encoding='utf-8')); nodes=[]
    for n in tree.body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith('test_'):
            nodes.append(f'{module}::{n.name}')
    return hashlib.sha256('\n'.join(sorted(nodes)).encode()).hexdigest()


def write_tests():
    Path(TEST).write_text(r'''from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases


def _rows(question, intent):
    return [r for r in build_project_retrieval_aliases(question) if r.intent_id == intent]


def test_preparation_error_gets_subject_aware_troubleshooting_probe():
    q = "The documentation preparation task finished with an error. Should I repeat my original question now, or take another step first?"
    rows = _rows(q, "troubleshooting")
    assert len(rows) == 1
    assert rows[0].text == "documentation preparation job status terminal failed docs_status"


def test_ru_no_network_dependency_cache_question_gets_neutral_acquisition_probe():
    q = "Ноутбук не подключён к сети, а документация этой зависимости никогда не кэшировалась. Может ли обычный запрос документации загрузить её?"
    rows = _rows(q, "offline_dependency_acquisition")
    assert len(rows) == 1
    assert rows[0].text == "external dependency documentation normal retrieval network acquisition cache"
    assert _rows(q, "offline_usage")
    assert all(forbidden not in rows[0].text for forbidden in ("cannot", "must", "fetch denied", "ask user"))


def test_plain_offline_question_keeps_generic_probe_and_no_test_bias():
    rows = _rows("How does DocAtlas work in offline mode?", "offline_usage")
    assert rows
    assert rows[0].text.endswith("offline mode")
    assert "test suite" not in " ".join(r.text for r in rows)
    assert not _rows("How does DocAtlas work in offline mode?", "offline_dependency_acquisition")


def _boundary_texts(question):
    return [r.text for r in _rows(question, "documentation_scope_boundary")]


def test_ru_project_vs_external_dependency_docs_gets_diverse_neutral_boundary_probes():
    q = "Чем поиск по собственной документации этого репозитория отличается от поиска по документации внешнего пакета?"
    assert _boundary_texts(q) == [
        "project-owned documentation external dependency documentation different separate",
        "project-owned documentation repository retrieval scope provenance",
        "external dependency documentation retrieval scope provenance",
    ]


def test_en_project_vs_external_dependency_docs_uses_same_boundary_probes():
    q = "How is searching this repository's own documentation different from searching an external package's documentation?"
    assert _boundary_texts(q) == [
        "project-owned documentation external dependency documentation different separate",
        "project-owned documentation repository retrieval scope provenance",
        "external dependency documentation retrieval scope provenance",
    ]


def test_boundary_probes_do_not_inject_answer_side_mechanisms():
    q = "Чем поиск по собственной документации этого репозитория отличается от поиска по документации внешнего пакета?"
    joined = " ".join(_boundary_texts(q))
    assert all(word not in joined for word in ("manifest", "lockfile", "sync_project_docs", "prefetch"))
    assert len(_boundary_texts(q)) <= 4
''',encoding='utf-8')
    Path(MANIFEST).write_text(json.dumps({
        'schema_version':1,'module_labels':{TEST:'behavioral'},'node_overrides':{},
        'module_node_hashes':{TEST:digest(TEST)}},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def apply_fix():
    path='docmancer/docs/domain/project_retrieval_intent.py'
    replace_once(
        path,
        '    "offline_usage": (("runbook", "development", "api_contract"), ("adr", "roadmap")),\n',
        '    "offline_usage": (("runbook", "development", "api_contract"), ("adr", "roadmap")),\n'
        '    "offline_dependency_acquisition": (("overview", "api_contract", "runbook"), ("adr", "roadmap")),\n'
        '    "documentation_scope_boundary": (("runbook", "api_contract", "overview"), ("adr", "roadmap")),\n',
    )
    replace_once(
        path,
        '''    # Broad newcomer/workflow questions deliberately return docs_context.\n    if _has(tokens, "офлайн", "offline") or _has_phrase(\n        normalized, "без интернета", "без сети", "without internet", "no network",\n    ):\n        emit(\n            "offline_usage",\n            True,\n            f"{product_prefix}offline mode",\n            *((f"{product_prefix}offline test suite",) if _has(tokens, "test", "pytest", "тест") else ()),\n            *(("DOCATLAS_OFFLINE",) if _has(tokens, "test", "pytest", "тест", "docatlas_offline") else ()),\n        )''',
        '''    # Broad newcomer/workflow questions deliberately return docs_context.\n    offline_question = _has(tokens, "офлайн", "offline") or _has_phrase(\n        normalized,\n        "без интернета", "без сети", "without internet", "no network",\n        "не подключен к сети", "не подключён к сети",\n        "not connected to the network", "no network access",\n    )\n    if offline_question:\n        emit(\n            "offline_usage",\n            True,\n            f"{product_prefix}offline mode",\n            *((f"{product_prefix}offline test suite",) if _has(tokens, "test", "pytest", "тест") else ()),\n            *(("DOCATLAS_OFFLINE",) if _has(tokens, "test", "pytest", "тест", "docatlas_offline") else ()),\n        )\n        offline_subject = (\n            mentions_docs\n            and (\n                _has(tokens, "dependency", "package", "зависим", "пакет")\n                or _has(tokens, "cache", "cached", "prefetch", "кэш", "кеш")\n            )\n        )\n        if offline_subject:\n            emit(\n                "offline_dependency_acquisition",\n                True,\n                "external dependency documentation normal retrieval network acquisition cache",\n            )''',
    )
    replace_once(
        path,
        '''                "ошиб", "диагност", "troubleshoot", "fail", "stale",\n                "insufficient_evidence",''',
        '''                "ошиб", "диагност", "troubleshoot", "fail", "error", "stale",\n                "insufficient_evidence",''',
    )
    marker='''    if mentions_product and _has(tokens, "replace") and _has(tokens, "system"):\n        emit(\n            "product_boundaries",\n            True,\n            f"{product_prefix}product boundaries",\n            f"{product_prefix}does not replace",\n        )\n'''
    insertion=marker+'''    documentation_scope_boundary = (\n        mentions_docs\n        and _has(tokens, "репозитор", "repository", "project")\n        and _has(tokens, "пакет", "package", "dependency", "library", "зависим")\n        and _has(tokens, "отлич", "differ", "different", "compare", "разниц")\n    )\n    if documentation_scope_boundary:\n        emit(\n            "documentation_scope_boundary",\n            True,\n            "project-owned documentation external dependency documentation different separate",\n            "project-owned documentation repository retrieval scope provenance",\n            "external dependency documentation retrieval scope provenance",\n        )\n'''
    replace_once(path,marker,insertion)


def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=('tests','fix'));a=p.parse_args()
    write_tests() if a.phase=='tests' else apply_fix()
if __name__=='__main__': main()
