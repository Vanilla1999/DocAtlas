from __future__ import annotations

import json

from docmancer.docs.domain.project_answer_contract import build_project_answer_contract
from docmancer.docs.domain.question_plan import compile_question_plan


def test_dump_current_contract_signatures() -> None:
    questions = [
        "How does prepare_docs sync_project_docs work?",
        "What does Phase 3.1 require for RetrievalDispatcher, the raw topic, EvidenceRequirementSet hints, and vector or embedding calls?",
        "What does docs_status report and when should it be used?",
        "What are the three public Docs MCP tools?",
        "Which source types are supported for indexing?",
        "How do I sync project docs after changing a file?",
        "What are the three public Docs MCP tools and when do I use each one?",
        "How does evidence selection differ from question planning?",
        "Where is the project answer contract documented?",
        "What happens when the preview plan is stale?",
        "Why does clear-index always delete remote Qdrant collections?",
        "What are the public tools and their purposes?",
        "Назови три публичных инструмента Docs MCP и когда использовать каждый.",
        "What is the difference between evidence selection and question planning?",
        "Explain the storage mutation coordination contract.",
    ]
    rows = []
    for question in questions:
        plan = compile_question_plan(question)
        contract = build_project_answer_contract(question)
        rows.append({
            "question": question,
            "plan_handled": plan.handled,
            "plan_trace": list(plan.parse_trace),
            "plan_unresolved": list(plan.unresolved_parts),
            "contract_trace": list(contract.parse_trace),
            "contract_unresolved": list(contract.unresolved_parts),
            "signature": [
                {
                    "kind": item.kind,
                    "subject": item.subject,
                    "attribute": item.attribute,
                    "relation": item.relation,
                    "target": item.target,
                    "value_kind": item.value_kind,
                    "expected_value": item.expected_value,
                    "item_kind": item.item_kind,
                    "cardinality": item.cardinality,
                    "response_mode": item.response_mode,
                    "context": item.context,
                }
                for item in contract.proof_obligations
            ],
        })
    raise AssertionError("SIGNATURE_DUMP=" + json.dumps(rows, ensure_ascii=False, sort_keys=True))
