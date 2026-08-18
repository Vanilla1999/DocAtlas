"""Diagnostic 100-question probe for Project Docs QA.

This script is intentionally not a release test.  It compares desired bounded
user-facing behavior with the exact parser/contract behavior of the checked-out
commit and emits a JSON report for architectural analysis.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any

from docmancer.docs.domain.project_answer_contract import build_project_answer_contract
from docmancer.docs.domain.question_plan import compile_question_plan


def _case(number: int, category: str, expectation: str, question: str) -> dict[str, Any]:
    return {
        "id": number,
        "category": category,
        "expectation": expectation,
        "question": question,
    }


CASES = (
    # Inventory and typed categories.
    _case(1, "inventory", "plan", "What source types are supported for indexing?"),
    _case(2, "inventory", "support", "Which source types can DocAtlas index?"),
    _case(3, "inventory", "support", "List the supported source types."),
    _case(4, "inventory", "support", "What file formats are supported for local files?"),
    _case(5, "inventory", "support", "Which document formats does indexing accept?"),
    _case(6, "inventory", "plan", "List the pytest markers."),
    _case(7, "inventory", "support", "What markers does the offline suite define?"),
    _case(8, "inventory", "support", "Какие типы источников можно индексировать?"),
    _case(9, "inventory", "support", "Какие форматы локальных файлов поддерживаются?"),
    _case(10, "inventory", "support", "Какие pytest-маркеры есть в проекте?"),

    # Commands, sync, workflows, and configuration.
    _case(11, "workflow", "plan", "How do I sync project docs after editing a file?"),
    _case(12, "workflow", "support", "Which command should I run after project docs change?"),
    _case(13, "workflow", "support", "Refresh project documentation after a file changes."),
    _case(14, "workflow", "plan", "Как обновить документацию проекта после изменения файла?"),
    _case(15, "workflow", "support", "Какой командой синхронизировать документацию проекта?"),
    _case(16, "workflow", "plan", "How do I run the offline suite?"),
    _case(17, "workflow", "support", "How can I run the offline suite?"),
    _case(18, "workflow", "support", "How do I configure project docs in docmancer.yaml?"),
    _case(19, "workflow", "plan", "Where is project docs configuration defined?"),
    _case(20, "workflow", "plan", "What command starts the Docs MCP server?"),

    # Public tools and per-tool usage.
    _case(21, "public_tools", "plan", "What are the three public Docs MCP tools and when do I use each one?"),
    _case(22, "public_tools", "support", "Which public Docs MCP tools are available?"),
    _case(23, "public_tools", "support", "List the public Docs MCP tools."),
    _case(24, "public_tools", "support", "What does get_docs_context do?"),
    _case(25, "public_tools", "support", "When should I use get_docs_context?"),
    _case(26, "public_tools", "support", "What does prepare_docs do and when should I use it?"),
    _case(27, "public_tools", "legacy", "What does docs_status report and when should it be used?"),
    _case(28, "public_tools", "support", "What are the public tools and their purposes?"),
    _case(29, "public_tools", "support", "Назови три публичных инструмента Docs MCP и когда использовать каждый."),
    _case(30, "public_tools", "support", "Какие публичные инструменты есть у Docs MCP?"),

    # Comparison and location.
    _case(31, "comparison_location", "plan", "How does evidence selection differ from question planning?"),
    _case(32, "comparison_location", "plan", "Compare evidence selection with question planning."),
    _case(33, "comparison_location", "support", "What is the difference between evidence selection and question planning?"),
    _case(34, "comparison_location", "support", "Evidence selection vs question planning: what differs?"),
    _case(35, "comparison_location", "plan", "Чем evidence selection отличается от question planning?"),
    _case(36, "comparison_location", "plan", "Сравни evidence selection и question planning."),
    _case(37, "comparison_location", "plan", "Where is the project answer contract documented?"),
    _case(38, "comparison_location", "plan", "Which file defines the project answer contract?"),
    _case(39, "comparison_location", "plan", "Where can I find the project answer contract?"),
    _case(40, "comparison_location", "plan", "В каком файле описан project answer contract?"),

    # Conditions and consequences.
    _case(41, "condition", "plan", "What happens when the preview plan is stale?"),
    _case(42, "condition", "plan", "What happens if the preview plan becomes stale?"),
    _case(43, "condition", "support", "What happens when the preview plan expires?"),
    _case(44, "condition", "plan", "Can clear-index run while the MCP server is alive?"),
    _case(45, "condition", "support", "Is clear-index allowed while the MCP server is running?"),
    _case(46, "condition", "plan", "Under which conditions is cleanup blocked?"),
    _case(47, "condition", "support", "When is cleanup blocked?"),
    _case(48, "condition", "plan", "Что происходит, когда preview plan устарел?"),
    _case(49, "condition", "plan", "Можно ли запустить clear-index, пока MCP server работает?"),
    _case(50, "condition", "plan", "При каких условиях cleanup блокируется?"),

    # False premises, quantifiers, and cardinality.
    _case(51, "premise", "plan", "Why does clear-index always delete remote Qdrant collections?"),
    _case(52, "premise", "plan", "Why does clear-index never delete remote Qdrant collections?"),
    _case(53, "premise", "support", "Why does clear-index delete remote Qdrant collections?"),
    _case(54, "premise", "plan", "Why does clear-index always preserve remote Qdrant collections?"),
    _case(55, "premise", "support", "Why does clear-index sometimes delete remote Qdrant collections?"),
    _case(56, "premise", "plan", "Why are there four public Docs MCP tools?"),
    _case(57, "premise", "plan", "Why are there three public Docs MCP tools?"),
    _case(58, "premise", "support", "Why are there four storage layers?"),
    _case(59, "premise", "plan", "Почему clear-index всегда удаляет удалённые коллекции Qdrant?"),
    _case(60, "premise", "support", "Почему у Docs MCP четыре публичных инструмента?"),

    # Compound coverage and independent tails.
    _case(61, "compound", "abstain", "Which source types are supported for indexing, what is the Bitcoin price?"),
    _case(62, "compound", "support", "Which source types are supported for indexing and explain clear-index."),
    _case(63, "compound", "abstain", "Where is the project answer contract documented and what is the Bitcoin price?"),
    _case(64, "compound", "abstain", "How does evidence selection differ from question planning and what is the Bitcoin price?"),
    _case(65, "compound", "abstain", "What happens when the preview plan is stale, also tell me the Bitcoin price?"),
    _case(66, "compound", "abstain", "Why does clear-index always delete remote Qdrant collections; calculate 2+2."),
    _case(67, "compound", "plan", "What test markers are available and how do I run the offline suite?"),
    _case(68, "compound", "plan", "Which source types are supported for indexing; which file formats are supported for indexing?"),
    _case(69, "compound", "plan", "Where is the project answer contract documented and where is question planning documented?"),
    _case(70, "compound", "support", "What happens when the preview plan is stale and the index writer is active?"),

    # Explicit legacy ownership and generic safety.
    _case(71, "ownership", "legacy", "How does prepare_docs sync_project_docs work?"),
    _case(72, "ownership", "legacy", "What does Phase 3.1 require for RetrievalDispatcher, the raw topic, EvidenceRequirementSet hints, and vector or embedding calls?"),
    _case(73, "ownership", "legacy", "What does docs_status report and when should it be used?"),
    _case(74, "ownership", "legacy", "What are the three public Docs MCP tools?"),
    _case(75, "ownership", "abstain", "What does the project require?"),
    _case(76, "ownership", "abstain", "How does the project work?"),
    _case(77, "ownership", "abstain", "What does the system do?"),
    _case(78, "ownership", "support", "What is the architecture of the MCP server?"),
    _case(79, "ownership", "support", "How does the MCP server handle requests?"),
    _case(80, "ownership", "support", "What is the timeout for provider requests?"),

    # Russian parity and natural phrasing.
    _case(81, "russian", "support", "Какие типы источников поддерживает DocAtlas?"),
    _case(82, "russian", "support", "Какие форматы файлов поддерживает DocAtlas?"),
    _case(83, "russian", "plan", "Какие тестовые маркеры доступны?"),
    _case(84, "russian", "plan", "Как синхронизировать проектную документацию?"),
    _case(85, "russian", "support", "Как запустить офлайн-тесты DocAtlas?"),
    _case(86, "russian", "plan", "Где документирован контракт ответа проекта?"),
    _case(87, "russian", "plan", "Чем выбор доказательств отличается от планирования вопроса?"),
    _case(88, "russian", "support", "Что произойдёт, если план предпросмотра устарел?"),
    _case(89, "russian", "plan", "Почему clear-index никогда не удаляет удалённые коллекции Qdrant?"),
    _case(90, "russian", "support", "При каких условиях clear-index нельзя запускать?"),

    # Broader project questions that should remain answerable.
    _case(91, "general", "support", "What Python versions does DocAtlas support?"),
    _case(92, "general", "support", "Which Python versions are supported?"),
    _case(93, "general", "plan", "Where is DOCMANCER_OFFLINE documented?"),
    _case(94, "general", "plan", "What is DOCMANCER_OFFLINE and when should it be used?"),
    _case(95, "general", "support", "What does clear-index delete and preserve?"),
    _case(96, "general", "support", "What source types and file formats are supported?"),
    _case(97, "general", "plan", "How does indexing split documents into sections and chunks?"),
    _case(98, "general", "plan", "How does evidence selection choose candidates?"),
    _case(99, "general", "support", "How do I verify project answer quality protocols?"),
    _case(100, "general", "support", "Explain the storage mutation coordination contract."),
)


def _signature(contract: Any) -> list[dict[str, Any]]:
    return [
        {
            "kind": row.kind,
            "subject": row.subject,
            "relation": row.relation,
            "target": row.target,
            "attribute": row.attribute,
            "item_kind": row.item_kind,
            "expected_value": row.expected_value,
            "response_mode": row.response_mode,
            "context": row.context,
        }
        for row in contract.proof_obligations
    ]


def _evaluate(case: dict[str, Any]) -> dict[str, Any]:
    question = case["question"]
    plan = compile_question_plan(question)
    contract = build_project_answer_contract(question)
    supported_contract = bool(contract.proof_obligations) and not contract.unresolved_parts
    if plan.facets and not plan.unresolved_parts:
        actual = "plan"
    elif not plan.handled and supported_contract:
        actual = "legacy"
    else:
        actual = "abstain"

    expectation = case["expectation"]
    if expectation == "support":
        passed = supported_contract
    elif expectation == "plan":
        passed = actual == "plan" and supported_contract
    elif expectation == "legacy":
        passed = actual == "legacy" and supported_contract
    elif expectation == "abstain":
        passed = not supported_contract
    else:
        raise AssertionError(f"unknown expectation: {expectation}")

    return {
        **case,
        "passed": passed,
        "actual": actual,
        "plan_handled": plan.handled,
        "plan_facets": [
            {
                "kind": row.kind,
                "subject": row.subject,
                "relation": row.relation,
                "target": row.target,
                "context": row.context,
            }
            for row in plan.facets
        ],
        "plan_trace": list(plan.parse_trace),
        "plan_unresolved": list(plan.unresolved_parts),
        "contract_unresolved": list(contract.unresolved_parts),
        "contract_signature": _signature(contract),
    }


def main() -> int:
    assert len(CASES) == 100
    results = [_evaluate(case) for case in CASES]
    failures = [row for row in results if not row["passed"]]
    by_category: dict[str, Counter[str]] = defaultdict(Counter)
    for row in results:
        by_category[row["category"]]["total"] += 1
        by_category[row["category"]]["passed" if row["passed"] else "failed"] += 1
    report = {
        "schema_version": "docatlas-question-probe-v1",
        "total": len(results),
        "passed": len(results) - len(failures),
        "failed": len(failures),
        "actual_ownership": dict(Counter(row["actual"] for row in results)),
        "category_summary": {key: dict(value) for key, value in sorted(by_category.items())},
        "failures": failures,
        "results": results,
    }
    output = Path("question-probe-100-results.json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("QUESTION_PROBE_SUMMARY=" + json.dumps({
        key: report[key] for key in ("total", "passed", "failed", "actual_ownership", "category_summary")
    }, ensure_ascii=False, sort_keys=True))
    print("QUESTION_PROBE_FAILURES_BEGIN")
    print(json.dumps(failures, ensure_ascii=False, indent=2))
    print("QUESTION_PROBE_FAILURES_END")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
