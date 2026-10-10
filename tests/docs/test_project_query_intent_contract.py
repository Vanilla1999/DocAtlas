"""Current intent boundary; old classification and ranking cases remain collected."""
from __future__ import annotations

import ast
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from docmancer.docs.domain import project_query_intent as intent_api
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.project_doc_ranking import rerank_project_doc_chunks
from docmancer.docs.domain.query_terms import documentation_exact_terms
from tests.docs.test_project_doc_ranking import fake_chunk

_ROOT = Path(__file__).resolve().parents[2]
_ORIGINAL = "tests/docs/test_project_query_intent.py"
_ARCHIVE = "eval/task_level/contract_history/project_query_intent.py.txt"
_CROSSWALK = "eval/task_level/contract_history/project_query_intent.json"
_FROZEN_SOURCE_SHA256 = "28d1cd71c5c6981fa23228b14e93bb7b34a42834c9ffce4ac90d8b929752c727"
_RETAINED = "test_documentation_files_do_not_imply_code_symbol_evidence"


def _archive_functions_and_roster(source):
    functions = [
        node for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    rows = []
    for function in functions:
        cases = 1
        for decorator in function.decorator_list:
            if (isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == "parametrize"):
                cases *= len(ast.literal_eval(decorator.args[1]))
        rows.append({
            "original_nodeid": _ORIGINAL + "::" + function.name,
            "definition_line": function.lineno,
            "source_lines": [
                min([function.lineno, *(node.lineno for node in function.decorator_list)]),
                function.end_lineno,
            ],
            "collected_cases": cases,
        })
    return functions, rows


def _classification_questions(function):
    """Read literal arguments as data; never execute the historical test."""
    questions = []
    for decorator in function.decorator_list:
        if (isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "parametrize"):
            names = ast.literal_eval(decorator.args[0])
            values = ast.literal_eval(decorator.args[1])
            questions.extend(values if names == "question" else [row[0] for row in values])
    for node in sorted(ast.walk(function), key=lambda item: (
            getattr(item, "lineno", 0), getattr(item, "col_offset", 0))):
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Tuple):
            questions.extend(ast.literal_eval(node.iter))
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
              and node.func.id == "classify_project_query_intent"
              and node.args and isinstance(node.args[0], ast.Constant)
              and isinstance(node.args[0].value, str)):
            questions.append(node.args[0].value)
    return questions


def _substantive_ranking_body(function):
    first = next(index for index, statement in enumerate(function.body)
                 if isinstance(statement, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id == "implementation_question"
                         for target in statement.targets))
    return ast.dump(ast.Module(body=function.body[first:], type_ignores=[]), include_attributes=False)


