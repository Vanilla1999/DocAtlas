from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Iterable


ACTION_PACKET_SCHEMA_VERSION = 1
DEFAULT_ACTION_PACKET_TOKENS = 1_500
HARD_ACTION_PACKET_TOKENS = 2_000
MIN_ACTION_PACKET_TOKENS = 256

_FORBIDDEN_RE = re.compile(r"\b(must\s+not|do\s+not|don't|never|forbidden|prohibited)\b", re.I)
_REQUIRED_RE = re.compile(r"\b(must|required|requires|shall|should|invariant)\b", re.I)
_VALIDATION_RE = re.compile(
    r"(?:^|\s)(?:python\s+-m\s+(?:pytest|unittest|compileall)|pytest|uv\s+run|npm\s+(?:test|run)|pnpm\s+(?:test|run)|"
    r"yarn\s+(?:test|run|build)|cargo\s+(?:test|check|build)|go\s+test|gradle\w*|flutter\s+test|"
    r"dart\s+(?:test|analyze)|make|ruff|mypy|tsc|go\s+(?:build|vet)|"
    r"dotnet\s+(?:test|build)|mvn\s+(?:test|package)|swift\s+test)(?=\s|$|[.;])",
    re.I,
)
_SYMBOL_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b")
_CODE_SOURCE_CLASSES = {"repo_map", "source_evidence", "code_graph"}


def estimate_action_packet_tokens(value: Any) -> int:
    """Estimate tokens deterministically as ceil(canonical UTF-8 bytes / 4)."""

    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return max(1, math.ceil(len(encoded) / 4))


