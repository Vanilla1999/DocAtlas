"""Specialized local-proof predicates for QuestionPlan v4 facets.

The legacy answer-unit proof engine stays frozen for v1-v3 semantics.  New
compositional intents are validated here so adding a parser rule does not grow
one monolithic validator.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from docmancer.docs.domain.project_answer_contract import ProofObligation
from docmancer.docs.domain.question_premise_proof import premise_relation_proof
from docmancer.docs.domain.technical_terms import term_sequence_present


@dataclass(frozen=True, slots=True)
class PlannedProof:
    valid: bool
    relation_score: int = 0
    value_score: int = 0
    reason: str = ""
    # Relation-specific validators may bind a semantic subject through a
    # closed set of exact anchors (for example all three public tool names).
    # This is never granted merely because the relation predicate matched.
    subject_score: int = 0


def _norm(value: object) -> str:
    return " ".join(str(value or "").casefold().replace("_", " ").split())


def _has(value: str, text: str) -> bool:
    return term_sequence_present(value, text)


def _proposition_clauses(text: str) -> tuple[str, ...]:
    """Split one visible unit into conservative proposition-local clauses.

    Sentence terminators, semicolons, and physical line boundaries end a
    proposition. Dotted identifiers and versions stay intact because a period
    is a boundary only before whitespace or the end of the unit.
    """

    source = str(text or "")
    if not source:
        return ()
    clauses: list[str] = []
    start = 0
    for boundary in re.finditer(r"(?:[.!?](?=\s|$)|;|\n)", source):
        end = boundary.end()
        clause = source[start:end].strip()
        if clause:
            clauses.append(clause)
        start = end
    tail = source[start:].strip()
    if tail:
        clauses.append(tail)
    return tuple(clauses)


_REQUIREMENT_RELATION_RE = re.compile(
    r"\b(?:require(?:s|d)?|required|must|mandatory|need(?:s|ed)?|do\s+not)\b",
    re.I,
)


def _requirement_detail_count(text: str) -> int:
    return len(re.findall(
        r"\b(?:preflight|canary|exactly|retry|audit|verify|stream|cell|step)\w*\b",
        _norm(text),
    ))


def _structured_requirement_proof(
    obligation: ProofObligation,
    text: str,
) -> tuple[bool, int]:
    """Accept only a subject-bound requirement clause or its explicit list."""

    best_detail_count = 0
    for clause in _proposition_clauses(text):
        if not _has(obligation.subject, clause):
            continue
        if _REQUIREMENT_RELATION_RE.search(clause) is None:
            continue
        detail_count = _requirement_detail_count(clause)
        if detail_count >= 2:
            best_detail_count = max(best_detail_count, detail_count)

    if best_detail_count >= 2:
        return True, best_detail_count

    lines = [line for line in str(text or "").splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if not _has(obligation.subject, line):
            continue
        if _REQUIREMENT_RELATION_RE.search(line) is None:
            continue
        bullets: list[str] = []
        for following in lines[index + 1:]:
            if re.match(r"^\s*(?:[-*+]|\d+[.)])\s+", following) is None:
                break
            bullets.append(following)
        if len(bullets) < 2:
            continue
        detail_count = _requirement_detail_count("\n".join(bullets))
        if detail_count >= 2:
            return True, detail_count
    return False, 0


def relation_proof(
    obligation: ProofObligation,
    text: str,
    *,
    source: Mapping[str, object] | None = None,
) -> PlannedProof | None:
    """Validate relations introduced only by the compositional planner."""

    relation = str(obligation.relation or "")
    premise = premise_relation_proof(obligation, text, source=source)
    if premise is not None:
        return PlannedProof(*premise)
    if relation not in {
        "blocking_gates", "token_bounding", "per_tool_usage", "verification",
        "conditional_behavior", "release_line_limit", "storage_coordination",
        "conditional_library_removal", "requirements", "conditional_outcome",
        "blocking_conditions", "premise_check", "premise_cardinality",
        "public_tool_usage",
    }:
        return None
    normalized = _norm(text)
    source_text = _norm(" ".join(str((source or {}).get(key) or "") for key in (
        "path", "source", "title", "heading_path", "project_doc_path",
    )))

    if relation == "public_tool_usage":
        subject = _has(obligation.subject, text)
        context = bool(
            re.search(r"\b(?:docs\s+mcp|public\s+tools?|mcp\s+tools?)\b", normalized)
            or "docs mcp" in source_text
        )
        usage = bool(
            re.search(
                rf"(?:use\s+`?{re.escape(obligation.subject)}`?|"
                rf"`?{re.escape(obligation.subject)}`?\s+(?:for|when|to))",
                text,
                re.I,
            )
        )
        valid = subject and context and usage
        return PlannedProof(
            valid, 4 if valid else 0, 3 if valid else 0,
            "public_tool_usage" if valid else "public_tool_usage_missing",
            3 if valid else 0,
        )

    if relation == "conditional_outcome":
        context_tokens = {
            token for token in re.findall(r"[a-zа-яё0-9_-]{3,}", _norm(obligation.context))
            if token not in {"when", "while", "если", "когда", "пока", "the"}
        }
        best_context_hits = 0
        valid = False
        for clause in _proposition_clauses(text):
            clause_normalized = _norm(clause)
            context_hits = sum(token in clause_normalized for token in context_tokens)
            consequence = bool(re.search(
                r"\b(?:then|therefore|returns?|refuses?|blocks?|fails?|rebuilds?|"
                r"retries?|cannot|must|becomes?|stays?|remains?|"
                r"затем|поэтому|возвращает|отказывает|блокирует|становится|нельзя)\b",
                clause_normalized,
            ))
            local = (
                _has(obligation.subject, clause)
                and bool(context_tokens)
                and context_hits >= min(2, len(context_tokens))
                and consequence
            )
            if local:
                valid = True
                best_context_hits = max(best_context_hits, context_hits)
        return PlannedProof(
            valid, 4 if valid else 0, best_context_hits if valid else 0,
            "conditional_outcome" if valid else "conditional_outcome_missing",
            3 if valid else 0,
        )

    if relation == "blocking_conditions":
        valid = False
        for clause in _proposition_clauses(text):
            clause_normalized = _norm(clause)
            blocking = bool(re.search(
                r"\b(?:block(?:s|ed|ing)?|refus(?:e|es|ed)|cannot|must\s+not|"
                r"hard\s+blocker|блокир\w*|нельзя|отказ\w*)\b",
                clause_normalized,
            ))
            condition = bool(re.search(
                r"\b(?:when|while|if|unless|until|condition|only\s+when|"
                r"когда|если|пока|при\s+условии|до\s+тех\s+пор)\b",
                clause_normalized,
            ))
            if _has(obligation.subject, clause) and blocking and condition:
                valid = True
                break
        return PlannedProof(
            valid, 4 if valid else 0, 3 if valid else 0,
            "blocking_conditions" if valid else "blocking_conditions_missing",
            3 if valid else 0,
        )

    if relation == "premise_check":
        subject = _has(obligation.subject, text)
        target_tokens = {
            token for token in re.findall(r"[a-zа-яё0-9_-]{3,}", _norm(obligation.target))
            if token not in {"does", "always", "never", "всегда", "никогда"}
        }
        target_hits = sum(token in normalized for token in target_tokens)
        polarity = bool(re.search(
            r"\b(?:always|never|does\s+not|do\s+not|cannot|only|unless|"
            r"всегда|никогда|не\s+\w+|только)\b",
            normalized,
        ))
        valid = subject and bool(target_tokens) and target_hits >= min(2, len(target_tokens)) and polarity
        return PlannedProof(
            valid, 4 if valid else 0, target_hits if valid else 0,
            "premise_check" if valid else "premise_evidence_missing",
            3 if valid else 0,
        )

    if relation == "premise_cardinality":
        target_tokens = {
            token for token in re.findall(r"[a-zа-яё0-9_-]{3,}", _norm(obligation.target))
            if token not in {"there", "public"}
        }
        target_hits = sum(token in normalized for token in target_tokens)
        cardinality = bool(re.search(
            r"\b(?:exactly\s+)?(?:one|two|three|four|five|six|seven|eight|nine|ten|"
            r"\d{1,2}|один|одна|два|две|три|четыре|пять|шесть|семь|восемь|девять|десять)\b",
            normalized,
        ))
        context = bool(
            re.search(r"\b(?:public\s+docs\s+mcp\s+tools?|docs\s+mcp\s+public\s+tools?|mcp\s+tools?)\b", normalized)
            or "docs mcp" in source_text
        )
        valid = bool(target_tokens) and target_hits >= min(2, len(target_tokens)) and cardinality and context
        return PlannedProof(
            valid, 4 if valid else 0, target_hits if valid else 0,
            "premise_cardinality" if valid else "premise_cardinality_missing",
            2 if valid else 0,
        )

    if relation == "requirements":
        valid, detail_count = _structured_requirement_proof(obligation, text)
        return PlannedProof(
            valid, 4 if valid else 0, min(6, detail_count) if valid else 0,
            "requirements" if valid else "requirements_evidence_missing",
            3 if valid else 0,
        )

    if relation == "blocking_gates":
        valid = bool(
            re.search(r"\brelease\b", normalized)
            and re.search(r"\b(?:gate|gates|control|approval|authorization|stable|green|pass|block)\w*\b", normalized)
        )
        return PlannedProof(valid, 4 if valid else 0, 3 if valid else 0, "blocking_gates" if valid else "blocking_gates_missing")

    if relation == "token_bounding":
        valid = bool(
            re.search(r"\b(?:token|tokens|estimated tokens|ceiling|budget)\b", normalized)
            and re.search(r"\b(?:bounded|at most|maximum|max|ceiling|limit|target)\b", normalized)
            and (
                re.search(r"\b(?:projection|model visible|docs answer|patch context|insufficient evidence)\b", normalized)
                or "projection" in source_text
            )
        )
        return PlannedProof(valid, 4 if valid else 0, 3 if valid else 0, "token_bounding" if valid else "token_bounding_missing")

    if relation == "per_tool_usage":
        tools = ("get_docs_context", "prepare_docs", "docs_status")
        present = sum(_has(tool, text) for tool in tools)
        usage_shape = bool(
            re.search(r"\buse(?:s|d)?\b", normalized)
            and sum(
                bool(re.search(rf"(?:use\s+`?{re.escape(tool)}`?|`?{re.escape(tool)}`?\s+(?:for|when|to))", text, re.I))
                for tool in tools
            ) >= 2
        )
        valid = present == 3 and usage_shape
        return PlannedProof(
            valid, 4 if valid else 0, present,
            "per_tool_usage" if valid else "per_tool_usage_incomplete",
            2 if valid else 0,
        )

    if relation == "verification":
        context = _norm(obligation.context)
        cardinality = bool(re.search(r"\b(?:cardinality|exactly|count|cap|three|3)\b", normalized))
        artifacts = bool(re.search(r"\b(?:event|events|events jsonl|thread started|turn completed|artifact|manifest)\b", normalized))
        if "event" in context:
            valid = cardinality and artifacts
        else:
            valid = cardinality and bool(re.search(r"\b(?:verify|audit|check|confirm)\w*\b", normalized))
        exact_subject = _has(obligation.subject, text)
        provider_cardinality_subject = bool(
            "provider" in _norm(obligation.subject)
            and "cardinality" in _norm(obligation.subject)
            and re.search(r"\bprovider[- ]call(?:\s+(?:cap|count|cardinality))?\b|\bprovider_call_cap\b", normalized)
            and re.search(r"\b(?:cardinality|exactly|count|cap)\b", normalized)
        )
        subject_score = 3 if exact_subject else 2 if provider_cardinality_subject else 0
        valid = valid and subject_score > 0
        return PlannedProof(
            valid, 4 if valid else 0, 3 if valid else 0,
            "verification" if valid else "verification_evidence_missing",
            subject_score if valid else 0,
        )

    if relation == "conditional_behavior":
        context = _norm(obligation.context)
        live_condition = "live" in context and "process" in context
        live_evidence = bool(re.search(r"\b(?:live|running)\b", normalized) and re.search(r"\b(?:process|pid|mcp|qdrant|synchronization)\b", normalized))
        blocking = bool(re.search(r"\b(?:hard blocker|blocked|blocker|refuses?|rejects?|cannot|must stop)\b", normalized))
        valid = live_condition and live_evidence and blocking
        return PlannedProof(valid, 4 if valid else 0, 3 if valid else 0, "conditional_behavior" if valid else "conditional_behavior_missing")

    if relation == "release_line_limit":
        line_limit = bool(re.search(r"\b(?:1,?000|1000)\s+lines?\b", normalized))
        canonical_set = "canonical user-facing release set" in normalized
        members = sum(
            phrase in normalized
            for phrase in (
                "readme", "product brief", "docs mcp reference",
                "capability reference", "release checklist",
            )
        )
        valid = line_limit and canonical_set and members >= 3
        return PlannedProof(
            valid,
            4 if valid else 0,
            members if valid else 0,
            "release_line_limit" if valid else "release_line_limit_missing",
            3 if valid else 0,
        )

    if relation == "storage_coordination":
        subject_present = _has(obligation.subject, text)
        writer_lease = bool(re.search(r"\bwriter\s+lease\b", normalized))
        cleanup_barrier = bool(re.search(r"\bcleanup\s+barrier\b", normalized))
        refresh = bool(re.search(r"\b(?:library\s+refresh|project\s+sync|index\s+writer)\b", normalized))
        blocking = bool(re.search(r"\b(?:fail(?:s)?\s+closed|block(?:s|ed)?|refus(?:e|es))\b", normalized))
        valid = subject_present and writer_lease and cleanup_barrier and refresh and blocking
        return PlannedProof(
            valid,
            4 if valid else 0,
            4 if valid else 0,
            "storage_coordination" if valid else "storage_coordination_missing",
            3 if valid else 0,
        )

    if relation == "conditional_library_removal":
        subject = _has(obligation.subject, text)
        refresh = bool(re.search(r"\b(?:library\s+refresh|writer\s+lease|active\s+index\s+writer)\b", normalized))
        refusal = bool(re.search(r"\b(?:refus(?:e|es)|block(?:s|ed)?|fails?\s+closed|does\s+not\s+remove)\b", normalized))
        valid = subject and refresh and refusal
        return PlannedProof(
            valid,
            4 if valid else 0,
            3 if valid else 0,
            "conditional_library_removal" if valid else "conditional_library_removal_missing",
            3 if valid else 0,
        )

    return None


def usage_proof(
    obligation: ProofObligation,
    text: str,
    *,
    source: Mapping[str, object] | None = None,
) -> PlannedProof | None:
    """Validate v4 usage facets without broadening legacy usage semantics."""

    if obligation.kind != "usage" or obligation.subject_kind != "env_var":
        return None
    normalized = _norm(text)
    subject_present = _has(obligation.subject, text)
    usage_shape = bool(
        re.search(r"\bshould\s+be\s+used\s+when\b", normalized)
        or re.search(r"\buse\s+[^.]{0,80}\bwhen\b", normalized)
        or re.search(r"\bwhen\b[^.]{0,80}\buse(?:d)?\b", normalized)
    )
    valid = subject_present and usage_shape
    return PlannedProof(
        valid, 4 if valid else 0, 2 if valid else 0,
        "usage" if valid else "usage_evidence_missing",
        3 if valid else 0,
    )


def workflow_proof(
    obligation: ProofObligation,
    text: str,
    *,
    source: Mapping[str, object] | None = None,
) -> PlannedProof | None:
    relation = str(obligation.relation or "")
    if relation not in {"procedure", "configuration", "protocol_run"}:
        return None
    normalized = _norm(text)
    source_text = _norm(" ".join(str((source or {}).get(key) or "") for key in (
        "path", "source", "title", "heading_path", "project_doc_path",
    )))
    executable_step = bool(
        re.search(r"\b(?:pytest|python|uv\s+run|doc-atlas|prepare_docs)\b", text, re.I)
        or re.search(r"^\s*\d+[.)]\s+|^\s*[-*+]\s+", text, re.M)
    )
    if relation == "configuration":
        subject = _norm(obligation.subject)
        subject_present = subject in normalized or subject in source_text
        config_shape = bool(re.search(r"\b(?:config|configuration|yaml|project-local)\b", normalized))
        concrete_setting = bool(
            re.search(r"\b(?:index|query|vector_store|embeddings|retrieval)(?:\.[a-z_]+)?\s*[:=]", text, re.I)
            or re.search(r"\bdoc-atlas\s+(?:init|setup)\b", text, re.I)
        )
        valid = subject_present and config_shape and concrete_setting
        return PlannedProof(valid, 4 if valid else 0, 3 if valid else 0, "configuration_workflow" if valid else "configuration_workflow_missing")

    if relation == "protocol_run":
        command = bool(re.search(
            r"python\s+(?:(?:-m\s+eval\.)|(?:eval/))?project_answer_quality_v4_protocol(?:\.py)?\b",
            text,
            re.I,
        ))
        produces_report = "--output" in text
        validation_only = "--validate-protocol" in text and not produces_report
        source_matches = all(token in source_text for token in ("project", "answer", "quality", "v4"))
        valid = command and produces_report and not validation_only and source_matches
        return PlannedProof(
            valid,
            4 if valid else 0,
            4 if valid else 0,
            "protocol_run" if valid else "protocol_run_command_missing",
            3 if valid else 0,
        )

    # Procedure proof requires a named topic plus either an executable/checkable
    # step or a locally bound multi-stage summary.  The latter prevents a
    # single command from masquerading as the complete answer to a named
    # multi-step procedure such as the Task 33 two-cell smoke.
    subject_tokens = [token for token in re.findall(r"[a-z0-9]+", _norm(obligation.subject)) if len(token) > 2]
    combined = f"{normalized} {source_text}"
    overlap = sum(token in combined for token in set(subject_tokens))
    required_overlap = 1 if len(set(subject_tokens)) <= 2 else 2
    subject_local = _has(obligation.subject, text)
    stage_count = len(re.findall(
        r"\b(?:run|preflight|canary|cell|retry|audit|verify|compare|report)\w*\b",
        normalized,
    ))
    summary_shape = subject_local and stage_count >= 4
    valid = overlap >= required_overlap and (executable_step or summary_shape)
    value = overlap + (4 if summary_shape else 1 if executable_step else 0)
    return PlannedProof(
        valid, 4 if valid else 0, value if valid else 0,
        "procedure" if valid else "procedure_missing",
        3 if subject_local and valid else 0,
    )


def behavior_proof(
    obligation: ProofObligation,
    text: str,
    *,
    source: Mapping[str, object] | None = None,
) -> PlannedProof | None:
    relation = str(obligation.relation or "")
    if relation not in {"chunking", "selection_policy"}:
        return None
    normalized = _norm(text)

    if relation == "selection_policy":
        subject_present = _has(obligation.subject, text)
        candidate_shape = bool(re.search(r"\b(?:candidate|candidates|evidence|witness|proof)\b", normalized))
        selection_shape = bool(re.search(
            r"\b(?:choose|chooses|chosen|select|selects|selected|rank|ranks|ranked|require|requires|requiring|outrank|outranks)\b",
            normalized,
        ))
        proof_shape = bool(re.search(r"\b(?:proof|mandatory|facet|subject|relation|value|complete|exact)\b", normalized))
        valid = subject_present and candidate_shape and selection_shape and proof_shape
        return PlannedProof(
            valid, 4 if valid else 0, 4 if valid else 0,
            "selection_policy" if valid else "selection_policy_missing",
            3 if valid else 0,
        )

    # A chunking answer must describe both semantic parent sections and child
    # chunks.  Merely mentioning an index over heading-normalized sections is
    # not enough to answer how documents are split.
    subject_present = _has(obligation.subject, text)
    has_sections = bool(re.search(r"\b(?:section|sections|parent section|parent sections)\b", normalized))
    has_chunks = bool(re.search(r"\b(?:chunk|chunks|child chunk|child chunks)\b", normalized))
    mechanism = bool(re.search(
        r"\b(?:split(?:s|ting)?|normaliz(?:e|es|ed|ing)|group(?:s|ed|ing)?|parent[- ]child|token[- ]bounded|target tokens|hard max)\b",
        normalized,
    ))
    valid = subject_present and has_sections and has_chunks and mechanism
    return PlannedProof(
        valid, 4 if valid else 0, 4 if valid else 0,
        "chunking" if valid else "chunking_missing",
        3 if valid else 0,
    )


__all__ = [
    "PlannedProof", "behavior_proof", "relation_proof", "usage_proof",
    "workflow_proof",
]
