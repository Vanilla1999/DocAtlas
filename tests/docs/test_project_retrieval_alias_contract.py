"""One current alias contract; historical questions remain a byte-bound archive."""
from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path

from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan, technical_anchors
from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases

_ROOT = Path(__file__).resolve().parents[2]
_CROSSWALK = "eval/task_level/contract_history/direct_question_retrieval_intents.json"
_FROZEN_SOURCE_SHA256 = "23e0e84815cf887cdd1ab5bd4c4caa550580982e9b5fd52ae9a2beb4075c7791"


_CONTEXT7_CROSSWALK = "eval/task_level/contract_history/context7_newcomer_alias_inputs.json"
_CONTEXT7_ORIGINAL = "tests/docs/test_context7_style_project_chat.py"
_CONTEXT7_ARCHIVE = "eval/task_level/contract_history/context7_newcomer_alias_inputs.py.txt"
_CONTEXT7_FUNCTION = "test_russian_newcomer_queries_get_retrieval_only_aliases"
_CONTEXT7_SOURCE_SHA256 = "a573bb62e7546920dd4738456b860420ce8db72fe359b6f1d61ebccfbb3f16b8"
_CONTEXT7_ROSTER_SHA256 = "39591084bef65604349d5f6237066b9a2492c1d83c4f38dbf033ba2bceee9f81"
_CONTEXT7_INPUT_SHA256 = "eb8a4ac593d8659f59a8081d5140109dd2684b5a23c3abd9c66c198fcd9820c6"
_PRIOR_QUESTIONS_SHA256 = "fad4c95805cf51cd3257f244b00c81d3be13a6b116efa962904dd555d1aaa186"
_ALL_QUESTIONS_SHA256 = "77a8c8ff1372debd437a24fe1ca43ffeff6c9453907dfd534cd71714205ed7e1"

_PLAN_INPUT_CROSSWALK = "eval/task_level/contract_history/documentation_query_plan_explicit_inputs.json"
_PLAN_INPUT_ARCHIVE = "eval/task_level/contract_history/documentation_query_plan_explicit_inputs.py.txt"
_PLAN_INPUT_ORIGINAL = "tests/docs/test_documentation_query_plan.py"
_PLAN_INPUT_FUNCTIONS = (
    "test_documentation_query_plan_owns_public_retrieval_query_ids",
    "test_documentation_query_plan_owns_retrieval_only_alias_lineage",
    "test_same_text_lookups_retain_independent_public_and_canonical_ids",
)
_PLAN_INPUT_SOURCE_SHA256 = "bb96a79c3005efd943b4f5bb11b4b8fdaf17c5d5cfcae871968870b55e0b9109"
_PLAN_INPUT_ROSTER_SHA256 = "7577838d21c2121b60804f1e1c798cd5f87303477bb96ca5b0f801a5f12e23d1"
_PLAN_INPUT_RECORDS_SHA256 = "ee96d2abc69481735513a82a70a7db2d6b3729fb5612db2b6e7247292591d3c5"

_COMPILER_CROSSWALK = "eval/task_level/contract_history/documentation_query_plan_compiler_retirement.json"
_COMPILER_ROSTER_SHA256 = "b910fa3dd979b133e630c45aa35c4b71fd66d5c62f95094422120c993d057b60"
_COMPILER_RECORDS_SHA256 = "4c28bcbe98ec8fbb338555a7a45536139c60ace5dcfd2643b1cd12ae4bec6047"


_RELATION_COMPILER_CROSSWALK = "eval/task_level/contract_history/admission_relation_compiler_inputs.json"
_RELATION_COMPILER_SOURCE_SHA256 = "34620c11c83e58dad640b4ee56711830de9ab3ba18ca0c64e88e6f26ffea2809"
_RELATION_COMPILER_ROSTER_SHA256 = "8f70e346a0c0cb4ba2e4580d715637895d10ebe1b11ccd4e6ebafdd7fc9ffbae"
_RELATION_COMPILER_INPUT_SHA256 = "c75cba6725098b2ca036a47634091f015a5917c3c5b10bed88a001f57b1b474b"
_RELATION_COMPILER_REPRESENTATIVE_SHA256 = "5943d52139a599c91cebfe3eddb1eab73fde67287d509fc3af9524c359ef57b7"