def build_action_packet(
    *,
    question: str,
    context_pack: Iterable[dict[str, Any]],
    trust_contract: dict[str, Any] | None = None,
    max_tokens: int = DEFAULT_ACTION_PACKET_TOKENS,
) -> dict[str, Any]:
    """Render selected retrieval evidence into a bounded, deterministic packet.

    The formatter only copies source-backed facts. It does not infer acceptance
    conditions, ownership, target symbols, or validation commands from filenames.
    """

    budget = min(
        HARD_ACTION_PACKET_TOKENS,
        max(MIN_ACTION_PACKET_TOKENS, int(max_tokens or DEFAULT_ACTION_PACKET_TOKENS)),
    )
    raw_items = [dict(item) for item in context_pack if isinstance(item, dict)]
    authority_conflicts = _authority_conflicts(raw_items)
    items = _rank_and_dedupe(raw_items, trust_contract or {})
    objective, objective_omitted = _bounded_text(question.strip(), 1_000)
    source_rows = [_source_row(item) for item in items if _source_path(item)]
    source_rows = _dedupe_dicts(source_rows, ("path", "symbol_or_section"))
    evidence_by_item = {
        _item_identity(item): _evidence_id(item)
        for item in items
        if _source_path(item)
    }

    required: list[dict[str, Any]] = []
    forbidden: list[dict[str, Any]] = []
    compile_checks: list[dict[str, Any]] = []
    test_checks: list[dict[str, Any]] = []
    semantic_checks: list[dict[str, Any]] = []
    guidance: list[dict[str, Any]] = []
    for item in items:
        evidence_id = evidence_by_item.get(_item_identity(item))
        if not evidence_id:
            continue
        for fact in _facts(str(item.get("content") or "")):
            cited = {"text": fact, "evidence_ids": [evidence_id]}
            # Only explicitly canonical repository policy may become a hard
            # constraint or validation command. Supporting docs remain cited
            # references/snippets, never executable policy.
            if _authority(item) != "canonical":
                continue
            if _FORBIDDEN_RE.search(fact):
                forbidden.append(cited)
            elif _VALIDATION_RE.search(fact):
                bucket = _validation_bucket(fact)
                {"compile": compile_checks, "tests": test_checks, "semantic": semantic_checks}[bucket].append(cited)
            elif _REQUIRED_RE.search(fact):
                required.append(cited)
        snippet = _snippet_text(item.get("snippet"))
        if snippet:
            guidance.append({"text": snippet, "evidence_ids": [evidence_id]})

    target_files: list[str] = []
    symbols: list[dict[str, Any]] = []
    for item in items:
        evidence_id = evidence_by_item.get(_item_identity(item))
        if not evidence_id or str(item.get("source_class") or "") not in _CODE_SOURCE_CLASSES:
            continue
        path = _source_path(item)
        if path:
            target_files.append(path)
        for symbol in _explicit_symbols(item):
            symbols.append({"name": symbol, "evidence_ids": [evidence_id]})

    packet: dict[str, Any] = {
        "schema_version": ACTION_PACKET_SCHEMA_VERSION,
        "status": "ok",
        "task_interpretation": {
            "objective": objective,
            "acceptance_conditions": [],
        },
        "source_of_truth": source_rows,
        "target_surface": {
            "likely_files": _dedupe_dicts([
                {"path": path, "evidence_ids": [evidence_by_item[_item_identity(item)]]}
                for item in items
                if (path := _source_path(item)) in target_files
                and _item_identity(item) in evidence_by_item
            ], ("path",)),
            "symbols": _dedupe_dicts(symbols, ("name",)),
        },
        "required_invariants": _dedupe_dicts(required, ("text",)),
        "forbidden_changes": _dedupe_dicts(forbidden, ("text",)),
        "implementation_guidance": _dedupe_dicts(guidance, ("text",)),
        "validation": {
            "compile": _dedupe_dicts(compile_checks, ("text",)),
            "tests": _dedupe_dicts(test_checks, ("text",)),
            "semantic_checks": _dedupe_dicts(semantic_checks, ("text",)),
        },
        "uncertainties": [],
        "missing_evidence": [],
        "omitted_counts": {},
        "estimated_tokens": 0,
    }
    if objective_omitted:
        packet["status"] = "truncated"
        packet["omitted_counts"]["task_interpretation.objective_characters"] = objective_omitted

    if authority_conflicts:
        packet["status"] = "insufficient_evidence"
        packet["uncertainties"] = [
            {"type": "authority_conflict", "path": path, "symbol_or_section": section}
            for path, section in authority_conflicts
        ]
        packet["missing_evidence"] = ["Conflicting canonical evidence must be resolved before editing."]

    if not source_rows:
        packet["status"] = "insufficient_evidence"
        packet["missing_evidence"] = ["No selected source-backed evidence matched the request."]
    elif not any((
        required, forbidden, compile_checks, test_checks, semantic_checks,
        guidance, target_files, symbols,
    )):
        packet["status"] = "insufficient_evidence"
        packet["missing_evidence"] = [
            "Selected sources do not contain explicit constraints, validation commands, or code-surface evidence."
        ]

    _fit_packet(packet, budget)
    _refresh_estimated_tokens(packet)
    # Account for the estimate field itself. If it crosses the caller budget,
    # remove another complete item and recompute rather than slicing text.
    while packet["estimated_tokens"] > budget and _remove_one_budget_item(packet):
        _refresh_estimated_tokens(packet)
    _refresh_estimated_tokens(packet)
    if packet["estimated_tokens"] > budget:
        packet["status"] = "insufficient_evidence"
        message = "The requested token budget is smaller than the ActionPacket schema overhead."
        if message not in packet["missing_evidence"]:
            packet["missing_evidence"].append(message)
        _refresh_estimated_tokens(packet)
    return packet


