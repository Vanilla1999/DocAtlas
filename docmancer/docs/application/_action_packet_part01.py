"""Implementation shard 1 for action_packet."""
from __future__ import annotations

from ._action_packet_shared import *  # noqa: F401,F403
from docmancer.docs.project_docs_catalog import read_project_docs_catalog

def estimate_action_packet_tokens(value: Any) -> int:
    """Estimate tokens deterministically as ceil(serialized UTF-8 bytes / 4)."""

    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return max(1, math.ceil(len(encoded) / 4))


def evidence_identity_for_item(item: dict[str, Any]) -> tuple[str, str, str]:
    """Expose the immutable ActionPacket evidence identity to projection code."""

    return _evidence_id(item), _source_path(item), _section(item)


def _ensure_selection_survives_packet(
    packet: dict[str, Any], selection: SelectionDecision
) -> None:
    """Fail closed if formatting removed a selector-owned requirement."""

    visible_text = _packet_visible_text(packet)
    target = packet.get("target_surface") if isinstance(packet.get("target_surface"), dict) else {}
    retained_evidence_ids = {
        str(row.get("evidence_id") or "")
        for row in packet.get("source_of_truth") or []
        if isinstance(row, dict)
    }
    selected_by_stable = {item.stable_id: item for item in selection.selected_candidates}
    assignments = {item.requirement_id: item for item in selection.assignments}
    missing: list[str] = []
    for requirement in selection.requirements:
        if not requirement.mandatory:
            continue
        assignment = assignments.get(requirement.requirement_id)
        if assignment is None:
            continue
        covering = [
            item for item in selection.selected_candidates
            if requirement.requirement_id in item.covered_requirement_ids
        ]
        assigned_candidate = selected_by_stable.get(assignment.evidence_id)
        assigned_id = (
            _evidence_id(dict(assigned_candidate.original))
            if assigned_candidate is not None else assignment.evidence_id
        )
        assigned_survived = assigned_id in retained_evidence_ids
        assigned_unit = next((
            witness for witness in (assigned_candidate.requirement_witnesses if assigned_candidate else ())
            if witness.requirement_id == requirement.requirement_id
            and (assignment.unit_id is None or witness.unit_id == assignment.unit_id)
        ), None)
        if assigned_unit is not None:
            assigned_survived = assigned_survived and (
                _normalized_fact_text(assigned_unit.unit_text)
                in _normalized_fact_text(visible_text)
            )
        if requirement.proof_role == "target_identity":
            mutation = packet.get("mutation_intent") or {}
            resolved_bindings = {
                (
                    str(target.get("requested_value") or "").casefold(),
                    str(target.get("evidence_id") or ""),
                )
                for key in ("resolved_targets", "preserved_targets")
                for target in mutation.get(key) or []
                if isinstance(target, dict)
            }
            satisfied = any(
                requested == requirement.value.casefold()
                and evidence_id in retained_evidence_ids
                for requested, evidence_id in resolved_bindings
            )
        elif requirement.kind == "evidence_path":
            paths = {
                _normalized_source_key(row.get("path"))
                for row in packet.get("source_of_truth") or [] if isinstance(row, dict)
            }
            satisfied = assigned_survived and _normalized_source_key(requirement.value) in paths
        elif requirement.kind == "target_path":
            paths = {
                _normalized_source_key(row.get("path"))
                for row in target.get("likely_files") or [] if isinstance(row, dict)
            }
            satisfied = _normalized_source_key(requirement.value) in paths
        elif requirement.kind == "exact_version":
            satisfied = assigned_survived and any(
                _evidence_id(dict(item.original)) in retained_evidence_ids
                and item.resolved_version.casefold() == requirement.value.casefold()
                for item in covering
            )
        elif requirement.kind == "canonical_policy":
            candidate = selected_by_stable.get(requirement.value)
            satisfied = (
                assigned_survived
                and candidate is not None
                and _policy_witness_survived(packet, assigned_id, candidate)
            )
        else:
            satisfied = assigned_survived and (
                assigned_unit is not None
                or requirement_value_visible(requirement.value, visible_text)
            )
        if not satisfied:
            missing.append(requirement.requirement_id)
    if not missing:
        return
    packet["status"] = "insufficient_evidence"
    packet["omitted_counts"]["mandatory_requirements"] = len(missing)
    message = "Mandatory selected evidence was not preserved by packet formatting: " + ", ".join(missing[:3])
    if message not in packet["missing_evidence"]:
        packet["missing_evidence"].append(message)


