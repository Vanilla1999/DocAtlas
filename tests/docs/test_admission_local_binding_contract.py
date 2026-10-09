"""Current default-binding ABI precheck; historical cases remain collected."""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from docmancer.docs.domain import admission_local_binding as binding
from docmancer.docs.application import retrieval_need_support as support

_ROOT = Path(__file__).resolve().parents[2]
_ORIGINAL = "tests/docs/test_admission_local_binding.py"
_ARCHIVE = "eval/task_level/contract_history/admission_local_binding.py.txt"
_CROSSWALK = "eval/task_level/contract_history/admission_local_binding.json"
_SOURCE_SHA256 = "e3eec4a7f10584855352228cca65972f2747bb81e7d3693ec3253ac24ebcc676"
_INPUT_SHA256 = "2a1fd29dd230996a3621651b0829bf067d961f3919fa50a8e68b17372759dac3"
_TAIL = "test_recognized_condition_does_not_hide_unsupported_constraint_tail"
_GUARD_ABI = "critical_default_binding_unknown_abi"
_GUARD_VETO = "critical_default_binding_unknown_veto"
_GUARD_ORIGINAL = "critical_default_binding_nonneeds_preserved"


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fixture_query(subject="RelayClient", attribute="timeout"):
    # Independent literal fixture DTO, not a production default or an NL parser.
    assert isinstance(subject, str) and isinstance(attribute, str)
    return {
        "query_id": "need-default", "query_origin": "retrieval_need",
        "text": f"What is the default {attribute} of {subject}?",
        "need_subject": subject, "need_relation": "default",
    }


def _literal_data(node, environment):
    """Read the frozen input grammar only; never execute a test or its assertion."""
    if isinstance(node, ast.Constant):
        assert isinstance(node.value, (str, int, bool)) or node.value is None
        return node.value
    if isinstance(node, ast.Name):
        assert node.id in environment
        return environment[node.id]
    if isinstance(node, ast.Dict):
        assert all(key is not None for key in node.keys)
        return {_literal_data(key, environment): _literal_data(value, environment)
                for key, value in zip(node.keys, node.values, strict=True)}
    if isinstance(node, ast.BinOp):
        assert isinstance(node.op, ast.Add)
        left, right = _literal_data(node.left, environment), _literal_data(node.right, environment)
        assert isinstance(left, str) and isinstance(right, str)
        return left + right
    if isinstance(node, ast.JoinedStr):
        parts = []
        for part in node.values:
            if isinstance(part, ast.Constant):
                assert isinstance(part.value, str)
                parts.append(part.value)
            else:
                assert isinstance(part, ast.FormattedValue)
                assert part.conversion == -1 and part.format_spec is None
                value = _literal_data(part.value, environment)
                assert isinstance(value, (str, int, bool))
                parts.append(str(value))
        return "".join(parts)
    assert isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    assert node.func.id == "default_need" and len(node.args) <= 1
    assert all(keyword.arg in {"subject", "attribute"} for keyword in node.keywords)
    keywords = {keyword.arg: _literal_data(keyword.value, environment) for keyword in node.keywords}
    assert len(keywords) == len(node.keywords)
    assert not node.args or "subject" not in keywords
    if node.args:
        keywords["subject"] = _literal_data(node.args[0], environment)
    return _fixture_query(**keywords)


def _parameters(function):
    assert len(function.decorator_list) <= 1
    if not function.decorator_list:
        return [{}]
    decorator, = function.decorator_list
    assert isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
    assert decorator.func.attr == "parametrize" and len(decorator.args) == 2 and not decorator.keywords
    names = [name.strip() for name in ast.literal_eval(decorator.args[0]).split(",")]
    rows = ast.literal_eval(decorator.args[1])
    assert isinstance(rows, (list, tuple)) and rows
    environments = []
    for row in rows:
        values = (row,) if len(names) == 1 else row
        assert isinstance(values, (list, tuple)) and len(values) == len(names)
        environments.append(dict(zip(names, values, strict=True)))
    return environments


