"""Implementation shard 2 for answer_units."""
from __future__ import annotations

from ._answer_units_shared import *  # noqa: F401,F403

from ._answer_units_part01 import (
    AnswerUnit,
    LocalProof,
    _bounded_clauses,
    _contains_term,
    _context_score,
    _effect_relation_valid,
    _normal,
    _purpose_clause,
    _subject_present,
    _subject_spans,
    _word_distance,
)

def _attribute_aliases(attribute: str | None) -> tuple[str, ...]:
    normalized = _normal(attribute)
    aliases = {
        "python version": ("python version", "requires-python", "python_requires", "python requirement", "python"),
        "version": ("version", "requires", "runtime"),
        "timeout": ("timeout", "time-out", "deadline", "request timeout", "timeout_seconds", "timeout_ms", "время ожидания", "тайм-аут"),
        "status": ("status", "state", "статус", "состояние"),
        "public tools": ("public tools", "tools", "commands", "methods", "инструменты", "команды"),
        "scope": ("scope", "scopes", "область", "области"),
        "marker": ("marker", "markers", "test marker", "test markers", "pytest marker", "pytest markers"),
        "source": ("source", "sources", "source type", "source types"),
        "file format": (
            "file format", "file formats", "document format", "document formats",
            "local file format", "local file formats",
        ),
    }
    return aliases.get(normalized, (attribute,) if attribute else ())


def _attribute_present(attribute: str | None, text: str) -> bool:
    return any(_contains_term(alias, text) for alias in _attribute_aliases(attribute))


def _inventory_anchor(text: str, item_kind: str | None = None) -> re.Match[str] | None:
    if not item_kind or item_kind == "public_tool":
        return _TOOL_INVENTORY_ANCHOR_RE.search(text)
    forms = controlled_noun_forms(item_kind)
    if not forms:
        return None
    variants = set(forms)
    singular = forms[-1]
    if re.fullmatch(r"[a-z][a-z0-9_-]{2,}", singular) and not singular.endswith("s"):
        variants.add(singular + "s")
    if singular == "scope":
        variants.update(("scope", "scopes", "область", "области"))
    elif singular == "mode":
        variants.update(("mode", "modes", "режим", "режимы"))
    elif singular == "option":
        variants.update(("option", "options", "опция", "опции"))
    pattern = re.compile(
        r"(?<![A-Za-zА-Яа-яЁё0-9_-])(?:"
        + "|".join(re.escape(value) for value in sorted(variants, key=lambda value: (-len(value), value)))
        + r")(?![A-Za-zА-Яа-яЁё0-9_-])",
        re.I,
    )
    return pattern.search(text)