def _explicit_acceptance_conditions(evidence: dict[str, Any]) -> set[str]:
    metadata = evidence.get("metadata") if isinstance(evidence.get("metadata"), dict) else {}
    values: list[Any] = []
    for source in (evidence, metadata):
        value = source.get("acceptance_conditions")
        values.extend(value if isinstance(value, list) else [value] if value else [])
    result: set[str] = set()
    for value in values:
        text = str(value.get("text") or value.get("condition") or "") if isinstance(value, dict) else str(value)
        if text.strip():
            result.add(text.strip())
    return result


def _refresh_estimated_tokens(packet: dict[str, Any]) -> None:
    packet["estimated_tokens"] = 0
    for _ in range(8):
        actual = estimate_action_packet_tokens(packet)
        if actual == packet["estimated_tokens"]:
            return
        packet["estimated_tokens"] = actual


def _effective_authority(
    item: dict[str, Any], *, project_path: str | None, target_paths: Iterable[str]
) -> str:
    declared = {
        str(value).lower()
        for value in (item.get("authority"), item.get("repository_authority"))
        if value
    }
    if not declared & {
        "canonical", "source_of_truth", "explicit_agent_policy", "primary",
        "project_rule", "official", "project_owned",
    }:
        return "supporting"
    if item.get("repository_authority") == "explicit_agent_policy":
        return "canonical" if _scope_applies(item, project_path=project_path, target_paths=target_paths) else "supporting"
    if str(item.get("source_class") or "").casefold() == "project_doc" and project_path:
        root = Path(project_path).expanduser()
        if root.is_dir():
            catalog = read_project_docs_catalog(root)
            if not catalog.present:
                # Legacy benchmark contracts use the explicit project_rule
                # classification. A bare source_of_truth claim is not enough
                # without a catalog declaration.
                return "canonical" if "project_rule" in declared else "supporting"
            source = _normalized_source_key(_source_path(item))
            catalog_authority = next((
                entry.authority
                for entry in catalog.entries
                if _normalized_source_key(entry.path) == source
                and entry.status == "active"
            ), None)
            if catalog_authority is None:
                catalog_authority = next((
                    catalog_root.authority
                    for catalog_root in catalog.roots
                    if catalog_root.status == "active"
                    and (
                        source == _normalized_source_key(catalog_root.path)
                        or source.startswith(_normalized_source_key(catalog_root.path) + "/")
                    )
                ), None)
            if not catalog.valid or catalog_authority != "source_of_truth":
                return "supporting"
    if str(item.get("doc_scope") or "") == "module" or item.get("module_path"):
        return "canonical" if _scope_applies(item, project_path=project_path, target_paths=target_paths) else "supporting"
    return "canonical"


def _declares_canonical_authority(item: dict[str, Any]) -> bool:
    declared = {
        str(value).lower()
        for value in (item.get("authority"), item.get("repository_authority"))
        if value
    }
    return bool(declared & {"canonical", "source_of_truth", "explicit_agent_policy", "primary", "project_rule"})


def _critical_fact_count(item: dict[str, Any]) -> int:
    if str(item.get("source_class") or "") in _CODE_SOURCE_CLASSES:
        return 0
    facts, oversized = _extract_facts(_content_text(item))
    return oversized + sum(
        1 for fact_type, _ in facts if fact_type in {"required", "forbidden", "validation"}
    )


def _scope_applies(
    item: dict[str, Any], *, project_path: str | None, target_paths: Iterable[str]
) -> bool:
    root = str(item.get("authority_root") or project_path or "").strip()
    raw_scope = str(item.get("policy_scope") or item.get("module_path") or root).strip()
    if not raw_scope:
        return False
    scope = _absolute_scope(raw_scope, root)
    targets = [str(value).strip() for value in target_paths if str(value).strip()]
    if not targets:
        return bool(root and _same_path(scope, _absolute_scope(root, root)))
    return any(_is_within(_absolute_scope(target, root), scope) for target in targets)