def _input_digest(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _context7_questions(prior_questions):
    crosswalk = json.loads((_ROOT / _CONTEXT7_CROSSWALK).read_text(encoding="utf-8"))
    assert crosswalk["source"]["original_path"] == _CONTEXT7_ORIGINAL
    assert crosswalk["source"]["archive_path"] == _CONTEXT7_ARCHIVE
    frozen = (_ROOT / _CONTEXT7_ARCHIVE).read_bytes()
    assert hashlib.sha256(frozen).hexdigest() == crosswalk["source"]["sha256"] == _CONTEXT7_SOURCE_SHA256
    archived_nodes = ast.parse(frozen.decode("utf-8")).body
    function, = [node for node in archived_nodes
                 if isinstance(node, ast.FunctionDef) and node.name == _CONTEXT7_FUNCTION]
    decorator, = function.decorator_list
    assert isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
    assert decorator.func.attr == "parametrize" and len(decorator.args) == 2 and not decorator.keywords
    assert ast.literal_eval(decorator.args[0]) == ("question", "intent_id")
    # Read literal decorator inputs, never import the old module or execute its assertions.
    rows = ast.literal_eval(decorator.args[1])
    assert isinstance(rows, list) and len(rows) == 21
    assert all(isinstance(row, tuple) and len(row) == 2
               and all(isinstance(value, str) for value in row) for row in rows)
    records = [{
        "case_index": index, "question": question, "historical_intent_id": intent_id,
        "question_sha256": hashlib.sha256(question.encode("utf-8")).hexdigest(),
    } for index, (question, intent_id) in enumerate(rows)]
    roster = {
        "original_nodeid": _CONTEXT7_ORIGINAL + "::" + _CONTEXT7_FUNCTION,
        "definition_line": function.lineno,
        "source_lines": [decorator.lineno, function.end_lineno], "collected_cases": len(rows),
    }
    assert roster == crosswalk["selected_function"]
    identity = (f'{roster["original_nodeid"]}:{roster["source_lines"][0]}-'
                f'{roster["source_lines"][1]}:{roster["collected_cases"]}')
    assert hashlib.sha256(identity.encode("utf-8")).hexdigest() == (
        crosswalk["frozen_selected_roster_sha256"]) == _CONTEXT7_ROSTER_SHA256
    assert records == crosswalk["inputs"]
    assert _input_digest(records) == crosswalk["frozen_input_roster_sha256"] == _CONTEXT7_INPUT_SHA256
    assert list(prior_questions) == crosswalk["prior_questions"]
    assert _input_digest(prior_questions) == crosswalk["prior_questions_sha256"] == _PRIOR_QUESTIONS_SHA256
    questions = tuple(question for question, _historical_intent in rows)
    assert len(set(questions)) == 21 and not set(questions).intersection(prior_questions)
    assert _input_digest((*prior_questions, *questions)) == (
        crosswalk["combined_questions_sha256"]) == _ALL_QUESTIONS_SHA256

    # The selected family may be retired only in a later reviewed change. Every
    # other node, including imports, helper class and native quality tests, stays.
    working_nodes = ast.parse((_ROOT / _CONTEXT7_ORIGINAL).read_text(encoding="utf-8")).body
    def outside_selected(node):
        return not (isinstance(node, ast.FunctionDef) and node.name == _CONTEXT7_FUNCTION)
    assert [ast.dump(node, include_attributes=False) for node in working_nodes if outside_selected(node)] == [
        ast.dump(node, include_attributes=False) for node in archived_nodes if outside_selected(node)
    ]
    working_selected = [node for node in working_nodes if not outside_selected(node)]
    assert len(working_selected) <= 1
    if working_selected:
        assert ast.dump(working_selected[0], include_attributes=False) == ast.dump(
            function, include_attributes=False)
    return questions


def _compiler_precheck_inputs(archived_nodes, working_nodes, selected_node, archived_source):
    crosswalk = json.loads((_ROOT / _COMPILER_CROSSWALK).read_text(encoding="utf-8"))
    assert crosswalk["protocol"] == "documentation-query-compiler-retirement-v1"
    assert crosswalk["source"] == {
        "original_path": _PLAN_INPUT_ORIGINAL, "archive_path": _PLAN_INPUT_ARCHIVE,
        "git_blob_sha": "25de8f3898ba60a33a08425d3e045353fa8014f9",
        "sha256": _PLAN_INPUT_SOURCE_SHA256,
    }
    roster = crosswalk["roster"]
    assert _input_digest(roster) == crosswalk["frozen_roster_sha256"] == _COMPILER_ROSTER_SHA256
    assert len(roster) == 12
    assert sum(row["collected_cases"] for row in roster) == 35
    assert sum(row["retired_cases"] for row in roster) == 30
    assert sum(row["retained_cases"] for row in roster) == 5
    functions = {node.name: node for node in archived_nodes if isinstance(node, ast.FunctionDef)}
    retired_names, partial = set(), {}
    source_lines = archived_source.splitlines()
    for row in roster:
        function = functions[row["function"]]
        assert row["original_nodeid"] == _PLAN_INPUT_ORIGINAL + "::" + function.name
        start = min([function.lineno, *(node.lineno for node in function.decorator_list)])
        assert row["definition_line"] == function.lineno
        assert row["source_lines"] == [start, function.end_lineno]
        frozen_function = "\n".join(source_lines[start - 1:function.end_lineno])
        assert hashlib.sha256(frozen_function.encode("utf-8")).hexdigest() == row["source_sha256"]
        count = 1
        for decorator in function.decorator_list:
            assert isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
            assert decorator.func.attr == "parametrize"
            assert len(decorator.args) == 2 and not decorator.keywords
            count *= len(ast.literal_eval(decorator.args[1]))
        assert count == row["collected_cases"]
        removed, kept = row["retired_case_indices"], row["retained_case_indices"]
        assert sorted(removed + kept) == list(range(count)) and not set(removed).intersection(kept)
        assert len(removed) == row["retired_cases"] and len(kept) == row["retained_cases"]
        if kept:
            assert row["action"] == "retain_exact_negative_parameter_rows"
            decorator, = function.decorator_list
            assert isinstance(decorator.args[1], ast.List)
            partial[function.name] = kept
        else:
            assert row["action"] == "retire_obsolete_compiler_function"
            retired_names.add(function.name)
    assert len(retired_names) == 10
    assert partial == {
        "test_exact_project_facets_and_negative_neighbors": [6, 8],
        "test_audited_installation_equivalence_is_complete_and_bounded": [1, 2, 3],
    }
    exact = functions["test_exact_project_facets_and_negative_neighbors"]
    values = ast.literal_eval(exact.decorator_list[0].args[1])
    assert [values[index] for index in partial[exact.name]] == [
        ("Где находятся модули?", set()), ("Какие инструменты нужны для ремонта?", set()),
    ]
    installation = functions["test_audited_installation_equivalence_is_complete_and_bounded"]
    values = ast.literal_eval(installation.decorator_list[0].args[1])
    assert [values[index] for index in partial[installation.name]] == [
        (" и объяснить архитектуру?", False),
        (" и проверить неизвестный контракт?", False),
        (" с UnknownLedger?", False),
    ]

    # DQP3 is checked separately. Every other node must match one complete state;
    # partial retirements, changed bodies, decorators, helpers or imports do not match.
    frozen_other = [node for node in archived_nodes if not selected_node(node)]
    retired_other = []
    for node in frozen_other:
        if isinstance(node, ast.FunctionDef) and node.name in retired_names:
            continue
        if isinstance(node, ast.FunctionDef) and node.name in partial:
            node = copy.deepcopy(node)
            rows = node.decorator_list[0].args[1]
            rows.elts = [rows.elts[index] for index in partial[node.name]]
        retired_other.append(node)
    actual = [ast.dump(node, include_attributes=False)
              for node in working_nodes if not selected_node(node)]
    precheck = [ast.dump(node, include_attributes=False) for node in frozen_other]
    retirement = [ast.dump(node, include_attributes=False) for node in retired_other]
    assert actual == precheck or actual == retirement, "critical_compiler_retirement_exact_scope"

    records = crosswalk["representative_inputs"]
    assert len(records) == 2
    assert _input_digest(records) == crosswalk["representative_inputs_sha256"] == _COMPILER_RECORDS_SHA256
    compound = functions["test_alias_budget_is_fair_across_requested_facets"]
    calls = sorted([
        node for node in ast.walk(compound) if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name) and node.func.id == "build_project_retrieval_aliases"
    ], key=lambda node: (node.lineno, node.col_offset))
    assert len(calls) == 2
    equivalent = functions["test_only_audited_complete_equivalence_derives_original"]
    assignment, = [
        node for node in equivalent.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "question" for target in node.targets)
    ]
    originals = (ast.literal_eval(calls[0].args[0]), ast.literal_eval(assignment.value))
    for index, record in enumerate(records):
        assert record["case_index"] == index and record["archive_question_index"] == 0
        function = (compound, equivalent)[index]
        assert record["original_nodeid"] == _PLAN_INPUT_ORIGINAL + "::" + function.name
        assert record["question"] == originals[index]
        assert record["question_sha256"] == hashlib.sha256(originals[index].encode("utf-8")).hexdigest()
    assert records[0]["lookup_queries"] == []
    assert records[1]["lookup_queries"] == [originals[1]]
    return records


