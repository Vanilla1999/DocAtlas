"""Precheck for retiring inferred admission meanings; live guards remain collected."""
from __future__ import annotations

import ast
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path

from docmancer.docs.domain import admission_meaning as meaning
from docmancer.docs.domain.admission_grammar import MeaningSlot, canonical_phrase
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.query_reference_binding import CatalogSource, ScopeKey, resolve_references

_ROOT = Path(__file__).resolve().parents[2]
_ORIGINAL = "tests/docs/test_admission_meaning.py"
_ARCHIVE = "eval/task_level/contract_history/admission_meaning.py.txt"
_CROSSWALK = "eval/task_level/contract_history/admission_meaning.json"
_FROZEN_SOURCE_SHA256 = "3ecadb74c344ba2613adcf8a1c5ecbc937a8f42e77a88e538972102238dedfd7"
_RETAINED = {
    "test_unknown_question_does_not_disappear",
    "test_question_with_an_unsupported_second_clause_is_not_fully_supported",
    "test_arguments_with_and_or_are_not_made_equivalent",
    "test_mismatched_reference_plan_cannot_verify_a_rewrite",
}
_QUOTED = ("worker.run", "for", "для", "--fast-mode", "ΣClient", "name?literal")
_GUARD = "critical_admission_meaning_no_inferred_equivalence"


