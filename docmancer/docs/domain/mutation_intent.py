"""Immutable mutation intent and operation-aware target readiness."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
import re
from typing import Any, Iterable, Literal, Mapping

from docmancer.docs.domain.request_intent import is_change_request
from docmancer.docs.domain.patch_request_plan import PatchRequestPlan, build_patch_request_plan
from docmancer.retrieval.contracts import canonical_hash


MUTATION_INTENT_SCHEMA = "mutation-intent-v2"
MAX_MUTATION_TARGETS = 12
MAX_ACCEPTANCE_CONDITIONS = 12

MutationOperation = Literal["modify", "create", "delete", "rename", "none"]
ArtifactKind = Literal["source", "docs", "config", "test", "generated_answer", "unknown"]
TargetBindingKind = Literal["target", "parent_context"]

_PATH_RE = re.compile(
    r"(?<![\w/])(?:\.?\.?/)?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:py|dart|js|jsx|ts|tsx|go|rs|java|kt|swift|c|cc|cpp|h|hpp|md|mdx|rst|txt|adoc|toml|yaml|yml|json|ini|cfg|xml)(?![\w/])",
    re.I,
)
_SYMBOL_RE = re.compile(
    r"`([^`\n]{2,160})`"
    r"|\b([A-Za-z_][A-Za-z0-9_]*(?:(?:::|\.)[A-Za-z_][A-Za-z0-9_]*)+)\b"
    r"|\b([A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+)\b"
    r"|\b([A-Z][A-Za-z0-9]*(?:[A-Z][A-Za-z0-9]*)+)\b"
)
_CREATE_RE = re.compile(r"\b(?:create|add|new|generate|созда(?:ть|й)|добав(?:ить|ь)|нов(?:ый|ую|ое))\b", re.I)
_DELETE_RE = re.compile(r"\b(?:delete|remove|drop|удал(?:ить|и)|убра(?:ть|ть))\b", re.I)
_RENAME_RE = re.compile(r"\b(?:rename|move|перенес(?:ти|и)|переименова(?:ть|й))\b", re.I)
_MODIFY_RE = re.compile(r"\b(?:modify|change|update|fix|patch|implement|refactor|исправ(?:ить|ь)|измен(?:ить|и)|обнов(?:ить|и)|реализова(?:ть|ть)|рефактор)\b", re.I)
_CODE_WORD_RE = re.compile(r"\b(?:code|source|class|function|method|implementation|код|исходник|класс|функци|метод|реализаци)\b", re.I)
_DOC_WORD_RE = re.compile(r"\b(?:readme|docs?|documentation|adr|roadmap|markdown|документаци|ридми|описани)\b", re.I)
_CONFIG_WORD_RE = re.compile(r"\b(?:config|configuration|settings?|manifest|toml|yaml|json|конфиг|настройк|манифест)\b", re.I)
_TEST_WORD_RE = re.compile(r"\b(?:tests?|specs?|fixture|pytest|тест(?:ы|ов|а)?|фикстур)\b", re.I)
_ACCEPTANCE_SPLIT_RE = re.compile(r"[\n;]+|(?<=[.!?])\s+")


def _normal_path(value: str) -> str:
    return str(PurePosixPath(value.replace("\\", "/").removeprefix("./")))[:500]


def _artifact_for_target(path: str) -> ArtifactKind:
    value = path.casefold()
    name = PurePosixPath(value).name
    if "/test" in f"/{value}" or name.startswith("test_") or name.endswith(("_test.py", ".spec.ts", ".test.ts", "_test.dart")):
        return "test"
    if name in {"pyproject.toml", "package.json", "pubspec.yaml", "cargo.toml", "settings.gradle", "gradle.properties"} or PurePosixPath(value).suffix in {".toml", ".yaml", ".yml", ".json", ".ini", ".cfg", ".xml"}:
        return "config"
    if PurePosixPath(value).suffix in {".md", ".mdx", ".rst", ".txt", ".adoc"}:
        return "docs"
    if PurePosixPath(value).suffix in {".py", ".dart", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".kt", ".swift", ".c", ".cc", ".cpp", ".h", ".hpp"}:
        return "source"
    return "unknown"


def _artifact_from_question(question: str, targets: tuple[str, ...]) -> ArtifactKind:
    kinds = {_artifact_for_target(value) for value in targets} - {"unknown"}
    if len(kinds) == 1:
        return next(iter(kinds))
    if _TEST_WORD_RE.search(question):
        return "test"
    if _CONFIG_WORD_RE.search(question):
        return "config"
    if _DOC_WORD_RE.search(question):
        return "docs"
    if _CODE_WORD_RE.search(question):
        return "source"
    if re.search(r"\b(?:example|snippet|answer|пример|сниппет|ответ)\b", question, re.I):
        return "generated_answer"
    return "unknown"


@dataclass(frozen=True, slots=True)
class RequestedTarget:
    value: str
    kind: Literal["path", "symbol"]
    query_span_start: int
    query_span_end: int
    provenance: str = "user_request"


@dataclass(frozen=True, slots=True)
class ResolvedTarget:
    requested_value: str
    path: str
    symbol: str | None
    evidence_id: str
    artifact_kind: ArtifactKind
    exists: bool
    collision_free: bool | None = None
    binding_kind: TargetBindingKind = "target"


@dataclass(frozen=True, slots=True)
class MutationIntentContract:
    operation: MutationOperation
    artifact_kind: ArtifactKind
    requested_targets: tuple[RequestedTarget, ...]
    resolved_targets: tuple[ResolvedTarget, ...] = ()
    preserved_targets: tuple[ResolvedTarget, ...] = ()
    destination: str | None = None
    acceptance_conditions: tuple[str, ...] = ()
    request_plan: PatchRequestPlan | None = None
    schema_version: str = MUTATION_INTENT_SCHEMA

    def __post_init__(self) -> None:
        if (
            len(self.requested_targets) > MAX_MUTATION_TARGETS
            or len(self.resolved_targets) > MAX_MUTATION_TARGETS
            or len(self.preserved_targets) > MAX_MUTATION_TARGETS
        ):
            raise ValueError("mutation target contract exceeds bounds")
        if len(self.acceptance_conditions) > MAX_ACCEPTANCE_CONDITIONS:
            raise ValueError("mutation acceptance contract exceeds bounds")
        if self.destination is not None and not str(self.destination).strip():
            raise ValueError("rename/create destination cannot be empty")

    @property
    def hash_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "operation": self.operation,
            "artifact_kind": self.artifact_kind,
            "requested_targets": [asdict(item) for item in self.requested_targets],
            "resolved_targets": [asdict(item) for item in self.resolved_targets],
            "preserved_targets": [asdict(item) for item in self.preserved_targets],
            "destination": self.destination,
            "acceptance_conditions": list(self.acceptance_conditions),
            "request_plan": self.request_plan.hash_payload if self.request_plan is not None else None,
        }

    @property
    def contract_hash(self) -> str:
        return canonical_hash(self.hash_payload)

    def with_resolved_targets(
        self,
        targets: Iterable[ResolvedTarget],
        *,
        preserved_targets: Iterable[ResolvedTarget] | None = None,
    ) -> "MutationIntentContract":
        return MutationIntentContract(
            operation=self.operation,
            artifact_kind=self.artifact_kind,
            requested_targets=self.requested_targets,
            resolved_targets=tuple(targets),
            preserved_targets=(
                tuple(preserved_targets)
                if preserved_targets is not None else self.preserved_targets
            ),
            destination=self.destination,
            acceptance_conditions=self.acceptance_conditions,
            request_plan=self.request_plan,
        )


@dataclass(frozen=True, slots=True)
class MutationReadiness:
    ready: bool
    constraints_only: bool
    missing: tuple[str, ...]
    resolved_target_ids: tuple[str, ...]
    contract_hash: str


def build_mutation_intent(question: str) -> MutationIntentContract:
    raw = str(question or "")[:4_000]
    request_plan = build_patch_request_plan(raw)
    if request_plan.operation != "none":
        operation: MutationOperation = request_plan.operation
    elif _RENAME_RE.search(raw):
        operation = "rename"
    elif _DELETE_RE.search(raw):
        operation = "delete"
    elif _CREATE_RE.search(raw):
        operation = "create"
    elif _MODIFY_RE.search(raw):
        operation = "modify"
    elif is_change_request(raw):
        # Routing recognizes a broader imperative vocabulary than the
        # operation-specific patterns. Keep every routed patch mutable even
        # when its verb only has generic modify semantics here.
        operation = "modify"
    else:
        operation = "none"

    requested = [RequestedTarget(
        value=_normal_path(item.value) if item.kind == "path" else item.value,
        kind=item.kind,
        query_span_start=item.query_span_start,
        query_span_end=item.query_span_end,
    ) for item in request_plan.mutation_targets]
    if request_plan.operation == "none":
        path_spans: list[tuple[int, int]] = []
        for match in _PATH_RE.finditer(raw):
            path_spans.append((match.start(), match.end()))
            requested.append(RequestedTarget(
                value=_normal_path(match.group(0)), kind="path",
                query_span_start=match.start(), query_span_end=match.end(),
            ))
        for match in _SYMBOL_RE.finditer(raw):
            if any(start < match.end() and match.start() < end for start, end in path_spans):
                continue
            value = next((group for group in match.groups() if group), "")
            if (
                not value
                or (match.group(1) is None and value.isupper() and not re.search(r"[_:.]", value))
                or any(item.value.casefold() == value.casefold() for item in requested)
            ):
                continue
            requested.append(RequestedTarget(
                value=value[:240], kind="symbol",
                query_span_start=match.start(), query_span_end=match.end(),
            ))
        requested = requested[:MAX_MUTATION_TARGETS]
    path_targets = tuple(item.value for item in requested if item.kind == "path")
    artifact = _artifact_from_question(raw, path_targets)

    destination: str | None = None
    if operation == "rename" and len(path_targets) >= 2:
        destination = path_targets[-1]
    elif operation == "create" and path_targets:
        destination = path_targets[-1]

    acceptance: list[str] = []
    for clause in _ACCEPTANCE_SPLIT_RE.split(raw):
        clause = " ".join(clause.split()).strip()
        if len(clause) >= 8 and re.search(r"\b(?:must|should|without|so that|чтобы|долж|без)\b", clause, re.I):
            acceptance.append(clause[:500])
    return MutationIntentContract(
        operation=operation,
        artifact_kind=artifact,
        requested_targets=tuple(requested),
        destination=destination,
        acceptance_conditions=tuple(dict.fromkeys(acceptance))[:MAX_ACCEPTANCE_CONDITIONS],
        request_plan=request_plan if request_plan.operation != "none" else None,
    )


def with_explicit_path_targets(
    contract: MutationIntentContract,
    paths: Iterable[str],
    *,
    provenance: str = "explicit_task_contract",
) -> MutationIntentContract:
    """Bind caller-declared target paths without pretending they came from query text.

    Public MCP ingress normally supplies a complete mutation contract built once
    from the user request.  Direct/internal callers (for example frozen task
    evaluation contracts) may instead provide explicit ``required_target_paths``.
    Those paths are legitimate requested targets only when their provenance is
    retained; they must never be reconstructed from retrieved documentation.
    """

    existing = {item.value.casefold() for item in contract.requested_targets}
    requested = list(contract.requested_targets)
    for raw in paths:
        value = _normal_path(str(raw or "").strip())
        if not value or value.casefold() in existing:
            continue
        requested.append(RequestedTarget(
            value=value,
            kind="path",
            query_span_start=-1,
            query_span_end=-1,
            provenance=provenance,
        ))
        existing.add(value.casefold())
        if len(requested) >= MAX_MUTATION_TARGETS:
            break
    if tuple(requested) == contract.requested_targets:
        return contract
    path_targets = tuple(item.value for item in requested if item.kind == "path")
    artifact = contract.artifact_kind
    if artifact == "unknown":
        inferred = {_artifact_for_target(value) for value in path_targets} - {"unknown"}
        if len(inferred) == 1:
            artifact = next(iter(inferred))
    destination = contract.destination
    if contract.operation == "rename" and not destination and len(path_targets) >= 2:
        destination = path_targets[-1]
    elif contract.operation == "create" and not destination and path_targets:
        destination = path_targets[-1]
    return MutationIntentContract(
        operation=contract.operation,
        artifact_kind=artifact,
        requested_targets=tuple(requested),
        resolved_targets=contract.resolved_targets,
        preserved_targets=contract.preserved_targets,
        destination=destination,
        acceptance_conditions=contract.acceptance_conditions,
        request_plan=contract.request_plan,
    )


def resolve_mutation_targets(
    contract: MutationIntentContract,
    evidence_items: Iterable[Mapping[str, Any]],
    *,
    evidence_id_for_item: Any,
) -> MutationIntentContract:
    resolved: list[ResolvedTarget] = []
    items = [item for item in evidence_items if isinstance(item, Mapping)]
    for requested in contract.requested_targets:
        wanted = requested.value.casefold().replace("\\", "/")
        matches: list[tuple[Mapping[str, Any], str, str | None]] = []
        for item in items:
            path = str(item.get("path") or item.get("source") or item.get("source_path") or "").replace("\\", "/")
            metadata = item.get("metadata") if isinstance(item.get("metadata"), Mapping) else {}
            symbols = [
                str(value.get("name") if isinstance(value, Mapping) else value)
                for source in (item, metadata)
                for key in ("symbols", "matched_symbols", "symbol_names")
                for value in (source.get(key) or [])
            ]
            path_match = requested.kind == "path" and (
                path.casefold() == wanted or path.casefold().endswith("/" + wanted)
            )
            symbol_match = requested.kind == "symbol" and any(value.casefold() == wanted for value in symbols)
            if path_match or symbol_match:
                matches.append((item, path, requested.value if symbol_match else None))
        if not matches and requested.kind == "symbol":
            aliases: list[tuple[Mapping[str, Any], str, str | None]] = []
            for item in items:
                path = str(item.get("path") or item.get("source") or item.get("source_path") or "").replace("\\", "/")
                if _artifact_for_target(path) != "source":
                    continue
                stem = PurePosixPath(path).stem
                alias = "".join(part[:1].upper() + part[1:] for part in stem.split("_") if part)
                if alias.casefold() == wanted:
                    aliases.append((item, path, requested.value))
            if len({path.casefold() for _, path, _ in aliases}) == 1:
                matches = aliases[:1]
        if requested.kind == "symbol" and len({path.casefold() for _, path, _ in matches}) > 1:
            matches = []
        if matches:
            item, path, symbol = matches[0]
            evidence_id = str(evidence_id_for_item(dict(item)))
            resolved.append(ResolvedTarget(
                requested_value=requested.value,
                path=path,
                symbol=symbol,
                evidence_id=evidence_id,
                artifact_kind=_artifact_for_target(path),
                exists=True,
            ))

    # Creating a new path must be authorized by real local parent/module
    # context.  The absent destination itself can never be a retrieval hit, so
    # bind one deterministic sibling/code-graph witness without pretending the
    # target already exists.
    if contract.operation == "create" and contract.destination:
        destination = PurePosixPath(_normal_path(contract.destination))
        parent = destination.parent
        parent_candidates: list[tuple[str, Mapping[str, Any]]] = []
        for item in items:
            path = str(item.get("path") or item.get("source") or item.get("source_path") or "").replace("\\", "/")
            if not path:
                continue
            normalized = PurePosixPath(_normal_path(path))
            metadata = item.get("metadata") if isinstance(item.get("metadata"), Mapping) else {}
            source_class = str(item.get("source_class") or metadata.get("source_class") or "").casefold()
            module_path = str(item.get("module_path") or metadata.get("module_path") or "").replace("\\", "/").strip("/")
            same_parent = normalized.parent == parent
            module_parent = bool(module_path) and (
                str(parent) == module_path or str(parent).startswith(module_path + "/")
            )
            local_structure = source_class in {"code_graph", "repo_map", "project_file"}
            concrete_sibling = _artifact_for_target(path) in {"source", "config", "test"}
            if same_parent and concrete_sibling or module_parent and local_structure:
                parent_candidates.append((path.casefold(), item))
        if parent_candidates:
            _, item = min(parent_candidates, key=lambda pair: pair[0])
            path = str(item.get("path") or item.get("source") or item.get("source_path") or "").replace("\\", "/")
            resolved.append(ResolvedTarget(
                requested_value=contract.destination,
                path=path,
                symbol=None,
                evidence_id=str(evidence_id_for_item(dict(item))),
                artifact_kind=_artifact_for_target(contract.destination),
                exists=False,
                collision_free=True,
                binding_kind="parent_context",
            ))
    preserved: list[ResolvedTarget] = []
    for requested in (contract.request_plan.preserve_targets if contract.request_plan else ()):
        wanted = requested.value.casefold()
        matches: list[tuple[Mapping[str, Any], str, str | None]] = []
        for item in items:
            path = str(item.get("path") or item.get("source") or item.get("source_path") or "").replace("\\", "/")
            metadata = item.get("metadata") if isinstance(item.get("metadata"), Mapping) else {}
            symbols = [
                str(value.get("name") if isinstance(value, Mapping) else value)
                for source in (item, metadata)
                for key in ("symbols", "matched_symbols", "symbol_names")
                for value in (source.get(key) or [])
            ]
            path_match = requested.kind == "path" and (
                path.casefold() == wanted or path.casefold().endswith("/" + wanted)
            )
            symbol_match = requested.kind == "symbol" and any(value.casefold() == wanted for value in symbols)
            if path_match or symbol_match:
                matches.append((item, path, requested.value if symbol_match else None))
        if len({path.casefold() for _, path, _ in matches}) == 1:
            item, path, symbol = matches[0]
            preserved.append(ResolvedTarget(
                requested_value=requested.value,
                path=path,
                symbol=symbol,
                evidence_id=str(evidence_id_for_item(dict(item))),
                artifact_kind=_artifact_for_target(path),
                exists=True,
            ))
    return contract.with_resolved_targets(resolved, preserved_targets=preserved)


def evaluate_mutation_readiness(contract: MutationIntentContract) -> MutationReadiness:
    requested_paths = {item.value.casefold() for item in contract.requested_targets if item.kind == "path"}
    requested_values = {item.value.casefold() for item in contract.requested_targets}
    resolved_values = {item.requested_value.casefold() for item in contract.resolved_targets if item.exists}
    missing: list[str] = []
    if contract.request_plan is not None:
        missing.extend(contract.request_plan.unresolved_parts)
        preserve_values = {item.value.casefold() for item in contract.request_plan.preserve_targets}
        preserved_values = {item.requested_value.casefold() for item in contract.preserved_targets}
        if not preserve_values.issubset(preserved_values):
            missing.append("preserve_target_not_resolved")
    if contract.operation in {"modify", "delete"}:
        if not requested_values:
            missing.append("mutation_target_not_requested")
        elif not requested_values.issubset(resolved_values):
            missing.append("mutation_target_not_resolved")
    elif contract.operation == "rename":
        source_values = set(requested_values)
        if contract.destination:
            source_values.discard(contract.destination.casefold())
        if not source_values:
            missing.append("rename_source_not_requested")
        elif not source_values.issubset(resolved_values):
            missing.append("rename_source_not_resolved")
        if not contract.destination:
            missing.append("rename_destination_not_requested")
        if any(item.path.casefold() == str(contract.destination or "").casefold() for item in contract.resolved_targets):
            missing.append("rename_destination_collision")
    elif contract.operation == "create":
        if not contract.destination and not requested_paths:
            missing.append("create_target_not_requested")
        destination = str(contract.destination or next(iter(requested_paths), ""))
        target_bindings = [
            item for item in contract.resolved_targets
            if item.binding_kind == "target" and item.exists
        ]
        if destination and any(item.path.casefold() == destination.casefold() for item in target_bindings):
            missing.append("create_target_collision")
        parent_context = [
            item for item in contract.resolved_targets
            if item.binding_kind == "parent_context"
            and item.requested_value.casefold() == destination.casefold()
            and item.collision_free is True
        ]
        if destination and not parent_context:
            missing.append("create_parent_or_module_not_resolved")
    elif contract.operation == "none":
        return MutationReadiness(
            ready=False, constraints_only=False,
            missing=("mutation_intent_not_detected",), resolved_target_ids=(),
            contract_hash=contract.contract_hash,
        )

    compatible = {
        "source": {"source"}, "docs": {"docs"}, "config": {"config"},
        "test": {"test"}, "generated_answer": {"generated_answer"}, "unknown": {"source", "docs", "config", "test", "unknown"},
    }
    if contract.operation in {"modify", "delete", "rename"} and contract.resolved_targets:
        allowed = compatible.get(contract.artifact_kind, {contract.artifact_kind})
        if not all(item.artifact_kind in allowed for item in contract.resolved_targets):
            missing.append("mutation_target_artifact_kind_mismatch")

    return MutationReadiness(
        ready=not missing,
        # Evidence-backed constraint availability is computed by ActionPacket
        # assembly; mutation intent alone cannot prove documentation facts.
        constraints_only=False,
        missing=tuple(sorted(set(missing))),
        resolved_target_ids=tuple(sorted({item.evidence_id for item in contract.resolved_targets})),
        contract_hash=contract.contract_hash,
    )


__all__ = [
    "ArtifactKind", "MUTATION_INTENT_SCHEMA", "MutationIntentContract",
    "MutationOperation", "MutationReadiness", "RequestedTarget", "ResolvedTarget",
    "build_mutation_intent", "evaluate_mutation_readiness", "resolve_mutation_targets",
    "with_explicit_path_targets",
]
