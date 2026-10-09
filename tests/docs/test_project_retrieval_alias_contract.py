"""One current alias contract; historical questions remain a byte-bound archive."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases

_ROOT = Path(__file__).resolve().parents[2]
_CROSSWALK = "eval/task_level/contract_history/direct_question_retrieval_intents.json"
_FROZEN_SOURCE_SHA256 = "23e0e84815cf887cdd1ab5bd4c4caa550580982e9b5fd52ae9a2beb4075c7791"


def test_current_alias_boundary_preserves_explicit_queries_without_inference():
    crosswalk = json.loads((_ROOT / _CROSSWALK).read_text(encoding="utf-8"))
    assert crosswalk["source"]["original_path"] == "tests/docs/test_direct_question_retrieval_intents.py"
    assert crosswalk["source"]["archive_path"] == (
        "eval/task_level/contract_history/direct_question_retrieval_intents.py.txt"
    )
    archive = _ROOT / crosswalk["source"]["archive_path"]
    frozen = archive.read_bytes()
    assert crosswalk["source"]["sha256"] == _FROZEN_SOURCE_SHA256
    assert hashlib.sha256(frozen).hexdigest() == _FROZEN_SOURCE_SHA256
    # Parse the archive as data. Its historical assertions are never executed
    # by this control; its original module was also collected during precheck.
    functions = [
        node for node in ast.parse(frozen.decode("utf-8")).body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    actual = []
    for function in functions:
        cases = 1
        for decorator in function.decorator_list:
            if (isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == "parametrize"):
                cases *= len(ast.literal_eval(decorator.args[1]))
        actual.append({
            "original_nodeid": crosswalk["source"]["original_path"] + "::" + function.name,
            "definition_line": function.lineno,
            "source_lines": [
                min([function.lineno, *(node.lineno for node in function.decorator_list)]),
                function.end_lineno,
            ],
            "collected_cases": cases,
        })
    assert len(actual) == 19 and sum(row["collected_cases"] for row in actual) == 49
    assert actual == [
        {key: row[key] for key in actual[0]} for row in crosswalk["roster"]
    ]
    roster_identity = "\n".join(
        f'{row["original_nodeid"]}:{row["source_lines"][0]}-{row["source_lines"][1]}:'
        f'{row["collected_cases"]}' for row in actual
    )
    assert hashlib.sha256(roster_identity.encode()).hexdigest() == crosswalk["frozen_roster_sha256"]

    # Independent original-input oracle: preserve exact text, including Unicode,
    # spacing and an unknown tool. Explicit lookup text is authored by the caller.
    questions = (
        "What is the recommended sequence of MCP tool calls for answering a normal project documentation question?",
        "Как устроен полный процесс работы Docs MCP?",
        "  Ω e\u0301 `OtherTool.  open` — где описание неизвестного вызова?\r\n",
    )
    lookup = "  `OtherTool.open` selected documentation passage\r\n"
    for question in questions:
        original_only = build_documentation_query_plan(question)
        explicit = build_documentation_query_plan(
            question, lookup_queries=(lookup,), explicit_path="docs/manual.md",
        )
        assert original_only.original_question == explicit.original_question == question
        assert [row.text for row in original_only.queries] == [question]
        assert [row.text for row in explicit.queries] == [question, lookup]
        assert explicit.explicit_paths == ("docs/manual.md",)
        original, host = explicit.queries
        assert (original.query_id, original.origin, original.relation, original.coverage_required) == (
            "query-original", "original", "direct", True,
        )
        assert (host.query_id, host.origin, host.relation, host.coverage_required) == (
            "query-lookup-1", "host_lookup", "host_lookup", False,
        )
        for row in explicit.queries:
            assert row.public_parent_query_id is None
            assert row.preferred_catalog_roles == row.forbidden_catalog_roles == ()
            assert row.forbidden_evidence_terms == row.parent_exact_terms == ()
            assert row.need_subject is row.need_relation is row.need_context is None
        assert explicit.component_contract == () and explicit.component_scope_complete is False
        assert explicit.as_payload()["required_query_ids"] == ["query-original"]

    # A real nonempty alias DTO produced by the directed production mutant must
    # fail here. Blanketing the query plan with an empty result fails above.
    for question in questions:
        assert build_project_retrieval_aliases(question) == (), "critical_alias_no_generated_queries"
