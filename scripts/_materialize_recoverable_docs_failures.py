#!/usr/bin/env python3
"""One-shot materializer for the recoverable documentation-failure PR."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement, found {count}: {old[:120]!r}")
    write(path, text.replace(old, new, 1))


def replace_optional(path: str, old: str, new: str) -> bool:
    text = read(path)
    if old not in text:
        return False
    write(path, text.replace(old, new))
    return True


# Fix the generated exact-rephrase marker. It recognizes only DocAtlas's own
# fixed wrapper and therefore does not add another natural-language vocabulary.
replace_once(
    "docmancer/docs/application/recovery.py",
    r'r"^\s*according\s+to\s+[`\"\']?(?:\.?\.\?/)?(?:[A-Za-z0-9_.-]+/)*"',
    r'r"^\s*according\s+to\s+[`\"\']?(?:\.{0,2}/)?(?:[A-Za-z0-9_.-]+/)*"',
)

# Exact-document recovery reuses canonical stored sections from the active
# generation. No working-tree reread, no alternate parser, no selector bypass.
replace_once(
    "docmancer/docs/application/_project_docs_service_part03.py",
    "from ._project_docs_service_shared import *  # noqa: F401,F403\n\n\nclass _ProjectDocsServicePart03:\n",
    '''from ._project_docs_service_shared import *  # noqa: F401,F403\nfrom docmancer.core.models import RetrievedChunk\n\n\n_EXACT_DOCUMENT_FALLBACK_LIMIT = 12\n\n\ndef _exact_document_index_chunks(\n    agent: Any,\n    *,\n    root: Path,\n    evidence_path: str,\n    requirements: Any | None,\n) -> list[RetrievedChunk]:\n    \"\"\"Return bounded canonical stored sections for one resolved indexed document.\n\n    This fallback is used only after the normal retrieval lane returned no\n    candidates. It reads the active generation's already-indexed display text,\n    never reparses the working-tree file, and therefore cannot create a second\n    source of truth. Canonical evidence selection still decides support.\n    \"\"\"\n\n    try:\n        rows = list(agent.store.list_sections_for_embedding())\n    except (AttributeError, OSError, RuntimeError):\n        return []\n\n    normalized_path = normalize_doc_path(evidence_path)\n    probes = tuple(dict.fromkeys(\n        probe\n        for requirement in requirements or ()\n        if getattr(requirement, \"mandatory\", False)\n        and (probe := requirement_probe_query(requirement))\n    ))[:8]\n    terms = tuple(dict.fromkeys(\n        token.casefold()\n        for probe in probes\n        for token in re.findall(r\"[A-Za-zА-Яа-яЁё0-9_.:/=+-]{3,}\", probe)\n    ))[:24]\n\n    metadata_cache: dict[str, dict[str, Any]] = {}\n    candidates: list[RetrievedChunk] = []\n    for row in rows:\n        source = str(row.get(\"source\") or \"\")\n        if not source:\n            continue\n        if source not in metadata_cache:\n            try:\n                metadata_cache[source] = dict(agent.store.source_metadata(source) or {})\n            except (AttributeError, OSError, RuntimeError):\n                metadata_cache[source] = {}\n        source_metadata = metadata_cache[source]\n        row_path = normalize_doc_path(\n            source_metadata.get(\"project_doc_path\") or row.get(\"source_path\")\n        )\n        if row_path != normalized_path:\n            continue\n        indexed_project_path = str(\n            source_metadata.get(\"project_path\") or row.get(\"project_path\") or \"\"\n        )\n        if indexed_project_path != str(root):\n            continue\n        source_class = str(\n            source_metadata.get(\"source_class\") or row.get(\"source_class\") or \"\"\n        )\n        if source_class != \"project_file\":\n            continue\n        display_text = str(row.get(\"display_text\") or row.get(\"text\") or \"\").strip()\n        if not display_text:\n            continue\n\n        searchable = \" \".join((\n            str(row.get(\"title\") or \"\"),\n            str(row.get(\"anchor\") or \"\"),\n            str(row.get(\"text\") or \"\"),\n            display_text,\n        )).casefold()\n        hit_count = sum(term in searchable for term in terms)\n        metadata = {**source_metadata}\n        metadata.update({\n            \"project_doc_path\": row_path,\n            \"source_path\": row_path,\n            \"source_class\": source_class,\n            \"project_path\": indexed_project_path,\n            \"project_identity\": (\n                source_metadata.get(\"project_identity\")\n                or row.get(\"project_identity\")\n            ),\n            \"doc_scope\": source_metadata.get(\"doc_scope\") or row.get(\"doc_scope\") or \"project\",\n            \"module_id\": source_metadata.get(\"module_id\") or row.get(\"module_id\"),\n            \"project_doc_authority\": (\n                source_metadata.get(\"project_doc_authority\")\n                or row.get(\"authority\")\n            ),\n            \"project_doc_lifecycle_status\": (\n                source_metadata.get(\"project_doc_lifecycle_status\")\n                or row.get(\"lifecycle_status\")\n                or \"active\"\n            ),\n            \"title\": row.get(\"title\"),\n            \"anchor\": row.get(\"anchor\"),\n            \"token_estimate\": int(row.get(\"token_estimate\") or 0),\n            \"stable_chunk_id\": row.get(\"stable_chunk_id\"),\n            \"parent_logical_id\": row.get(\"parent_logical_id\"),\n        })\n        start, end = row.get(\"char_start\"), row.get(\"char_end\")\n        if isinstance(start, int) and isinstance(end, int) and 0 <= start < end:\n            metadata[\"char_span\"] = [start, end]\n        candidates.append(RetrievedChunk(\n            source=source,\n            chunk_index=int(row.get(\"chunk_index\") or 0),\n            text=display_text,\n            score=float(1000 + hit_count),\n            metadata=metadata,\n        ))\n\n    candidates.sort(key=lambda item: (-item.score, item.chunk_index, item.source))\n    return candidates[:_EXACT_DOCUMENT_FALLBACK_LIMIT]\n\n\nclass _ProjectDocsServicePart03:\n''',
)

replace_once(
    "docmancer/docs/application/_project_docs_service_part03.py",
    '''        chunks = self.query_project_docs(\n            str(root), query, tokens=tokens, limit=limit, expand=expand,\n            scope=query_scope, module_path=resolved_module_path, evidence_path=evidence_path,\n            requirements=requirements,\n        )\n        current_by_path = {\n            item.get(\"path\"): item\n            for item in indexed_sources\n            if item.get(\"path\")\n        }\n        safe_chunks = []\n''',
    '''        chunks = self.query_project_docs(\n            str(root), query, tokens=tokens, limit=limit, expand=expand,\n            scope=query_scope, module_path=resolved_module_path, evidence_path=evidence_path,\n            requirements=requirements,\n        )\n        current_by_path = {\n            item.get(\"path\"): item\n            for item in indexed_sources\n            if item.get(\"path\")\n        }\n        exact_document_fallback_used = False\n        if evidence_path and not chunks and current_by_path.get(evidence_path):\n            chunks = _exact_document_index_chunks(\n                self._agent_instance(),\n                root=root,\n                evidence_path=evidence_path,\n                requirements=requirements,\n            )\n            exact_document_fallback_used = bool(chunks)\n        safe_chunks = []\n''',
)
replace_once(
    "docmancer/docs/application/_project_docs_service_part03.py",
    '''        if dropped_placeholder_chunks:\n            preflight_diagnostics[\"dropped_placeholder_project_docs\"] = dropped_placeholder_chunks\n''',
    '''        if dropped_placeholder_chunks:\n            preflight_diagnostics[\"dropped_placeholder_project_docs\"] = dropped_placeholder_chunks\n        if exact_document_fallback_used:\n            preflight_diagnostics[\"exact_document_index_fallback\"] = True\n''',
)
replace_once(
    "docmancer/docs/application/_project_docs_service_part03.py",
    '''                project_path=str(root),\n                query=query,\n                status=status,\n''',
    '''                project_path=str(root),\n                query=query,\n                resolved_evidence_path=evidence_path,\n                status=status,\n''',
)
replace_once(
    "docmancer/docs/application/_project_docs_service_part03.py",
    '        reason_code = "project_docs_stale" if stale_sources else "no_project_docs_results"\n',
    '''        reason_code = (\n            \"project_docs_stale\"\n            if stale_sources\n            else \"resolved_document_no_witness\"\n            if evidence_path\n            else \"no_project_docs_results\"\n        )\n''',
)
replace_once(
    "docmancer/docs/application/_project_docs_service_part03.py",
    '''            reason="project_docs_stale" if stale_sources else "no_project_docs_results",\n''',
    '''            reason=(\n                \"project_docs_stale\"\n                if stale_sources\n                else \"resolved_document_no_witness\"\n                if evidence_path\n                else \"no_project_docs_results\"\n            ),\n''',
)
replace_once(
    "docmancer/docs/application/_project_docs_service_part03.py",
    '''            message="Indexed project docs exist, but no results matched this query." + (" Some indexed docs are stale." if stale_sources else ""),\n''',
    '''            message=(\n                f\"Indexed document {evidence_path!r} was resolved, but no bounded witness matched the requested requirements.\"\n                if evidence_path and not stale_sources\n                else \"Indexed project docs exist, but no results matched this query.\"\n            ) + (\" Some indexed docs are stale.\" if stale_sources else \"\"),\n''',
)

# Attach recovery diagnosis after canonical support has already been computed.
replace_once(
    "docmancer/docs/interfaces/mcp/context_tools.py",
    "from docmancer.docs.application.evidence_selection import AggregateMixedSelectionDecision, SelectionDecision\n",
    "from docmancer.docs.application.evidence_selection import AggregateMixedSelectionDecision, SelectionDecision\nfrom docmancer.docs.application.recovery import build_recovery_diagnosis, recovery_action\n",
)
replace_once(
    "docmancer/docs/interfaces/mcp/context_tools.py",
    '''    raw = normalize_public_docs_actions(raw)\n    raw.update(_bounded_project_operational_diagnostics(raw))\n    raw = _replace_network_retries_with_prepare_actions(raw, args)\n''',
    '''    raw = normalize_public_docs_actions(raw)\n    raw.update(_bounded_project_operational_diagnostics(raw))\n    raw = _replace_network_retries_with_prepare_actions(raw, args)\n    raw = _attach_recovery_diagnosis(\n        raw,\n        question=question,\n        request=args,\n        canonical_selection=canonical_selection,\n        operational_reason_code=operational_reason_code,\n    )\n''',
)

recovery_helpers = '''\n_RECOVERY_SUMMARY_KEYS = (\n    \"documentation_supported\", \"investigation_allowed\", \"hard_stop\",\n    \"recovery_origin\", \"recovery_reason_code\", \"recovery_disposition\",\n)\n\n\ndef _attach_recovery_diagnosis(\n    payload: dict[str, Any],\n    *,\n    question: str,\n    request: dict[str, Any],\n    canonical_selection: SelectionDecision | AggregateMixedSelectionDecision | None,\n    operational_reason_code: Any = None,\n) -> dict[str, Any]:\n    if canonical_selection is None:\n        return payload\n    support = getattr(canonical_selection, \"support_decision\", None)\n    if support is not None and bool(getattr(support, \"answer_supported\", False)):\n        return payload\n    diagnosis = build_recovery_diagnosis(\n        question,\n        canonical_selection,\n        operational_reason_code=(\n            payload.get(\"operational_reason_code\")\n            or operational_reason_code\n            or payload.get(\"reason_code\")\n        ),\n    )\n    if not diagnosis:\n        return payload\n    updated = dict(payload)\n    updated.update({\n        \"documentation_supported\": bool(diagnosis.get(\"documentation_supported\")),\n        \"investigation_allowed\": bool(diagnosis.get(\"investigation_allowed\", True)),\n        \"hard_stop\": bool(diagnosis.get(\"hard_stop\")),\n        \"recovery_origin\": str(diagnosis.get(\"origin\") or \"selection\"),\n        \"recovery_reason_code\": str(diagnosis.get(\"reason_code\") or \"support_not_provable\"),\n        \"recovery_disposition\": str(diagnosis.get(\"disposition\") or \"search_local_source\"),\n    })\n    action = recovery_action(\n        diagnosis,\n        project_path=_clean_string(request.get(\"project_path\")),\n        scope=_clean_string(request.get(\"scope\")),\n        mode=_clean_string(request.get(\"mode\")),\n    )\n    if action:\n        existing = [\n            item for item in updated.get(\"next_actions\") or []\n            if isinstance(item, dict) and item != action\n        ]\n        updated[\"next_action\"] = action\n        updated[\"next_actions\"] = [action, *existing]\n    return updated\n\n\ndef _recovery_summary(payload: dict[str, Any]) -> dict[str, Any]:\n    return {\n        key: deepcopy(payload[key])\n        for key in _RECOVERY_SUMMARY_KEYS\n        if key in payload\n    }\n\n\ndef _annotate_recovery_handoff(\n    projection: dict[str, Any], recovery: dict[str, Any] | None\n) -> None:\n    hard_stop = bool(projection.get(\"hard_stop\"))\n    if hard_stop:\n        projection.update({\n            \"disposition\": \"resolve_authoritative_conflict\",\n            \"edit_ready\": False,\n            \"source_search_status\": \"blocked\",\n        })\n        _refresh_projection_estimate(projection)\n        return\n    if not isinstance(recovery, dict):\n        return\n    if recovery.get(\"type\") == \"rephrase_question\":\n        projection.update({\n            \"disposition\": \"rephrase_question\",\n            \"edit_ready\": False,\n            \"source_search_status\": \"not_required\",\n            \"requires_confirmation\": False,\n        })\n    elif recovery.get(\"tool\") == \"code_search\":\n        projection.update({\n            \"disposition\": \"search_local_source\",\n            \"edit_ready\": False,\n            \"source_search_status\": \"required\",\n            \"requires_confirmation\": False,\n        })\n    _refresh_projection_estimate(projection)\n\n'''
replace_once(
    "docmancer/docs/interfaces/mcp/context_tools.py",
    "\ndef _bounded_recovery_action(payload: dict[str, Any]) -> dict[str, Any] | None:\n",
    recovery_helpers + "\ndef _bounded_recovery_action(payload: dict[str, Any]) -> dict[str, Any] | None:\n",
)
replace_once(
    "docmancer/docs/interfaces/mcp/context_tools.py",
    '''    elif source_search_required:\n        candidates.sort(key=lambda action: 0 if isinstance(action, dict) and action.get("tool") == "code_search" else 1)\n''',
    '''    elif payload.get("recovery_disposition") == "rephrase_question":\n        candidates.sort(key=lambda action: 0 if isinstance(action, dict) and action.get("type") == "rephrase_question" else 1)\n    elif source_search_required:\n        candidates.sort(key=lambda action: 0 if isinstance(action, dict) and action.get("tool") == "code_search" else 1)\n''',
)
replace_once(
    "docmancer/docs/interfaces/mcp/context_tools.py",
    '''        if tool not in {"prepare_docs", "code_search", "docs_status"} and action_type != "ask_user_for_library_docs_source":\n            continue\n''',
    '''        rephrase = tool == "get_docs_context" and action_type == "rephrase_question"\n        if (\n            tool not in {"prepare_docs", "code_search", "docs_status"}\n            and action_type != "ask_user_for_library_docs_source"\n            and not rephrase\n        ):\n            continue\n''',
)
replace_once(
    "docmancer/docs/interfaces/mcp/context_tools.py",
    '''def _annotate_source_search_handoff(\n    projection: dict[str, Any], recovery: dict[str, Any]\n) -> None:\n    if recovery.get("tool") != "code_search":\n        return\n    projection.update({\n        "disposition": "search_local_source",\n        "edit_ready": False,\n        "source_search_status": "required",\n        "requires_confirmation": False,\n    })\n    _refresh_projection_estimate(projection)\n\n\n''',
    "",
)
# Docs projection: carry diagnosis even when there is no callable recovery (conflict).
replace_once(
    "docmancer/docs/interfaces/mcp/context_tools.py",
    '''            if projection.get("status") == "insufficient_evidence":\n                projection.update(_bounded_project_operational_diagnostics(raw))\n            if projection.get("status") == "insufficient_evidence" and recovery:\n''',
    '''            if projection.get("status") == "insufficient_evidence":\n                projection.update(_bounded_project_operational_diagnostics(raw))\n                projection.update(_recovery_summary(raw))\n            if projection.get("status") == "insufficient_evidence" and recovery:\n''',
)
replace_once(
    "docmancer/docs/interfaces/mcp/context_tools.py",
    '''                projection.update(support_projection)\n                _annotate_source_search_handoff(projection, recovery)\n                _prioritize_module_recovery_projection(projection)\n''',
    '''                projection.update(support_projection)\n                projection.update(_recovery_summary(raw))\n                _annotate_recovery_handoff(projection, recovery)\n                _prioritize_module_recovery_projection(projection)\n''',
)
replace_once(
    "docmancer/docs/interfaces/mcp/context_tools.py",
    '''            if projection.get("status") == "insufficient_evidence":\n                _prioritize_module_recovery_projection(projection)\n''',
    '''            if projection.get("status") == "insufficient_evidence":\n                projection.update(_recovery_summary(raw))\n                _annotate_recovery_handoff(projection, recovery)\n                _prioritize_module_recovery_projection(projection)\n''',
)
# Patch projection uses the same recovery semantics.
replace_once(
    "docmancer/docs/interfaces/mcp/context_tools.py",
    '''            projection = project_insufficient(\n                kind="patch_context",\n                missing=projection.get("missing") or [],\n                recommended_next_action=recovery,\n                max_tokens=min(INSUFFICIENT_EVIDENCE_MAX_TOKENS, output_budget),\n            )\n            _annotate_source_search_handoff(projection, recovery)\n''',
    '''            projection = project_insufficient(\n                kind="patch_context",\n                missing=projection.get("missing") or [],\n                recommended_next_action=recovery,\n                max_tokens=min(INSUFFICIENT_EVIDENCE_MAX_TOKENS, output_budget),\n            )\n            projection.update(_recovery_summary(raw))\n            _annotate_recovery_handoff(projection, recovery)\n''',
)
replace_once(
    "docmancer/docs/interfaces/mcp/context_tools.py",
    '''        if projection.get("status") == "insufficient_evidence":\n            _bound_module_recovery_projection(\n''',
    '''        if projection.get("status") == "insufficient_evidence":\n            projection.update(_recovery_summary(raw))\n            _annotate_recovery_handoff(projection, recovery)\n            _bound_module_recovery_projection(\n''',
)

# Keep recovery identity and one executable rephrase under the 300-token failure budget.
replace_once(
    "docmancer/docs/application/model_visible_projection.py",
    '''    action = payload.get("recommended_next_action")\n    if isinstance(action, dict):\n        for key in (\n            "type", "reason", "confirmation_reason", "agent_question", "observations",\n            "security_scope", "decision_options",\n        ):\n''',
    '''    action = payload.get("recommended_next_action")\n    if isinstance(action, dict):\n        for key in (\n            "observations", "decision_options", "agent_question", "security_scope",\n            "reason", "confirmation_reason",\n        ):\n''',
)
replace_once(
    "docmancer/docs/application/model_visible_projection.py",
    '''    # The terminal fallback contains no unbounded caller data.\n    kind = payload.get("kind")\n    support = {\n''',
    '''    # The terminal fallback contains no unbounded caller data. Recovery\n    # keeps only fixed enums/booleans and one complete server-generated retry.\n    kind = payload.get("kind")\n    recovery_summary = {\n        key: deepcopy(payload[key])\n        for key in (\n            "documentation_supported", "investigation_allowed", "hard_stop",\n            "recovery_origin", "recovery_reason_code", "recovery_disposition",\n        )\n        if key in payload\n    }\n    minimal_recovery = None\n    action = payload.get("recommended_next_action")\n    if isinstance(action, dict) and action.get("type") == "rephrase_question":\n        args = action.get("arguments_patch") if isinstance(action.get("arguments_patch"), dict) else {}\n        question = str(args.get("question") or "")[:320]\n        if question:\n            minimal_recovery = {\n                "tool": "get_docs_context",\n                "type": "rephrase_question",\n                "arguments_patch": {"question": question},\n                "auto_execute": False,\n            }\n    support = {\n''',
)
replace_once(
    "docmancer/docs/application/model_visible_projection.py",
    '''    payload.update(support)\n    payload["answer_supported"] = False\n''',
    '''    payload.update(support)\n    payload.update(recovery_summary)\n    if minimal_recovery is not None:\n        payload["recommended_next_action"] = minimal_recovery\n    payload["answer_supported"] = False\n''',
)

# Advertise bounded recovery fields without adding a tool or changing inputs.
replace_once(
    "docmancer/mcp/_docs_server_schema.py",
    '''        "operational_reason_code": {"type": "string"},\n        "module_candidates": {\n''',
    '''        "operational_reason_code": {"type": "string"},\n        "documentation_supported": {"type": "boolean"},\n        "investigation_allowed": {"type": "boolean"},\n        "hard_stop": {"type": "boolean"},\n        "recovery_origin": {"type": "string"},\n        "recovery_reason_code": {"type": "string"},\n        "recovery_disposition": {"type": "string"},\n        "module_candidates": {\n''',
)

# Runtime/installed guidance follows the same semantic policy.
replace_optional(
    "docmancer/mcp/_docs_server_tool_data.py",
    '- In bounded delivery, stop before editing when action_packet.status is insufficient_evidence. In unbounded exploration, navigation_only or partial_navigational requires source search before answering.',
    '- In bounded delivery, insufficient_evidence never proves a documentary claim. Follow one typed recovery: one non-automatic rephrase for parser/retrieval uncertainty, then local source/tests when hard_stop=false; stop before an edit when hard_stop=true or the task explicitly requires a still-unproved documentary contract. In unbounded exploration, navigation_only or partial_navigational requires source search before answering.',
)
replace_optional(
    "docs/AGENT_DOCS_WORKFLOW.md",
    '4. Inspect the returned status and do not edit when it is `insufficient_evidence`.',
    '4. If the result is `insufficient_evidence`, do not claim documentation support. Follow at most one non-automatic `rephrase_question` recovery for parser/retrieval uncertainty; if it still fails and `hard_stop=false`, continue repository investigation with local source/tests while keeping the documentary claim unproved. Stop before an edit when `hard_stop=true` or when the task explicitly requires a documentary contract that remains unproved.',
)
replace_optional(
    "SKILL.md",
    '4. For bounded responses, inspect `action_packet.status`, `missing_evidence`, and `omitted_counts`; do not edit when status is `insufficient_evidence`.',
    '4. For bounded `insufficient_evidence`, do not claim documentation support. Follow at most one non-automatic `rephrase_question`; after that, investigate local source/tests when `hard_stop=false`. Stop before editing when `hard_stop=true` or when the requested change explicitly depends on a documentary contract that remains unproved.',
)
replace_optional(
    "docmancer/mcp/_docs_server_resources.py",
    '   - `status="insufficient_evidence"`: do not edit. Follow only a typed `recommended_next_action` after required confirmation.',
    '   - `status="insufficient_evidence"`: do not claim documentation support. Follow one typed recovery; a server-suggested rephrase is never automatic. If recovery is exhausted and `hard_stop=false`, investigate local source/tests while keeping documentary claims unproved. Stop before editing on `hard_stop=true` or when the task explicitly requires the still-unproved documentary contract.',
)
replace_optional(
    "docmancer/mcp/_docs_server_resources.py",
    '4. Do not edit on `insufficient_evidence`; follow only the bounded typed recovery action after confirmation.',
    '4. On `insufficient_evidence`, do not claim documentation support. Follow the bounded typed recovery; retry at most one server-suggested rephrase. If it still fails and `hard_stop=false`, use local source/tests for investigation. Stop before editing on `hard_stop=true` or when the task requires the unproved documentary contract.',
)
replace_optional(
    "docmancer/templates/agent_contract.md",
    'do not edit when status is `insufficient_evidence`',
    'do not claim documentation support when status is `insufficient_evidence`; follow one typed recovery, and stop before editing only on `hard_stop=true` or when the task explicitly requires a still-unproved documentary contract',
)
replace_optional(
    "docs/mcp-docs-server.md",
    'The bounded model-visible result is exactly one canonical projection: `docs_answer` for documentation/API questions, `patch_context` for explicit change tasks, or `insufficient_evidence` when required evidence is missing.',
    'The bounded model-visible result is exactly one canonical projection: `docs_answer` for documentation/API questions, `patch_context` for explicit change tasks, or `insufficient_evidence` when required evidence is missing. Recoverable parser/retrieval failures may return one non-automatic `rephrase_question`; after that, `hard_stop=false` permits local source/test investigation without converting it into a documented claim. Authoritative conflicts remain `hard_stop=true`.',
)

# Permanent regression gate: pure recovery classes + real indexed exact-document fallback.
recovery_gate = r'''#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.docs.application.docs_job_service import DocsJobTracker
from docmancer.docs.application.evidence_selection import build_requirements, project_docs_selection_config, select_evidence
from docmancer.docs.application.model_visible_projection import estimate_projection_tokens
from docmancer.docs.application.recovery import build_recovery_diagnosis, recovery_action
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import call_docs_tool_payload
from docmancer.retrieval.query_planning import extract_document_locator

TREASURE = (
    "What is the documented contract for adaptive treasure gem trip sampling across positions 1,2,3, "
    "including 200 completed probes per position, meet_type=6 counters, gold encounter handling, "
    "checkpoint persistence, winner selection, and ambiguous mutation handling?"
)
FIXED_WRAPPER = {"what", "does", "the", "project", "documentation", "say", "about", "according", "to", "it"}


def _decision(question: str, candidates: list[dict], *, profile: str = "project_docs_answer"):
    requirements = build_requirements(question, profile=profile)
    return select_evidence(
        candidates,
        question=question,
        config=project_docs_selection_config(800),
        requirements=requirements,
    )


def _assert_suggestion_integrity(original: str, suggestion: str) -> None:
    original_tokens = set(re.findall(r"[A-Za-zА-Яа-яЁё0-9_.:/=+-]+", original.casefold()))
    suggestion_tokens = set(re.findall(r"[A-Za-zА-Яа-яЁё0-9_.:/=+-]+", suggestion.casefold()))
    invented = {
        token for token in suggestion_tokens
        if token not in original_tokens and token not in FIXED_WRAPPER
    }
    if invented:
        raise AssertionError(f"rephrase invented domain tokens: {sorted(invented)!r}; {suggestion!r}")


def _service(root: Path) -> tuple[LibraryDocsService, Path]:
    os.environ["DOCMANCER_HOME"] = str(root / "home")
    project = root / "project"
    docs = project / "docs"
    docs.mkdir(parents=True)
    (docs / "ADAPTIVE_TREASURE_CONTRACT.md").write_text(
        """# Adaptive Treasure Contract