def _explicit_plan_inputs():
    crosswalk = json.loads((_ROOT / _PLAN_INPUT_CROSSWALK).read_text(encoding="utf-8"))
    assert crosswalk["source"]["original_path"] == _PLAN_INPUT_ORIGINAL
    assert crosswalk["source"]["archive_path"] == _PLAN_INPUT_ARCHIVE
    frozen = (_ROOT / _PLAN_INPUT_ARCHIVE).read_bytes()
    assert hashlib.sha256(frozen).hexdigest() == crosswalk["source"]["sha256"] == _PLAN_INPUT_SOURCE_SHA256
    archived_nodes = ast.parse(frozen.decode("utf-8")).body
    functions = [node for node in archived_nodes
                 if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")]
    counts = []
    for function in functions:
        count = 1
        for decorator in function.decorator_list:
            assert isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
            assert decorator.func.attr == "parametrize"
            count *= len(ast.literal_eval(decorator.args[1]))
        counts.append(count)
    assert len(functions) == 29 and sum(counts) == 70
    selected = [node for node in functions if node.name in _PLAN_INPUT_FUNCTIONS]
    assert [node.name for node in selected] == list(_PLAN_INPUT_FUNCTIONS)
    actual = [{
        "original_nodeid": _PLAN_INPUT_ORIGINAL + "::" + function.name,
        "definition_line": function.lineno,
        "source_lines": [function.lineno, function.end_lineno],
        "collected_cases": 1,
    } for function in selected]
    assert actual == crosswalk["selected_functions"]
    identity = "\n".join(
        f'{row["original_nodeid"]}:{row["source_lines"][0]}-'
        f'{row["source_lines"][1]}:{row["collected_cases"]}' for row in actual
    )
    assert hashlib.sha256(identity.encode("utf-8")).hexdigest() == (
        crosswalk["frozen_selected_roster_sha256"]) == _PLAN_INPUT_ROSTER_SHA256
    records = crosswalk["inputs"]
    assert len(records) == 3
    assert _input_digest(records) == crosswalk["frozen_input_roster_sha256"] == _PLAN_INPUT_RECORDS_SHA256
    for index, (function, record) in enumerate(zip(selected, records, strict=True)):
        assert not function.decorator_list
        call, = [
            node for node in ast.walk(function) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name) and node.func.id == "build_documentation_query_plan"
        ]
        assert len(call.args) == 1
        keyword, = call.keywords
        assert keyword.arg == "lookup_queries"
        question, lookups = ast.literal_eval(call.args[0]), ast.literal_eval(keyword.value)
        assert isinstance(question, str) and isinstance(lookups, tuple)
        assert all(isinstance(value, str) for value in lookups)
        assert len(lookups) == (5, 1, 3)[index]
        assert record["case_index"] == index and record["original_nodeid"] == actual[index]["original_nodeid"]
        assert record["question"] == question and record["lookup_queries"] == list(lookups)
        assert record["question_sha256"] == hashlib.sha256(question.encode("utf-8")).hexdigest()
        assert record["lookup_sha256s"] == [hashlib.sha256(value.encode("utf-8")).hexdigest() for value in lookups]

    # Preserve every unselected test/import/helper; do not execute the archive.
    # Selected tests remain live for precheck and may leave only in a later reviewed slice.
    working_nodes = ast.parse((_ROOT / _PLAN_INPUT_ORIGINAL).read_text(encoding="utf-8")).body
    def selected_node(node):
        return isinstance(node, ast.FunctionDef) and node.name in _PLAN_INPUT_FUNCTIONS
    compiler_inputs = _compiler_precheck_inputs(
        archived_nodes, working_nodes, selected_node, frozen.decode("utf-8"),
    )
    working_selected = [node for node in working_nodes if selected_node(node)]
    assert len(working_selected) in (0, 3)
    if working_selected:
        assert [ast.dump(node, include_attributes=False) for node in working_selected] == [
            ast.dump(node, include_attributes=False) for node in selected
        ]
    return records, compiler_inputs


