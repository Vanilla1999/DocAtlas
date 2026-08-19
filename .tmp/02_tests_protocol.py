from pathlib import Path
import hashlib
import json
import re


def r(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"{path}: replacement count={text.count(old)}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


path = "tests/docs/test_question_plan_v4.py"
probe = '''        (\n            requirements,\n            _unit(\n                "OrderValidationContract requires a non-empty customer id, "\n                "at least one line item, and a positive total."\n            ),\n            True,\n        ),\n'''
r(
    path,
    probe,
    probe + '''        (\n            requirements,\n            _unit("OrderValidationContract requires a positive total."),\n            True,\n        ),\n        (\n            requirements,\n            _unit(\n                "OrderValidationContract requires:\\n"\n                "- a positive total.",\n                kind="unit_group",\n            ),\n            True,\n        ),\n        (\n            requirements,\n            _unit("OrderValidationContract requires."),\n            False,\n        ),\n        (\n            requirements,\n            _unit("PaymentContract requires a positive total."),\n            False,\n        ),\n''',
)
probe = '''    assert local_proof_for_obligation(\n        readme_behavior,\n        _unit("The amber lighthouse invariant requires deterministic offline release checks."),\n        source={"authority": "source_of_truth", "path": "README.md"},\n    ).valid is True\n'''
r(
    path,
    probe,
    probe + '''    assert local_proof_for_obligation(\n        readme_behavior,\n        _unit(\n            "Deterministic offline release checks appear in this section. "\n            "PaymentOutbox validates payments.",\n            kind="unit_group",\n        ),\n        source={"authority": "source_of_truth", "path": "README.md"},\n    ).valid is False\n''',
)

path = "tests/test_tool_selection_policy.py"
r(
    path,
    '''from docmancer.docs.domain.tool_selection import (\n    PUBLIC_DOCS_TOOLS,\n    select_public_docs_tool,\n)\n''',
    '''from docmancer.docs.domain.tool_selection import (\n    PUBLIC_DOCS_TOOLS,\n    normalize_public_docs_action,\n    select_public_docs_tool,\n)\n''',
)
r(
    path,
    'def test_natural_docs_question_defaults_to_context():\n',
    '''def test_returned_docs_status_action_has_priority_and_requests_module_details():\n    decision = select_public_docs_tool(\n        "How does authentication work?",\n        next_action_tool="docs_status",\n    )\n\n    assert decision.tool == "docs_status"\n    assert decision.reason_code == "returned_next_action"\n\n    action = normalize_public_docs_action({\n        "tool": "inspect_project_docs",\n        "arguments_patch": {"project_path": "/repo"},\n    })\n    assert action is not None\n    assert action["tool"] == "docs_status"\n    assert action["arguments_patch"] == {\n        "project_path": "/repo",\n        "action": "project",\n        "details": True,\n    }\n\n\ndef test_unrecognized_returned_action_does_not_escape_public_allowlist():\n    decision = select_public_docs_tool(\n        "How does authentication work?",\n        next_action_tool="inspect_project_docs",\n    )\n\n    assert decision.tool == "get_docs_context"\n    assert decision.reason_code == "natural_question_entrypoint"\n\n\ndef test_natural_docs_question_defaults_to_context():\n''',
)

p = Path("tests/test_unified_docs_context_mcp.py")
p.write_text(
    p.read_text(encoding="utf-8")
    + '''\n\ndef test_module_recovery_projection_keeps_callable_action_and_full_path_under_tiny_budget():\n    from docmancer.docs.interfaces.mcp.context_tools import (\n        _bound_module_recovery_projection,\n    )\n\n    paths = [\n        f"services/domain_{index:02d}/" + "deep_segment/" * 6 + "auth"\n        for index in range(8)\n    ]\n    payload = {\n        "status": "insufficient_evidence",\n        "kind": "docs_answer",\n        "missing": ["unrelated diagnostic prose " * 8 for _ in range(5)],\n        "answer_supported": False,\n        "answer_available": False,\n        "support_status": "insufficient_evidence",\n        "decision_hash": "a" * 64,\n        "operational_status": "module_ambiguous",\n        "operational_reason_code": "module_ambiguous",\n        "recommended_next_action": {\n            "tool": "docs_status",\n            "type": "docs_status",\n            "arguments_patch": {\n                "action": "project",\n                "project_path": "/repo",\n                "details": True,\n            },\n            "reason": "inspect exact module paths " * 12,\n            "auto_execute": False,\n        },\n        "module_candidates": [\n            {\n                "module_path": value,\n                "module_name": "auth",\n                "module_type": "service",\n            }\n            for value in paths\n        ],\n        "estimated_tokens": 0,\n    }\n\n    _bound_module_recovery_projection(payload, max_tokens=256)\n\n    assert payload["estimated_tokens"] <= 256\n    assert payload["operational_reason_code"] == "module_ambiguous"\n    assert payload["edit_ready"] is False\n    assert payload["recommended_next_action"]["tool"] == "docs_status"\n    assert payload["recommended_next_action"]["arguments_patch"] == {\n        "action": "project",\n        "project_path": "/repo",\n        "details": True,\n    }\n    visible_paths = [row["module_path"] for row in payload["module_candidates"]]\n    assert visible_paths\n    assert all(value in paths for value in visible_paths)\n    assert all(not value.endswith("...") for value in visible_paths)\n''',
    encoding="utf-8",
)

p = Path("eval/agent_developer_v1/tasks.json")
data = json.loads(p.read_text(encoding="utf-8"))
row = next(x for x in data["tasks"] if x["id"] == "ambiguous_module_recovery_named_gap")
if row.get("max_get_docs_context_calls") != 1:
    raise RuntimeError("unexpected context-call baseline")
row["max_get_docs_context_calls"] = 2
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

p = Path("eval/agent_developer_v1/expected_trajectories.json")
data = json.loads(p.read_text(encoding="utf-8"))
row = next(x for x in data["trajectories"] if x["id"] == "ambiguous_module_recovery_named_gap")
row["required_scopes"] = [
    {"scope": "module", "module": "auth"},
    {"scope": "module", "module_path": "packages/auth"},
]
row["forbidden_sources"] = []
call = row["calls"][0]
call["forbidden_sources"] = ["packages/auth/README.md", "services/auth/README.md"]
call["target_next_action_arguments"] = {
    "action": "project",
    "project_path": "$PROJECT",
    "details": True,
}
call["target_requires_confirmation"] = False
call["target_edit_ready"] = False
call["target_follow_up"] = {
    "tool": "docs_status",
    "required_module_candidates": ["packages/auth", "services/auth"],
    "retry": {
        "question": "What is PackageAuthBoundary?",
        "mode": "project",
        "scope": "module",
        "module_path": "packages/auth",
        "target_expected_status": "ok",
        "required_sources": ["packages/auth/README.md"],
        "forbidden_sources": ["services/auth/README.md"],
    },
}
for task_id in ("stale_module_docs_recovery", "dependency_prefetch_recovery"):
    target = next(x for x in data["trajectories"] if x["id"] == task_id)["calls"][0]
    target["target_requires_confirmation"] = True
    target["target_edit_ready"] = False
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

r(
    "eval/agent_developer_v1/README.md",
    '''The runner exits non-zero when a call matches neither its frozen baseline nor its complete target contract, or when it produces false support, missing required evidence, a wrong recovery action, or forbidden-source contamination. A target gap is reported until the complete target contract is closed.\n''',
    '''The runner exits non-zero when a call matches neither its frozen baseline nor its complete target contract, or when it produces false support, missing required evidence, a wrong recovery action, or forbidden-source contamination. It also validates that the declared working file exists, that `required_scopes` exactly match the complete target trajectory, and that the published target metrics are actually met. A target gap is reported until the complete target contract is closed.\n''',
)
r(
    "eval/agent_developer_v1/README.md",
    '''After the scope/recovery contract hardening, the provider-free oracle closes all **11/11** reviewed trajectories. Module ambiguity remains fail-closed, but the bounded response preserves `operational_reason_code=module_ambiguous`, returns at most eight exact `module_candidates`, recommends public `docs_status`, and requires the agent to retry with an exact `module_path`. The permanent `advanced-contract` CI job runs this protocol on every pull request and push to `main`.\n''',
    '''After the scope/recovery contract hardening, the provider-free oracle closes all **11/11** reviewed trajectories. Module ambiguity remains fail-closed: the bounded response preserves `operational_reason_code=module_ambiguous`, keeps as many complete exact `module_candidates` as fit the packet budget, recommends public `docs_status(action="project", details=true)`, verifies the returned module inventory, and performs a second bounded call with an exact `module_path`. The permanent `advanced-contract` CI job runs this protocol on every pull request and push to `main`.\n''',
)

labels_path = Path("tests/diagnostic_labels.json")
labels = json.loads(labels_path.read_text(encoding="utf-8"))
changed = {
    "tests/docs/test_question_plan_v4.py",
    "tests/test_tool_selection_policy.py",
    "tests/test_unified_docs_context_mcp.py",
}
updated = False

def walk(value):
    global updated
    if isinstance(value, dict):
        for key, child in list(value.items()):
            if key in changed and isinstance(child, str) and re.fullmatch(r"[0-9a-f]{64}", child):
                value[key] = hashlib.sha256(Path(key).read_bytes()).hexdigest()
                updated = True
            else:
                walk(child)
    elif isinstance(value, list):
        for child in value:
            walk(child)

walk(labels)
if updated:
    labels_path.write_text(json.dumps(labels, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