def _inventory_facts(
    text: str,
    *,
    item_kind: str | None = None,
) -> tuple[int | None, tuple[str, ...], bool]:
    anchor = _inventory_anchor(text, item_kind)
    if anchor is None:
        return None, (), False
    window = text[max(0, anchor.start() - 40):anchor.end() + 700]
    explicit_count: int | None = None
    count_match = _EXPLICIT_COUNT_RE.search(window)
    if count_match:
        raw = count_match.group(1).casefold()
        explicit_count = int(raw) if raw.isdigit() else _NUMBER_WORD_VALUES.get(raw)
    names: list[str] = []
    tail = window[window.casefold().find(anchor.group(0).casefold()) + len(anchor.group(0)):]
    # Closed inventories are introduced by punctuation/copula and contain
    # code-shaped or quoted names.  Ordinary identifiers elsewhere in a
    # branding sentence are deliberately ignored.
    introduced = re.search(r"(?:\b(?:are|include|consist\s+of|namely)\b|[:=-])\s*(.+)$", tail, re.I | re.S)
    if introduced:
        material = introduced.group(1).split("\n\n", 1)[0]
        for match in re.finditer(r"`([^`\n]{2,120})`", material):
            candidate = match.group(1).strip().rstrip("()")
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.:-]{1,119}", candidate):
                names.append(_normal(candidate))
        for part in re.split(r"\s*[,;]\s*|\s+(?:and|or|и|или)\s+", material):
            candidate = re.sub(r"^(?:and|or|и|или)\s+", "", part.strip(), flags=re.I)
            candidate = candidate.strip(" `.'\"()[]")
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.:-]{1,80}", candidate) and (
                "_" in candidate or "." in candidate or ":" in candidate or candidate.islower()
            ):
                names.append(_normal(candidate))
    # Generic closed inventories may be documented as Markdown tables or a
    # parenthesized/backticked list.  Keep public-tool parsing strict, but let
    # already-typed item kinds use those reviewable structures.
    if item_kind and item_kind != "public_tool" and len(names) < 2:
        lines = text.splitlines()
        anchor_line = next((idx for idx, line in enumerate(lines) if _inventory_anchor(line, item_kind)), None)
        if anchor_line is not None and "|" in lines[anchor_line]:
            for line in lines[anchor_line + 1:]:
                if not line.strip():
                    break
                if re.match(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+", line):
                    continue
                cells = [cell.strip(" `") for cell in line.strip().strip("|").split("|")]
                if cells and cells[0] and len(cells[0]) <= 120:
                    names.append(_normal(cells[0]))
        if len(names) < 2:
            for match in re.finditer(r"`([^`\n]{1,80})`", window):
                candidate = match.group(1).strip()
                if candidate and len(candidate.split()) <= 4:
                    names.append(_normal(candidate))
    unique = tuple(dict.fromkeys(value for value in names if value))
    return explicit_count, unique, True


def _subject_token_overlap(subject: str, text: str) -> int:
    ignored = {"docatlas", "the", "a", "an", "execution", "document", "docs"}
    wanted = [token for token in re.findall(r"[a-z0-9_]+", _normal(subject)) if token not in ignored and len(token) > 2]
    haystack = _normal(text)
    return sum(1 for token in set(wanted) if token in haystack)


def _value_score(value_kind: str, text: str, *, cardinality: int | None = None) -> int:
    if value_kind == "version_range":
        return 3 if _VERSION_VALUE_RE.search(text) else 0
    if value_kind == "duration":
        return 3 if _DURATION_RE.search(text) else 0
    if value_kind == "status":
        return 3 if _STATUS_VALUE_RE.search(text) else 0
    if value_kind == "number":
        return 2 if re.search(r"(?<!\w)\d+(?:\.\d+)?(?!\w)", text) else 0
    if value_kind == "boolean":
        return 2 if re.search(r"\b(?:true|false|yes|no|enabled|disabled|да|нет|включен|выключен)\b", text, re.I) else 0
    if value_kind == "path":
        return 2 if re.search(r"(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+", text) else 0
    if value_kind in {"code", "call_expression"}:
        return 2 if (
            re.search(r"`[^`]+`|\b[A-Za-z_]\w*(?:(?:::|\.)[A-Za-z_]\w*)+", text)
            or _CODE_DECL_RE.match(text)
            or re.search(r"\b(?:const|let|var|final)\s+[A-Za-z_]\w*\s*=", text, re.I)
        ) else 0
    if value_kind == "identifier_list":
        _count, identifiers, anchored = _inventory_facts(text)
        if not anchored:
            return 0
        count = len(identifiers)
        if cardinality is not None:
            return 3 if count == cardinality else 0
        return 3 if count >= 2 else 0
    # text values need a predicate/content beyond a bare identity.
    return 1 if len(re.findall(r"\w+", text, re.UNICODE)) >= 3 else 0


def _subject_before_pattern(subject: str, pattern: re.Pattern[str], text: str, *, words: int = 8) -> bool:
    subject_pattern = re.escape(_normal(subject)).replace(r"\ ", r"[\s_]+")
    normalized = _normal(text)
    return re.search(
        rf"(?<!\w){subject_pattern}(?!\w)(?:\W+\w+){{0,{words}}}?\W+{pattern.pattern}",
        normalized,
        pattern.flags,
    ) is not None


_COMPARISON_PREDICATE_RE = re.compile(
    r"\b(?:returns?|selects?|chooses?|converts?|creates?|blocks?|awaits?|"
    r"schedules?|produces?|emits?|builds?|ranks?|retrieves?|validates?|plans?)\b",
    re.I,
)


def _comparison_predicate_name(value: str) -> str:
    normalized = value.casefold()
    if normalized.endswith("ies") and len(normalized) > 4:
        return normalized[:-3] + "y"
    if normalized.endswith("s") and not normalized.endswith("ss") and len(normalized) > 3:
        return normalized[:-1]
    return normalized


def _comparison_predicates(
    obligation: ProofObligation,
    text: str,
) -> tuple[set[str], set[str]]:
    """Bind comparison predicates to each side inside bounded clauses."""

    left: set[str] = set()
    right: set[str] = set()
    for _start, _end, clause in _bounded_clauses(text):
        predicates = [
            (match.span(), _comparison_predicate_name(match.group(0)))
            for match in _COMPARISON_PREDICATE_RE.finditer(clause)
        ]
        if not predicates:
            continue
        for subject_span in _subject_spans(obligation, clause):
            for predicate_span, predicate in predicates:
                if _word_distance(subject_span, predicate_span, clause) <= 8:
                    left.add(predicate)
        for target_span in term_sequence_spans(obligation.target or "", clause):
            for predicate_span, predicate in predicates:
                if _word_distance(target_span, predicate_span, clause) <= 8:
                    right.add(predicate)
    return left, right


def _explicit_comparison_is_local(
    obligation: ProofObligation,
    text: str,
) -> bool:
    return any(
        _subject_present(obligation, clause)
        and _contains_term(obligation.target, clause)
        and _CONTRAST_RE.search(clause) is not None
        for _start, _end, clause in _bounded_clauses(text)
    )


_GENERIC_BEHAVIOR_RE = re.compile(
    r"\b(?:returns?|reports?|shows?|reads?|writes?|loads?|indexes?|retrieves?|selects?|"
    r"validates?|handles?|processes?|dispatches?|routes?|binds?|creates?|updates?|deletes?|use(?:s|d)?|exposes?|"
    r"invokes?|supplies?|calls?|replaces?|preserves?|keeps?|sets?|configures?|requires?|governs?|"
    r"owns?|manages?|controls?|stores?|persists?|saves?|delegates?|maps?|emits?|publishes?|enqueues?|"
    r"accepts?|rejects?|allows?|denies?|coordinates?|schedules?|forwards?|assigns?|applies?|resolves?|"
    r"возвращает|показывает|сообщает|читает|записывает|индексирует|извлекает|выбирает|"
    r"проверяет|обрабатывает|маршрутизирует|создает|обновляет|удаляет|хранит|сохраняет|"
    r"владеет|управляет|делегирует|публикует|отклоняет|разрешает|координирует)\b",
    re.I,
)


def _predicate_has_local_value(match: re.Match[str], clause: str) -> bool:
    """Require a non-empty complement after one locally bound predicate."""

    tail = clause[match.end():]
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9_~:+.-]+", tail)
    return bool(words)