def _absolute_scope(value: str, root: str) -> str:
    if "://" in value:
        return value
    path = Path(value)
    if not path.is_absolute() and root:
        path = Path(root) / path
    return os.path.normcase(os.path.normpath(str(path)))


def _same_path(left: str, right: str) -> bool:
    return os.path.normcase(os.path.normpath(left)) == os.path.normcase(os.path.normpath(right))


def _is_within(path: str, scope: str) -> bool:
    if "://" in path or "://" in scope:
        return path == scope or path.startswith(scope.rstrip("/") + "/")
    try:
        return os.path.commonpath([path, scope]) == scope
    except ValueError:
        return False


def _instruction_risk_flags(item: dict[str, Any]) -> list[str]:
    values: list[Any] = []
    for raw in (item.get("instruction_risk_flags"), item.get("risk_flags")):
        if isinstance(raw, (list, tuple, set)):
            values.extend(raw)
        elif raw:
            values.append(raw)
    return [
        str(value)
        for value in values
        if value
    ]


def _content_instruction_risk_flags(text: str) -> list[str]:
    return [
        reason
        for reason, pattern in _DANGEROUS_CONTENT_PATTERNS
        if pattern.search(str(text or ""))
    ]


def _source_scope(item: dict[str, Any]) -> str:
    return str(
        item.get("module_path")
        or item.get("policy_scope")
        or item.get("doc_scope")
        or "unscoped"
    )


def _version_binding(item: dict[str, Any]) -> str:
    return str(
        item.get("docs_exactness")
        or item.get("version_binding")
        or item.get("version")
        or "not_applicable"
    )


def _relevance_score(item: dict[str, Any]) -> float:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    for source in (item, metadata):
        for key in ("score", "relevance_score", "similarity", "rank_score", "confidence_score"):
            value = source.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
                return float(value)
    return 0.0


def _version_exactness_rank(item: dict[str, Any]) -> int:
    exactness = _version_binding(item).strip().lower().replace("-", "_")
    if exactness in {"exact", "exact_version", "version_exact", "exact_version_indexed"}:
        return 0
    if "fallback" in exactness or exactness in {"latest", "best_effort", "unknown"}:
        return 2
    return 1


