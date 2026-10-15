"""Negative prose compatibility and bounded literal patch-target coordinates."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Literal

from docmancer.docs.domain.canonical import canonical_hash


PATCH_REQUEST_PLAN_SCHEMA = "patch-request-plan-v2"
MAX_PATCH_TARGETS = 12
MAX_PATCH_CLAUSES = 12
MAX_PATCH_FIELD_LENGTH = 500

PatchOperation = Literal["modify", "create", "delete", "rename", "none"]
PatchLanguage = Literal["en", "ru"]
PatchTargetRole = Literal["mutate", "preserve", "destination", "parent"]

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
_LIST_SEPARATOR_RE = re.compile(r"\s*,\s*")
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
    # A verb supplied to the legacy prose helper is not typed mutation input.
    return "none"


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
        kind: Literal["path", "symbol"] = (
            "path"
            if match.group("path") or (match.group("quoted") and re.fullmatch(_PATH_PATTERN, value))
            else "symbol"
        )
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
    # Explicit task contracts are handled by typed consumers, not this parser.
    return _unsupported(raw, language, "unsupported_patch_surface")


__all__ = [
    "PATCH_REQUEST_PLAN_SCHEMA", "PatchClause", "PatchRequestPlan", "PatchTarget",
    "build_patch_request_plan",
]