def _predicate_is_negated(match: re.Match[str], clause: str) -> bool:
    """Return whether the matched predicate is locally negated in its clause."""

    prefix = clause[max(0, match.start() - 48):match.start()]
    return bool(re.search(
        r"\b(?:not|never|cannot|can't|does\s+not|do\s+not|did\s+not|"
        r"must\s+not|should\s+not|will\s+not|не|никогда\s+не|нельзя)\s+"
        r"(?:\w+\s+){0,2}$",
        prefix,
        re.I,
    ))


def _definition_clause(obligation: ProofObligation, text: str) -> str | None:
    """Find one proposition that binds definition subject, predicate, and value."""

    for _start, _end, clause in _bounded_clauses(text):
        subject_spans = _subject_spans(obligation, clause)
        if not subject_spans:
            continue
        for match in _COPULA_RE.finditer(clause):
            if not _predicate_has_local_value(match, clause):
                continue
            if re.match(r"\s+(?:not|never|не)\b", clause[match.end():], re.I):
                continue
            if any(
                subject[0] <= match.start()
                and _word_distance(subject, match.span(), clause) <= 10
                for subject in subject_spans
            ):
                return clause
    return None


def _behavior_clause(
    obligation: ProofObligation,
    text: str,
) -> tuple[str, bool] | None:
    """Find one subject-bound generic behavior proposition and its local polarity."""

    for _start, _end, clause in _bounded_clauses(text):
        subject_spans = _subject_spans(obligation, clause)
        if not subject_spans:
            continue
        for match in _GENERIC_BEHAVIOR_RE.finditer(clause):
            if not _predicate_has_local_value(match, clause):
                continue
            if any(
                subject[0] <= match.start()
                and _word_distance(subject, match.span(), clause) <= 10
                for subject in subject_spans
            ):
                return clause, _predicate_is_negated(match, clause)
    return None