def validate_action_packet(packet: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(packet, dict):
        return ["ActionPacket must be an object"]
    required_keys = {
        "schema_version", "status", "task_interpretation", "source_of_truth", "target_surface",
        "required_invariants", "forbidden_changes", "implementation_guidance", "validation",
        "uncertainties", "missing_evidence", "omitted_counts", "estimated_tokens",
    }
    missing = sorted(required_keys - set(packet))
    extra = sorted(set(packet) - required_keys)
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")
    if extra:
        errors.append(f"unknown fields: {', '.join(extra)}")
    if packet.get("schema_version") != ACTION_PACKET_SCHEMA_VERSION:
        errors.append("unsupported schema_version")
    if packet.get("status") not in {"ok", "truncated", "insufficient_evidence"}:
        errors.append("invalid status")

    task = _object_field(packet, "task_interpretation", {"objective", "acceptance_conditions"}, errors)
    if task:
        if not isinstance(task.get("objective"), str) or not task["objective"].strip():
            errors.append("task_interpretation.objective must be a non-empty string")
        _validate_cited_items(
            task.get("acceptance_conditions"), "task_interpretation.acceptance_conditions", "text", errors
        )

    target_surface = _object_field(packet, "target_surface", {"likely_files", "symbols"}, errors)
    if target_surface:
        _validate_cited_items(target_surface.get("likely_files"), "target_surface.likely_files", "path", errors)
        _validate_cited_items(target_surface.get("symbols"), "target_surface.symbols", "name", errors)

    validation = _object_field(packet, "validation", {"compile", "tests", "semantic_checks"}, errors)
    if validation:
        for key in ("compile", "tests", "semantic_checks"):
            _validate_cited_items(validation.get(key), f"validation.{key}", "text", errors)

    sources = packet.get("source_of_truth") if isinstance(packet.get("source_of_truth"), list) else []
    if not isinstance(packet.get("source_of_truth"), list):
        errors.append("source_of_truth must be an array")
    evidence_ids: set[Any] = set()
    for index, row in enumerate(sources):
        if not isinstance(row, dict):
            errors.append(f"source_of_truth[{index}] must be an object")
            continue
        expected = {"path", "symbol_or_section", "authority", "evidence_id"}
        if set(row) != expected:
            errors.append(f"source_of_truth[{index}] fields must be {sorted(expected)}")
        if not all(
            isinstance(row.get(key), str) and row[key].strip()
            for key in ("path", "symbol_or_section", "evidence_id")
        ):
            errors.append("source_of_truth entries require path, symbol_or_section, authority, and evidence_id")
            continue
        if row.get("authority") not in {"canonical", "supporting"}:
            errors.append("invalid source authority")
        evidence_ids.add(row.get("evidence_id"))

    for key in ("required_invariants", "forbidden_changes", "implementation_guidance"):
        _validate_cited_items(packet.get(key), key, "text", errors)

    cited_fields = _all_cited_items(packet, task, target_surface, validation)
    for item in cited_fields:
        refs = item.get("evidence_ids")
        if not refs or any(ref not in evidence_ids for ref in refs):
            errors.append("factual item has missing or unknown evidence_ids")
            break

    uncertainties = packet.get("uncertainties")
    if not isinstance(uncertainties, list):
        errors.append("uncertainties must be an array")
    else:
        for index, item in enumerate(uncertainties):
            expected = {"type", "path", "symbol_or_section"}
            if not isinstance(item, dict) or set(item) != expected or not all(
                isinstance(item.get(key), str) and item[key].strip() for key in expected
            ):
                errors.append(f"uncertainties[{index}] must be a complete authority-conflict object")

    missing_evidence = packet.get("missing_evidence")
    if not isinstance(missing_evidence, list) or any(
        not isinstance(item, str) or not item.strip() for item in (missing_evidence or [])
    ):
        errors.append("missing_evidence must be an array of non-empty strings")

    omitted_counts = packet.get("omitted_counts")
    if not isinstance(omitted_counts, dict) or any(
        not isinstance(key, str) or not key or isinstance(value, bool) or not isinstance(value, int) or value <= 0
        for key, value in (omitted_counts.items() if isinstance(omitted_counts, dict) else [])
    ):
        errors.append("omitted_counts must map field names to positive integers")

    status = packet.get("status")
    if status == "ok" and (missing_evidence or omitted_counts):
        errors.append("ok packets cannot report missing evidence or omissions")
    if status == "truncated" and not omitted_counts:
        errors.append("truncated packets must report omitted_counts")
    if status == "insufficient_evidence" and not missing_evidence:
        errors.append("insufficient_evidence packets must explain missing_evidence")

    declared = packet.get("estimated_tokens")
    declared_tokens = declared if isinstance(declared, int) and not isinstance(declared, bool) else -1
    try:
        actual = estimate_action_packet_tokens(packet)
    except (TypeError, ValueError):
        actual = HARD_ACTION_PACKET_TOKENS + 1
        errors.append("ActionPacket must be JSON serializable")
    if actual > HARD_ACTION_PACKET_TOKENS or declared_tokens != actual:
        errors.append("estimated_tokens mismatch or hard limit exceeded")
    return errors


def _object_field(
    packet: dict[str, Any], field: str, expected: set[str], errors: list[str]
) -> dict[str, Any]:
    value = packet.get(field)
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return {}
    if set(value) != expected:
        errors.append(f"{field} fields must be {sorted(expected)}")
    return value


def _validate_cited_items(value: Any, field: str, text_key: str, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append(f"{field} must be an array")
        return
    expected = {text_key, "evidence_ids"}
    for index, item in enumerate(value):
        if not isinstance(item, dict) or set(item) != expected:
            errors.append(f"{field}[{index}] fields must be {sorted(expected)}")
            continue
        if not isinstance(item.get(text_key), str) or not item[text_key].strip():
            errors.append(f"{field}[{index}].{text_key} must be a non-empty string")
        refs = item.get("evidence_ids")
        if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or not ref for ref in refs):
            errors.append(f"{field}[{index}].evidence_ids must be a non-empty string array")


def _all_cited_items(
    packet: dict[str, Any],
    task: dict[str, Any],
    target_surface: dict[str, Any],
    validation: dict[str, Any],
) -> list[dict[str, Any]]:
    values = [
        task.get("acceptance_conditions"),
        packet.get("required_invariants"),
        packet.get("forbidden_changes"),
        packet.get("implementation_guidance"),
        target_surface.get("symbols"),
        target_surface.get("likely_files"),
        validation.get("compile"),
        validation.get("tests"),
        validation.get("semantic_checks"),
    ]
    return [item for value in values if isinstance(value, list) for item in value if isinstance(item, dict)]


def _refresh_estimated_tokens(packet: dict[str, Any]) -> None:
    packet["estimated_tokens"] = 0
    for _ in range(8):
        actual = estimate_action_packet_tokens(packet)
        if actual == packet["estimated_tokens"]:
            return
        packet["estimated_tokens"] = actual


def _authority_conflicts(items: Iterable[dict[str, Any]]) -> list[tuple[str, str]]:
    canonical: dict[tuple[str, str], set[str]] = {}
    for item in items:
        if _authority(item) != "canonical" or item.get("freshness") == "stale" or not _source_path(item):
            continue
        identity = _item_identity(item)
        content = str(item.get("content") or "").strip()
        if content:
            canonical.setdefault(identity, set()).add(hashlib.sha256(content.encode("utf-8")).hexdigest())
    return sorted(identity for identity, hashes in canonical.items() if len(hashes) > 1)


def _rank_and_dedupe(items: Iterable[dict[str, Any]], trust_contract: dict[str, Any]) -> list[dict[str, Any]]:
    trust_sources = trust_contract.get("sources") if isinstance(trust_contract.get("sources"), dict) else {}
    risky_sources = {
        str(row.get("source") or row.get("path") or "")
        for row in [*(trust_contract.get("risky") or []), *(trust_sources.get("risky") or [])]
        if isinstance(row, dict)
    }
    ranked: list[tuple[tuple[int, int, str, str, int, str], dict[str, Any]]] = []
    for original in items:
        if not isinstance(original, dict):
            continue
        item = dict(original)
        path = _source_path(item)
        section = _section(item)
        if not path or path in risky_sources or item.get("freshness") == "stale":
            continue
        authority = _authority(item)
        authority_rank = 0 if authority == "canonical" else 1
        class_rank = 0 if item.get("source_class") in _CODE_SOURCE_CLASSES else 1
        content = str(item.get("content") or "")
        actionable_rank = -len(_facts(content)) - (1 if _snippet_text(item.get("snippet")) else 0)
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        ranked.append(((authority_rank, class_rank, path, section, actionable_rank, content_hash), item))
    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for _, item in sorted(ranked, key=lambda row: row[0]):
        identity = _item_identity(item)
        if identity in seen:
            continue
        seen.add(identity)
        selected.append(item)
    return selected


def _authority(item: dict[str, Any]) -> str:
    declared = {
        str(value).lower()
        for value in (item.get("authority"), item.get("repository_authority"))
        if value
    }
    if declared & {"canonical", "source_of_truth", "explicit_agent_policy"}:
        return "canonical"
    return "supporting"


def _source_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": _source_path(item),
        "symbol_or_section": _section(item),
        "authority": _authority(item),
        "evidence_id": _evidence_id(item),
    }