def _relation_compiler_inputs():
    crosswalk = json.loads((_ROOT / _RELATION_COMPILER_CROSSWALK).read_text(encoding="utf-8"))
    assert crosswalk["protocol"] == "admission-relation-compiler-precheck-v1"
    original = "tests/docs/test_admission_relation_witnesses.py"
    archive = "eval/task_level/contract_history/admission_relation_compiler_inputs.py.txt"
    assert crosswalk["source"] == {
        "original_path": original, "archive_path": archive,
        "git_blob_sha": "f230beaa41ebb0b999f97493007fe253c629ef78",
        "sha256": _RELATION_COMPILER_SOURCE_SHA256,
    }
    frozen = (_ROOT / archive).read_bytes()
    assert hashlib.sha256(frozen).hexdigest() == _RELATION_COMPILER_SOURCE_SHA256
    source = frozen.decode("utf-8")
    archived = ast.parse(source).body
    working = ast.parse((_ROOT / original).read_text(encoding="utf-8")).body
    names = (
        "test_local_relation_not_question_word_overlap",
        "test_new_lexical_family_and_markdown_layout",
    )
    selected = [node for node in archived if isinstance(node, ast.FunctionDef) and node.name in names]
    assert [node.name for node in selected] == list(names)
    all_nodes = [ast.dump(node, include_attributes=False) for node in archived]
    removed_nodes = [ast.dump(node, include_attributes=False) for node in archived
                     if not (isinstance(node, ast.FunctionDef) and node.name in names)]
    actual_nodes = [ast.dump(node, include_attributes=False) for node in working]
    # This also binds CASES, probe, qualify, every import and all 47 other cases.
    assert actual_nodes == all_nodes or actual_nodes == removed_nodes, "critical_relation_retirement_exact_scope"
    roster = crosswalk["selected_functions"]
    assert _input_digest(roster) == crosswalk["frozen_roster_sha256"] == _RELATION_COMPILER_ROSTER_SHA256
    assert len(roster) == 2 and sum(row["collected_cases"] for row in roster) == 25
    source_lines = source.splitlines()
    for function, row, count in zip(selected, roster, (20, 5), strict=True):
        start = min([function.lineno, *(node.lineno for node in function.decorator_list)])
        assert row["function"] == function.name and row["original_nodeid"] == original + "::" + function.name
        assert row["definition_line"] == function.lineno and row["source_lines"] == [start, function.end_lineno]
        assert row["collected_cases"] == count and row["action"] == "future_retire_generated_typed_relation_expectation"
        text = "\n".join(source_lines[start - 1:function.end_lineno])
        assert hashlib.sha256(text.encode("utf-8")).hexdigest() == row["source_sha256"]

    cases_assignment, = [node for node in archived if isinstance(node, ast.Assign)
                         and any(isinstance(target, ast.Name) and target.id == "CASES" for target in node.targets)]
    cases = ast.literal_eval(cases_assignment.value)
    assert len(cases) == 5 and all(len(row) == 5 and all(isinstance(value, str) for value in row) for row in cases)
    first, second = selected
    assert len(first.decorator_list) == 3 and len(second.decorator_list) == 1
    for decorator in (*first.decorator_list, *second.decorator_list):
        assert isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
        assert decorator.func.attr == "parametrize" and len(decorator.args) == 2 and not decorator.keywords
    assert [ast.literal_eval(node.args[0]) for node in first.decorator_list] == [
        "english,russian,body,opposite,operator", "language", "answer",
    ]
    family_node = first.decorator_list[0].args[1]
    assert isinstance(family_node, ast.Name) and family_node.id == "CASES"
    languages = ast.literal_eval(first.decorator_list[1].args[1])
    answers = ast.literal_eval(first.decorator_list[2].args[1])
    assert languages == ["en", "ru"] and answers == ["first", "other"]
    layout_decorator, = second.decorator_list
    assert ast.literal_eval(layout_decorator.args[0]) == "question,body"
    layouts = ast.literal_eval(layout_decorator.args[1])
    assert len(layouts) == 5 and all(len(row) == 2 and all(isinstance(value, str) for value in row) for row in layouts)
    # Expand literal archive data, never the retired probe/qualify/test bodies.
    records = []
    for answer in answers:
        for language in languages:
            for family, row in enumerate(cases):
                question, body = row[0 if language == "en" else 1], row[2 if answer == "first" else 3]
                records.append({
                    "original_nodeid": original + "::" + names[0], "case_index": len(records),
                    "case_family_index": family, "language": language, "answer": answer,
                    "question": question, "body": body, "operator": row[4],
                    "question_sha256": hashlib.sha256(question.encode("utf-8")).hexdigest(),
                    "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                    "historical_assertion": {
                        "qualified": True, "admission_route": "typed_local", "nonempty_source_witness_spans": True,
                    },
                })
    for index, (question, body) in enumerate(layouts):
        records.append({
            "original_nodeid": original + "::" + names[1], "case_index": index,
            "question": question, "body": body,
            "question_sha256": hashlib.sha256(question.encode("utf-8")).hexdigest(),
            "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "historical_assertion": {"qualified": True, "admission_route": "typed_local"},
        })
    assert len(records) == 25 and records == crosswalk["archived_inputs"]
    assert _input_digest(records) == crosswalk["frozen_input_roster_sha256"] == _RELATION_COMPILER_INPUT_SHA256
    representatives = crosswalk["representative_inputs"]
    assert len(representatives) == 2
    assert _input_digest(representatives) == crosswalk["representative_inputs_sha256"] == _RELATION_COMPILER_REPRESENTATIVE_SHA256
    for index, (record, archived_record) in enumerate(zip(representatives, (records[6], records[24]), strict=True)):
        assert record["case_index"] == index and record["archive_nodeid"] == archived_record["original_nodeid"]
        assert record["archive_case_index"] == archived_record["case_index"]
        assert record["question"] == archived_record["question"]
        assert record["question_sha256"] == archived_record["question_sha256"] and record["lookup_queries"] == []
    return representatives


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
    context7_questions = _context7_questions(questions)
    lookup = "  `OtherTool.open` selected documentation passage\r\n"
    for question in (*questions, *context7_questions):
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

    # These three unchanged request fixtures add five-slot and duplicate-slot coverage.
    # Expected rows are frozen literal records, not an instance using producer defaults.
    plan_inputs, compiler_inputs = _explicit_plan_inputs()
    for record in plan_inputs:
        plan = build_documentation_query_plan(
            record["question"], lookup_queries=tuple(record["lookup_queries"]),
        )
        rows = [[row.query_id, row.text, row.origin, row.relation, row.coverage_required]
                for row in plan.queries]
        assert rows == record["expected_rows"], record["guard"]
        payload = plan.as_payload()
        assert plan.original_question == payload["original_question"] == record["question"], record["guard"]
        assert [[row["query_id"], row["text"], row["origin"], row["relation"], row["coverage_required"]]
                for row in payload["queries"]] == record["expected_rows"], record["guard"]
        assert payload["query_ids"] == payload["public_query_ids"] == record["expected_public_query_ids"], record["guard"]
        assert payload["required_query_ids"] == record["expected_required_query_ids"], record["guard"]
        assert not plan.explicit_paths and not plan.component_contract and plan.component_scope_complete is False
        for row in plan.queries:
            assert row.public_parent_query_id is None
            assert row.preferred_catalog_roles == row.forbidden_catalog_roles == ()
            assert row.forbidden_evidence_terms == row.parent_exact_terms == ()
            assert row.need_subject is row.need_relation is row.need_context is None
        for literal in record["required_literal_identifiers"]:
            assert literal in technical_anchors(record["question"]), "critical_explicit_query_literal_identity"

    # A real nonempty alias DTO produced by the directed production mutant must
    # fail here. Blanketing the query plan with an empty result fails above.
    for question in questions:
        assert build_project_retrieval_aliases(question) == (), "critical_alias_no_generated_queries"

    # This scoped topic-router fault is dormant for the three prior inputs.
    # All 24 original/explicit-lookup positive controls have already passed.
    for question in context7_questions:
        assert build_project_retrieval_aliases(question) == (), "critical_context7_no_topic_router_aliases"

    # Two independent representatives, not a replay of the 35 historical cases.
    # Earlier alias/intent/lookup controls keep their own first-failure markers.
    for record in compiler_inputs:
        question, guard = record["question"], record["guard"]
        original_only = build_documentation_query_plan(question)
        assert [[row.query_id, row.text, row.origin, row.relation, row.coverage_required]
                for row in original_only.queries] == record["expected_original_rows"], guard
        plan = (build_documentation_query_plan(question, lookup_queries=tuple(record["lookup_queries"]))
                if record["lookup_queries"] else original_only)
        assert [[row.query_id, row.text, row.origin, row.relation, row.coverage_required]
                for row in plan.queries] == record["expected_rows"], guard
        for current in (original_only, plan):
            assert current.original_question == question, guard
            assert current.component_contract == () and current.component_scope_complete is False, guard
            for row in current.queries:
                assert row.public_parent_query_id is None, guard
                assert row.preferred_catalog_roles == row.forbidden_catalog_roles == (), guard
                assert row.forbidden_evidence_terms == row.parent_exact_terms == (), guard
                assert row.need_subject is row.need_relation is row.need_context is None, guard
        payload = plan.as_payload()
        assert payload["original_question"] == question, guard
        assert [[row["query_id"], row["text"], row["origin"], row["relation"], row["coverage_required"]]
                for row in payload["queries"]] == record["expected_rows"], guard
        assert payload["query_ids"] == payload["public_query_ids"] == record["expected_public_query_ids"], guard
        assert payload["required_query_ids"] == record["expected_required_query_ids"], guard
        assert all(row["public_parent_query_id"] is None for row in payload["queries"]), guard
        assert build_project_retrieval_aliases(question) == (), guard

    # Two raw representatives cover the removed relation-lane generator. The
    # 25 frozen source/answer rows above are data, not hidden qualification runs.
    for record in _relation_compiler_inputs():
        question, guard = record["question"], record["guard"]
        plan = build_documentation_query_plan(question)
        assert [[row.query_id, row.text, row.origin, row.relation, row.coverage_required]
                for row in plan.queries] == record["expected_rows"], guard
        assert plan.original_question == question, guard
        original, = plan.queries
        assert original.public_parent_query_id is None, guard
        assert original.need_subject is original.need_relation is original.need_context is None, guard
        assert original.preferred_catalog_roles == original.forbidden_catalog_roles == (), guard
        assert original.forbidden_evidence_terms == original.parent_exact_terms == (), guard
        assert plan.component_contract == () and plan.component_scope_complete is False, guard
        assert plan.as_payload() == record["expected_payload"], guard
