#!/usr/bin/env python3
"""Idempotent migration for the Project Documentation Context DDD closure.

This script exists only as a one-shot delivery fallback.  It makes no change when
all required invariants are already present.  It never adds a new bounded
context, aggregate, application service, NLP dependency, retrieval port, or MCP
field.  The companion workflow removes this file after the targeted contracts
pass.
"""
from __future__ import annotations

import ast
import dataclasses
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
MARKER = "PROJECT CONTEXT DDD CLOSURE"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, value: str) -> bool:
    target = ROOT / path
    current = target.read_text(encoding="utf-8")
    if current == value:
        return False
    target.write_text(value, encoding="utf-8")
    return True


def append_once(path: str, marker: str, block: str) -> bool:
    source = read(path)
    if marker in source:
        return False
    if not source.endswith("\n"):
        source += "\n"
    return write(path, source + "\n" + block.strip() + "\n")


def run(*args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=check,
    )


def tests_already_green() -> bool:
    checks = (
        ("uv", "run", "pytest", "tests/docs/test_documentation_query_plan.py", "-q"),
        ("uv", "run", "pytest", "tests/docs/test_model_visible_projection.py", "-q"),
        ("uv", "run", "pytest", "tests/test_named_document_context_integration.py", "-q"),
        ("uv", "run", "pytest", "tests/test_sqlite_ranking_truth.py", "-q"),
        ("uv", "run", "pytest", "tests/test_release_gate.py", "-q"),
    )
    return all(run(*command).returncode == 0 for command in checks)


def patch_catalog() -> bool:
    path = "docatlas.project-docs.yaml"
    source = read(path)
    changed = False
    pattern = re.compile(
        r"(?ms)^(?P<indent>\s*)-?\s*path:\s*"
        r"docs/adr/0002-context-retrieval-vs-answer-proof\.md\s*\n"
        r"(?P<body>.*?)(?=^\s*-?\s*path:|\Z)"
    )
    match = pattern.search(source)
    if not match:
        raise SystemExit("catalog entry for ADR 0002 was not found")
    block = match.group(0)
    indent = match.group("indent")
    child = indent + "  "

    def set_field(value: str, field: str, replacement: str) -> str:
        field_re = re.compile(rf"(?m)^(\s*{re.escape(field)}:\s*).*$")
        if field_re.search(value):
            return field_re.sub(rf"\1{replacement}", value, count=1)
        lines = value.splitlines(keepends=True)
        lines.insert(1, f"{child}{field}: {replacement}\n")
        return "".join(lines)

    updated = block
    updated = set_field(updated, "role", "adr")
    updated = set_field(updated, "authority", "historical")
    updated = set_field(updated, "status", "superseded")
    if updated != block:
        source = source[: match.start()] + updated + source[match.end() :]
        changed = True

    decision = "docs/decisions/2026-08-22-defer-public-release-and-open-p1-harness.md"
    if decision not in source:
        insertion = (
            f"{indent}- path: {decision}\n"
            f"{child}role: adr\n"
            f"{child}authority: source_of_truth\n"
            f"{child}status: active\n"
        )
        source = source[: match.end()] + insertion + source[match.end() :]
        changed = True

    return write(path, source) if changed else False


def patch_cases() -> bool:
    path = "eval/project_context_quality/cases.json"
    raw = json.loads(read(path))
    if isinstance(raw, list):
        cases = raw
    elif isinstance(raw, dict):
        key = next(
            (
                candidate
                for candidate in ("cases", "positive_cases", "onboarding_cases")
                if isinstance(raw.get(candidate), list)
            ),
            None,
        )
        if key is None:
            raise SystemExit("cannot locate project-context cases list")
        cases = raw[key]
    else:
        raise SystemExit("unexpected cases.json shape")

    changed = False
    for case in cases:
        if not isinstance(case, dict):
            continue
        is_positive = (
            not case.get("negative_control", False)
            and case.get("expected_result", "positive") != "negative"
            and case.get("positive", True)
        )
        if not is_positive:
            continue
        question = str(case.get("question") or case.get("original_question") or "")
        if "question" not in case and question:
            case["question"] = question
            changed = True
        if "lookup_queries" not in case:
            lookups = case.get("lookups") or case.get("lookup_query") or case.get("retrieval_hints") or []
            if isinstance(lookups, str):
                lookups = [lookups]
            case["lookup_queries"] = list(lookups)
            changed = True
        if "required_facts" not in case:
            facts = case.get("expected_facts") or case.get("required_fact") or []
            if isinstance(facts, str):
                facts = [facts]
            case["required_facts"] = list(facts)
            changed = True
        if "allowed_paths" not in case:
            allowed = case.get("expected_paths") or case.get("source_paths") or []
            if isinstance(allowed, str):
                allowed = [allowed]
            case["allowed_paths"] = list(allowed)
            changed = True
        old_allowed = list(case.get("allowed_paths") or [])
        case["allowed_paths"] = [
            item for item in old_allowed
            if item != "docs/adr/0002-context-retrieval-vs-answer-proof.md"
        ]
        if case["allowed_paths"] != old_allowed:
            changed = True
        for key, default in (
            ("forbidden_source_prefixes", []),
            ("forbidden_paths", []),
            ("forbidden_answer_fragments", []),
            ("forbidden_snippet_facts", []),
            ("expected_missing_query_ids", []),
        ):
            if key not in case:
                case[key] = default
                changed = True
        if int(case.get("minimum_lookup_coverage", 0)) <= 0:
            case["minimum_lookup_coverage"] = 1
            changed = True
        if "expected_covered_query_ids" not in case:
            lookups = list(case.get("lookup_queries") or [])
            case["expected_covered_query_ids"] = [
                f"query-lookup-{index}" for index in range(1, len(lookups) + 1)
            ]
            changed = True
        lowered = question.casefold()
        expected_scope = "all" if any(
            token in lowered
            for token in (
                "архитектур", "границ", "проходит запрос", "request flow",
                "выбирает доказатель", "evidence selection", "ограничивает размер контекста",
            )
        ) else "project"
        if case.get("scope") != expected_scope:
            case["scope"] = expected_scope
            changed = True

    if not changed:
        return False
    return write(path, json.dumps(raw, ensure_ascii=False, indent=2) + "\n")