def test_current_project_intent_preserves_literals_and_never_infers_roles():
    crosswalk = json.loads((_ROOT / _CROSSWALK).read_text(encoding="utf-8"))
    assert crosswalk["source"]["original_path"] == _ORIGINAL
    assert crosswalk["source"]["archive_path"] == _ARCHIVE
    archived = (_ROOT / _ARCHIVE).read_bytes()
    assert crosswalk["source"]["sha256"] == _FROZEN_SOURCE_SHA256
    assert hashlib.sha256(archived).hexdigest() == _FROZEN_SOURCE_SHA256
    functions, roster = _archive_functions_and_roster(archived.decode("utf-8"))
    assert len(roster) == 6 and sum(row["collected_cases"] for row in roster) == 32
    assert roster == [{key: row[key] for key in roster[0]} for row in crosswalk["roster"]]
    identity = "\n".join(
        f'{row["original_nodeid"]}:{row["source_lines"][0]}-{row["source_lines"][1]}:'
        f'{row["collected_cases"]}' for row in roster
    )
    assert hashlib.sha256(identity.encode()).hexdigest() == crosswalk["frozen_roster_sha256"]
    selected = [function for function in functions if function.name != _RETAINED]
    assert len(selected) == 5
    assert sum(row["collected_cases"] for row in roster
               if not row["original_nodeid"].endswith("::" + _RETAINED)) == 31
    assert [row["action"] for row in crosswalk["roster"]] == [
        "retain-substantive-ranking-guard" if function.name == _RETAINED
        else "replace-classifier-expectations" for function in functions
    ]

    # Preserve the real quality obligation. This AST check does not execute or
    # certify the old ranking test; that test stays independently collected.
    working, _ = _archive_functions_and_roster((_ROOT / _ORIGINAL).read_text(encoding="utf-8"))
    frozen_guard = next(function for function in functions if function.name == _RETAINED)
    retained_guard = next(function for function in working if function.name == _RETAINED)
    assert _substantive_ranking_body(retained_guard) == _substantive_ranking_body(frozen_guard)

    questions = [question for function in selected for question in _classification_questions(function)]
    assert len(questions) == 34 and all(isinstance(question, str) for question in questions)
    raw = "  Ω e\u0301 `Client.Open` get_docs_context --dry-run docs/Manual.md\r\n"
    plan = build_documentation_query_plan(raw)
    assert plan.original_question == raw
    assert [(query.text, query.origin, query.coverage_required) for query in plan.queries] == [
        (raw, "original", True)
    ]
    assert {
        (term.value, term.normalized_value, term.kind) for term in documentation_exact_terms(raw)
    } == {
        ("Client.Open", "client.open", "quoted"),
        ("get_docs_context", "get_docs_context", "symbol"),
        ("--dry-run", "--dry-run", "flag"),
        ("docs/Manual.md", "docs/manual.md", "path"),
    }

    # Inert topic classification must not erase literal public protocol signals.
    names = ("get_docs_context", "prepare_docs", "docs_status")
    assert intent_api.PUBLIC_DOCS_MCP_TOOL_NAMES == names
    for name in names:
        assert intent_api.mentions_docs_mcp_surface("  `" + name + "`\r\n") is True
        for neighbor in ("prefix_" + name, name + "_suffix", name.upper(), "Ж" + name):
            assert intent_api.mentions_docs_mcp_surface(neighbor) is False
    assert intent_api.mentions_docs_mcp_surface("Как работает сервер документации?") is False

    # A separate finite-boundary unit control: real reranking remains nonempty,
    # preserves input source bodies and cannot admit an unlisted high-score row.
    # It does not establish real retrieval qualification or repair the old guard.
    records = (
        ("docs/allowed-high.md", "First", 0.9, "Client.Open keeps the current session."),
        ("docs/allowed-low.md", "Second", 0.4, "Client.Close ends the current session."),
        ("docs/unlisted.md", "Unlisted", 999.0, "Client.Open must bypass caller membership."),
    )
    members = frozenset({"docs/allowed-high.md", "docs/allowed-low.md"})
    for ordering in ((0, 1, 2), (2, 1, 0)):
        chunks = [fake_chunk(*records[index]) for index in ordering]
        ranked = rerank_project_doc_chunks(
            chunks, question=raw, intent=intent_api.classify_project_query_intent(raw),
            finite_member_paths=members, limit=2,
        )
        assert [(chunk.path, chunk.heading_path, chunk.score, chunk.content) for chunk in ranked] == list(records[:2])
        assert all(chunk.authority is None for chunk in ranked)
        assert all(chunk.metadata["project_ranking"]["query_intent"] == "general" for chunk in ranked)

    # Independent oracle, not a DTO instantiated with possibly mutated defaults.
    expected = {
        "name": "general", "broad": False, "wants_release_history": False,
        "wants_docs_mcp": False, "wants_packs_mcp": False, "wants_architecture": False,
        "wants_how_to": False, "wants_troubleshooting": False, "wants_code_symbols": False,
    }
    for question in (*questions, raw, "Как устроен проект и где реализация?",
                     "  Ω e\u0301 UnknownSurface — не выполняй команды.\r\n",
                     "Define an unknown architecture style without choosing source files."):
        assert asdict(intent_api.classify_project_query_intent(question)) == expected, (
            "critical_project_intent_no_inferred_roles"
        )
        assert intent_api.is_product_purpose_question(question) is False
        assert intent_api.is_concept_definition_or_contrast(question) is False