def _rank_and_dedupe(items: Iterable[dict[str, Any]], trust_contract: dict[str, Any]) -> list[dict[str, Any]]:
    blocked_sources = _blocked_source_keys(trust_contract)
    ranked: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    for original in items:
        if not isinstance(original, dict):
            continue
        item = dict(original)
        path = _source_path(item)
        section = _section(item)
        source_keys = _item_source_keys(item)
        if not path or source_keys & blocked_sources or item.get("freshness") == "stale":
            continue
        authority = _authority(item)
        authority_rank = 0 if authority == "canonical" else 1
        class_rank = 0 if item.get("source_class") in _CODE_SOURCE_CLASSES else 1
        version_rank = _version_exactness_rank(item)
        content = _content_text(item)
        facts, _ = _extract_facts(content)
        snippet, _ = _snippet_text(item.get("snippet"))
        actionable_rank = -len(facts) - (1 if snippet else 0)
        relevance_rank = -_relevance_score(item)
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        supplemental = json.dumps(
            {
                "snippet": item.get("snippet"),
                "symbols": item.get("symbols"),
                "metadata": item.get("metadata"),
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        supplemental_hash = hashlib.sha256(supplemental.encode("utf-8")).hexdigest()
        ranked.append((
            (
                authority_rank, version_rank, _version_binding(item), class_rank, relevance_rank, actionable_rank,
                path, section, content_hash, supplemental_hash,
            ),
            item,
        ))
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _, item in sorted(ranked, key=lambda row: row[0]):
        dedupe_id = _dedupe_id(item)
        if dedupe_id in seen:
            continue
        seen.add(dedupe_id)
        selected.append(item)
    return selected


def _blocked_source_keys(trust_contract: dict[str, Any]) -> set[str]:
    return _risky_source_keys(trust_contract) | _rejected_source_keys(trust_contract)


def _risky_source_keys(trust_contract: dict[str, Any]) -> set[str]:
    return _trust_source_keys(trust_contract, "risky")


def _rejected_source_keys(trust_contract: dict[str, Any]) -> set[str]:
    return _trust_source_keys(trust_contract, "rejected")


def _trust_source_keys(trust_contract: dict[str, Any], field: str) -> set[str]:
    trust_sources = trust_contract.get("sources") if isinstance(trust_contract.get("sources"), dict) else {}
    rows: list[Any] = []
    aliases = [field]
    if field == "risky":
        aliases.append("risky_sources")
    elif field == "rejected":
        aliases.append("rejected_sources")
    for key in aliases:
        for value in (trust_contract.get(key), trust_sources.get(key)):
            if isinstance(value, list):
                rows.extend(value)
            elif isinstance(value, (str, dict)):
                rows.append(value)
    return {
        key
        for row in rows
        if isinstance(row, (str, dict))
        if (key := _normalized_source_key(
            row.get("source") or row.get("path") or row.get("url")
            or row.get("canonical_id") or row.get("library_id") or row.get("library") or ""
            if isinstance(row, dict) else row
        ))
    }


def _item_source_keys(item: dict[str, Any]) -> set[str]:
    return {
        key
        for value in (
            _source_path(item), item.get("url"), item.get("canonical_id"),
            item.get("library_id"), item.get("library"),
        )
        if value
        if (key := _normalized_source_key(value))
    }


def _normalized_source_key(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("path") or value.get("source") or value.get("url") or ""
    return str(value).strip().replace("\\", "/").rstrip("/").lower()


def _authority(item: dict[str, Any]) -> str:
    packet_authority = item.get("_packet_authority")
    if packet_authority in {"canonical", "supporting"}:
        return str(packet_authority)
    declared = {
        str(value).lower()
        for value in (item.get("authority"), item.get("repository_authority"))
        if value
    }
    if declared & {"canonical", "source_of_truth", "explicit_agent_policy", "primary", "project_rule"}:
        return "canonical"
    return "supporting"


def _source_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": _source_path(item),
        "symbol_or_section": _section(item),
        "authority": _authority(item),
        "instruction_trust": str(item.get("instruction_trust") or "untrusted_data"),
        "scope": _source_scope(item),
        "version_binding": _version_binding(item),
        "evidence_id": _evidence_id(item),
    }


def _source_path(item: dict[str, Any]) -> str:
    value = item.get("path") or item.get("source") or item.get("url") or ""
    if isinstance(value, dict):
        value = value.get("path") or value.get("source") or value.get("url") or ""
    return str(value).strip()


def _editable_target_path(value: str) -> bool:
    normalized = value.strip().replace("\\", "/").lstrip("./")
    if not normalized:
        return False
    parts = tuple(part.lower() for part in normalized.split("/") if part)
    name = parts[-1] if parts else ""
    return not (
        parts[:1] in {("tests",), ("test",), ("docs",)}
        or name in {"readme.md", "architecture.md", "pubspec.lock", "pyproject.toml"}
        or name.startswith("test_")
        or name.endswith(("_test.py", ".freezed.dart", ".g.dart"))
    )


def _section(item: dict[str, Any]) -> str:
    section = item.get("section") if isinstance(item.get("section"), dict) else {}
    value = item.get("heading_path") or item.get("title") or section.get("heading_path") or section.get("title") or "document"
    if isinstance(value, list):
        return " > ".join(str(part) for part in value)
    return str(value)


def _dedupe_id(item: dict[str, Any]) -> str:
    """Identify the same evidence payload independently of version preference."""

    identity = json.dumps(
        {
            "path": _source_path(item),
            "section": _section(item),
            "content": _content_text(item),
            "snippet": item.get("snippet"),
            "symbols": _explicit_symbols(item),
            "source_class": item.get("source_class"),
            "line_start": item.get("line_start"),
            "line_end": item.get("line_end"),
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _evidence_id(item: dict[str, Any]) -> str:
    identity = json.dumps(
        {
            "path": _source_path(item),
            "source": item.get("source"),
            "url": item.get("url"),
            "canonical_id": item.get("canonical_id"),
            "library_id": item.get("library_id"),
            "section": _section(item),
            "content": _content_text(item),
            "snippet": item.get("snippet"),
            "symbols": _explicit_symbols(item),
            "source_class": item.get("source_class"),
            "authority": _authority(item),
            "instruction_trust": item.get("instruction_trust"),
            "scope": _source_scope(item),
            "version_binding": _version_binding(item),
            "requested_version": item.get("requested_version"),
            "line_start": item.get("line_start"),
            "line_end": item.get("line_end"),
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return "ev-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]


def _content_text(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    return str(item.get("display_text") or item.get("content") or "")


def _add_mandatory_requirement_witnesses(
    packet: dict[str, Any], selection: SelectionDecision
) -> set[tuple[str, str]]:
    """Render bounded source text needed to keep selector requirements visible."""

    visible_text = _packet_visible_text(packet)
    requirements = {
        requirement.requirement_id: requirement
        for requirement in selection.requirements
        if requirement.mandatory
        and (
            requirement.kind in {
                "exact_term", "entity", "canonical_policy",
                "behavioral_contract", "cross_module_invariant",
            }
            or (
                requirement.kind == "source_fact"
                and requirement.requirement_id.startswith("behavioral_contract:")
            )
        )
        and requirement.proof_role != "target_identity"
    }
    source_ids = {
        str(row.get("evidence_id") or "")
        for row in packet.get("source_of_truth") or []
        if isinstance(row, dict)
    }
    mandatory_rows: set[tuple[str, str]] = set()
    for candidate in selection.selected_candidates:
        evidence = dict(candidate.original)
        evidence_id = _evidence_id(evidence)
        if evidence_id not in source_ids or _instruction_risk_flags(evidence):
            continue
        custom_witnesses = [
            witness for witness in candidate.requirement_witnesses
            if witness.requirement_id in requirements
            and (
                requirements[witness.requirement_id].kind in {
                    "behavioral_contract", "cross_module_invariant",
                }
                or (
                    requirements[witness.requirement_id].kind == "source_fact"
                    and witness.requirement_id.startswith("behavioral_contract:")
                )
            )
        ]
        canonical_requirement_id = f"canonical_policy:{candidate.stable_id}"
        for witness in custom_witnesses:
            if not witness.unit_text or _content_instruction_risk_flags(witness.unit_text):
                continue
            if _normalized_fact_text(witness.unit_text) in _normalized_fact_text(visible_text):
                continue
            requirement = requirements[witness.requirement_id]
            field = (
                "required_invariants"
                if requirement.kind == "cross_module_invariant"
                else "implementation_guidance"
            )
            text = witness.unit_text
            if requirement.kind == "cross_module_invariant":
                targets = [
                    value.casefold()
                    for value in requirement.value.splitlines()
                    if value
                ]
                text = next((
                    fact
                    for modality, fact in _extract_facts(witness.unit_text)[0]
                    if modality == "required"
                    and all(target in fact.casefold() for target in targets)
                ), "")
                if not text:
                    continue
                packet["implementation_guidance"] = [
                    row
                    for row in packet["implementation_guidance"]
                    if row.get("text") != text
                ]
            packet[field].append({
                "text": text,
                "evidence_ids": [evidence_id],
            })
            mandatory_rows.add((witness.unit_text, evidence_id))
            visible_text += "\n" + witness.unit_text.casefold()
        if canonical_requirement_id in candidate.covered_requirement_ids:
            missing_facts = [
                fact
                for _, fact in _extract_facts(_content_text(evidence))[0]
                if fact
                and not _content_instruction_risk_flags(fact)
                and _normalized_fact_text(fact) not in _normalized_fact_text(visible_text)
            ]
            if missing_facts:
                text = "\n".join(missing_facts)
                packet["implementation_guidance"].append({
                    "text": text,
                    "evidence_ids": [evidence_id],
                })
                mandatory_rows.add((text, evidence_id))
                visible_text += "\n" + text.casefold()
        remaining = [
            requirements[requirement_id]
            for requirement_id in sorted(candidate.covered_requirement_ids)
            if requirement_id in requirements
            and requirements[requirement_id].kind in {"exact_term", "entity"}
        ]
        while remaining:
            witness = _requirement_witness(
                _content_text(evidence), [requirement.value for requirement in remaining]
            )
            if not witness or _content_instruction_risk_flags(witness):
                break
            packet["implementation_guidance"].append({
                "text": witness,
                "evidence_ids": [evidence_id],
            })
            mandatory_rows.add((witness, evidence_id))
            visible_text += "\n" + witness.casefold()
            remaining = [
                requirement for requirement in remaining
                if not requirement_value_visible(requirement.value, visible_text)
            ]
    packet["implementation_guidance"] = _dedupe_cited(
        packet["implementation_guidance"], "text"
    )
    packet["required_invariants"] = _dedupe_cited(
        packet["required_invariants"], "text"
    )
    invariant_texts = [
        str(row.get("text") or "")
        for row in packet["required_invariants"]
        if row.get("text")
    ]
    packet["implementation_guidance"] = [
        row
        for row in packet["implementation_guidance"]
        if str(row.get("text") or "") not in invariant_texts
    ]
    return mandatory_rows


def _packet_visible_text(packet: dict[str, Any]) -> str:
    values: list[str] = []
    for row in packet.get("source_of_truth") or []:
        if isinstance(row, dict):
            values.extend(str(row.get(key) or "") for key in (
                "path", "symbol_or_section", "version_binding",
            ))
    target = packet.get("target_surface") or {}
    for key, value_key in (("likely_files", "path"), ("symbols", "name")):
        values.extend(
            str(row.get(value_key) or "")
            for row in target.get(key) or [] if isinstance(row, dict)
        )
    for rows in (
        (packet.get("task_interpretation") or {}).get("acceptance_conditions"),
        packet.get("required_invariants"), packet.get("forbidden_changes"),
        packet.get("implementation_guidance"),
        *((packet.get("validation") or {}).values()),
    ):
        values.extend(
            str(row.get("text") or "") for row in rows or [] if isinstance(row, dict)
        )
    return "\n".join(values).casefold()


def _normalized_fact_text(value: str) -> str:
    return " ".join(value.replace("`", "").lstrip("-* ").casefold().split())


def _requirement_witness(content: str, values: list[str]) -> str:
    fragments: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        fragments.extend(
            segment.strip() for segment in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", line)
            if segment.strip()
        )
    matches = [
        fragment for fragment in fragments
        if len(fragment) <= 500
        and any(requirement_value_visible(value, fragment) for value in values)
    ]
    if not matches:
        return ""
    return max(
        matches,
        key=lambda fragment: (
            sum(requirement_value_visible(value, fragment) for value in values),
            -len(fragment),
        ),
    )


def _extract_facts(content: str) -> tuple[list[tuple[str, str]], int]:
    facts: list[tuple[str, str]] = []
    omitted_critical = 0
    in_fence = False
    python_declaration_lines = python_declaration_line_indexes(content)
    for line_index, raw in enumerate(content.splitlines()):
        if line_index in python_declaration_lines:
            continue
        stripped = raw.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if (
            in_fence
            or stripped.startswith(">")
            or stripped.startswith("#")
            or (stripped.startswith("|") and stripped.count("|") >= 2)
        ):
            continue
        line = stripped.lstrip("-* ").strip().replace("`", "")
        if not line:
            continue
        segments = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", line)
        for segment in segments:
            fact = segment.strip()
            if not fact:
                continue
            modality = classify_normative_modality(fact)
            looks_critical = bool(
                modality
                or _validation_command(fact)
            )
            if len(fact) > 500:
                omitted_critical += int(looks_critical)
                continue
            if modality == "forbidden":
                facts.append((modality, fact))
                continue
            command = _validation_command(fact)
            if command:
                facts.append(("validation", command))
                continue
            if modality == "required":
                facts.append((modality, fact))
    return facts, omitted_critical


def _validation_command(value: str) -> str | None:
    command = value.strip()
    if _UNSAFE_COMMAND_RE.search(command):
        return None
    return command if _VALIDATION_START_RE.fullmatch(command) else None


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


def _snippet_text(value: Any) -> tuple[str, int]:
    if isinstance(value, dict):
        value = value.get("code") or value.get("content") or value.get("text")
    if not isinstance(value, str):
        return "", 0
    text = value.strip()
    if not text:
        return "", 0
    return (text, 0) if len(text) <= 1_000 else ("", 1)


def _dedupe_cited(rows: Iterable[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        identity = str(row.get(key) or "")
        if not identity:
            continue
        if identity not in merged:
            merged[identity] = {key: identity, "evidence_ids": []}
        refs = [str(ref) for ref in row.get("evidence_ids") or [] if ref]
        merged[identity]["evidence_ids"] = sorted(set([*merged[identity]["evidence_ids"], *refs]))
    return list(merged.values())


def _cited_evidence_ids(packet: dict[str, Any]) -> set[str]:
    mutation = packet.get("mutation_intent") or {}
    rows = [
        *(packet["task_interpretation"].get("acceptance_conditions") or []),
        *packet["target_surface"]["likely_files"],
        *packet["target_surface"]["symbols"],
        *packet["required_invariants"],
        *packet["forbidden_changes"],
        *packet["implementation_guidance"],
        *packet["validation"]["compile"],
        *packet["validation"]["tests"],
        *packet["validation"]["semantic_checks"],
        *(mutation.get("resolved_targets") or []),
        *(mutation.get("preserved_targets") or []),
    ]
    return {
        str(ref)
        for row in rows
        for ref in (
            row.get("evidence_ids")
            or ([row.get("evidence_id")] if row.get("evidence_id") else [])
        )
        if isinstance(row, dict) and ref
    }


def _policy_witness_survived(
    packet: dict[str, Any],
    evidence_id: str,
    candidate: Any,
) -> bool:
    validation = packet.get("validation") or {}
    rows = [
        *packet.get("required_invariants", []),
        *packet.get("forbidden_changes", []),
        *packet.get("implementation_guidance", []),
        *(validation.get("compile") or []),
        *(validation.get("tests") or []),
        *(validation.get("semantic_checks") or []),
    ]
    safe_facts = {
        fact
        for _, fact in _extract_facts(_content_text(dict(candidate.original)))[0]
        if fact and not _content_instruction_risk_flags(fact)
    }
    witnessed = [
        _normalized_fact_text(str(row.get("text") or ""))
        for row in rows
        if isinstance(row, dict)
        and evidence_id in {
            str(ref) for ref in row.get("evidence_ids") or [] if ref
        }
    ]
    return bool(safe_facts) and all(
        any(_normalized_fact_text(fact) in text for text in witnessed)
        for fact in safe_facts
    )


def _has_actionable_items(packet: dict[str, Any]) -> bool:
    target = packet.get("target_surface") if isinstance(packet.get("target_surface"), dict) else {}
    validation = packet.get("validation") if isinstance(packet.get("validation"), dict) else {}
    return any((
        (packet.get("task_interpretation") or {}).get("acceptance_conditions"),
        target.get("likely_files"),
        target.get("symbols"),
        packet.get("required_invariants"),
        packet.get("forbidden_changes"),
        packet.get("implementation_guidance"),
        validation.get("compile"),
        validation.get("tests"),
        validation.get("semantic_checks"),
    ))

__all__=['estimate_action_packet_tokens', 'evidence_identity_for_item', '_ensure_selection_survives_packet', '_explicit_acceptance_conditions', '_refresh_estimated_tokens', '_effective_authority', '_declares_canonical_authority', '_critical_fact_count', '_scope_applies', '_absolute_scope', '_same_path', '_is_within', '_instruction_risk_flags', '_content_instruction_risk_flags', '_source_scope', '_version_binding', '_relevance_score', '_version_exactness_rank', '_rank_and_dedupe', '_blocked_source_keys', '_risky_source_keys', '_rejected_source_keys', '_trust_source_keys', '_item_source_keys', '_normalized_source_key', '_authority', '_source_row', '_source_path', '_editable_target_path', '_section', '_dedupe_id', '_evidence_id', '_content_text', '_add_mandatory_requirement_witnesses', '_packet_visible_text', '_requirement_witness', '_extract_facts', '_validation_command', '_explicit_symbols', '_snippet_text', '_dedupe_cited', '_cited_evidence_ids', '_has_actionable_items']