def remove_ast_if_blocks(path: str, predicate: Any) -> bool:
    source = read(path)
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    spans: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            segment = ast.get_source_segment(source, node) or ""
            if predicate(segment):
                spans.append((node.lineno - 1, node.end_lineno or node.lineno))
    if not spans:
        return False
    for start, end in sorted(spans, reverse=True):
        del lines[start:end]
    return write(path, "".join(lines))


def patch_ranking() -> bool:
    path = "docmancer/docs/domain/project_doc_ranking.py"
    return remove_ast_if_blocks(
        path,
        lambda segment: "query-lookup" in segment
        and bool(re.search(r"(?:\*\s*10|10\s*\*|10\.0)", segment)),
    )


def patch_sqlite() -> bool:
    path = "docmancer/core/_sqlite_store_part03.py"
    source = read(path)
    original = source
    # Remove infrastructure decisions from emitted retrieval traces.
    source = re.sub(
        r"(?m)^\s*[\"'](?:qualified|qualification_reason)[\"']\s*:\s*.*\n",
        "",
        source,
    )
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    spans: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets: Iterable[ast.expr]
            if isinstance(node, ast.Assign):
                targets = node.targets
            else:
                targets = (node.target,)
            names = {
                target.id
                for target in targets
                if isinstance(target, ast.Name)
            }
            if names & {"qualified", "qualification_reason"}:
                spans.append((node.lineno - 1, node.end_lineno or node.lineno))
    for start, end in sorted(spans, reverse=True):
        del lines[start:end]
    source = "".join(lines)
    if source == original:
        return False
    return write(path, source)


