"""Bounded, polarity-aware grammar for explicit patch requests."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Literal

from docmancer.retrieval.contracts import canonical_hash


PATCH_REQUEST_PLAN_SCHEMA = "patch-request-plan-v2"
MAX_PATCH_TARGETS = 12
MAX_PATCH_CLAUSES = 12
MAX_PATCH_FIELD_LENGTH = 500

PatchOperation = Literal["modify", "create", "delete", "rename", "none"]
PatchLanguage = Literal["en", "ru"]
PatchTargetRole = Literal["mutate", "preserve", "destination", "parent"]

_ROOT_ACTION = re.compile(
    r"^\s*(?:(?P<wrapper>please)\s+)?(?P<verb>"
    r"fix|update|modify|change|patch|implement|refactor|make|create|add|delete|remove|rename|"
    r"исправ(?:ить|ь)|обнов(?:ить|и)|измен(?:ить|и)|реализова(?:ть|ть)|"
    r"(?:от)?рефактор(?:ить|и)?|"
    r"созда(?:ть|й)|добав(?:ить|ь)|удал(?:ить|и)|переименова(?:ть|й))\b",
    re.I,
)
_PRESERVE_HEAD = re.compile(
    r"\b(?:without\s+(?:changing|modifying|editing|touching)|"
    r"but\s+do\s+not\s+(?:change|modify|edit|touch)|"
    r"do\s+not\s+(?:change|modify|edit|touch)|"
    r"без\s+изменения|не\s+(?:изменяй|редактируй|трогай))\b",
    re.I,
)
_ACCEPTANCE_HEAD = re.compile(r"\b(?:so\s+that|чтобы)\b", re.I)
_BEHAVIOR_TARGET_HEAD = re.compile(r"\s+(?:in|across|в)\s+", re.I)
_TARGET_BEHAVIOR_HEAD = re.compile(r"\s+for\s+", re.I)
_RENAME_HEAD = re.compile(r"\s+to\s+", re.I)
_CREATE_PARENT_HEAD = re.compile(r"\s+in\s+", re.I)
_PATH_PATTERN = (
    r"(?:\.?\.?/)?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\."
    r"(?:py|dart|js|jsx|ts|tsx|go|rs|java|kt|swift|c|cc|cpp|h|hpp|md|mdx|rst|txt|adoc|toml|yaml|yml|json|ini|cfg|xml)"
)
_QUALIFIED_PATTERN = r"[A-Za-z_][A-Za-z0-9_]*(?:(?:::|\.)[A-Za-z_][A-Za-z0-9_]*)+"
_SNAKE_PATTERN = r"[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+"
_CAMEL_PATTERN = r"[A-Z][A-Za-z0-9]*(?:[A-Z][A-Za-z0-9]*)+"
_QUOTED_PATTERN = r"`[^`\n]{2,160}`"
_TARGET_RE = re.compile(
    rf"(?P<path>{_PATH_PATTERN})|(?P<qualified>{_QUALIFIED_PATTERN})|"
    rf"(?P<snake>{_SNAKE_PATTERN})|(?P<camel>{_CAMEL_PATTERN})|(?P<quoted>{_QUOTED_PATTERN})"
)
_LIST_SEPARATOR_RE = re.compile(
    r"\s*(?:,\s*(?:(?:and|и)\s+)?|\s+(?:and|и)\s+)\s*", re.I,
)
_TRAILING_PUNCTUATION_RE = re.compile(r"[\s.,;:!?]*$")


@dataclass(frozen=True, slots=True)
class PatchClause:
    kind: Literal[
        "operation", "behavior", "mutation_targets", "preserve_targets",
        "acceptance", "scope",
    ]
    text: str
    query_span_start: int
    query_span_end: int


@dataclass(frozen=True, slots=True)
class PatchTarget:
    value: str
    kind: Literal["path", "symbol"]
    query_span_start: int
    query_span_end: int
    polarity: Literal["mutate", "preserve"]
    role: PatchTargetRole = "mutate"
    provenance: Literal["user_request", "explicit_task_contract"] = "user_request"


@dataclass(frozen=True, slots=True)
class PatchRequestPlan:
    operation: PatchOperation
    mutation_targets: tuple[PatchTarget, ...]
    preserve_targets: tuple[PatchTarget, ...] = ()
    destination: PatchTarget | None = None
    parent_context: PatchTarget | None = None
    scope_terms: tuple[str, ...] = ()
    behavioral_requirements: tuple[PatchClause, ...] = ()
    acceptance_conditions: tuple[PatchClause, ...] = ()
    consumed_spans: tuple[tuple[int, int], ...] = ()
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

    @property
    def hash_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "operation": self.operation,
            "mutation_targets": [asdict(item) for item in self.mutation_targets],
            "preserve_targets": [asdict(item) for item in self.preserve_targets],
            "destination": asdict(self.destination) if self.destination is not None else None,
            "parent_context": asdict(self.parent_context) if self.parent_context is not None else None,
            "scope_terms": list(self.scope_terms),
            "behavioral_requirements": [asdict(item) for item in self.behavioral_requirements],
            "acceptance_conditions": [asdict(item) for item in self.acceptance_conditions],
            "consumed_spans": [list(item) for item in self.consumed_spans],
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


def _target_list(
    raw: str,
    *,
    start: int,
    end: int,
    role: PatchTargetRole,
) -> tuple[tuple[PatchTarget, ...], str | None]:
    text = raw[start:end]
    content_end = _TRAILING_PUNCTUATION_RE.search(text)
    bounded_end = content_end.start() if content_end is not None else len(text)
    text = text[:bounded_end]
    if not text.strip():
        return (), "target_list_empty"
    targets: list[PatchTarget] = []
    cursor = 0
    for match in _TARGET_RE.finditer(text):
        gap = text[cursor:match.start()]
        if cursor == 0:
            if gap.strip():
                return (), f"unresolved_patch_clause:{text.strip()[:160]}"
        elif _LIST_SEPARATOR_RE.fullmatch(gap) is None:
            return tuple(targets), f"unresolved_patch_clause:{text[cursor:].strip()[:160]}"
        token = match.group(0)
        value = token[1:-1] if match.group("quoted") else token.removeprefix("./")
        kind: Literal["path", "symbol"] = "path" if match.group("path") else "symbol"
        polarity: Literal["mutate", "preserve"] = "preserve" if role == "preserve" else "mutate"
        targets.append(PatchTarget(
            value=value,
            kind=kind,
            query_span_start=start + match.start(),
            query_span_end=start + match.end(),
            polarity=polarity,
            role=role,
        ))
        cursor = match.end()
    if not targets:
        return (), f"unresolved_patch_clause:{text.strip()[:160]}"
    if text[cursor:].strip():
        return tuple(targets), f"unresolved_patch_clause:{text[cursor:].strip()[:160]}"
    unique: dict[str, PatchTarget] = {}
    for target in targets:
        unique.setdefault(target.value.casefold(), target)
    if len(unique) > MAX_PATCH_TARGETS:
        return (), "input_limit:mutation_targets" if role != "preserve" else "input_limit:preserve_targets"
    return tuple(unique.values()), None


def _clause(kind: PatchClause.__annotations__["kind"], raw: str, start: int, end: int) -> PatchClause:
    text = " ".join(raw[start:end].split()).strip(" .;,:")
    return PatchClause(kind, text[:MAX_PATCH_FIELD_LENGTH], start, end)


def _unsupported(raw: str, language: PatchLanguage, reason: str) -> PatchRequestPlan:
    unresolved = (reason,)
    if reason == "unsupported_patch_surface:ru":
        unresolved = (reason, "mutation_target_not_requested")
    return PatchRequestPlan(
        operation="none",
        mutation_targets=(),
        language=language,
        unresolved_parts=unresolved,
    )


def build_patch_request_plan(question: str) -> PatchRequestPlan:
    source = str(question or "")
    raw = source[:4_000]
    language: PatchLanguage = "ru" if re.search(r"[А-Яа-яЁё]", raw) else "en"
    if len(source) > len(raw):
        return _unsupported(raw, language, "input_limit:question")
    root = _ROOT_ACTION.match(raw)
    if root is None:
        return _unsupported(raw, language, "unsupported_patch_surface")
    operation = _operation(root.group("verb"))
    preserve_match = _PRESERVE_HEAD.search(raw, root.end())
    main_end = preserve_match.start() if preserve_match else len(raw)
    acceptance_match = _ACCEPTANCE_HEAD.search(raw, root.end(), main_end)
    target_region_end = acceptance_match.start() if acceptance_match else main_end
    body_start = root.end()
    while body_start < target_region_end and raw[body_start].isspace():
        body_start += 1
    unresolved: list[str] = []
    consumed: list[tuple[int, int]] = [(root.start(), root.end())]
    behavior: list[PatchClause] = []
    acceptance: list[PatchClause] = []
    mutation_targets: tuple[PatchTarget, ...] = ()
    preserve_targets: tuple[PatchTarget, ...] = ()
    destination: PatchTarget | None = None
    parent_context: PatchTarget | None = None
    surface = f"imperative:{operation}:{language}"

    if operation == "rename":
        separator = _RENAME_HEAD.search(raw, body_start, target_region_end)
        if separator is None:
            unresolved.append("rename_destination_not_requested")
        else:
            sources, error = _target_list(raw, start=body_start, end=separator.start(), role="mutate")
            destinations, destination_error = _target_list(raw, start=separator.end(), end=target_region_end, role="destination")
            if error:
                unresolved.append(error)
            if destination_error:
                unresolved.append(destination_error)
            mutation_targets = sources
            destination = destinations[0] if len(destinations) == 1 else None
            if len(destinations) != 1:
                unresolved.append("rename_destination_not_requested")
            consumed.append((body_start, target_region_end))
            surface += ":source_to_destination"
    elif operation == "create":
        separator = _CREATE_PARENT_HEAD.search(raw, body_start, target_region_end)
        destination_end = separator.start() if separator else target_region_end
        destinations, error = _target_list(raw, start=body_start, end=destination_end, role="destination")
        if error:
            unresolved.append(error)
        destination = destinations[0] if len(destinations) == 1 else None
        if len(destinations) != 1:
            unresolved.append("create_target_not_requested")
        if separator is not None:
            parents, parent_error = _target_list(raw, start=separator.end(), end=target_region_end, role="parent")
            if parent_error:
                unresolved.append(parent_error)
            parent_context = parents[0] if len(parents) == 1 else None
            if len(parents) != 1:
                unresolved.append("create_parent_not_requested")
        else:
            unresolved.append("create_parent_not_requested")
        consumed.append((body_start, target_region_end))
        surface += ":destination"
    else:
        target_start = body_start
        behavior_separator = None
        for candidate in _BEHAVIOR_TARGET_HEAD.finditer(raw, body_start, target_region_end):
            parsed, error = _target_list(raw, start=candidate.end(), end=target_region_end, role="mutate")
            if parsed and error is None:
                behavior_separator = candidate
                mutation_targets = parsed
                target_start = candidate.end()
        if behavior_separator is not None:
            behavior.append(_clause("behavior", raw, body_start, behavior_separator.start()))
            surface += ":behavior_in_targets"
            if "across" in behavior_separator.group(0).casefold():
                surface += ":across"
        else:
            for_separator = _TARGET_BEHAVIOR_HEAD.search(raw, body_start, target_region_end)
            if for_separator is not None:
                parsed, error = _target_list(raw, start=body_start, end=for_separator.start(), role="mutate")
                if parsed and error is None:
                    mutation_targets = parsed
                    behavior.append(_clause("behavior", raw, for_separator.end(), target_region_end))
                    surface += ":targets_for_behavior"
            if not mutation_targets:
                mutation_targets, error = _target_list(raw, start=body_start, end=target_region_end, role="mutate")
                if error:
                    unresolved.append(error)
                surface += ":targets"
        if mutation_targets:
            consumed.append((target_start, target_region_end))
        elif not unresolved:
            unresolved.append("mutation_target_not_requested")

    if acceptance_match is not None:
        acceptance_start = acceptance_match.end()
        if not raw[acceptance_start:main_end].strip(" .;,:"):
            unresolved.append("acceptance_condition_not_requested")
        else:
            acceptance.append(_clause("acceptance", raw, acceptance_start, main_end))
            consumed.append((acceptance_match.start(), main_end))
            surface += ":acceptance"

    if preserve_match is not None:
        preserve_targets, error = _target_list(
            raw, start=preserve_match.end(), end=len(raw), role="preserve",
        )
        if error:
            unresolved.append(error)
        if not preserve_targets:
            unresolved.append("preserve_target_not_resolved")
        consumed.append((preserve_match.start(), len(raw)))
        surface += ":preserve"

    mutate_values = {item.value.casefold(): item.value for item in mutation_targets}
    preserve_values = {item.value.casefold(): item.value for item in preserve_targets}
    for key in sorted(mutate_values.keys() & preserve_values.keys()):
        unresolved.append(f"target_polarity_conflict:{mutate_values[key]}")

    if not mutation_targets and operation in {"modify", "delete"} and not any(
        item.startswith(("mutation_target_not_requested", "input_limit:mutation_targets"))
        for item in unresolved
    ):
        unresolved.append("mutation_target_not_requested")

    return PatchRequestPlan(
        operation=operation,
        mutation_targets=mutation_targets,
        preserve_targets=preserve_targets,
        destination=destination,
        parent_context=parent_context,
        scope_terms=tuple(item.text for item in behavior),
        behavioral_requirements=tuple(behavior),
        acceptance_conditions=tuple(acceptance),
        consumed_spans=tuple(sorted(set(consumed))),
        unresolved_parts=tuple(dict.fromkeys(unresolved))[:MAX_PATCH_CLAUSES],
        language=language,
        surface_id=surface,
    )


__all__ = [
    "PATCH_REQUEST_PLAN_SCHEMA", "PatchClause", "PatchRequestPlan", "PatchTarget",
    "build_patch_request_plan",
]