## Scope
Adaptive treasure trip sampling covers positions 1,2,3.

## Sampling
Each position uses 200 completed probes.

## Counters
meet_type uses value 6 for gem counters.

## Persistence
checkpoint persistence stores completed progress.

## Selection
winner selection chooses the sampled position.

## Recovery
ambiguous mutation handling stops before state mutation.

## Safety
gold encounter handling preserves the gold target.
""",
        encoding="utf-8",
    )
    (project / "docatlas.project-docs.yaml").write_text(
        """schema_version: 1
documents:
  - path: docs/ADAPTIVE_TREASURE_CONTRACT.md
    role: development
    scope: project
    description: Adaptive treasure source-of-truth contract.
    authority: source_of_truth
    status: active
    impact: track
""",
        encoding="utf-8",
    )
    config = DocmancerConfig()
    config.index.db_path = str(root / "docmancer.db")
    config.index.extracted_dir = str(root / "extracted")
    service = LibraryDocsService(
        config=config,
        registry=LibraryRegistry(config.index.db_path),
        agent=DocmancerAgent(config=config),
        job_tracker=DocsJobTracker(),
    )
    sync = service.sync_project_docs(str(project), with_vectors=False)
    if sync.status != "success":
        raise AssertionError(sync)
    return service, project


def main() -> int:
    # 1. Real regression: parser implementation details become bounded recovery,
    # not a global edit prohibition.
    decision = _decision(TREASURE, [])
    diagnosis = build_recovery_diagnosis(TREASURE, decision)
    assert diagnosis["origin"] == "parsing", diagnosis
    assert diagnosis["reason_code"] == "question_parse_uncertain", diagnosis
    assert diagnosis["documentation_supported"] is False
    assert diagnosis["investigation_allowed"] is True
    assert diagnosis["hard_stop"] is False
    assert diagnosis["disposition"] == "rephrase_question", diagnosis
    suggestions = diagnosis.get("suggested_questions") or []
    assert 1 <= len(suggestions) <= 2
    for suggestion in suggestions:
        _assert_suggestion_integrity(TREASURE, suggestion)
    action = recovery_action(diagnosis, project_path="/repo", scope="project", mode="project")
    assert action and action["type"] == "rephrase_question"
    assert action["tool"] == "get_docs_context"
    assert action["auto_execute"] is False
    assert action["arguments_patch"]["question"] == suggestions[0]

    # 2. Unknown modifier fuzz: recovery must not depend on adding words to a
    # special stop-word dictionary.
    for index in range(100):
        nonce = f"zxqv{index}"
        question = f"What is the {nonce} contract for adaptive treasure sampling?"
        d = build_recovery_diagnosis(question, _decision(question, []))
        assert d["hard_stop"] is False, (question, d)
        assert d["origin"] in {"parsing", "retrieval", "selection"}, (question, d)

    # 3. Circuit breaker: one server-generated rephrase may not recursively
    # propose another rephrase.
    retried = suggestions[0]
    exhausted = build_recovery_diagnosis(retried, _decision(retried, []))
    assert exhausted["disposition"] == "search_local_source", exhausted
    assert exhausted["rephrase_exhausted"] is True
    exhausted_action = recovery_action(exhausted, project_path="/repo", mode="project")
    assert exhausted_action and exhausted_action["tool"] == "code_search"
    assert exhausted_action["repeat_docs_context"] is False

    # 4. Eligibility is a concrete evidence-state problem, not a wording problem.
    known = "What are the public tools of the Docs MCP server?"
    stale = _decision(known, [{
        "stable_id": "stale",
        "source": "README.md",
        "content": "The public tools are get_docs_context, prepare_docs, and docs_status.",
        "freshness": "stale",
    }])
    stale_diag = build_recovery_diagnosis(known, stale)
    assert stale_diag["origin"] == "eligibility", stale_diag
    assert stale_diag["disposition"] == "repair_evidence_state"
    assert "suggested_questions" not in stale_diag

    # 5. Documentation gaps are not disguised as parser/retrieval failures.
    navigation = _decision(known, [{
        "stable_id": "navigation",
        "source": "docs/index.md",
        "content": "See the API reference for the public tool inventory.",
        "navigation_only": True,
    }])
    nav_diag = build_recovery_diagnosis(known, navigation)
    assert nav_diag["origin"] == "source_documentation", nav_diag
    assert nav_diag["reason_code"] == "documentation_gap"
    assert nav_diag["disposition"] == "search_local_source"
    assert "suggested_questions" not in nav_diag

    # 6. Positive authoritative conflict is the hard-stop class.
    conflict = {
        "status": "insufficient_evidence",
        "metrics": {"candidate_count": 2, "eligible_count": 2, "selected_count": 0},
        "unresolved_conflicts": ["winner policy conflicts"],
        "support_decision": {
            "answer_supported": False,
            "mandatory_requirement_ids": ["winner"],
            "missing_requirement_ids": ["winner"],
        },
    }
    conflict_diag = build_recovery_diagnosis("What is the winner policy?", conflict)
    assert conflict_diag["origin"] == "conflict", conflict_diag
    assert conflict_diag["hard_stop"] is True
    assert conflict_diag["disposition"] == "resolve_authoritative_conflict"
    assert recovery_action(conflict_diag, project_path="/repo") is None

    # 7. Explicit locator grammar and exact indexed-source fallback. Force the
    # normal lexical lane to zero so success can only come from canonical stored
    # sections for the resolved source.
    locator_question = (
        "According to ADAPTIVE_TREASURE_CONTRACT.md, what does it say about meet_type?"
    )
    assert extract_document_locator(locator_question) == "ADAPTIVE_TREASURE_CONTRACT.md"
    with tempfile.TemporaryDirectory(prefix="docatlas-recovery-") as tmp:
        service, project = _service(Path(tmp))
        original_query = service.project_docs.query_project_docs
        service.project_docs.query_project_docs = lambda *args, **kwargs: []
        try:
            result = call_docs_tool_payload(
                "get_docs_context",
                {
                    "question": "In docs/ADAPTIVE_TREASURE_CONTRACT.md, summarize meet_type.",
                    "project_path": str(project),
                    "mode": "project",
                    "delivery_strategy": "bounded_direct",
                    "packet_tokens": 1500,
                },
                service,
            )
        finally:
            service.project_docs.query_project_docs = original_query
        assert result["status"] == "ok", json.dumps(result, indent=2, default=str)
        assert result["answer_supported"] is True
        assert {row["path_or_url"] for row in result["sources"]} == {
            "docs/ADAPTIVE_TREASURE_CONTRACT.md"
        }
        assert "meet_type" in result["answer"]

        # 8. Public parser recovery is bounded to the insufficient-evidence budget.
        parser_result = call_docs_tool_payload(
            "get_docs_context",
            {
                "question": TREASURE,
                "project_path": str(project),
                "mode": "project",
                "delivery_strategy": "bounded_direct",
                "packet_tokens": 1500,
            },
            service,
        )
        assert parser_result["status"] == "insufficient_evidence", parser_result
        assert parser_result["documentation_supported"] is False
        assert parser_result["investigation_allowed"] is True
        assert parser_result["hard_stop"] is False
        assert parser_result["recovery_origin"] == "parsing", parser_result
        recovery = parser_result.get("recommended_next_action") or {}
        assert recovery.get("type") == "rephrase_question", parser_result
        assert recovery.get("auto_execute") is False
        assert recovery.get("arguments_patch", {}).get("question")
        assert estimate_projection_tokens(parser_result) <= 300

    print(
        "PASS: parser/retrieval failures expose bounded non-automatic recovery; "
        "100 unknown contract modifiers do not create hard stops; rephrase is limited "
        "to one retry; eligibility/documentation/conflict classes remain distinct; "
        "exact indexed documents recover canonical stored sections when lexical retrieval misses; "
        "public insufficient projection stays <=300 tokens"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''
write("scripts/run_recovery_contract_gate.py", recovery_gate)

mutation_gate = r'''#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = [sys.executable, "scripts/run_recovery_contract_gate.py"]
MUTANTS = (
    (
        "rephrase-auto-executes",
        "docmancer/docs/application/recovery.py",
        '"auto_execute": False,',
        '"auto_execute": True,',
    ),
    (
        "authoritative-conflict-does-not-stop",
        "docmancer/docs/application/recovery.py",
        '"hard_stop": True,',
        '"hard_stop": False,',
    ),
    (
        "unbounded-rephrase-loop",
        "docmancer/docs/application/recovery.py",
        'if _already_rephrased(question):',
        'if False and _already_rephrased(question):',
    ),
    (
        "rephrase-invents-domain-fact",
        "docmancer/docs/application/recovery.py",
        'fragment = _clean_fragment(fragment, max_chars=140)',
        'fragment = "INVENTED_DOMAIN_FACT"',
    ),
    (
        "eligibility-treated-as-retrieval",
        "docmancer/docs/application/recovery.py",
        'elif proof_origin == "eligibility":',
        'elif False and proof_origin == "eligibility":',
    ),
    (
        "exact-document-fallback-disabled",
        "docmancer/docs/application/_project_docs_service_part03.py",
        'if evidence_path and not chunks and current_by_path.get(evidence_path):',
        'if False and evidence_path and not chunks and current_by_path.get(evidence_path):',
    ),
)


def run_gate() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        GATE,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
        check=False,
    )


def main() -> int:
    baseline = run_gate()
    if baseline.returncode != 0:
        print(baseline.stdout, file=sys.stderr)
        print("FAIL: recovery mutation baseline is red", file=sys.stderr)
        return 1

    killed = 0
    for name, relative, old, new in MUTANTS:
        path = ROOT / relative
        original = path.read_text(encoding="utf-8")
        if original.count(old) != 1:
            print(f"FAIL: mutant {name} patch target count={original.count(old)}", file=sys.stderr)
            return 1
        path.write_text(original.replace(old, new, 1), encoding="utf-8")
        try:
            result = run_gate()
        finally:
            path.write_text(original, encoding="utf-8")
        if result.returncode == 0:
            print(f"FAIL: mutant survived: {name}\n{result.stdout}", file=sys.stderr)
            return 1
        killed += 1
        print(f"KILLED: {name}")

    if killed != len(MUTANTS):
        print(f"FAIL: killed {killed}/{len(MUTANTS)}", file=sys.stderr)
        return 1
    print(f"PASS: recoverable documentation failure mutation gate killed {killed}/{len(MUTANTS)} mutants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''
write("scripts/run_recovery_mutation_gate.py", mutation_gate)

# Wire both permanent gates into advanced CI.
replace_once(
    ".github/workflows/ci.yml",
    '''      - name: Run legacy contract completeness gate\n        run: python scripts/run_legacy_contract_gate.py\n\n      - name: Run Project Docs self-hosting closure gate\n''',
    '''      - name: Run legacy contract completeness gate\n        run: python scripts/run_legacy_contract_gate.py\n\n      - name: Run recoverable documentation failure gate\n        run: python scripts/run_recovery_contract_gate.py\n\n      - name: Run recoverable documentation failure mutation gate\n        run: python scripts/run_recovery_mutation_gate.py\n\n      - name: Run Project Docs self-hosting closure gate\n''',
)

print("materialized recoverable documentation failure implementation")