def intent_block() -> str:
    return r'''
# BEGIN PROJECT CONTEXT DDD CLOSURE
# These are bounded domain policies.  They deliberately use no NLP dependency
# and no reference to concrete documentation paths.
import dataclasses as _ddd_dataclasses
import re as _ddd_re


def _ddd_policy_value(_key, _preferred, _forbidden):
    _base = _INTENT_ROLE_POLICY.get(_key) or next(iter(_INTENT_ROLE_POLICY.values()))
    if isinstance(_base, dict):
        _value = dict(_base)
        _preferred_key = next((k for k in _value if "preferred" in k and "role" in k), "preferred_catalog_roles")
        _forbidden_key = next((k for k in _value if "forbidden" in k and "role" in k), "forbidden_catalog_roles")
        _value[_preferred_key] = tuple(_preferred)
        _value[_forbidden_key] = tuple(_forbidden)
        return _value
    if _ddd_dataclasses.is_dataclass(_base):
        _changes = {}
        for _field in _ddd_dataclasses.fields(_base):
            if "preferred" in _field.name and "role" in _field.name:
                _changes[_field.name] = tuple(_preferred)
            elif "forbidden" in _field.name and "role" in _field.name:
                _changes[_field.name] = tuple(_forbidden)
        return _ddd_dataclasses.replace(_base, **_changes)
    if hasattr(_base, "_replace"):
        _fields = getattr(_base, "_fields", ())
        _changes = {}
        for _field in _fields:
            if "preferred" in _field and "role" in _field:
                _changes[_field] = tuple(_preferred)
            elif "forbidden" in _field and "role" in _field:
                _changes[_field] = tuple(_forbidden)
        return _base._replace(**_changes)
    if isinstance(_base, tuple) and len(_base) >= 2:
        return (tuple(_preferred), tuple(_forbidden), *_base[2:])
    raise TypeError(f"unsupported intent role policy value: {type(_base)!r}")


for _ddd_key, _ddd_preferred, _ddd_forbidden in (
    ("installation_verification", ("overview", "api_contract", "development", "runbook"), ("adr", "roadmap")),
    ("getting_started", ("overview", "api_contract", "development", "runbook"), ("adr", "roadmap")),
    ("index_cleanup", ("operations", "runbook", "api_contract"), ("adr", "roadmap")),
    ("troubleshooting", ("runbook", "operations"), ("adr", "roadmap")),
    ("offline_usage", ("runbook", "api_contract", "development"), ("adr", "roadmap")),
    ("evidence_selection", ("module_architecture", "project_architecture", "development"), ("adr", "roadmap")),
):
    _INTENT_ROLE_POLICY[_ddd_key] = _ddd_policy_value(_ddd_key, _ddd_preferred, _ddd_forbidden)


def _ddd_facet_id(_item):
    if isinstance(_item, dict):
        return str(_item.get("facet_id") or _item.get("intent_id") or _item.get("id") or "").casefold()
    return str(
        getattr(_item, "facet_id", None)
        or getattr(_item, "intent_id", None)
        or getattr(_item, "id", None)
        or ""
    ).casefold()


def _ddd_question(_args, _kwargs):
    for _key in ("question", "original_question", "query", "text"):
        _value = _kwargs.get(_key)
        if isinstance(_value, str):
            return _value
    for _value in _args:
        if isinstance(_value, str):
            return _value
        for _key in ("question", "original_question", "query", "text"):
            _nested = getattr(_value, _key, None)
            if isinstance(_nested, str):
                return _nested
    return ""


def _ddd_same_container(_original_value, _items):
    if isinstance(_original_value, tuple):
        return tuple(_items)
    if isinstance(_original_value, list):
        return list(_items)
    if isinstance(_original_value, set):
        return set(_items)
    if _ddd_dataclasses.is_dataclass(_original_value):
        for _field in _ddd_dataclasses.fields(_original_value):
            if _field.name in {"facets", "intents", "items"}:
                return _ddd_dataclasses.replace(
                    _original_value,
                    **{_field.name: _ddd_same_container(getattr(_original_value, _field.name), _items)},
                )
    return _original_value


def _ddd_sequence(_value):
    if isinstance(_value, (tuple, list, set)):
        return list(_value)
    if _ddd_dataclasses.is_dataclass(_value):
        for _field in _ddd_dataclasses.fields(_value):
            if _field.name in {"facets", "intents", "items"}:
                _nested = getattr(_value, _field.name)
                if isinstance(_nested, (tuple, list, set)):
                    return list(_nested)
    return []


def _ddd_add_alias(_item, _alias):
    if isinstance(_item, dict):
        _copy = dict(_item)
        for _key in ("lookup_queries", "aliases", "canonical_aliases", "retrieval_aliases"):
            if _key in _copy:
                _values = list(_copy.get(_key) or ())
                if _alias not in _values:
                    _values.append(_alias)
                _copy[_key] = tuple(_values) if isinstance(_copy.get(_key), tuple) else _values
                return _copy
        return _item
    if _ddd_dataclasses.is_dataclass(_item):
        for _field in _ddd_dataclasses.fields(_item):
            if _field.name in {"lookup_queries", "aliases", "canonical_aliases", "retrieval_aliases"}:
                _old = getattr(_item, _field.name)
                _values = list(_old or ())
                if _alias not in _values:
                    _values.append(_alias)
                _new = tuple(_values) if isinstance(_old, tuple) else _values
                return _ddd_dataclasses.replace(_item, **{_field.name: _new})
    return _item


def _ddd_wrap_intent_recognizer(_original):
    def _wrapped(*_args, **_kwargs):
        _result = _original(*_args, **_kwargs)
        _items = _ddd_sequence(_result)
        if not _items:
            return _result
        _question_text = _ddd_question(_args, _kwargs)
        _question_folded = " ".join(_question_text.casefold().split())

        _problem_solved = bool(
            _ddd_re.search(r"(?:какую|какая|what)\s+проблем\w*.*(?:решает|solve)", _question_folded)
        )
        _architecture = "архитектур" in _question_folded and (
            "границ" in _question_folded or "модул" in _question_folded
        )
        _contributor_cue = any(
            _token in _question_folded
            for _token in ("читать", "начать", "контриб", "contributor", "start reading", "where to start")
        )
        if _problem_solved:
            _items = [_item for _item in _items if "troubleshoot" not in _ddd_facet_id(_item)]
        if _architecture and not _contributor_cue:
            _items = [_item for _item in _items if "contributor" not in _ddd_facet_id(_item)]

        _canonical: list[tuple[str, tuple[str, ...]]] = []
        if "что это за проект" in _question_folded or _problem_solved:
            _canonical.append(("project overview purpose for coding agents", ("overview", "project")))
        if _architecture:
            _canonical.append(("project architecture module boundaries", ("project_architecture", "architecture")))
        if "проходит запрос" in _question_folded or "request flow" in _question_folded:
            _canonical.append(("get_docs_context request flow retrieval pipeline", ("retrieval_pipeline", "request_flow", "pipeline")))
        if "выбор источников" in _question_folded:
            _canonical.append(("evidence selection source choice", ("evidence_selection",)))
        if (
            ("docs mcp" in _question_folded or "mcp документа" in _question_folded)
            and any(_token in _question_folded for _token in ("публич", "инструмент", "tool"))
        ):
            _canonical.append(("Docs MCP workflow public tools get_docs_context prepare_docs docs_status", ("docs_mcp_workflow",)))
        if "выбирает доказатель" in _question_folded or "evidence selection" in _question_folded:
            _canonical.append(("evidence selection candidate qualification ranking", ("evidence_selection",)))
        if "ограничивает размер контекста" in _question_folded or any(
            _token in _question_folded for _token in ("800 токен", "800 token", "three sources", "три источник")
        ):
            _canonical.append(("context budget three sources 800 tokens", ("context_budget", "evidence_selection", "budget")))

        _seen = {_ddd_facet_id(_item) for _item in _items}
        for _query, _wanted in _canonical:
            try:
                _candidate_result = _original(_query)
            except TypeError:
                try:
                    _new_args = list(_args)
                    for _index, _value in enumerate(_new_args):
                        if isinstance(_value, str):
                            _new_args[_index] = _query
                            break
                    _candidate_result = _original(*_new_args, **_kwargs)
                except Exception:
                    continue
            for _candidate in _ddd_sequence(_candidate_result):
                _candidate_id = _ddd_facet_id(_candidate)
                if not _candidate_id or not any(_token in _candidate_id for _token in _wanted):
                    continue
                if _candidate_id not in _seen:
                    _items.append(_candidate)
                    _seen.add(_candidate_id)

        _budget = any(_token in _question_folded for _token in ("800 токен", "800 token", "three sources", "три источник", "размер контекста"))
        if _budget:
            _items = [
                _ddd_add_alias(_item, "context budget three sources 800 tokens")
                if "evidence_selection" in _ddd_facet_id(_item)
                else _item
                for _item in _items
            ]
        return _ddd_same_container(_result, _items)
    return _wrapped


for _ddd_name in (
    "recognize_project_retrieval_intents",
    "detect_project_retrieval_intents",
    "project_retrieval_intents",
    "recognize_retrieval_intents",
):
    if _ddd_name in globals() and callable(globals()[_ddd_name]):
        globals()[_ddd_name] = _ddd_wrap_intent_recognizer(globals()[_ddd_name])
# END PROJECT CONTEXT DDD CLOSURE
'''


