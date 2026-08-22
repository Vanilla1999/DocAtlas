from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement anchor, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


recovery_projection = ROOT / "docmancer/docs/interfaces/mcp/recovery_projection.py"
replace_once(
    recovery_projection,
    """def _annotate_recovery_handoff(\n    projection: dict[str, Any], recovery: dict[str, Any] | None\n) -> None:\n""",
    """def _annotate_recovery_handoff(\n    projection: dict[str, Any],\n    recovery: dict[str, Any] | None,\n    *,\n    edit_authorized: bool = False,\n) -> None:\n""",
)
replace_once(
    recovery_projection,
    """    elif is_safe_local_source_handoff(recovery):\n        projection.update({\n            \"disposition\": \"search_local_source\",\n            \"edit_ready\": True,\n            \"source_search_status\": \"required\",\n            \"requires_confirmation\": False,\n        })\n""",
    """    elif is_safe_local_source_handoff(recovery):\n        # Source investigation and edit authorization are separate decisions.\n        # Only the host-owned request classifier may authorize continuation of\n        # an explicit mutation workflow; the recovery action cannot self-grant it.\n        projection.update({\n            \"disposition\": \"search_local_source\",\n            \"edit_ready\": bool(edit_authorized),\n            \"source_search_status\": \"required\",\n            \"requires_confirmation\": False,\n        })\n""",
)

context_tools = ROOT / "docmancer/docs/interfaces/mcp/context_tools.py"
text = context_tools.read_text(encoding="utf-8")
old = """        recovery = _bounded_recovery_action(raw)\n        kind = projection_kind(question)\n"""
new = """        recovery = _bounded_recovery_action(raw)\n        source_search_edit_authorized = bool(\n            mutation_intent.operation != \"none\"\n            and not raw.get(\"hard_stop\")\n            and not raw.get(\"requires_confirmation\")\n            and not is_operational_recovery_action(recovery)\n        )\n        kind = projection_kind(question)\n"""
if text.count(old) != 1:
    raise SystemExit(
        f"{context_tools}: expected one host authorization anchor, found {text.count(old)}"
    )
text = text.replace(old, new, 1)
old = """        mutation = packet.get(\"mutation_intent\") if isinstance(packet.get(\"mutation_intent\"), dict) else {}\n        if mutation.get(\"operation\") != \"none\" and mutation.get(\"ready\") is not True:\n"""
new = """        mutation = packet.get(\"mutation_intent\") if isinstance(packet.get(\"mutation_intent\"), dict) else {}\n        if source_search_edit_authorized and mutation.get(\"ready\") is not True:\n"""
if text.count(old) != 1:
    raise SystemExit(
        f"{context_tools}: expected one mutation target-resolution anchor, found {text.count(old)}"
    )
text = text.replace(old, new, 1)
old = """                \"tool\": \"code_search\",\n                \"type\": \"search_local_source\",\n                \"reason\": \"Resolve the requested mutation target before editing.\",\n"""
new = """                \"tool\": \"code_search\",\n                \"type\": \"search_local_source\",\n                \"handled_by\": \"coding_agent\",\n                \"reason\": \"Resolve the requested mutation target before editing.\",\n"""
if text.count(old) != 1:
    raise SystemExit(
        f"{context_tools}: expected one generated source-handoff anchor, found {text.count(old)}"
    )
text = text.replace(old, new, 1)
old = """                \"requires_confirmation\": False,\n                \"auto_execute\": False,\n            }\n"""
new = """                \"requires_confirmation\": False,\n                \"repeat_docs_context\": False,\n                \"auto_execute\": False,\n            }\n"""
if text.count(old) != 1:
    raise SystemExit(
        f"{context_tools}: expected one generated handoff safety anchor, found {text.count(old)}"
    )
text = text.replace(old, new, 1)
old_call = "            _annotate_recovery_handoff(projection, recovery)\n"
if text.count(old_call) != 4:
    raise SystemExit(
        f"{context_tools}: expected four recovery annotations, found {text.count(old_call)}"
    )
new_call = """            _annotate_recovery_handoff(\n                projection,\n                recovery,\n                edit_authorized=source_search_edit_authorized,\n            )\n"""
text = text.replace(old_call, new_call)
context_tools.write_text(text, encoding="utf-8")

readiness_tests = ROOT / "tests/test_source_search_edit_readiness.py"
replace_once(
    readiness_tests,
    """def test_projection_does_not_authorize_partial_code_search_shape() -> None:\n    projection = {\"hard_stop\": False}\n    action = _safe_action()\n    action.pop(\"auto_execute\")\n\n    _annotate_recovery_handoff(projection, action)\n\n    assert projection.get(\"edit_ready\") is not True\n""",
    """def test_projection_does_not_authorize_partial_code_search_shape() -> None:\n    projection = {\"hard_stop\": False}\n    action = _safe_action()\n    action.pop(\"auto_execute\")\n\n    _annotate_recovery_handoff(projection, action, edit_authorized=True)\n\n    assert projection.get(\"edit_ready\") is not True\n""",
)
replace_once(
    readiness_tests,
    """def test_projection_authorizes_complete_safe_source_handoff() -> None:\n    projection = {\"hard_stop\": False}\n\n    _annotate_recovery_handoff(projection, _safe_action())\n\n    assert projection[\"disposition\"] == \"search_local_source\"\n    assert projection[\"edit_ready\"] is True\n    assert projection[\"source_search_status\"] == \"required\"\n""",
    """def test_projection_authorizes_complete_safe_source_handoff() -> None:\n    projection = {\"hard_stop\": False}\n\n    _annotate_recovery_handoff(\n        projection, _safe_action(), edit_authorized=True\n    )\n\n    assert projection[\"disposition\"] == \"search_local_source\"\n    assert projection[\"edit_ready\"] is True\n    assert projection[\"source_search_status\"] == \"required\"\n\n    investigation_only = {\"hard_stop\": False}\n    _annotate_recovery_handoff(investigation_only, _safe_action())\n    assert investigation_only[\"disposition\"] == \"search_local_source\"\n    assert investigation_only[\"edit_ready\"] is False\n    assert investigation_only[\"source_search_status\"] == \"required\"\n""",
)
replace_once(
    readiness_tests,
    """    _annotate_recovery_handoff(projection, _safe_action())\n\n    assert projection[\"disposition\"] == \"resolve_authoritative_conflict\"\n""",
    """    _annotate_recovery_handoff(\n        projection, _safe_action(), edit_authorized=True\n    )\n\n    assert projection[\"disposition\"] == \"resolve_authoritative_conflict\"\n""",
)

service_tests = ROOT / "tests/test_docs_service_part03.py"
replace_once(
    service_tests,
    """    assert index_witness_payload[\"edit_ready\"] is True\n    assert index_witness_payload[\"recommended_next_action\"][\"tool\"] == \"code_search\"\n    assert \"library_docs_service.py\" in index_witness_payload[\"recommended_next_action\"][\"suggested_doc_paths\"]\n""",
    """    assert index_witness_payload[\"edit_ready\"] is True\n    source_handoff = index_witness_payload[\"recommended_next_action\"]\n    assert source_handoff[\"tool\"] == \"code_search\"\n    assert source_handoff[\"type\"] == \"search_local_source\"\n    assert source_handoff[\"handled_by\"] == \"coding_agent\"\n    assert source_handoff[\"requires_confirmation\"] is False\n    assert source_handoff[\"repeat_docs_context\"] is False\n    assert source_handoff[\"auto_execute\"] is False\n    assert \"library_docs_service.py\" in source_handoff[\"suggested_doc_paths\"]\n""",
)

print("edit-readiness repair materialized")
