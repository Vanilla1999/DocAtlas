"""Bounded, polarity-aware parsing for explicit patch requests."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Literal

from docmancer.retrieval.contracts import canonical_hash


PATCH_REQUEST_PLAN_SCHEMA = "patch-request-plan-v1"
MAX_PATCH_TARGETS = 12
MAX_PATCH_CLAUSES = 12

PatchOperation = Literal["modify", "create", "delete", "rename", "none"]
PatchLanguage = Literal["en", "ru"]

_ROOT_ACTION = re.compile(
    r"^\s*(?P<verb>fix|update|modify|change|patch|implement|refactor|create|add|delete|remove|rename|"
    r"исправ(?:ить|ь)|обнов(?:ить|и)|измен(?:ить|и)|реализова(?:ть|ть)|рефактор(?:ить)?|"
    r"созда(?:ть|й)|добав(?:ить|ь)|удал(?:ить|и)|переименова(?:ть|й))\b",
    re.I,
)
_PRESERVE_HEAD = re.compile(
    r"\b(?:without\s+(?:changing|modifying|editing|touching)|but\s+do\s+not\s+(?:change|modify|edit|touch)|"
    r"do\s+not\s+(?:change|modify|edit|touch)|без\s+изменения|не\s+(?:изменяй|редактируй|трогай))\b",
    re.I,
)
_ACCEPTANCE_HEAD = re.compile(r"\b(?:so\s+that|must|should|чтобы|долж(?:ен|на|но|ны))\b", re.I)
_PATH_RE = re.compile(
    r"(?<![\w/])(?:\.?\.?/)?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\."
    r"(?:py|dart|js|jsx|ts|tsx|go|rs|java|kt|swift|c|cc|cpp|h|hpp|md|mdx|rst|txt|adoc|toml|yaml|yml|json|ini|cfg|xml)(?![\w/])",
    re.I,
)
_SYMBOL_RE = re.compile(
    r"`([^`\n]{2,160})`"
    r"|\b([A-Za-z_][A-Za-z0-9_]*(?:(?:::|\.)[A-Za-z_][A-Za-z0-9_]*)+)\b"
    r"|\b([A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+)\b"
    r"|\b([A-Z][A-Za-z0-9]*(?:[A-Z][A-Za-z0-9]*)+)\b"
)


@dataclass(frozen=True, slots=True)
class PatchTarget:
    value: str
    kind: Literal["path", "symbol"]
    query_span_start: int
    query_span_end: int
    polarity: Literal["mutate", "preserve"]


@dataclass(frozen=True, slots=True)
class PatchRequestPlan:
    operation: PatchOperation
    mutation_targets: tuple[PatchTarget, ...]
    preserve_targets: tuple[PatchTarget, ...] = ()
    scope_terms: tuple[str, ...] = ()
    behavioral_requirements: tuple[str, ...] = ()
    acceptance_conditions: tuple[str, ...] = ()
    unresolved_parts: tuple[str, ...] = ()
    language: PatchLanguage = "en"
    surface_id: str = "unsupported"
    schema_version: str = PATCH_REQUEST_PLAN_SCHEMA

    def __post_init__(self) -> None:
        if len(self.mutation_targets) > MAX_PATCH_TARGETS or len(self.preserve_targets) > MAX_PATCH_TARGETS:
            raise ValueError("patch request target plan exceeds bounds")
        if any(len(values) > MAX_PATCH_CLAUSES for values in (
            self.scope_terms, self.behavioral_requirements,
            self.acceptance_conditions, self.unresolved_parts,
        )):
            raise ValueError("patch request clause plan exceeds bounds")
        mutate = {item.value.casefold() for item in self.mutation_targets}
        preserve = {item.value.casefold() for item in self.preserve_targets}
        if mutate & preserve:
            raise ValueError("patch target cannot be both mutable and preserved")

    @property
    def hash_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "operation": self.operation,
            "mutation_targets": [asdict(item) for item in self.mutation_targets],
            "preserve_targets": [asdict(item) for item in self.preserve_targets],
            "scope_terms": list(self.scope_terms),
            "behavioral_requirements": list(self.behavioral_requirements),
            "acceptance_conditions": list(self.acceptance_conditions),
            "unresolved_parts": list(self.unresolved_parts),
            "language": self.language,
            "surface_id": self.surface_id,
        }

    @property
    def plan_hash(self) -> str:
        return canonical_hash(self.hash_payload)


def _operation(verb: str) -> PatchOperation:
    value = verb.casefold()
    if re.fullmatch(r"create|add|созда(?:ть|й)|добав(?:ить|ь)", value):
        return "create"
    if re.fullmatch(r"delete|remove|удал(?:ить|и)", value):
        return "delete"
    if re.fullmatch(r"rename|переименова(?:ть|й)", value):
        return "rename"
    return "modify"


def _targets(raw: str, preserve_start: int | None) -> tuple[tuple[PatchTarget, ...], tuple[PatchTarget, ...]]:
    found: list[PatchTarget] = []
    path_spans: list[tuple[int, int]] = []
    for match in _PATH_RE.finditer(raw):
        path_spans.append((match.start(), match.end()))
        polarity = "preserve" if preserve_start is not None and match.start() >= preserve_start else "mutate"
        found.append(PatchTarget(match.group(0).removeprefix("./"), "path", match.start(), match.end(), polarity))
    for match in _SYMBOL_RE.finditer(raw):
        if any(start < match.end() and match.start() < end for start, end in path_spans):
            continue
        value = next((group for group in match.groups() if group), "")
        if not value or (match.group(1) is None and value.isupper() and not re.search(r"[_:.]", value)):
            continue
        polarity = "preserve" if preserve_start is not None and match.start() >= preserve_start else "mutate"
        found.append(PatchTarget(value[:240], "symbol", match.start(), match.end(), polarity))
    unique: dict[tuple[str, str], PatchTarget] = {}
    for target in found:
        unique.setdefault((target.polarity, target.value.casefold()), target)
    mutate = tuple(item for item in unique.values() if item.polarity == "mutate")[:MAX_PATCH_TARGETS]
    preserve = tuple(item for item in unique.values() if item.polarity == "preserve")[:MAX_PATCH_TARGETS]
    return mutate, preserve


def build_patch_request_plan(question: str) -> PatchRequestPlan:
    raw = str(question or "")[:4_000]
    language: PatchLanguage = "ru" if re.search(r"[А-Яа-яЁё]", raw) else "en"
    root = _ROOT_ACTION.match(raw)
    if root is None:
        return PatchRequestPlan(
            operation="none", mutation_targets=(), language=language,
            unresolved_parts=("unsupported_patch_surface",),
        )
    preserve = _PRESERVE_HEAD.search(raw)
    mutate_targets, preserve_targets = _targets(raw, preserve.end() if preserve else None)
    acceptance = tuple(
        dict.fromkeys(
            " ".join(raw[match.start():].split())[:500]
            for match in _ACCEPTANCE_HEAD.finditer(raw[:preserve.start() if preserve else len(raw)])
        )
    )[:MAX_PATCH_CLAUSES]
    unresolved: list[str] = []
    if not mutate_targets:
        unresolved.append("mutation_target_not_requested")
    if preserve is not None and not preserve_targets:
        unresolved.append("preserve_target_not_resolved")
    operation = _operation(root.group("verb"))
    surface = f"imperative:{operation}:{language}"
    if preserve is not None:
        surface += ":preserve"
    objective_end = preserve.start() if preserve else len(raw)
    objective = " ".join(raw[root.end():objective_end].split()).strip(" .;,")
    return PatchRequestPlan(
        operation=operation,
        mutation_targets=mutate_targets,
        preserve_targets=preserve_targets,
        behavioral_requirements=(objective[:500],) if objective else (),
        acceptance_conditions=acceptance,
        unresolved_parts=tuple(unresolved),
        language=language,
        surface_id=surface,
    )


__all__ = [
    "PATCH_REQUEST_PLAN_SCHEMA", "PatchRequestPlan", "PatchTarget",
    "build_patch_request_plan",
]