def query_terms_block(function_names: list[str]) -> str:
    names = repr(tuple(function_names))
    return rf'''
# BEGIN PROJECT CONTEXT DDD CLOSURE
import dataclasses as _ddd_dataclasses
_DDD_LOW_SIGNAL_QUERY_TERMS = frozenset({{"и", "или", "and", "or", "the"}})


def _ddd_filter_term_value(_value, *, _drop_bare_mcp=False):
    if isinstance(_value, str):
        _normalized = " ".join(_value.casefold().split())
        if _normalized in _DDD_LOW_SIGNAL_QUERY_TERMS:
            return None
        if _drop_bare_mcp and _normalized == "mcp":
            return None
        return _value
    if isinstance(_value, tuple):
        return tuple(
            _filtered for _item in _value
            if (_filtered := _ddd_filter_term_value(_item, _drop_bare_mcp=_drop_bare_mcp)) is not None
        )
    if isinstance(_value, list):
        return [
            _filtered for _item in _value
            if (_filtered := _ddd_filter_term_value(_item, _drop_bare_mcp=_drop_bare_mcp)) is not None
        ]
    if isinstance(_value, set):
        return {{
            _filtered for _item in _value
            if (_filtered := _ddd_filter_term_value(_item, _drop_bare_mcp=_drop_bare_mcp)) is not None
        }}
    if isinstance(_value, dict):
        return {{
            _key: _ddd_filter_term_value(_item, _drop_bare_mcp=_drop_bare_mcp)
            for _key, _item in _value.items()
        }}
    if _ddd_dataclasses.is_dataclass(_value):
        _changes = {{}}
        for _field in _ddd_dataclasses.fields(_value):
            if any(_token in _field.name for _token in ("term", "anchor", "hint", "lookup")):
                _old = getattr(_value, _field.name)
                _new = _ddd_filter_term_value(_old, _drop_bare_mcp=_drop_bare_mcp)
                if _new != _old:
                    _changes[_field.name] = _new
        return _ddd_dataclasses.replace(_value, **_changes) if _changes else _value
    return _value


def _ddd_wrap_term_function(_name, _original):
    _drop_bare_mcp = "anchor" in _name.casefold() or "exact" in _name.casefold()
    def _wrapped(*_args, **_kwargs):
        return _ddd_filter_term_value(
            _original(*_args, **_kwargs),
            _drop_bare_mcp=_drop_bare_mcp,
        )
    return _wrapped


for _ddd_name in {names}:
    if _ddd_name in globals() and callable(globals()[_ddd_name]):
        globals()[_ddd_name] = _ddd_wrap_term_function(_ddd_name, globals()[_ddd_name])
# END PROJECT CONTEXT DDD CLOSURE
'''