def _archive_inputs(source):
    functions = {node.name: node for node in ast.parse(source).body
                 if isinstance(node, ast.FunctionDef)}
    helper = functions["default_need"]
    assert [argument.arg for argument in helper.args.args] == ["subject", "attribute"]
    assert [ast.literal_eval(default) for default in helper.args.defaults] == ["RelayClient", "timeout"]
    roster, records = [], []
    for function in functions.values():
        if not function.name.startswith("test_"):
            continue
        environments = _parameters(function)
        roster.append({
            "original_nodeid": _ORIGINAL + "::" + function.name,
            "definition_line": function.lineno,
            "source_lines": [
                min([function.lineno, *(item.lineno for item in function.decorator_list)]),
                function.end_lineno,
            ],
            "collected_cases": len(environments),
        })
        for index, parameters in enumerate(environments):
            environment = dict(parameters)
            for statement in function.body[:-1]:
                assert isinstance(statement, ast.Assign) and len(statement.targets) == 1
                target, = statement.targets
                value = _literal_data(statement.value, environment)
                if isinstance(target, ast.Name):
                    environment[target.id] = value
                else:
                    assert isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
                    assert target.value.id == "query" and ast.literal_eval(target.slice) == "text"
                    environment["query"]["text"] = value
            statement = function.body[-1]
            assert isinstance(statement, ast.Assert) and statement.msg is None
            comparison = statement.test
            assert isinstance(comparison, ast.Compare) and len(comparison.ops) == 1
            assert len(comparison.comparators) == 1
            operator, = comparison.ops
            assert isinstance(operator, (ast.Is, ast.IsNot))
            call = comparison.left
            assert isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
            assert call.func.id == "retrieval_need_local_witness" and len(call.args) == 2
            assert len(call.keywords) <= 1 and all(item.arg == "source" for item in call.keywords)
            query = _literal_data(call.args[0], environment)
            body = _literal_data(call.args[1], environment)
            source_metadata = _literal_data(call.keywords[0].value, environment) if call.keywords else None
            old_expected = _literal_data(comparison.comparators[0], environment)
            assert isinstance(query, dict) and isinstance(body, str) and type(old_expected) is bool
            records.append({
                "original_nodeid": _ORIGINAL + "::" + function.name, "case_index": index,
                "query": deepcopy(query), "body": body, "source": source_metadata,
                # Retained history, never the oracle for the current API.
                "historical_assertion": {
                    "operator": "is_not" if isinstance(operator, ast.IsNot) else "is",
                    "value": old_expected,
                },
            })
    return functions, roster, records


def _carried_trace(query, body):
    return {
        "query_id": query["query_id"], "query_text": query["text"],
        "qualified": True, "qualification_reason": "inherited_parent_claim",
        "source_key": "fixture/default.md", "diagnostic_tag": "preserve-this-value",
        "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "need_local_witness": True, "admission_route": "inherited_default",
        "matched_need_ids": ["inherited-need"], "need_witness_spans": [[0, len(body)]],
        "need_witness_source_key": "claimed-owner",
        "_admission_demands": [{"operator": "default", "unsupported_spans": []}],
        "context_eligible": True, "context_need_ids": ["inherited-need"],
        "_need_context": {"inherited": True},
    }


