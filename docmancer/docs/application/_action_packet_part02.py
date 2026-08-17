"""Implementation shard 2 for action_packet."""
from __future__ import annotations

from ._action_packet_shared import *  # noqa: F401,F403

from ._action_packet_part01 import _authority, _blocked_source_keys, _cited_evidence_ids, _content_text, _extract_facts, _has_actionable_items, _instruction_risk_flags, _item_source_keys, _normalized_source_key, _refresh_estimated_tokens, _section, _source_path, _version_exactness_rank, estimate_action_packet_tokens

def _authority_conflicts(
    items: Iterable[dict[str, Any]], trust_contract: dict[str, Any]
) -> list[tuple[str, str]]:
    constraints: dict[str, dict[str, set[tuple[str, str]]]] = {}
    blocked_sources = _blocked_source_keys(trust_contract)
    for item in items:
        if (
            _authority(item) != "canonical"
            or item.get("freshness") == "stale"
            or not _source_path(item)
            or _instruction_risk_flags(item)
            or _item_source_keys(item) & blocked_sources
        ):
            continue
        identity = _item_identity(item)
        content = _content_text(item).strip()
        facts, _ = _extract_facts(content)
        for fact_type, fact in facts:
            if fact_type not in {"required", "forbidden"}:
                continue
            signature = _constraint_signature(fact)
            if signature:
                constraints.setdefault(signature, {}).setdefault(fact_type, set()).add(identity)
    conflicts: set[tuple[str, str]] = set()
    for by_type in constraints.values():
        if by_type.get("required") and by_type.get("forbidden"):
            conflicts.update(by_type["required"])
            conflicts.update(by_type["forbidden"])
    return sorted(conflicts)


def _constraint_signature(value: str) -> str:
    normalized = re.sub(
        r"\b(?:must|shall|required|requires?|invariant|do|not|never|forbidden|prohibited|this|is|be)\b",
        " ",
        value.lower(),
    )
    return " ".join(re.findall(r"[a-z0-9_]+", normalized))


def _may_guide_workflow(item: dict[str, Any]) -> bool:
    return (
        _authority(item) == "canonical"
        and item.get("repository_authority") == "explicit_agent_policy"
        and item.get("instruction_trust") == "scoped_agent_policy"
        and bool(item.get("scope_verified"))
        and not _instruction_risk_flags(item)
    )


def _version_candidate_identity(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("canonical_id") or item.get("library_id") or _source_path(item)),
        _section(item),
        str(item.get("requested_version") or ""),
    )