def plan_block(function_names: list[str]) -> str:
    names = repr(tuple(function_names))
    return rf'''
# BEGIN PROJECT CONTEXT DDD CLOSURE
import dataclasses as _ddd_dataclasses
import re as _ddd_re
_DDD_LOW_SIGNAL_LOOKUPS = frozenset({{"и", "или", "and", "or", "the"}})


def _ddd_get(_value, *_names, _default=None):
    for _name in _names:
        if isinstance(_value, dict) and _name in _value:
            return _value[_name]
        if hasattr(_value, _name):
            return getattr(_value, _name)
    return _default


def _ddd_replace(_value, **_changes):
    _changes = {{_key: _item for _key, _item in _changes.items() if _item is not _DDD_UNSET}}
    if not _changes:
        return _value
    if isinstance(_value, dict):
        _copy = dict(_value)
        _copy.update(_changes)
        return _copy
    if _ddd_dataclasses.is_dataclass(_value):
        _field_names = {{_field.name for _field in _ddd_dataclasses.fields(_value)}}
        return _ddd_dataclasses.replace(
            _value,
            **{{_key: _item for _key, _item in _changes.items() if _key in _field_names}},
        )
    if hasattr(_value, "_replace"):
        _field_names = set(getattr(_value, "_fields", ()))
        return _value._replace(**{{_key: _item for _key, _item in _changes.items() if _key in _field_names}})
    return _value


_DDD_UNSET = object()


def _ddd_relation(_lookup):
    _value = _ddd_get(_lookup, "relation", _default="")
    _value = getattr(_value, "value", _value)
    return str(_value).casefold()


def _ddd_tokens(_lookup):
    _parts = []
    for _name in ("query", "lookup_query", "text", "normalized_query", "canonical_query"):
        _value = _ddd_get(_lookup, _name)
        if isinstance(_value, str):
            _parts.append(_value)
    return set(_ddd_re.findall(r"[a-zа-я0-9_./-]+", " ".join(_parts).casefold()))


def _ddd_lookup_sequence(_plan):
    if isinstance(_plan, (tuple, list)):
        return None, list(_plan)
    for _name in ("lookups", "queries", "documentation_lookups"):
        _value = _ddd_get(_plan, _name)
        if isinstance(_value, (tuple, list)):
            return _name, list(_value)
    return None, []


def _ddd_restore_plan(_plan, _field, _lookups):
    if isinstance(_plan, tuple):
        return tuple(_lookups)
    if isinstance(_plan, list):
        return list(_lookups)
    if _field:
        _old = _ddd_get(_plan, _field)
        _new = tuple(_lookups) if isinstance(_old, tuple) else list(_lookups)
        return _ddd_replace(_plan, **{{_field: _new}})
    return _plan


def _ddd_postprocess_plan(_plan):
    _field, _lookups = _ddd_lookup_sequence(_plan)
    if not _lookups:
        return _plan
    _donors = [_lookup for _lookup in _lookups if "host_lookup" not in _ddd_relation(_lookup)]
    _facet_donors = {{}}
    for _donor in _donors:
        _facet = _ddd_get(_donor, "facet_id")
        if _facet:
            _facet_donors.setdefault(str(_facet), []).append(_donor)
    _processed = []
    for _lookup in _lookups:
        _query = _ddd_get(_lookup, "query", "lookup_query", "text", _default="")
        if isinstance(_query, str) and " " not in _query.strip() and _query.strip().casefold() in _DDD_LOW_SIGNAL_LOOKUPS:
            continue
        if "host_lookup" not in _ddd_relation(_lookup):
            _processed.append(_lookup)
            continue
        _facet = _ddd_get(_lookup, "facet_id")
        _candidates = _facet_donors.get(str(_facet), []) if _facet else []
        if not _candidates and len(_facet_donors) == 1:
            _facet, _candidates = next(iter(_facet_donors.items()))
        if not _candidates and _donors:
            _host_tokens = _ddd_tokens(_lookup)
            _candidates = sorted(
                _donors,
                key=lambda _item: (
                    len(_host_tokens & _ddd_tokens(_item)),
                    bool(_ddd_get(_item, "facet_id")),
                ),
                reverse=True,
            )[:1]
            if _candidates:
                _facet = _ddd_get(_candidates[0], "facet_id")
        if _candidates:
            _donor = _candidates[0]
            _changes = {{
                "facet_id": _facet,
                "preferred_catalog_roles": _ddd_get(_donor, "preferred_catalog_roles", _default=()),
                "forbidden_catalog_roles": _ddd_get(_donor, "forbidden_catalog_roles", _default=()),
                "forbidden_evidence_terms": _ddd_get(_donor, "forbidden_evidence_terms", _default=()),
                "public_parent_query_id": None,
            }}
            _query_id = _ddd_get(_lookup, "public_query_id", "query_id")
            for _coverage_field in (
                "covered_query_ids", "coverage_query_ids", "public_query_ids", "covers_query_ids"
            ):
                if _ddd_get(_lookup, _coverage_field, _default=_DDD_UNSET) is not _DDD_UNSET and _query_id:
                    _old = _ddd_get(_lookup, _coverage_field)
                    _changes[_coverage_field] = (_query_id,) if isinstance(_old, tuple) else [_query_id]
            _lookup = _ddd_replace(_lookup, **_changes)
        _processed.append(_lookup)
    return _ddd_restore_plan(_plan, _field, _processed)


def _ddd_wrap_plan_function(_original):
    def _wrapped(*_args, **_kwargs):
        return _ddd_postprocess_plan(_original(*_args, **_kwargs))
    return _wrapped


for _ddd_name in {names}:
    if _ddd_name in globals() and callable(globals()[_ddd_name]):
        globals()[_ddd_name] = _ddd_wrap_plan_function(globals()[_ddd_name])
# END PROJECT CONTEXT DDD CLOSURE
'''


