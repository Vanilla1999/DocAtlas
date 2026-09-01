"""Implementation shard 2 for project_answer_contract."""
from __future__ import annotations

from ._project_answer_contract_shared import *  # noqa: F401,F403

from ._project_answer_contract_part01 import ProjectAnswerContract, ProofObligation, _append_relation_obligation, _best_subject, _bounded, _cardinality, _clean_phrase, _command_operation, _compound_workflow_subjects, _concept_queries, _contract_from_question_plan, _effect_relation, _explicit_subjects, _inventory_subject, _location_subject, _normal, _obligation, _retrieval_hints, _subject_fields, _subjects, _technical_term_for_value, _technical_terms, lifecycle_intent_for_question


_SOURCE_DOCUMENT_SUBJECTS = frozenset({
    "readme", "architecture", "changelog", "contributing", "roadmap", "runbook",
})
_SOURCE_DOCUMENT_CONTEXT_RE = re.compile(
    r"\b(?:say|says|state|states|report|reports|describe|describes)\s+"
    r"(?:about|regarding|on)\s+(.+?)(?:[?!.]|$)",
    re.I,
)


def _source_document_behavior_context(question: str, subject: str) -> str | None:
    """Return the requested topic for a conventional source-document query."""

    if _normal(subject) not in _SOURCE_DOCUMENT_SUBJECTS:
        return None
    match = _SOURCE_DOCUMENT_CONTEXT_RE.search(question)
    if match is None:
        return None
    return _clean_phrase(match.group(1)) or None


def _generic_behavior_qualifiers(
    question: str, subject: str,
) -> tuple[str | None, str | None]:
    """Preserve the requested action and object for generic mechanism questions."""

    subject_pattern = re.escape(subject).replace(r"\ ", r"[\s_]+")
    match = re.match(
        rf"^\s*(?:how|what)\s+does\s+(?:the\s+)?{subject_pattern}\s+"
        r"([A-Za-z][A-Za-z0-9_-]*)\s*(.*?)[?!.]*\s*$",
        question,
        re.I,
    )
    if match is None or match.group(1).casefold() in {"do", "work"}:
        return None, None
    action = _clean_phrase(match.group(1)) or None
    target = _clean_phrase(match.group(2)) or None
    if target and re.match(r"^(?:and|or)\b", target, re.I):
        return None, None
    return action, target