def _archive_functions_and_roster(source):
    functions = [
        node for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    rows = []
    for function in functions:
        cases = 1
        for decorator in function.decorator_list:
            if (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
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


def _archived_questions(functions):
    """Read frozen literals and one explicit f-string shape, never execute old tests."""
    records, lookup_case = [], {}
    quoted_prefix, quoted_suffix = "Can a handler for `", "` be synchronous?"
    for function in functions:
        if function.name in _RETAINED:
            continue
        for decorator in function.decorator_list:
            assert isinstance(decorator, ast.Call) and decorator.func.attr == "parametrize"
            names = ast.literal_eval(decorator.args[0]).split(",")
            rows = ast.literal_eval(decorator.args[1])
            if names == ["literal"]:
                assert tuple(rows) == _QUOTED
                joined = function.body[0].value
                assert isinstance(joined, ast.JoinedStr) and len(joined.values) == 3
                left, field, right = joined.values
                assert isinstance(left, ast.Constant) and left.value == quoted_prefix
                assert isinstance(right, ast.Constant) and right.value == quoted_suffix
                assert isinstance(field, ast.FormattedValue) and isinstance(field.value, ast.Name)
                assert field.value.id == "literal" and field.conversion == -1 and field.format_spec is None
                records.extend((
                    quoted_prefix + literal + quoted_suffix,
                    (literal.casefold(),), literal,
                ) for literal in rows)
                continue
            for row in rows:
                for index, name in enumerate(names):
                    if name in {"left", "right", "question"}:
                        question = row[index]
                        literal = next((value for value in ("QueueHub", "queuehub")
                                        if "`" + value + "`" in question), None)
                        records.append((question, (literal.casefold(),) if literal else (), literal))
        if function.name == "test_only_fully_verified_reformulation_can_derive_original":
            lookup_case = {
                node.targets[0].id: ast.literal_eval(node.value)
                for node in function.body if isinstance(node, ast.Assign)
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in {"original", "good", "changed"}
            }
            assert set(lookup_case) == {"original", "good", "changed"}
            records.extend((lookup_case[name], (), None) for name in ("original", "good", "changed"))
    return records, lookup_case


def test_current_admission_meaning_preserves_literals_without_inferred_equivalence():
    crosswalk = json.loads((_ROOT / _CROSSWALK).read_text(encoding="utf-8"))
    assert crosswalk["source"]["original_path"] == _ORIGINAL
    assert crosswalk["source"]["archive_path"] == _ARCHIVE
    archived = (_ROOT / _ARCHIVE).read_bytes()
    assert crosswalk["source"]["sha256"] == _FROZEN_SOURCE_SHA256
    assert hashlib.sha256(archived).hexdigest() == _FROZEN_SOURCE_SHA256
    functions, roster = _archive_functions_and_roster(archived.decode("utf-8"))
    assert len(roster) == 9 and sum(row["collected_cases"] for row in roster) == 34
    assert roster == [{key: row[key] for key in roster[0]} for row in crosswalk["roster"]]
    identity = "\n".join(
        f'{row["original_nodeid"]}:{row["source_lines"][0]}-{row["source_lines"][1]}:'
        f'{row["collected_cases"]}' for row in roster
    )
    assert hashlib.sha256(identity.encode()).hexdigest() == crosswalk["frozen_roster_sha256"]
    assert sum(row["collected_cases"] for row in roster
               if row["original_nodeid"].rsplit("::", 1)[1] not in _RETAINED) == 30
    assert [row["action"] for row in crosswalk["roster"]] == [
        "retain-live-residue-reference-guard" if function.name in _RETAINED
        else "replace-inferred-meaning-expectations" for function in functions
    ]

    # These four independent working tests continue to run; preservation is not their proof.
    working_source = (_ROOT / _ORIGINAL).read_text(encoding="utf-8")
    working, _ = _archive_functions_and_roster(working_source)
    for name in _RETAINED:
        frozen = next(function for function in functions if function.name == name)
        live = next(function for function in working if function.name == name)
        assert ast.dump(live, include_attributes=False) == ast.dump(frozen, include_attributes=False)


    # Shared fixtures may be imported by other independently collected modules.
    frozen_helpers = {
        node.name: node for node in ast.parse(archived.decode("utf-8")).body
        if isinstance(node, ast.FunctionDef) and node.name in {"demands", "demand"}
    }
    working_helpers = {
        node.name: node for node in ast.parse(working_source).body
        if isinstance(node, ast.FunctionDef) and node.name in {"demands", "demand"}
    }
    assert set(frozen_helpers) == set(working_helpers) == {"demands", "demand"}
    for name in ("demands", "demand"):
        assert ast.dump(working_helpers[name], include_attributes=False) == ast.dump(
            frozen_helpers[name], include_attributes=False,
        )

    records, lookup_case = _archived_questions(functions)
    assert len(records) == 50 and all(isinstance(question, str) for question, _, _ in records)
    assert tuple(literal for _, _, literal in records[36:42]) == _QUOTED
    raw = " \tΩ e\u0301 `Client.Open` `для` docs/Manual.md\r\n"
    scope = ScopeKey("fixture-repo", "1.0", "snapshot-a")
    demands = []
    for question, exact, quoted in [*records, (raw, ("client.open", "для"), None)]:
        references = resolve_references(question, catalog=(), scope=scope)
        compiled = meaning.compile_admission_demands(question, references)
        assert len(compiled) == 1
        row = compiled[0]
        # Literal expected fields: constructing another production DTO could copy a mutated default.
        assert asdict(row) == {
            "need": {
                "need_id": "need-1", "query_span_start": 0, "query_span_end": len(question),
                "query_span_text": question, "subject": "", "relation": "unresolved",
                "context": "", "hard_exact": exact,
            },
            "operator": "unknown", "arguments": (), "constraints": (),
            "unsupported_spans": ((0, len(question)),),
        }
        assert question[row.need.query_span_start:row.need.query_span_end] == question
        assert canonical_phrase(question) == question
        if quoted is not None:
            # The quoted occurrence and an equal unquoted connective are distinct.
            start = len("Can a handler for ") + 1
            end = start + len(quoted)
            ref, = [ref for ref in references.references
                    if (ref.mention.start, ref.mention.end) == (start, end)]
            assert ref.mention.text == question[start:end] == quoted
            assert ref.role == "symbol_identity" and ref.mention.explicit is True
            assert canonical_phrase(quoted) == quoted
            if quoted == "for":
                connective, = [ref for ref in references.references
                               if (ref.mention.start, ref.mention.end) == (14, 17)]
                assert (connective.mention.text, connective.role, connective.state,
                        connective.mention.explicit) == ("for", "unresolved", "unresolved", False)
        plan = build_documentation_query_plan(question)
        assert plan.original_question == question
        assert [(query.query_id, query.text, query.origin, query.relation,
                 query.coverage_required, query.public_parent_query_id) for query in plan.queries] == [
            ("query-original", question, "original", "direct", True, None)
        ]
        demands.append(row)
    for blank in ("", " \t\r\n"):
        assert meaning.compile_admission_demands(
            blank, resolve_references(blank, catalog=(), scope=scope),
        ) == ()

    original, good, changed = (lookup_case[name] for name in ("original", "good", "changed"))
    plan = build_documentation_query_plan(original, lookup_queries=(good, changed))
    assert [(query.text, query.origin, query.relation, query.public_parent_query_id)
            for query in plan.queries] == [
        (original, "original", "direct", None),
        (good, "host_lookup", "host_lookup", None),
        (changed, "host_lookup", "host_lookup", None),
    ]

    # A distinct finite reference-resolution control. It does not establish body/source proof.
    body_hash = hashlib.sha256(b"Client.Open = 7\n").hexdigest()
    allowed = CatalogSource("allowed", scope, "docs/Manual.md", body_hash)
    prefix = CatalogSource("prefix", scope, "docs/Manual.md.shadow", body_hash)
    foreign = CatalogSource(
        "foreign", ScopeKey("other-repo", "1.0", "snapshot-a"), "docs/Manual.md", body_hash,
    )
    duplicate = CatalogSource("duplicate", scope, "docs/Manual.md", body_hash)
    for catalog, complete, state, ids in [
        ((allowed, prefix, foreign), True, "resolved", ("allowed",)),
        ((foreign, prefix, allowed), True, "resolved", ("allowed",)),
        ((prefix, foreign), True, "missing", ()),
        ((allowed,), False, "unresolved", ()),
        ((duplicate, allowed), True, "ambiguous", ("allowed", "duplicate")),
    ]:
        references = resolve_references(raw, catalog=catalog, scope=scope, catalog_complete=complete)
        ref, = [ref for ref in references.references if ref.mention.text == "docs/Manual.md"]
        assert (ref.role, ref.state, ref.source_ids) == ("source_locator", state, ids)
        assert raw[ref.mention.start:ref.mention.end] == "docs/Manual.md"
        assert meaning.compile_admission_demands(raw, references) == (demands[-1],)

    start = raw.index("Client.Open")
    slot = MeaningSlot("subject", start, start + len("Client.Open"), "Client.Open", "Client.Open")
    assert raw[slot.start:slot.end] == slot.text == slot.canonical
    forged_complete = replace(
        demands[-1], operator="default", arguments=(slot,), constraints=(), unsupported_spans=(),
    )
    # Equal supplied slots are not semantic credit. The directed production mutant
    # must first fail here with this exact guard, never through an earlier generic assertion.
    pairs = [(demands[index], demands[index + 1]) for index in range(0, 36, 2)]
    for left, right in [(forged_complete, forged_complete), *[(row, row) for row in demands],
                        *pairs, *[(right, left) for left, right in pairs]]:
        assert meaning.same_supported_meaning(left, right) is False, _GUARD
    for left, right in [(original, good), (original, changed), (raw, raw), ("", "")]:
        assert meaning.questions_have_same_supported_meaning(left, right) is False, _GUARD