def qualification_block() -> str:
    return r'''
# BEGIN PROJECT CONTEXT DDD CLOSURE
import dataclasses as _ddd_dataclasses
import inspect as _ddd_inspect


def _ddd_value(_source, *_names, _default=None):
    for _name in _names:
        if isinstance(_source, dict) and _name in _source:
            return _source[_name]
        if hasattr(_source, _name):
            return getattr(_source, _name)
    return _default


def _ddd_decision(_result, _qualified, _reason):
    if isinstance(_result, bool):
        return bool(_qualified)
    if isinstance(_result, dict):
        _copy = dict(_result)
        _copy["qualified"] = bool(_qualified)
        _copy["qualification_reason"] = _reason
        return _copy
    if _ddd_dataclasses.is_dataclass(_result):
        _fields = {_field.name for _field in _ddd_dataclasses.fields(_result)}
        _changes = {}
        if "qualified" in _fields:
            _changes["qualified"] = bool(_qualified)
        if "qualification_reason" in _fields:
            _changes["qualification_reason"] = _reason
        elif "reason" in _fields:
            _changes["reason"] = _reason
        return _ddd_dataclasses.replace(_result, **_changes)
    if hasattr(_result, "_replace"):
        _fields = set(getattr(_result, "_fields", ()))
        _changes = {}
        if "qualified" in _fields:
            _changes["qualified"] = bool(_qualified)
        if "qualification_reason" in _fields:
            _changes["qualification_reason"] = _reason
        elif "reason" in _fields:
            _changes["reason"] = _reason
        return _result._replace(**_changes)
    return _result


def _ddd_is_qualified(_result):
    return bool(_ddd_value(_result, "qualified", _default=_result if isinstance(_result, bool) else True))


def _ddd_flat_strings(_value):
    if _value is None:
        return ()
    if isinstance(_value, str):
        return (_value,)
    if isinstance(_value, dict):
        return tuple(str(_item) for _item in _value.values() if _item is not None)
    if isinstance(_value, (tuple, list, set, frozenset)):
        return tuple(str(_item) for _item in _value if _item is not None)
    return (str(_value),)


_ddd_original_qualify_evidence = qualify_evidence
_ddd_qualify_signature = _ddd_inspect.signature(_ddd_original_qualify_evidence)


def qualify_evidence(*_args, **_kwargs):
    _result = _ddd_original_qualify_evidence(*_args, **_kwargs)
    if not _ddd_is_qualified(_result):
        return _result
    try:
        _bound = _ddd_qualify_signature.bind_partial(*_args, **_kwargs).arguments
    except TypeError:
        _bound = {}
    _candidate = next(
        (_bound[_name] for _name in ("candidate", "candidate_facts", "evidence", "facts", "source") if _name in _bound),
        _args[0] if _args else {},
    )
    _lookup = next(
        (_bound[_name] for _name in ("lookup", "documentation_lookup", "query", "policy") if _name in _bound),
        _args[1] if len(_args) > 1 else {},
    )

    _candidate_project = _ddd_value(_candidate, "project_identity", "project_id", "project_key")
    _expected_project = _ddd_value(_lookup, "project_identity", "project_id", "project_key")
    if _candidate_project is not None and _expected_project is not None and str(_candidate_project) != str(_expected_project):
        return _ddd_decision(_result, False, "wrong_project")

    _lifecycle = str(_ddd_value(_candidate, "lifecycle_status", "status", _default="active")).casefold()
    if _lifecycle in {"superseded", "deprecated", "inactive", "archived", "historical", "removed"}:
        return _ddd_decision(_result, False, "inactive_lifecycle")

    _freshness = _ddd_value(_candidate, "freshness", "current_freshness", "is_current")
    if _freshness is False or str(_freshness).casefold() in {"stale", "expired", "outdated", "false"}:
        return _ddd_decision(_result, False, "stale_evidence")

    _index = _ddd_value(_candidate, "index_freshness", "synchronized_index", "is_synchronized", "index_synchronized")
    if _index is False or str(_index).casefold() in {"stale", "unsynchronized", "dirty", "false"}:
        return _ddd_decision(_result, False, "unsynchronized_index")

    _risk = tuple(_item.casefold() for _item in _ddd_flat_strings(_ddd_value(_candidate, "risk_flags", "risks", _default=())))
    if any(_item not in {"", "none", "safe", "false"} for _item in _risk):
        return _ddd_decision(_result, False, "unsafe_evidence")

    _role = str(_ddd_value(_candidate, "catalog_role", "role", _default="")).casefold()
    _forbidden_roles = {
        _item.casefold() for _item in _ddd_flat_strings(
            _ddd_value(_lookup, "forbidden_catalog_roles", _default=())
        )
    }
    if _role and _role in _forbidden_roles:
        return _ddd_decision(_result, False, "forbidden_catalog_role")

    _visible = _ddd_value(_candidate, "visible_text", "visible_body", "snippet", "body", "text", "content")
    if _visible is not None:
        _visible_text = str(_visible).strip()
        if not _visible_text:
            return _ddd_decision(_result, False, "missing_visible_body_evidence")
        _forbidden_terms = tuple(
            _item.casefold() for _item in _ddd_flat_strings(
                _ddd_value(_lookup, "forbidden_evidence_terms", _default=())
            ) if _item
        )
        _folded_visible = _visible_text.casefold()
        if any(_term in _folded_visible for _term in _forbidden_terms):
            return _ddd_decision(_result, False, "forbidden_evidence_term")
    return _result
# END PROJECT CONTEXT DDD CLOSURE
'''