def _behavior_qualifiers_present(obligation: ProofObligation, clause: str) -> bool:
    """Keep requested behavior qualifiers bound to the same proposition."""

    operation = str(obligation.expected_value or "").strip()
    operation_present = not operation or re.search(
        rf"(?<!\w){re.escape(operation)}(?:s|es|ed|ing)?(?!\w)", clause, re.I,
    ) is not None
    return (
        operation_present
        and (not obligation.target or _contains_term(obligation.target, clause))
        and (not obligation.context or _contains_term(obligation.context, clause))
    )


_SOURCE_DOCUMENT_SUBJECT_RE = re.compile(
    r"^(?:readme|architecture|changelog|contributing|roadmap|runbook)$",
    re.I,
)


def _source_document_behavior_clause(
    obligation: ProofObligation,
    text: str,
    source_text: str,
) -> tuple[str, bool] | None:
    """Bind conventional document subjects to behavior stated by that document.

    Queries such as ``What does the README say about X?`` name the source
    document itself as the semantic subject. Preserve that source-subject
    contract only for conventional maintained-document identities; arbitrary
    code-shaped filenames must still carry their subject in the proposition.
    """

    if not _SOURCE_DOCUMENT_SUBJECT_RE.fullmatch(_normal(obligation.subject)):
        return None
    if not _subject_present(obligation, source_text):
        return None
    for _start, _end, clause in _bounded_clauses(text):
        if obligation.context and not _contains_term(obligation.context, clause):
            continue
        for match in _GENERIC_BEHAVIOR_RE.finditer(clause):
            if _predicate_has_local_value(match, clause):
                return clause, _predicate_is_negated(match, clause)
    return None


def _special_relation_valid(relation: str | None, text: str) -> bool:
    normalized = _normal(text)
    if relation == "recall_mechanism":
        return bool(
            re.search(r"\bexact(?:[- ]term| match| query)?\b", normalized)
            and re.search(r"\b(?:recall|retrieve|retrieval|lookup|match)\b", normalized)
        )
    if relation == "authority_invariant":
        return bool(
            re.search(r"\b(?:authority|scope)\b", normalized)
            and re.search(
                r"\b(?:unchanged|preserv(?:e|es|ed)|without\s+(?:widening|expanding|broadening)|"
                r"does\s+not\s+(?:widen|expand|broaden))\b",
                normalized,
            )
        )
    if relation == "request_handling":
        return bool(
            re.search(r"\brequest\b|\bзапрос", normalized)
            and re.search(r"\b(?:handles?|process(?:es|ing)?|dispatch(?:es|ing)?|routes?|validates?|forwards?)\b|\b(?:обрабатывает|маршрутизирует|проверяет)", normalized)
            and re.search(r"\b(?:handler|router|server|tool|transport|service|registry)\b", normalized)
        )
    if relation == "architecture":
        return len(set(_ARCH_COMPONENT_RE.findall(normalized))) >= 2 and bool(_ARCH_RELATION_RE.search(normalized))
    if relation == "responsiveness":
        return bool(
            re.search(r"\b(?:non[- ]blocking|asynchronous|async|does\s+not\s+block)\b", normalized)
            and re.search(r"\b(?:worker|background|event\s+loop|queue|thread|task)\b", normalized)
        )
    return False