def _drop_superseded_fallbacks(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    exact_identities = {
        _version_candidate_identity(item)
        for item in items
        if _version_exactness_rank(item) == 0
    }
    return [
        item
        for item in items
        if not (
            _version_exactness_rank(item) == 2
            and _version_candidate_identity(item) in exact_identities
        )
    ]


def _item_identity(item: dict[str, Any]) -> tuple[str, str]:
    return _source_path(item), _section(item)


def _validation_bucket(fact: str) -> str:
    lowered = fact.lower()
    if re.search(
        r"\b(python\s+-m\s+compileall|cargo\s+(check|build)|tsc|dart\s+analyze|"
        r"(?:\./)?gradlew?\s+.*build|(?:npm|pnpm|yarn)\s+(?:run\s+)?build|make\s+build|"
        r"go\s+build|dotnet\s+build|mvn\s+package)\b",
        lowered,
    ):
        return "compile"
    if re.search(r"\b(ruff|mypy|lint|go\s+vet)\b", lowered):
        return "semantic"
    return "tests"


def _bounded_text(value: str, max_characters: int) -> tuple[str, int]:
    if len(value) <= max_characters:
        return value, 0
    prefix = value[:max_characters].rsplit(" ", 1)[0].rstrip()
    if not prefix:
        prefix = value[:max_characters]
    return prefix, len(value) - len(prefix)


def _dedupe_dicts(rows: Iterable[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[tuple[str, ...]] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        identity = tuple(str(row.get(key) or "") for key in keys)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(row)
    return result


def _prune_orphan_sources(
    packet: dict[str, Any], required_source_keys: set[str] | frozenset[str] = frozenset()
) -> None:
    used = _cited_evidence_ids(packet)
    packet["source_of_truth"] = [
        row for row in packet["source_of_truth"]
        if row.get("evidence_id") in used
        or _normalized_source_key(row.get("path")) in required_source_keys
    ]


def _has_behavioral_contract(packet: dict[str, Any]) -> bool:
    raw_task = packet.get("task_interpretation")
    task: dict[str, Any] = raw_task if isinstance(raw_task, dict) else {}
    rows = [
        *(task.get("acceptance_conditions") or []),
        *(packet.get("required_invariants") or []),
        *(packet.get("forbidden_changes") or []),
        *(packet.get("implementation_guidance") or []),
    ]
    return any(
        classify_normative_modality(str(row.get("text") or "")) is not None
        for row in rows
        if isinstance(row, dict)
    )


def _fit_packet(
    packet: dict[str, Any],
    budget: int,
    required_source_keys: set[str],
    required_target_keys: set[str],
    mandatory_guidance: set[tuple[str, str]] | frozenset[tuple[str, str]] = frozenset(),
) -> None:
    while estimate_action_packet_tokens(packet) > budget and _remove_one_budget_item(
        packet, required_source_keys, required_target_keys, mandatory_guidance
    ):
        pass
    _prune_orphan_sources(packet, required_source_keys)
    if not packet["source_of_truth"]:
        packet["status"] = "insufficient_evidence"
        message = "No source attribution fit the requested packet budget."
        if message not in packet["missing_evidence"]:
            packet["missing_evidence"].append(message)


def _remove_one_budget_item(
    packet: dict[str, Any],
    required_source_keys: set[str],
    required_target_keys: set[str],
    mandatory_guidance: set[tuple[str, str]] | frozenset[tuple[str, str]] = frozenset(),
) -> bool:
    guidance = packet["implementation_guidance"]
    for index in range(len(guidance) - 1, -1, -1):
        row = guidance[index]
        if any(
            (str(row.get("text") or ""), str(evidence_id)) in mandatory_guidance
            for evidence_id in row.get("evidence_ids") or []
        ):
            continue
        guidance.pop(index)
        _record_omission(packet, "implementation_guidance")
        _prune_orphan_sources(packet, required_source_keys)
        return True

    objective = str(packet["task_interpretation"].get("objective") or "")
    if len(objective) > 32:
        target = max(32, len(objective) - max(32, len(objective) // 4))
        shortened, removed = _bounded_text(objective, target)
        packet["task_interpretation"]["objective"] = shortened
        _record_omission(packet, "task_interpretation.objective_characters", removed)
        return True

    symbols = packet["target_surface"]["symbols"]
    if symbols:
        symbols.pop()
        _record_omission(packet, "target_surface.symbols")
        _prune_orphan_sources(packet, required_source_keys)
        return True

    likely_files = packet["target_surface"]["likely_files"]
    for index in range(len(likely_files) - 1, -1, -1):
        if _normalized_source_key(likely_files[index].get("path")) in required_target_keys:
            continue
        likely_files.pop(index)
        _record_omission(packet, "target_surface.likely_files")
        _prune_orphan_sources(packet, required_source_keys)
        return True
    if not required_source_keys and not required_target_keys:
        rows_by_name = [
            ("validation.semantic_checks", packet["validation"]["semantic_checks"]),
            ("validation.compile", packet["validation"]["compile"]),
            ("validation.tests", packet["validation"]["tests"]),
            (
                "task_interpretation.acceptance_conditions",
                packet["task_interpretation"]["acceptance_conditions"],
            ),
            ("forbidden_changes", packet["forbidden_changes"]),
            ("required_invariants", packet["required_invariants"]),
        ]
        for name, rows in rows_by_name:
            if not rows:
                continue
            rows.pop()
            _record_omission(packet, name)
            if name in {
                "task_interpretation.acceptance_conditions",
                "forbidden_changes",
                "required_invariants",
            }:
                packet["status"] = "insufficient_evidence"
                message = "Critical constraints did not fit the requested packet budget."
                if message not in packet["missing_evidence"]:
                    packet["missing_evidence"].append(message)
            _prune_orphan_sources(packet, required_source_keys)
            return True
    if guidance:
        guidance.pop()
        _record_omission(packet, "mandatory_requirements")
        packet["status"] = "insufficient_evidence"
        message = "Mandatory selected evidence did not fit the requested packet budget."
        if message not in packet["missing_evidence"]:
            packet["missing_evidence"].append(message)
        _prune_orphan_sources(packet, required_source_keys)
        return True
    return False


def _ensure_post_fit_status(
    packet: dict[str, Any], required_source_keys: set[str] | frozenset[str] = frozenset()
) -> None:
    _prune_orphan_sources(packet, required_source_keys)
    if "task_interpretation.objective_characters" in packet.get("omitted_counts", {}):
        packet["status"] = "insufficient_evidence"
        message = "The complete task objective did not fit the bounded handoff."
        if message not in packet["missing_evidence"]:
            packet["missing_evidence"].append(message)
    if not _has_actionable_items(packet):
        packet["status"] = "insufficient_evidence"
        message = "No actionable evidence remained after applying the packet budget."
        if message not in packet["missing_evidence"]:
            packet["missing_evidence"].append(message)
    if not packet["source_of_truth"]:
        packet["status"] = "insufficient_evidence"
        message = "No source attribution remained after applying the packet budget."
        if message not in packet["missing_evidence"]:
            packet["missing_evidence"].append(message)


def _compact_failure_packet(packet: dict[str, Any], budget: int) -> None:
    original_omissions = {
        str(key): int(value)
        for key, value in packet.get("omitted_counts", {}).items()
        if isinstance(key, str)
        and key
        and isinstance(value, int)
        and not isinstance(value, bool)
        and value > 0
    }
    omitted_total = sum(original_omissions.values())

    required_invariants_omitted = (
        original_omissions.get("required_invariants", 0)
        + original_omissions.get("mandatory_requirements", 0)
    )
    objective_characters_omitted = original_omissions.get(
        "task_interpretation.objective_characters", 0
    )
    compact_omissions: dict[str, int] = {}
    if required_invariants_omitted:
        compact_omissions["required_invariants"] = required_invariants_omitted
    if objective_characters_omitted:
        compact_omissions["task_interpretation.objective_characters"] = (
            objective_characters_omitted
        )

    residual = max(
        0,
        omitted_total - required_invariants_omitted - objective_characters_omitted,
    )
    if residual > 0:
        compact_omissions["packet_items"] = residual
    if not compact_omissions:
        compact_omissions = {
            "packet_items": max(1, omitted_total)
        }

    contract_reason = "Source-backed behavioral contract is required before editing."
    failure_reason = (
        contract_reason
        if contract_reason in packet.get("missing_evidence", [])
        else "The available evidence did not fit the requested packet budget."
    )
    packet.update({
        "status": "insufficient_evidence",
        "source_of_truth": [],
        "target_surface": {"likely_files": [], "symbols": []},
        "required_invariants": [],
        "forbidden_changes": [],
        "implementation_guidance": [],
        "validation": {"compile": [], "tests": [], "semantic_checks": []},
        "uncertainties": [],
        "missing_evidence": [failure_reason],
        "omitted_counts": compact_omissions,
    })
    mutation = packet.get("mutation_intent")
    if isinstance(mutation, dict):
        packet["mutation_intent"] = {
            "operation": mutation.get("operation", "none"),
            "artifact_kind": mutation.get("artifact_kind", "unknown"),
            "requested_targets": [],
            "resolved_targets": [],
            "destination": mutation.get("destination"),
            "acceptance_conditions": [],
            "ready": False,
            "constraints_only": bool(mutation.get("constraints_only")),
            "missing": list(mutation.get("missing") or [])[:3],
            "contract_hash": mutation.get("contract_hash") or "0" * 64,
        }
    objective = str(packet["task_interpretation"].get("objective") or "task")
    packet["task_interpretation"]["objective"] = objective[:64] or "task"
    packet["task_interpretation"]["acceptance_conditions"] = []
    _refresh_estimated_tokens(packet)
    if packet["estimated_tokens"] > budget:
        packet["task_interpretation"]["objective"] = "task"
        packet["missing_evidence"] = ["Evidence did not fit the packet budget."]
        _refresh_estimated_tokens(packet)


def _record_omission(packet: dict[str, Any], field: str, count: int = 1) -> None:
    packet["omitted_counts"][field] = int(packet["omitted_counts"].get(field) or 0) + count
    if packet["status"] == "ok":
        packet["status"] = "truncated"

__all__=['_authority_conflicts', '_constraint_signature', '_may_guide_workflow', '_version_candidate_identity', '_drop_superseded_fallbacks', '_item_identity', '_validation_bucket', '_bounded_text', '_dedupe_dicts', '_prune_orphan_sources', '_has_behavioral_contract', '_fit_packet', '_remove_one_budget_item', '_ensure_post_fit_status', '_compact_failure_packet', '_record_omission']