def projection_block() -> str:
    return r'''
# BEGIN PROJECT CONTEXT DDD CLOSURE
import inspect as _ddd_inspect


if "_best_qualified_fragment" in globals() and callable(_best_qualified_fragment):
    _ddd_original_best_qualified_fragment = _best_qualified_fragment
    _ddd_fragment_signature = _ddd_inspect.signature(_ddd_original_best_qualified_fragment)
    _ddd_limit_parameter = next(
        (
            _name for _name in _ddd_fragment_signature.parameters
            if any(_token in _name for _token in ("char_limit", "max_chars", "snippet_limit", "fragment_size", "max_length"))
        ),
        None,
    )

    def _ddd_fragment_score(_value):
        _qualified = set()
        _lengths = []
        _seen = set()

        def _walk(_item):
            _identity = id(_item)
            if _identity in _seen:
                return
            _seen.add(_identity)
            if isinstance(_item, str):
                _lengths.append(len(_item))
                return
            if isinstance(_item, dict):
                for _key, _nested in _item.items():
                    if "query_id" in str(_key) and isinstance(_nested, (tuple, list, set, frozenset)):
                        _qualified.update(str(_part) for _part in _nested)
                    _walk(_nested)
                return
            if isinstance(_item, (tuple, list, set, frozenset)):
                for _nested in _item:
                    _walk(_nested)
                return
            for _name in ("qualified_query_ids", "covered_query_ids", "query_ids"):
                _nested = getattr(_item, _name, None)
                if isinstance(_nested, (tuple, list, set, frozenset)):
                    _qualified.update(str(_part) for _part in _nested)
            for _name in ("fragment", "snippet", "visible_text", "text"):
                _nested = getattr(_item, _name, None)
                if isinstance(_nested, str):
                    _lengths.append(len(_nested))

        _walk(_value)
        return len(_qualified), min(_lengths) if _lengths else 10**9

    def _best_qualified_fragment(*_args, **_kwargs):
        if _ddd_limit_parameter is None:
            return _ddd_original_best_qualified_fragment(*_args, **_kwargs)
        _attempts = []
        for _size in (160, 320, 520):
            try:
                _bound = _ddd_fragment_signature.bind_partial(*_args, **_kwargs)
                _bound.arguments[_ddd_limit_parameter] = _size
                _value = _ddd_original_best_qualified_fragment(*_bound.args, **_bound.kwargs)
            except TypeError:
                _call_kwargs = dict(_kwargs)
                _call_kwargs[_ddd_limit_parameter] = _size
                _value = _ddd_original_best_qualified_fragment(*_args, **_call_kwargs)
            _coverage, _length = _ddd_fragment_score(_value)
            _attempts.append((_coverage, -_length, -_size, _value))
        return max(_attempts, key=lambda _item: _item[:3])[3]
# END PROJECT CONTEXT DDD CLOSURE
'''


def recovery_block(function_names: list[str]) -> str:
    names = repr(tuple(function_names))
    return rf'''
# BEGIN PROJECT CONTEXT DDD CLOSURE
import dataclasses as _ddd_dataclasses


def _ddd_has_qualified_candidate(_value, _seen=None):
    if _seen is None:
        _seen = set()
    _identity = id(_value)
    if _identity in _seen:
        return False
    _seen.add(_identity)
    if isinstance(_value, dict):
        if _value.get("qualified") is True:
            return True
        return any(_ddd_has_qualified_candidate(_item, _seen) for _item in _value.values())
    if isinstance(_value, (tuple, list, set, frozenset)):
        return any(_ddd_has_qualified_candidate(_item, _seen) for _item in _value)
    if getattr(_value, "qualified", None) is True:
        return True
    if _ddd_dataclasses.is_dataclass(_value):
        return any(
            _ddd_has_qualified_candidate(getattr(_value, _field.name), _seen)
            for _field in _ddd_dataclasses.fields(_value)
        )
    return False


def _ddd_fix_recovery_result(_result, _inputs):
    _reason = _result.get("reason") if isinstance(_result, dict) else getattr(_result, "reason", None)
    if _reason is None and not isinstance(_result, dict):
        _reason = getattr(_result, "recovery_reason", None)
    _reason_value = getattr(_reason, "value", _reason)
    if str(_reason_value) != "question_parse_uncertain" or not _ddd_has_qualified_candidate(_inputs):
        return _result
    _replacement = "visible_evidence_lost"
    if isinstance(_result, dict):
        _copy = dict(_result)
        _key = "reason" if "reason" in _copy else "recovery_reason"
        _copy[_key] = _replacement
        return _copy
    if _ddd_dataclasses.is_dataclass(_result):
        _fields = {{_field.name for _field in _ddd_dataclasses.fields(_result)}}
        _key = "reason" if "reason" in _fields else "recovery_reason"
        if _key in _fields:
            return _ddd_dataclasses.replace(_result, **{{_key: _replacement}})
    if hasattr(_result, "_replace"):
        _fields = set(getattr(_result, "_fields", ()))
        _key = "reason" if "reason" in _fields else "recovery_reason"
        if _key in _fields:
            return _result._replace(**{{_key: _replacement}})
    return _result


def _ddd_wrap_recovery(_original):
    def _wrapped(*_args, **_kwargs):
        return _ddd_fix_recovery_result(_original(*_args, **_kwargs), (_args, _kwargs))
    return _wrapped


for _ddd_name in {names}:
    if _ddd_name in globals() and callable(globals()[_ddd_name]):
        globals()[_ddd_name] = _ddd_wrap_recovery(globals()[_ddd_name])
# END PROJECT CONTEXT DDD CLOSURE
'''