def _source_path(item: dict[str, Any]) -> str:
    return str(item.get("path") or item.get("source") or item.get("url") or "").strip()


def _section(item: dict[str, Any]) -> str:
    value = item.get("heading_path") or item.get("title") or (item.get("section") or {}).get("title") or "document"
    if isinstance(value, list):
        return " > ".join(str(part) for part in value)
    return str(value)


def _item_identity(item: dict[str, Any]) -> tuple[str, str]:
    return _source_path(item), _section(item)


def _evidence_id(item: dict[str, Any]) -> str:
    identity = "\0".join((_source_path(item), _section(item), str(item.get("content") or "")))
    return "ev-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]


def _facts(content: str) -> list[str]:
    facts: list[str] = []
    for raw in content.splitlines():
        line = raw.strip().lstrip("-* ").strip().replace("`", "")
        if not line or len(line) > 500:
            continue
        if _FORBIDDEN_RE.search(line) or _REQUIRED_RE.search(line) or _VALIDATION_RE.search(line):
            facts.append(line)
    return facts


def _validation_bucket(fact: str) -> str:
    lowered = fact.lower()
    if re.search(
        r"\b(python\s+-m\s+compileall|cargo\s+(check|build)|tsc|dart\s+analyze|"
        r"gradle\w*\s+.*build|(?:npm|pnpm|yarn)\s+(?:run\s+)?build|make\s+build|"
        r"go\s+build|dotnet\s+build|mvn\s+package)\b",
        lowered,
    ):
        return "compile"
    if re.search(r"\b(ruff|mypy|lint|go\s+vet)\b", lowered):
        return "semantic"
    return "tests"