def local_proof_for_obligation(
    obligation: ProofObligation,
    unit: AnswerUnit,
    *,
    source: Mapping[str, Any] | None = None,
) -> LocalProof:
    """Validate one obligation against exactly one model-visible answer unit."""

    text = unit.text
    source = source or {}
    source_text = "\n".join(str(source.get(key) or "") for key in (
        "path", "source", "title", "heading_path", "project_identity", "module_id",
    ))
    authority = str(source.get("authority") or source.get("project_doc_authority") or "").casefold()
    lifecycle = str(
        source.get("lifecycle_status") or source.get("project_doc_lifecycle_status") or "active"
    ).casefold()
    if obligation.lifecycle_intent == "current" and lifecycle not in {"", "active", "current"}:
        return LocalProof(False, reason="historical_source_for_current_obligation")
    if obligation.lifecycle_intent == "historical" and lifecycle in {"", "active", "current"}:
        # Historical queries may still cite an active status table, but it cannot
        # be the sole witness for a completed/historical fact.
        return LocalProof(False, reason="current_source_for_historical_obligation")

    subject_local = _subject_present(obligation, text)
    authoritative_identity = (
        authority in {"canonical", "source_of_truth", "official", "project_owned", "project_rule", "primary"}
        and _subject_present(obligation, source_text)
    )
    # Synthetic parser fallbacks (``project``, ``request``, ``workflow`` and
    # similar placeholders) are never proof by themselves.  A very small set
    # of legacy semantic subjects is different: v1-v3 intentionally models
    # relations such as MCP architecture/request handling as a typed facet and
    # allows the locally visible component nouns (server/handler/transport) to
    # carry the subject identity.  Keep that frozen compatibility without
    # reopening the generic-subject false-positive path.
    legacy_semantic_subject = (
        _normal(obligation.subject) in {"mcp server", "exact-term retrieval", "authority scope"}
        and obligation.kind == "relation"
        and obligation.relation in {
            "recall_mechanism", "authority_invariant", "request_handling",
            "architecture", "responsiveness",
        }
    )
    subject_score = (
        3 if subject_local else
        2 if authoritative_identity else
        1 if legacy_semantic_subject and unit.proposition else
        0
    )

    if obligation.kind == "purpose":
        context = _context_score(obligation.context, text, source_text)
        purpose = _purpose_clause(obligation, text)
        bound_clause = purpose[0] if purpose is not None else None
        relation = purpose[1] if purpose is not None else 0
        value = _value_score("text", bound_clause or "")
        valid = subject_local and context > 0 and relation > 0 and value > 0 and unit.proposition
        return LocalProof(
            valid, subject_score, relation + context, value,
            subject_score + relation + context + value,
            "purpose" if valid else "purpose_subject_context_or_predicate_missing",
        )

    if obligation.kind == "effect":
        relation_valid = _effect_relation_valid(obligation, text)
        relation = 3 if relation_valid else 0
        value = 2 if relation_valid else 0
        valid = subject_score > 0 and relation > 0 and unit.proposition
        return LocalProof(
            valid, subject_score, relation, value,
            subject_score + relation + value,
            f"effect_{obligation.relation}" if valid else f"effect_{obligation.relation}_not_locally_bound",
        )

    if obligation.kind == "definition":
        bound_clause = _definition_clause(obligation, text)
        relation = 3 if bound_clause is not None else 0
        value = _value_score("text", bound_clause or "")
        local_subject_score = 3 if bound_clause is not None else 0
        valid = local_subject_score > 0 and relation > 0 and value > 0 and unit.proposition
        return LocalProof(
            valid, local_subject_score, relation, value,
            local_subject_score + relation + value,
            "definition" if valid else "definition_not_locally_bound",
        )

    if obligation.kind == "attribute":
        if obligation.relation in {"decision_for_action", "argument_value"}:
            planned = planned_relation_proof(obligation, text, source=source)
            if planned is not None:
                effective_subject_score = max(subject_score, planned.subject_score)
                valid = planned.valid and effective_subject_score > 0 and unit.proposition
                return LocalProof(
                    valid, effective_subject_score,
                    planned.relation_score if valid else 0,
                    planned.value_score if valid else 0,
                    effective_subject_score
                    + (planned.relation_score if valid else 0)
                    + (planned.value_score if valid else 0),
                    planned.reason,
                )
        attribute = 3 if _attribute_present(obligation.attribute, text) else 0
        value = _value_score(obligation.value_kind, text)
        local_binding = bool(attribute and value and (subject_local or authoritative_identity))
        return LocalProof(local_binding, subject_score, attribute, value, subject_score + attribute + value, "attribute" if local_binding else "attribute_value_not_locally_bound")

    if obligation.kind == "inventory":
        explicit_count, names, anchored = _inventory_facts(
            text, item_kind=obligation.item_kind,
        )
        attribute_bound = anchored and (
            obligation.item_kind == "public_tool"
            or _attribute_present(obligation.attribute, text)
        )
        attribute = 3 if attribute_bound else 0
        names_valid = len(names) >= 2 and (
            obligation.cardinality is None or len(names) == obligation.cardinality
        )
        derived_count = explicit_count if explicit_count is not None else (len(names) if names_valid else None)
        count_valid = derived_count is not None and (
            obligation.cardinality is None or derived_count == obligation.cardinality
        )
        mode = obligation.response_mode
        value = (
            3 if mode == "count" and count_valid else
            3 if mode == "names" and names_valid else
            3 if mode == "count_and_names" and count_valid and names_valid else 0
        )
        inventory_subject_score = subject_score
        if inventory_subject_score == 0 and obligation.item_kind == "public_tool" and anchored:
            # ``Docs MCP`` is a domain label rather than text that every
            # canonical inventory sentence must repeat.  A closed public-tool
            # inventory is itself sufficient subject binding; this exception is
            # intentionally limited to the frozen public-tool contract.
            inventory_subject_score = 1
        valid = inventory_subject_score >= 1 and attribute > 0 and value > 0
        reason = "inventory" if valid else "inventory_not_closed_or_not_locally_bound"
        return LocalProof(valid, inventory_subject_score, attribute, value, inventory_subject_score + attribute + value, reason)

    if obligation.kind == "command":
        expected = obligation.expected_value or obligation.subject
        expected_present = _contains_term(expected, text)
        normalized = _normal(text)
        action_binding = bool(
            re.search(rf"\baction\s*=\s*[\"']{re.escape(expected)}[\"']", text, re.I)
            or re.search(rf"\b[A-Za-z_][A-Za-z0-9_]*\s*\([^)]*{re.escape(expected)}", text, re.I | re.S)
            or ("doc-atlas" in normalized and expected.replace("_", " ") in normalized)
        )
        call_shape = bool(re.search(r"\b[A-Za-z_][A-Za-z0-9_]*\s*\(", text) or "doc-atlas" in normalized)
        relation = 3 if expected_present and action_binding and call_shape else 0
        valid = relation > 0 and unit.proposition and unit.source_field is None
        return LocalProof(valid, 3 if expected_present else 0, relation, 3 if call_shape else 0, relation + (3 if expected_present else 0) + (3 if call_shape else 0), "command" if valid else "command_operation_not_locally_bound")

    if obligation.kind == "location":
        if unit.source_field not in {"path_or_url", "path", "source_path"}:
            return LocalProof(False, reason="location_requires_source_field")
        source_identity_text = source_text + "\n" + text
        overlap = _subject_token_overlap(obligation.subject, source_identity_text)
        value = _value_score("path", text)
        valid = overlap > 0 and value > 0
        return LocalProof(valid, min(3, overlap + 1), 3 if overlap else 0, value, overlap + value + 3, "location" if valid else "location_subject_not_bound_to_source")

    if obligation.kind == "status":
        attribute = 2 if _attribute_present("status", text) else 1 if _STATUS_VALUE_RE.search(text) else 0
        value = _value_score("status", text)
        valid = subject_score > 0 and attribute > 0 and value > 0
        return LocalProof(valid, subject_score, attribute, value, subject_score + attribute + value, "status" if valid else "status_subject_not_locally_bound")

    if obligation.kind == "comparison":
        target = 3 if _contains_term(obligation.target, text) else 0
        explicit = _explicit_comparison_is_local(obligation, text)
        left_predicates, right_predicates = _comparison_predicates(obligation, text)
        implicit_difference = bool(
            left_predicates
            and right_predicates
            and any(left != right for left in left_predicates for right in right_predicates)
        )
        relation = 3 if explicit else 2 if implicit_difference else 0
        valid = subject_score > 0 and target > 0 and relation > 0 and unit.proposition
        return LocalProof(
            valid, subject_score, relation, target,
            subject_score + relation + target,
            "comparison" if valid else "comparison_relation_missing",
        )

    if obligation.kind == "behavior":
        planned = planned_behavior_proof(obligation, text, source=source)
        if planned is not None:
            effective_subject_score = max(subject_score, planned.subject_score)
            valid = planned.valid and effective_subject_score > 0
            return LocalProof(
                valid, effective_subject_score, planned.relation_score if valid else 0,
                planned.value_score if valid else 0,
                effective_subject_score + (planned.relation_score if valid else 0) + (planned.value_score if valid else 0),
                planned.reason if valid else f"{planned.reason}_subject_not_bound",
            )
        bound_behavior = _behavior_clause(obligation, text)
        source_document_behavior = (
            _source_document_behavior_clause(obligation, text, source_text)
            if bound_behavior is None and authoritative_identity
            else None
        )
        proof_behavior = bound_behavior or source_document_behavior
        negated = bool(proof_behavior and proof_behavior[1])
        qualifiers_present = bool(
            proof_behavior
            and _behavior_qualifiers_present(obligation, proof_behavior[0])
        )
        relation = 3 if proof_behavior is not None and not negated and qualifiers_present else 0
        local_subject_score = (
            3 if bound_behavior is not None else
            2 if source_document_behavior is not None else
            0
        )
        valid = local_subject_score > 0 and relation > 0 and unit.proposition
        return LocalProof(
            valid, local_subject_score, relation, 1 if unit.proposition and valid else 0,
            local_subject_score + relation + int(unit.proposition and valid),
            (
                "behavior_negated" if negated else
                "behavior_qualifier_missing" if proof_behavior is not None and not qualifiers_present else
                "behavior_source_document" if valid and source_document_behavior is not None else
                "behavior" if valid else
                "behavior_not_locally_bound"
            ),
        )

    if obligation.kind == "usage":
        planned = planned_usage_proof(obligation, text, source=source)
        if planned is not None:
            effective_subject_score = max(subject_score, planned.subject_score)
            valid = planned.valid and effective_subject_score > 0
            return LocalProof(
                valid, effective_subject_score, planned.relation_score if valid else 0,
                planned.value_score if valid else 0,
                effective_subject_score + (planned.relation_score if valid else 0) + (planned.value_score if valid else 0),
                planned.reason if valid else f"{planned.reason}_subject_not_bound",
            )
        negated = bool(_NEGATION_RE.search(text))
        subject_pattern = re.escape(_normal(obligation.subject)).replace(r"\ ", r"[\s_]+")
        normalized = _normal(text)
        locally_bound = bool(
            re.search(rf"(?<!\w){subject_pattern}(?!\w)(?:\W+\w+){{0,8}}?\W+{_USAGE_RE.pattern}", normalized, _USAGE_RE.flags)
            or re.search(rf"{_USAGE_RE.pattern}(?:\W+\w+){{0,8}}?\W+(?<!\w){subject_pattern}(?!\w)", normalized, _USAGE_RE.flags)
        )
        relation = 3 if not negated and locally_bound else 0
        valid = subject_score > 0 and relation > 0 and unit.proposition
        return LocalProof(valid, subject_score, relation, 1 if unit.proposition else 0, subject_score + relation + int(unit.proposition), "usage" if valid else "usage_missing_or_negated")

    if obligation.kind == "workflow":
        planned = planned_workflow_proof(obligation, text, source=source)
        if planned is not None:
            effective_subject_score = max(subject_score, planned.subject_score)
            valid = planned.valid and effective_subject_score > 0
            return LocalProof(
                valid, effective_subject_score, planned.relation_score if valid else 0,
                planned.value_score if valid else 0,
                effective_subject_score + (planned.relation_score if valid else 0) + (planned.value_score if valid else 0),
                planned.reason if valid else f"{planned.reason}_subject_not_bound",
            )
        negated = bool(_NEGATION_RE.search(text))
        target_score = 3 if not obligation.target or _contains_term(obligation.target, text) else 0
        sequence = bool(_SEQUENCE_RE.search(text)) or text.count("\n-") + len(re.findall(r"^\s*\d+[.)]\s+", text, re.M)) >= 2
        action_count = len(_ACTION_RE.findall(text))
        relation = 3 if (
            not negated
            and target_score > 0
            and action_count >= 2
            and (sequence or unit.kind in {"unit_group", "heading_context", "code_block"})
        ) else 0
        valid = subject_score > 0 and relation > 0 and unit.proposition and unit.kind in {
            "unit_group", "heading_context", "code_block", "bullet", "sentence", "key_value",
        }
        return LocalProof(valid, subject_score, relation, action_count + target_score, subject_score + relation + action_count + target_score, "workflow" if valid else "workflow_subject_target_or_sequence_missing")

    if obligation.kind == "relation":
        planned = planned_relation_proof(obligation, text, source=source)
        if planned is not None:
            effective_subject_score = max(subject_score, planned.subject_score)
            valid = planned.valid and effective_subject_score > 0
            return LocalProof(
                valid, effective_subject_score, planned.relation_score if valid else 0,
                planned.value_score if valid else 0,
                effective_subject_score + (planned.relation_score if valid else 0) + (planned.value_score if valid else 0),
                planned.reason if valid else f"{planned.reason}_subject_not_bound",
            )
        special_valid = _special_relation_valid(obligation.relation, text)
        target = 2 if not obligation.target or _contains_term(obligation.target, text) else 0
        relation = 3 if special_valid else 0
        if not obligation.relation or obligation.relation == "relation":
            relation = 3 if (_BEHAVIOR_RE.search(text) or _SEQUENCE_RE.search(text) or _CONTRAST_RE.search(text)) else 0
        elif obligation.relation not in {
            "recall_mechanism", "authority_invariant", "request_handling",
            "architecture", "responsiveness",
        }:
            relation = 3 if _contains_term(obligation.relation, text) else 0
        valid = subject_score > 0 and target > 0 and relation > 0 and unit.proposition
        return LocalProof(valid, subject_score, relation, target, subject_score + relation + target, "relation" if valid else f"{obligation.relation or 'relation'}_missing")

    if obligation.kind == "exact_fact":
        relation = 2 if (not obligation.attribute or _attribute_present(obligation.attribute, text)) else 0
        value = _value_score(obligation.value_kind, text)
        if obligation.expected_value:
            value = max(value, 3 if _contains_term(obligation.expected_value, text) else 0)
        valid = subject_score > 0 and relation > 0 and value > 0 and unit.proposition
        return LocalProof(valid, subject_score, relation, value, subject_score + relation + value, "exact_fact" if valid else "exact_fact_missing")

    return LocalProof(False, reason="unsupported_obligation")


def best_local_proof(
    obligation: ProofObligation,
    units: Iterable[AnswerUnit],
    *,
    source: Mapping[str, Any] | None = None,
) -> tuple[AnswerUnit, LocalProof] | None:
    matches: list[tuple[AnswerUnit, LocalProof]] = []
    for unit in units:
        proof = local_proof_for_obligation(obligation, unit, source=source)
        if proof.valid:
            matches.append((unit, proof))
    if not matches:
        return None
    matches.sort(key=lambda pair: (
        -pair[1].completeness_score,
        0 if pair[0].proposition else 1,
        len(pair[0].text),
        pair[0].char_start if pair[0].char_start is not None else 10**9,
        pair[0].unit_id,
    ))
    return matches[0]

__all__=['_attribute_aliases', '_attribute_present', '_inventory_anchor', '_inventory_facts', '_subject_token_overlap', '_value_score', '_subject_before_pattern', '_special_relation_valid', 'local_proof_for_obligation', 'best_local_proof']
