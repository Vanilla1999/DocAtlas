"""Strict value-bearing proof for project governance QuestionPlan facets.

Governance questions are unusually vulnerable to topical/navigation prose:
"the policy is documented in X" mentions the right nouns but does not expose
an owner, state, requirement, or version. This module is the P0 semantic gate
between QuestionPlan and the generic relation prover. Non-governance
relations retain their existing implementation unchanged.
"""
from __future__ import annotations

import re
from typing import Mapping, Pattern

from docmancer.docs.domain.project_answer_contract import ProofObligation
from docmancer.docs.domain.question_plan_proof import (
    PlannedProof,
    relation_proof as _legacy_relation_proof,
)

_GOVERNANCE_RELATIONS = frozenset({
    "governed_scope",
    "governance_facet",
    "governance_ownership",
    "governance_requirement",
    "governance_state",
    "governance_version",
})
_CANONICAL_AUTHORITIES = frozenset({
    "canonical", "source_of_truth", "official", "primary",
    "project_owned", "project_rule",
})
_STOP_WORDS = frozenset({
    "a", "an", "and", "are", "for", "in", "is", "of", "on", "the", "this",
    "и", "в", "на", "для", "это",
})
_NAVIGATION_META_RE = re.compile(
    r"\b(?:documented|described|explained|recorded|listed|covered|located|found)\s+"
    r"(?:in|at|under|by)\b|\b(?:see|refer\s+to|consult)\b",
    re.I,
)
_PLACEHOLDER_VALUE_RE = re.compile(
    r"^\s*(?:unknown|unspecified|undefined|unclear|tbd|todo|none|n/?a|"
    r"not\s+(?:specified|defined|decided)|неизвест\w*|не\s+определ\w*)\b",
    re.I,
)
_VERSION_VALUE = r"v?\d+(?:\.\d+){1,3}(?:[-+][0-9A-Za-z.-]+)?"
_OWNER_RE = re.compile(
    r"\b(?:owns?|owned\s+by|owner\s+(?:is|=|:)|belongs?\s+to|"
    r"responsible\s+for|владе\w*|принадлеж\w*)\b",
    re.I,
)
_REQUIREMENT_RE = re.compile(
    r"\b(?:requires?|required|must|needs?|need\s+to|"
    r"requests?|requested|треб\w*|необходим\w*|запраш\w*)\b",
    re.I,
)
_DEFERRED_STATE_RE = re.compile(
    r"\b(?:remains?|stays?|is|are)\s+(?:explicitly\s+)?deferred\b"
    r"|\b(?:does|do|must|should)\s+not\s+(?:request|include|preflight)\b"
    r"|\b(?:остае\w*|явля\w*)\s+отлож\w*\b",
    re.I,
)
# governed_scope means the requested surfaces actually share one policy. A bare
# "governed by" or "applies to" is not enough because it can describe separate
# policies and still contain every topic word.
_SCOPE_RELATION_RE = re.compile(
    r"\b(?:"
    r"use[sd]?\s+(?:the\s+)?same|"
    r"share[sd]?\s+(?:(?:a|the|one|same|common|shared)\s+)?(?:\w+\s+){0,3}policy|"
    r"govern(?:s|ed)?\s+by\s+(?:the\s+)?same|"
    r"(?:same|one|common|shared)\s+(?:\w+\s+){0,3}policy|"
    r"еди\w*\s+политик\w*"
    r")\b",
    re.I,
)
_GENERIC_VALUE_RE = re.compile(
    r"\b(?:owns?|requires?|must|remains?|deferred|uses?|applies?|governs?|"
    r"controls?|sets?|pins?|владе\w*|треб\w*|отлож\w*|примен\w*)\b",
    re.I,
)
_ANDROID_13_RE = re.compile(r"\bandroid\s*13(?:\+|\s*plus)?\b", re.I)


def _norm(value: object) -> str:
    return " ".join(str(value or "").casefold().replace("_", " ").split())