def build_project_answer_contract(question: str) -> ProjectAnswerContract:
    """Build a bounded deterministic answer contract from the public question."""

    source_question = str(question or "")
    raw_question = source_question[:4_000]
    input_limits: list[str] = ["question"] if len(source_question) > 4_000 else []
    lifecycle = lifecycle_intent_for_question(raw_question)
    question_plan = compile_question_plan(raw_question)
    if question_plan.handled:
        return _contract_from_question_plan(
            raw_question, question_plan, lifecycle=lifecycle,
            input_limits=tuple(input_limits),
        )
    technical_terms = _technical_terms(raw_question)
    subjects = _subjects(raw_question)
    obligations: list[ProofObligation] = []

    declarative = _DECLARATIVE_RELATION_RE.match(raw_question)
    if declarative and not re.match(r"^(?:what|which|how|when|where|why|who|что|как|когда|где|почему)\b", raw_question, re.I):
        subject, relation, target = (
            _bounded(declarative.group(1)),
            _bounded(declarative.group(2)),
            _bounded(declarative.group(3).strip(" ?!.,:")),
        )
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="relation",
            subject=subject, relation=relation, target=target, value_kind="text",
            lifecycle_intent=lifecycle, span_value=declarative.group(0).strip(),
        ))

    if _IMPLEMENT_RE.search(raw_question):
        exact_values = [term.value.strip("`") for term in extract_exact_terms(raw_question)]
        implementation_subjects = exact_values or _explicit_subjects(raw_question, subjects)
        for subject in implementation_subjects[:4]:
            obligations.append(_obligation(
                question=raw_question, index=len(obligations), kind="exact_fact",
                subject=subject, relation="implementation", value_kind="code",
                lifecycle_intent=lifecycle,
                span_value=subject if subject.casefold() in raw_question.casefold() else _IMPLEMENT_RE.search(raw_question).group(0),
            ))

    comparison = _COMPARE_RE.search(raw_question)
    if comparison:
        left = (comparison.group(1) or comparison.group(3) or "").strip("`")
        right = (comparison.group(2) or comparison.group(4) or "").strip("`")
        if left and right:
            obligations.append(_obligation(
                question=raw_question, index=len(obligations), kind="comparison",
                subject=left, target=right, relation="contrast", value_kind="text",
                lifecycle_intent=lifecycle, span_value=comparison.group(0),
            ))

    task_match = _TASK_RE.search(raw_question)
    if task_match and _STATUS_RE.search(raw_question):
        task = f"Task {task_match.group(1)}"
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="status",
            subject=task, attribute="status", value_kind="status",
            lifecycle_intent=lifecycle, span_value=task_match.group(0),
        ))

    if _VERSION_QUESTION_RE.search(raw_question):
        subject = _best_subject(
            raw_question,
            [value for value in subjects if value.casefold() not in {"python", "version"}],
            fallback="project",
        )
        attribute = "python_version" if re.search(r"\bpython\b", raw_question, re.I) else "version"
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="attribute",
            subject=subject, attribute=attribute, value_kind="version_range",
            lifecycle_intent=lifecycle, span_value=_VERSION_QUESTION_RE.search(raw_question).group(0),
        ))

    if _TIMEOUT_RE.search(raw_question):
        timeout_match = _TIMEOUT_RE.search(raw_question)
        subject_candidates = [
            value for value in subjects
            if value.casefold() not in {"timeout", "deadline", "request", "provider"}
        ]
        subject = _best_subject(raw_question, subject_candidates, fallback="request")
        # Preserve a nearby provider/request qualifier as part of the subject.
        local = raw_question[max(0, timeout_match.start() - 80):timeout_match.end() + 80]
        qualifier = re.search(r"\b([A-Za-z_][A-Za-z0-9_.-]*(?:\s+(?:provider|request))|provider\s+request|request)\b", local, re.I)
        if qualifier and subject == "request":
            subject = qualifier.group(1)
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="attribute",
            subject=subject, attribute="timeout", value_kind="duration",
            lifecycle_intent=lifecycle, span_value=timeout_match.group(0),
        ))

    used_for = _USED_FOR_RE.match(raw_question)
    if used_for and not obligations:
        raw_subject = _clean_phrase(used_for.group(1))
        term = _technical_term_for_value(raw_subject, technical_terms)
        subject = term.raw if term is not None else raw_subject
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="purpose",
            subject=subject, relation="purpose", value_kind="text", response_mode="purpose",
            lifecycle_intent=lifecycle, span_value=used_for.group(1),
            **_subject_fields(subject, term),
        ))

    feature_context = _FEATURE_CONTEXT_RE.match(raw_question)
    if feature_context and not obligations:
        raw_subject = _clean_phrase(feature_context.group(1))
        context = _clean_phrase(feature_context.group(2))
        term = _technical_term_for_value(raw_subject, technical_terms)
        subject = term.raw if term is not None else raw_subject
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="purpose",
            subject=subject, relation="purpose", context=context, value_kind="text", response_mode="purpose",
            lifecycle_intent=lifecycle, span_value=feature_context.group(1),
            **_subject_fields(subject, term),
        ))

    term_in_context = _TERM_IN_CONTEXT_RE.match(raw_question)
    if term_in_context and not obligations:
        raw_subject = _clean_phrase(term_in_context.group(1))
        context = _clean_phrase(term_in_context.group(2))
        context_term = _technical_term_for_value(context, technical_terms)
        preferred_kind: TechnicalTermKind | None = None
        if context_term is not None and context_term.kind == "cli_command" and re.fullmatch(
            r"[A-Za-z][A-Za-z0-9_-]{2,120}", raw_subject,
        ):
            preferred_kind = "cli_flag"
        term = _technical_term_for_value(
            raw_subject, technical_terms, preferred_kind=preferred_kind,
        )
        if (
            term is not None
            and context_term is not None
            and context_term.kind == "cli_command"
        ):
            subject = term.raw
            obligations.append(_obligation(
                question=raw_question, index=len(obligations), kind="purpose",
                subject=subject, relation="purpose", context=context, value_kind="text", response_mode="purpose",
                lifecycle_intent=lifecycle, span_value=term_in_context.group(1),
                **_subject_fields(subject, term),
            ))

    supported_values = _SUPPORTED_VALUES_RE.match(raw_question)
    if supported_values and not obligations:
        raw_attribute = _clean_phrase(supported_values.group(1))
        forms = controlled_noun_forms(raw_attribute)
        attribute = next((value for value in forms if value != raw_attribute.casefold()), raw_attribute.casefold())
        raw_subject = _clean_phrase(supported_values.group(2))
        term = _technical_term_for_value(raw_subject, technical_terms)
        subject = term.raw if term is not None else raw_subject
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="inventory",
            subject=subject, attribute=attribute, item_kind=attribute,
            value_kind="identifier_list", response_mode="names",
            lifecycle_intent=lifecycle, span_value=supported_values.group(1),
            **_subject_fields(subject, term),
        ))

    coordinated_effect = _COORDINATED_EFFECT_RE.match(raw_question)
    if coordinated_effect and not obligations:
        raw_subject = _clean_phrase(coordinated_effect.group(1))
        term = _technical_term_for_value(raw_subject, technical_terms)
        subject = term.raw if term is not None else raw_subject
        for raw_relation in (coordinated_effect.group(2), coordinated_effect.group(3)):
            relation = _effect_relation(raw_relation)
            obligations.append(_obligation(
                question=raw_question, index=len(obligations), kind="effect",
                subject=subject, relation=relation, value_kind="text",
                lifecycle_intent=lifecycle, span_value=raw_relation,
                **_subject_fields(subject, term),
            ))

    command_question = _COMMAND_QUESTION_RE.search(raw_question)
    if command_question:
        operation = _command_operation(raw_question)
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="command",
            subject=operation, relation="invocation", value_kind="call_expression",
            expected_value=operation if operation != "requested operation" else None,
            response_mode="call", lifecycle_intent=lifecycle,
            span_value=command_question.group(0),
        ))

    inventory_noun = _PLURAL_TOOL_RE.search(raw_question)
    surface_inventory = re.search(r"\b(?:tool(?:s)?(?:[- ]\w+){0,5}\s+surface|three[- ]tool(?:[- ]\w+){0,5}\s+surface|public(?:[- ]\w+){0,5}\s+surface)\b", raw_question, re.I)
    generic_command_inventory = re.search(
        r"\b(?:commands?|methods?|команд(?:ы|а|ах|у)?|метод(?:ы|а|ов)?)\b",
        raw_question,
        re.I,
    )
    explicit_public_tool_context = bool(
        surface_inventory
        or re.search(
            r"\b(?:MCP|Docs\s+MCP|public\s+tools?|public\s+commands?|"
            r"публичн\w*\s+(?:инструмент|команд)\w*)\b",
            raw_question,
            re.I,
        )
    )
    if (
        not command_question
        and (inventory_noun or surface_inventory)
        and _INVENTORY_RE.search(raw_question)
        and (not generic_command_inventory or explicit_public_tool_context)
    ):
        tool_match = inventory_noun or surface_inventory
        subject = _inventory_subject(raw_question, subjects)
        count_requested = bool(re.search(r"\bhow\s+many\b|\bсколько\b", raw_question, re.I))
        names_requested = bool(re.search(
            r"\b(?:what\s+are|which|list|enumerate|surface)\b|\b(?:какие|перечисл|список)\b",
            raw_question, re.I,
        ))
        response_mode: ResponseMode = (
            "count_and_names" if count_requested and names_requested else
            "count" if count_requested else "names"
        )
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="inventory",
            subject=subject, attribute="public_tools",
            value_kind="number" if response_mode == "count" else "identifier_list",
            item_kind="public_tool", cardinality=_cardinality(raw_question),
            response_mode=response_mode, lifecycle_intent=lifecycle, span_value=tool_match.group(0),
        ))

    location_question = _LOCATION_QUESTION_RE.search(raw_question)
    if location_question:
        subject = _location_subject(raw_question, subjects)
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="location",
            subject=subject, relation="location", value_kind="path", response_mode="path",
            lifecycle_intent=lifecycle, span_value=location_question.group(0),
        ))

    special_relations: list[tuple[str, str, str]] = []
    if _RECALL_MECHANISM_RE.search(raw_question):
        special_relations.append(("exact-term retrieval", "recall_mechanism", _RECALL_MECHANISM_RE.search(raw_question).group(0)))
    if _AUTHORITY_INVARIANT_RE.search(raw_question):
        special_relations.append(("authority scope", "authority_invariant", _AUTHORITY_INVARIANT_RE.search(raw_question).group(0)))
    if _REQUEST_HANDLING_RE.search(raw_question):
        special_relations.append(("MCP server", "request_handling", _REQUEST_HANDLING_RE.search(raw_question).group(0)))
    architecture_match = _ARCHITECTURE_RE.search(raw_question)
    if architecture_match and re.search(r"\bMCP\b", raw_question, re.I):
        special_relations.append(("MCP server", "architecture", architecture_match.group(0)))
    if _RESPONSIVENESS_RE.search(raw_question):
        special_relations.append(("MCP server", "responsiveness", _RESPONSIVENESS_RE.search(raw_question).group(0)))
    for subject, relation, span_value in special_relations:
        _append_relation_obligation(
            obligations, question=raw_question, subject=subject,
            relation=relation, lifecycle=lifecycle, span_value=span_value,
        )

    definition = _DEFINITION_RE.search(raw_question)
    if definition and not _ARCHITECTURE_RE.search(raw_question) and not obligations:
        tail = raw_question[definition.end():].strip(" ?!.,:")
        subject = _best_subject(raw_question, subjects, fallback=_bounded(tail) or "project")
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="definition",
            subject=subject, value_kind="text", lifecycle_intent=lifecycle,
            span_value=subject if subject.casefold() in raw_question.casefold() else definition.group(0),
        ))

    explicit_subjects = _explicit_subjects(raw_question, subjects)
    if not obligations and _CONTRACT_FACT_RE.search(raw_question):
        # Contract questions commonly name several schema/symbol identities but
        # do not use a classic "what is" or "what does" frame. Turn each named
        # identity into a proposition-bearing exact-fact obligation instead of
        # treating the names themselves as proof. A topical contract subject
        # keeps the governing rule sentence visible as its own local witness.
        contract_subjects: list[str] = []
        if re.search(r"\bpresentation(?:-only)?\b|\bпредставлен", raw_question, re.I):
            contract_subjects.append("presentation")
        if re.search(r"\bvectors?\b|\bвектор", raw_question, re.I):
            contract_subjects.append("vectors")
        elif re.search(r"\bembeddings?\b|\bэмбед", raw_question, re.I):
            contract_subjects.append("embeddings")
        contract_subjects.extend(explicit_subjects)
        if not contract_subjects:
            contract_match = re.search(
                r"(?:phase\s+[0-9.]+\s+)?([A-Za-zА-Яа-яЁё][\w-]{2,})"
                r"(?:\s+[A-Za-zА-Яа-яЁё][\w-]{2,}){0,2}\s+"
                r"(?:contract|rule|requirement|invariant|policy)",
                raw_question,
                re.I,
            )
            if contract_match:
                candidate = contract_match.group(1).strip()
                if candidate.casefold() not in {"what", "which", "who", "how"}:
                    contract_subjects.append(candidate)
        for subject in list(dict.fromkeys(contract_subjects))[:4]:
            attribute = (
                "response contract"
                if re.search(r"\bresponse\s+contract\b", raw_question, re.I)
                else None
            )
            obligations.append(_obligation(
                question=raw_question, index=len(obligations), kind="exact_fact",
                subject=subject, attribute=attribute,
                relation="contract_fact", value_kind="text",
                lifecycle_intent=lifecycle,
                span_value=subject if subject.casefold() in raw_question.casefold() else _CONTRACT_FACT_RE.search(raw_question).group(0),
            ))

    workflow = _WORKFLOW_RE.search(raw_question)
    compound_subject, compound_target = _compound_workflow_subjects(raw_question)
    workflow_requested = bool(
        workflow
        or (
            re.search(r"\bhow\s+does\b|\bкак\s+работает\b", raw_question, re.I)
            and compound_subject and compound_target
        )
    )
    if workflow_requested and not any(item.kind in {"comparison", "inventory", "command", "location"} for item in obligations):
        subject = compound_subject or _best_subject(raw_question, subjects, fallback="workflow")
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="workflow",
            subject=subject, target=compound_target, relation="sequence", value_kind="text",
            response_mode="workflow", lifecycle_intent=lifecycle,
            span_value=(workflow.group(0) if workflow else subject),
        ))

    behavior = _BEHAVIOR_RE.search(raw_question)
    behavior_requested = bool(behavior or (_EXPLAIN_RE.search(raw_question) and explicit_subjects))
    if behavior_requested and not any(
        item.kind in {
            "attribute", "status", "inventory", "comparison", "relation", "exact_fact",
            "command", "location", "workflow", "purpose", "effect",
        }
        for item in obligations
    ):
        behavior_subjects = explicit_subjects or [_best_subject(raw_question, subjects, fallback="project")]
        for subject in behavior_subjects:
            operation, operation_target = _generic_behavior_qualifiers(raw_question, subject)
            obligations.append(_obligation(
                question=raw_question, index=len(obligations), kind="behavior",
                subject=subject, relation="behavior", target=operation_target,
                expected_value=operation, value_kind="text",
                context=_source_document_behavior_context(raw_question, subject),
                lifecycle_intent=lifecycle,
                span_value=subject if subject.casefold() in raw_question.casefold() else (behavior.group(0) if behavior else _EXPLAIN_RE.search(raw_question).group(0)),
            ))

    usage = _USAGE_RE.search(raw_question)
    usage_requested = bool(usage and re.search(
        r"\b(?:when|should|recommended|using)\b|\b(?:когда|следует|рекомендуется|используя)\b",
        raw_question,
        re.I,
    ))
    if usage_requested:
        usage_subjects = explicit_subjects or [_best_subject(raw_question, subjects, fallback="project")]
        for subject in usage_subjects:
            obligations.append(_obligation(
                question=raw_question, index=len(obligations), kind="usage",
                subject=subject, relation="usage", value_kind="text",
                lifecycle_intent=lifecycle,
                span_value=subject if subject.casefold() in raw_question.casefold() else usage.group(0),
            ))

    # De-duplicate semantic aliases while retaining the earliest query provenance.
    unique: dict[tuple[Any, ...], ProofObligation] = {}
    for obligation in obligations:
        key = (
            obligation.kind, _normal(obligation.subject), obligation.attribute,
            obligation.relation, _normal(obligation.target or ""), obligation.value_kind,
            obligation.expected_value, obligation.item_kind, obligation.cardinality,
            obligation.response_mode, obligation.subject_kind, obligation.subject_aliases,
            _normal(obligation.context or ""),
        )
        unique.setdefault(key, obligation)
    obligations = list(unique.values())[:MAX_PROOF_OBLIGATIONS]
    synthetic_subjects = {"project", "request", "workflow", "requested operation", "the"}
    unresolved_synthetic = tuple(sorted({
        obligation.subject
        for obligation in obligations
        if _normal(obligation.subject) in synthetic_subjects
        and (not subjects or _normal(obligation.subject) == "requested operation")
    }))
    if unresolved_synthetic:
        safe_subjects = [value for value in subjects if _normal(value) not in synthetic_subjects]
        hints = _retrieval_hints(raw_question, safe_subjects, technical_terms)
        return ProjectAnswerContract(
            question_hash=canonical_hash(raw_question),
            retrieval_hints=hints,
            concept_queries=(),
            subjects=tuple(safe_subjects),
            proof_obligations=(),
            lifecycle_intent=lifecycle,
            schema_version=PROJECT_ANSWER_CONTRACT_SCHEMA_V4,
            input_limits=tuple(input_limits),
            parse_trace=("fail_closed:synthetic_subject",),
            unresolved_parts=tuple(
                "unresolved_requested_operation" if value == "requested operation"
                else "unresolved_query_subject"
                for value in unresolved_synthetic
            ),
        )
    uses_v3 = any(
        obligation.kind in {"purpose", "effect"}
        or obligation.subject_kind is not None
        or obligation.context is not None
        or (obligation.kind == "inventory" and obligation.item_kind not in {None, "public_tool"})
        for obligation in obligations
    )
    contract_subjects = list(subjects)
    if uses_v3:
        contract_subjects.extend(term.raw for term in technical_terms)
        contract_subjects = list(dict.fromkeys(contract_subjects))[:MAX_SUBJECTS]
    hints = _retrieval_hints(
        raw_question,
        contract_subjects,
        technical_terms if uses_v3 else (),
    )
    concepts = _concept_queries(raw_question, hints, obligations)
    return ProjectAnswerContract(
        question_hash=canonical_hash(raw_question),
        retrieval_hints=hints,
        concept_queries=concepts,
        subjects=tuple(contract_subjects[:MAX_SUBJECTS]),
        proof_obligations=tuple(obligations),
        lifecycle_intent=lifecycle,
        schema_version=(
            PROJECT_ANSWER_CONTRACT_SCHEMA
            if uses_v3 else PROJECT_ANSWER_CONTRACT_SCHEMA_V2
        ),
        input_limits=tuple(input_limits),
    )

__all__=['build_project_answer_contract']