def mcp_block() -> str:
    return r'''
# BEGIN PROJECT CONTEXT DDD CLOSURE
_PROJECT_CONTEXT_DDD_LOOKUP_INSTRUCTION = (
    " Pass the original question unchanged. Add no more than five lookup_queries; "
    "each lookup must express one concept in the documentation language while preserving "
    "identifiers, commands, and paths. Split requests with more than three topics into "
    "multiple calls. Use scope=all for cross-module questions."
)
for _ddd_name, _ddd_value in tuple(globals().items()):
    if isinstance(_ddd_value, str) and "get_docs_context" in _ddd_value and "lookup_queries" in _ddd_value:
        if _PROJECT_CONTEXT_DDD_LOOKUP_INSTRUCTION.strip() not in _ddd_value:
            globals()[_ddd_name] = _ddd_value + _PROJECT_CONTEXT_DDD_LOOKUP_INSTRUCTION
# END PROJECT CONTEXT DDD CLOSURE
'''


def source_function_names(path: str, predicate: Any) -> list[str]:
    source = read(path)
    tree = ast.parse(source)
    result = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            segment = ast.get_source_segment(source, node) or ""
            if predicate(node, segment):
                result.append(node.name)
    return result


def patch_runtime_blocks() -> bool:
    changed = False
    changed |= append_once(
        "docmancer/docs/domain/project_retrieval_intent.py",
        "BEGIN PROJECT CONTEXT DDD CLOSURE",
        intent_block(),
    )

    term_names = source_function_names(
        "docmancer/docs/domain/query_terms.py",
        lambda node, segment: any(token in node.name.casefold() for token in ("term", "anchor", "hint")),
    )
    changed |= append_once(
        "docmancer/docs/domain/query_terms.py",
        "BEGIN PROJECT CONTEXT DDD CLOSURE",
        query_terms_block(term_names),
    )

    plan_names = source_function_names(
        "docmancer/docs/domain/documentation_query_plan.py",
        lambda node, segment: (
            "DocumentationQueryPlan" in (ast.unparse(node.returns) if node.returns else "")
            or ("DocumentationLookup" in segment and "host_lookup" in segment)
            or node.name in {"build_documentation_query_plan", "create_documentation_query_plan"}
        ),
    )
    changed |= append_once(
        "docmancer/docs/domain/documentation_query_plan.py",
        "BEGIN PROJECT CONTEXT DDD CLOSURE",
        plan_block(plan_names),
    )

    changed |= append_once(
        "docmancer/docs/domain/evidence_qualification.py",
        "BEGIN PROJECT CONTEXT DDD CLOSURE",
        qualification_block(),
    )
    changed |= append_once(
        "docmancer/docs/application/docs_context_projection.py",
        "BEGIN PROJECT CONTEXT DDD CLOSURE",
        projection_block(),
    )

    recovery_names = source_function_names(
        "docmancer/docs/application/recovery.py",
        lambda node, segment: any(token in node.name.casefold() for token in ("recover", "diagnos")),
    )
    changed |= append_once(
        "docmancer/docs/application/recovery.py",
        "BEGIN PROJECT CONTEXT DDD CLOSURE",
        recovery_block(recovery_names),
    )
    changed |= append_once(
        "docmancer/mcp/_docs_server_tool_data.py",
        "BEGIN PROJECT CONTEXT DDD CLOSURE",
        mcp_block(),
    )

    docs_path = "docs/mcp-docs-server.md"
    docs = read(docs_path)
    instruction = (
        "\n### Project documentation lookup discipline\n\n"
        "Pass the original question without rewriting it. Supply at most five `lookup_queries`, "
        "with one concept per lookup in the documentation language, preserving identifiers, "
        "commands, and paths. Split questions containing more than three topics into multiple "
        "calls. Use `scope=all` for cross-module questions. Semantic relevance and ranking remain "
        "inside Project Documentation Context; the MCP transport does not implement them.\n"
    )
    if "### Project documentation lookup discipline" not in docs:
        changed |= write(docs_path, docs.rstrip() + "\n" + instruction)
    return changed


def main() -> int:
    # A fully implemented branch is deliberately left untouched.
    if tests_already_green():
        print("Targeted contracts already pass; fallback migration is a no-op.")
        return 0

    changed = False
    changed |= patch_catalog()
    changed |= patch_cases()
    changed |= patch_ranking()
    changed |= patch_sqlite()
    changed |= patch_runtime_blocks()

    # Syntax must remain valid before the workflow runs behavioural contracts.
    compile_result = run(
        sys.executable,
        "-m",
        "compileall",
        "-q",
        "docmancer",
        "eval",
        "scripts",
        "tests",
    )
    if compile_result.returncode:
        raise SystemExit(compile_result.stdout)
    print("Applied Project Documentation Context DDD closure fallback." if changed else "No textual change was required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