def _tokens(value: object) -> set[str]:
    tokens: set[str] = set()
    for raw in re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", _norm(value)):
        if raw in _STOP_WORDS or len(raw) < 2:
            continue
        token = raw
        if raw in {"own", "owns", "owned", "owner", "ownership"}:
            token = "own"
        elif raw.startswith("defer"):
            token = "defer"
        elif raw.startswith("pin"):
            token = "pin"
        elif raw.endswith("s") and len(raw) > 4:
            token = raw[:-1]
        tokens.add(token)
    return tokens


def _subject_match(subject: object, clause: str) -> tuple[bool, int]:
    expected = _tokens(subject)
    actual = _tokens(clause)
    hits = len(expected & actual)
    required = max(2, min(4, (len(expected) + 1) // 2))
    return bool(expected) and hits >= required, hits


def _ordered_subject_pattern(subject: object, *, drop: frozenset[str] = frozenset()) -> str:
    words: list[str] = []
    for raw in re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", _norm(subject)):
        if raw in _STOP_WORDS or len(raw) < 2:
            continue
        canonical = "pin" if raw.startswith("pin") else raw
        if canonical in drop:
            continue
        words.append(re.escape(raw))
    if not words:
        return ""
    return r"[\s_.:/-]+".join(words)


def _canonical_source(source: Mapping[str, object] | None) -> bool:
    if not source:
        return False
    authority = str(
        source.get("project_doc_authority")
        or source.get("authority")
        or ""
    ).casefold()
    return authority in _CANONICAL_AUTHORITIES


def _clauses(text: str) -> tuple[str, ...]:
    source = str(text or "")
    if not source:
        return ()
    rows: list[str] = []
    start = 0
    for boundary in re.finditer(r"(?:[.!?](?=\s|$)|;|\n)", source):
        end = boundary.end()
        clause = source[start:end].strip()
        if clause:
            rows.append(clause)
        start = end
    tail = source[start:].strip()
    if tail:
        rows.append(tail)
    return tuple(rows)


def _predicate_is_negated(match: re.Match[str], clause: str) -> bool:
    """Mirror the existing answer-unit local polarity rule."""

    prefix = clause[max(0, match.start() - 48):match.start()]
    return bool(re.search(
        r"\b(?:not|never|no|cannot|can't|does\s+not|do\s+not|did\s+not|"
        r"must\s+not|should\s+not|will\s+not|не|никогда\s+не|нельзя)\s+"
        r"(?:\w+\s+){0,2}$",
        prefix,
        re.I,
    ))


def _tail_has_value(match: re.Match[str], clause: str, *, max_chars: int = 96) -> bool:
    """Require a non-placeholder complement after a generic governance predicate."""

    tail = clause[match.end():match.end() + max_chars].strip(" \t,:=-")
    if not tail or _PLACEHOLDER_VALUE_RE.search(tail):
        return False
    words = [
        word.casefold()
        for word in re.findall(r"[A-Za-zА-Яа-яЁё0-9_.:/+-]+", tail)
        if word.casefold() not in {"to", "by", "for", "as", "with", "и", "для"}
    ]
    return bool(words)


def _relation_value_is_bound(
    obligation: ProofObligation,
    clause: str,
    pattern: Pattern[str],
    *,
    relation_tokens: frozenset[str],
    radius: int = 48,
    require_tail_value: bool = False,
) -> bool:
    """Require one non-negated relation predicate near its requested target."""

    target_tokens = _tokens(obligation.subject) - relation_tokens
    if not target_tokens:
        return False
    required = min(3, len(target_tokens))
    for match in pattern.finditer(clause):
        if _predicate_is_negated(match, clause):
            continue
        window = clause[
            max(0, match.start() - radius):
            min(len(clause), match.end() + radius)
        ]
        if len(target_tokens & _tokens(window)) < required:
            continue
        if require_tail_value and not _tail_has_value(match, clause):
            continue
        return True
    return False


def _ownership_value_is_bound(obligation: ProofObligation, clause: str) -> bool:
    """Require both the ownership target and a concrete local owner value."""

    target_tokens = _tokens(obligation.subject) - {"own"}
    for match in _OWNER_RE.finditer(clause):
        if _predicate_is_negated(match, clause):
            continue
        window = clause[max(0, match.start() - 48):min(len(clause), match.end() + 64)]
        if not target_tokens or not (target_tokens & _tokens(window)):
            continue
        relation = _norm(match.group(0))
        if relation.startswith(("owner ", "owned by", "belongs to", "принадлеж")):
            value = clause[match.end():match.end() + 64].strip(" \t,:=-")
            if value and not _PLACEHOLDER_VALUE_RE.search(value):
                return True
            continue
        # Active ownership forms put the owner immediately before the predicate.
        prefix = clause[max(0, match.start() - 64):match.start()].strip(" \t,:=-")
        prefix_tokens = _tokens(prefix) - target_tokens - {"own"}
        if prefix_tokens and not _PLACEHOLDER_VALUE_RE.search(prefix):
            return True
    return False


def _version_value_is_bound(obligation: ProofObligation, clause: str) -> bool:
    """Require the version value to bind to the requested dependency identity.

    Merely placing another version-like number in the same sentence is not
    enough. This blocks, for example, Android 13.0 from satisfying the requested
    permission_handler version facet.
    """

    identity = _ordered_subject_pattern(
        obligation.subject,
        drop=frozenset({"version", "pin"}),
    )
    if not identity:
        return False
    value = _VERSION_VALUE
    patterns = (
        rf"\b{identity}\b\s+(?:(?:current|resolved|locked|pinned)\s+)?version\b"
        rf"(?:\s+(?:in|from)\s+\S+)?\s*(?:is|=|:|at|to|resolves?\s+to|resolved\s+to)?\s*{value}(?!\w)",
        rf"\b{identity}\b\s+(?:is\s+)?pin(?:ned|s)?\b\s*(?:to|at|=|:)?\s*{value}(?!\w)",
        rf"\b(?:version|pin(?:ned|s)?)\b\s+(?:of|for)\s+{identity}\b"
        rf"\s*(?:is|=|:|at|to)?\s*{value}(?!\w)",
        rf"\b{identity}\b\s*[:=]\s*{value}(?!\w)",
    )
    return any(re.search(pattern, clause, re.I) for pattern in patterns)


def _android_requirement_is_bound(obligation: ProofObligation, clause: str) -> bool:
    """Preserve both direction and polarity of an Android-13 requirement."""

    context = _norm(obligation.context)
    subject_pattern = _ordered_subject_pattern(obligation.subject)
    if not subject_pattern:
        return False
    subject_matches = tuple(re.finditer(rf"\b{subject_pattern}\b", clause, re.I))
    if not subject_matches:
        return False

    requirement_matches = tuple(
        match for match in _REQUIREMENT_RE.finditer(clause)
        if not _predicate_is_negated(match, clause)
    )
    if "android 13" not in context:
        return any(
            abs(match.start() - subject.start()) <= 80
            and _tail_has_value(match, clause)
            for match in requirement_matches
            for subject in subject_matches
        )

    android_matches = tuple(_ANDROID_13_RE.finditer(clause))
    for requirement in requirement_matches:
        word = _norm(requirement.group(0))
        for android in android_matches:
            for subject in subject_matches:
                # Active platform rule: Android 13 requires/needs/requests X.
                if (
                    word in {"require", "requires", "need", "needs", "request", "requests"}
                    and android.end() <= requirement.start() <= subject.start()
                    and requirement.start() - android.end() <= 80
                    and subject.start() - requirement.end() <= 80
                    and not re.search(r"\b(?:no|not)\b", clause[requirement.end():subject.start()], re.I)
                ):
                    return True
                # Passive/modal rule: X is required / must be requested on Android 13.
                if (
                    (word == "required" or word == "must" or word == "requested")
                    and subject.end() <= requirement.start() <= android.start()
                    and requirement.start() - subject.end() <= 80
                    and android.start() - requirement.end() <= 80
                ):
                    return True
                # Android 13 X is required is also a valid platform-scoped proposition.
                if (
                    word == "required"
                    and android.end() <= subject.start() <= requirement.start()
                    and subject.start() - android.end() <= 80
                    and requirement.start() - subject.end() <= 80
                ):
                    return True
    return False


def _scope_proof(obligation: ProofObligation, clause: str) -> tuple[bool, int]:
    subject, hits = _subject_match(obligation.subject, clause)
    if not subject or _NAVIGATION_META_RE.search(clause):
        return False, hits
    return _relation_value_is_bound(
        obligation,
        clause,
        _SCOPE_RELATION_RE,
        relation_tokens=frozenset({"same", "share", "use", "govern", "policy"}),
    ), hits


def _ownership_proof(obligation: ProofObligation, clause: str) -> tuple[bool, int]:
    subject, hits = _subject_match(obligation.subject, clause)
    if not subject or _NAVIGATION_META_RE.search(clause):
        return False, hits
    return _ownership_value_is_bound(obligation, clause), hits


def _version_proof(obligation: ProofObligation, clause: str) -> tuple[bool, int]:
    subject, hits = _subject_match(obligation.subject, clause)
    if not subject:
        return False, hits
    return _version_value_is_bound(obligation, clause), hits


def _state_proof(obligation: ProofObligation, clause: str) -> tuple[bool, int]:
    subject, hits = _subject_match(obligation.subject, clause)
    if not subject or _NAVIGATION_META_RE.search(clause):
        return False, hits
    return _relation_value_is_bound(
        obligation,
        clause,
        _DEFERRED_STATE_RE,
        relation_tokens=frozenset({"defer", "remain", "stay", "request", "include", "preflight"}),
    ), hits


def _requirement_proof(obligation: ProofObligation, clause: str) -> tuple[bool, int]:
    subject, hits = _subject_match(obligation.subject, clause)
    if not subject:
        return False, hits
    return bool(
        _android_requirement_is_bound(obligation, clause)
        and not _NAVIGATION_META_RE.search(clause)
    ), hits


def _generic_governance_proof(obligation: ProofObligation, clause: str) -> tuple[bool, int]:
    subject, hits = _subject_match(obligation.subject, clause)
    if not subject or _NAVIGATION_META_RE.search(clause):
        return False, hits
    return _relation_value_is_bound(
        obligation,
        clause,
        _GENERIC_VALUE_RE,
        relation_tokens=frozenset({
            "own", "require", "must", "remain", "defer", "use", "apply",
            "govern", "control", "set", "pin",
        }),
        require_tail_value=True,
    ), hits


def relation_proof(
    obligation: ProofObligation,
    text: str,
    *,
    source: Mapping[str, object] | None = None,
) -> PlannedProof | None:
    """Use strict substantive-value proof for governance; delegate everything else."""

    relation = str(obligation.relation or "")
    if relation not in _GOVERNANCE_RELATIONS:
        return _legacy_relation_proof(obligation, text, source=source)

    # Governance is project policy. Supporting summaries may guide retrieval,
    # but only canonical/source-of-truth evidence can authorize the answer.
    if not _canonical_source(source):
        return PlannedProof(False, reason="governance_authority_missing")

    prover = {
        "governed_scope": _scope_proof,
        "governance_ownership": _ownership_proof,
        "governance_version": _version_proof,
        "governance_state": _state_proof,
        "governance_requirement": _requirement_proof,
        "governance_facet": _generic_governance_proof,
    }[relation]

    for clause in _clauses(text):
        valid, hits = prover(obligation, clause)
        if valid:
            return PlannedProof(
                True,
                relation_score=4,
                value_score=max(3, hits),
                reason=relation,
                subject_score=3,
            )
    return PlannedProof(
        False,
        reason=f"{relation}_substantive_value_missing",
        value_score=0,
        subject_score=0,
    )


__all__ = ["relation_proof"]