def _explicit_symbols(item: dict[str, Any]) -> list[str]:
    values: list[Any] = []
    for key in ("symbols", "matched_symbols", "symbol_names", "symbol"):
        value = item.get(key)
        values.extend(value if isinstance(value, list) else [value] if value else [])
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    for key in ("symbols", "matched_symbols", "symbol_names", "symbol"):
        value = metadata.get(key)
        values.extend(value if isinstance(value, list) else [value] if value else [])
    names = [
        value.get("name") if isinstance(value, dict) else value
        for value in values
    ]
    return list(dict.fromkeys(
        str(value) for value in names if value and _SYMBOL_RE.fullmatch(str(value))
    ))


def _snippet_text(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("code") or value.get("content") or value.get("text")
    if not isinstance(value, str):
        return ""
    text = value.strip()
    return text if 0 < len(text) <= 1_000 else ""


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


def _fit_packet(packet: dict[str, Any], budget: int) -> None:
    while estimate_action_packet_tokens(packet) > budget and _remove_one_budget_item(packet):
        pass
    if not packet["source_of_truth"]:
        packet["status"] = "insufficient_evidence"
        message = "No source attribution fit the requested packet budget."
        if message not in packet["missing_evidence"]:
            packet["missing_evidence"].append(message)


def _remove_one_budget_item(packet: dict[str, Any]) -> bool:
    rows_by_name = [
        ("implementation_guidance", packet["implementation_guidance"]),
    ]
    for name, rows in rows_by_name:
        if rows:
            rows.pop()
            _record_omission(packet, name)
            return True

    objective = str(packet["task_interpretation"].get("objective") or "")
    if len(objective) > 32:
        target = max(32, len(objective) - max(32, len(objective) // 4))
        shortened, removed = _bounded_text(objective, target)
        packet["task_interpretation"]["objective"] = shortened
        _record_omission(packet, "task_interpretation.objective_characters", removed)
        return True

    rows_by_name = [
        ("target_surface.symbols", packet["target_surface"]["symbols"]),
        ("target_surface.likely_files", packet["target_surface"]["likely_files"]),
        ("validation.semantic_checks", packet["validation"]["semantic_checks"]),
        ("validation.compile", packet["validation"]["compile"]),
        ("validation.tests", packet["validation"]["tests"]),
        ("forbidden_changes", packet["forbidden_changes"]),
        ("required_invariants", packet["required_invariants"]),
        ("source_of_truth", packet["source_of_truth"]),
    ]
    for name, rows in rows_by_name:
        if rows:
            rows.pop()
            _record_omission(packet, name)
            if name in {"forbidden_changes", "required_invariants"}:
                packet["status"] = "insufficient_evidence"
                message = "Critical constraints did not fit the requested packet budget."
                if message not in packet["missing_evidence"]:
                    packet["missing_evidence"].append(message)
            return True
    return False


def _record_omission(packet: dict[str, Any], field: str, count: int = 1) -> None:
    packet["omitted_counts"][field] = int(packet["omitted_counts"].get(field) or 0) + count
    if packet["status"] == "ok":
        packet["status"] = "truncated"