def test_current_default_binding_keeps_unknown_without_inherited_need_credit():
    crosswalk = json.loads((_ROOT / _CROSSWALK).read_text(encoding="utf-8"))
    assert crosswalk["source"]["original_path"] == _ORIGINAL
    assert crosswalk["source"]["archive_path"] == _ARCHIVE
    archived = (_ROOT / _ARCHIVE).read_bytes()
    assert hashlib.sha256(archived).hexdigest() == crosswalk["source"]["sha256"] == _SOURCE_SHA256
    functions, roster, records = _archive_inputs(archived.decode("utf-8"))
    assert len(roster) == 16 and sum(row["collected_cases"] for row in roster) == 43
    assert len(records) == 43
    assert roster == [{key: row[key] for key in roster[0]} for row in crosswalk["roster"]]
    identity = "\n".join(
        f'{row["original_nodeid"]}:{row["source_lines"][0]}-{row["source_lines"][1]}:'
        f'{row["collected_cases"]}' for row in roster
    )
    assert hashlib.sha256(identity.encode("utf-8")).hexdigest() == crosswalk["frozen_roster_sha256"]
    assert hashlib.sha256(_canonical(records).encode("utf-8")).hexdigest() == _INPUT_SHA256
    assert crosswalk["frozen_input_roster_sha256"] == _INPUT_SHA256
    assert [row["action"] for row in crosswalk["roster"]] == [
        "retain-live-unsupported-tail-guard" if row["original_nodeid"].endswith("::" + _TAIL)
        else "replace-inferred-default-expectations" for row in roster
    ]
    working = {node.name: node for node in ast.parse(
        (_ROOT / _ORIGINAL).read_text(encoding="utf-8")).body if isinstance(node, ast.FunctionDef)}
    for name in ("default_need", _TAIL):
        assert ast.dump(working[name], include_attributes=False) == ast.dump(
            functions[name], include_attributes=False)

    # Positive pass-through comes first: an always-empty adapter must fail this
    # exact guard, not merely a later absence-of-need-credit assertion.
    raw = " \tWhat is the default timeout of RelayClient? Ω e\u0301\r\n"
    for origin in ("original", "host_lookup"):
        query = {"query_id": "query-" + origin, "query_origin": origin, "text": raw}
        trace = _carried_trace(query, "RelayClient default timeout is 7 seconds.\n")
        before = deepcopy({"query": query, "trace": trace})
        result = support.apply_retrieval_need_witness(query, trace, "unrelated body")
        assert result == before["trace"], _GUARD_ORIGINAL
        assert {"query": query, "trace": trace} == before

    for record in records:
        query, body, source = deepcopy(record["query"]), record["body"], deepcopy(record["source"])
        original_inputs = deepcopy({"query": query, "body": body, "source": source})
        assert binding.default_property(query) is None
        assert binding.bound_default_units(query, body) is None
        decision, spans = binding.default_local_witness(query, body)
        assert decision is None and spans == (), _GUARD_ABI
        assert support.retrieval_need_local_witness(query, body, source=source) is None, _GUARD_ABI
        trace = _carried_trace(query, body)
        trace_before = deepcopy(trace)
        expected = {
            "query_id": query["query_id"], "query_text": query["text"],
            "qualified": False, "qualification_reason": "missing_need_local_witness",
            "source_key": "fixture/default.md", "diagnostic_tag": "preserve-this-value",
            "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        }
        actual = support.apply_retrieval_need_witness(query, trace, body, source=source)
        assert actual == expected, _GUARD_VETO
        assert trace == trace_before
        assert {"query": query, "body": body, "source": source} == original_inputs

    # Existing rejection and invalid-input boundaries are distinct from unknown proof.
    query = _fixture_query()
    trace = _carried_trace(query, "fixture body")
    trace.update(qualified=False, qualification_reason="upstream_rejected")
    rejected = support.apply_retrieval_need_witness(query, trace, "fixture body")
    assert rejected == {
        "query_id": "need-default", "query_text": "What is the default timeout of RelayClient?",
        "qualified": False, "qualification_reason": "upstream_rejected",
        "source_key": "fixture/default.md", "diagnostic_tag": "preserve-this-value",
        "body_sha256": hashlib.sha256(b"fixture body").hexdigest(),
    }
    for text, source in [("", None), (" \t\r\n", None), (None, None), ("fixture body", [])]:
        invalid = support.apply_retrieval_need_witness(
            query, _carried_trace(query, "fixture body"), text, source=source,
        )
        assert invalid == {
            "query_id": "need-default", "query_text": "What is the default timeout of RelayClient?",
            "qualified": False, "qualification_reason": "invalid_need_witness_input",
            "source_key": "fixture/default.md", "diagnostic_tag": "preserve-this-value",
            "body_sha256": hashlib.sha256(b"fixture body").hexdigest(),
        }
