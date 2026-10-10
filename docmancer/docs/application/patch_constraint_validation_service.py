from __future__ import annotations

import fnmatch
import hashlib
import os
import re
import shlex
import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from docmancer.docs.models import (
    PatchConstraint,
    PatchConstraintPacket,
    PatchConstraintValidationPacket,
    PatchConstraintValidationResult,
)

GENERATED_PATTERNS = (
    "*.g.dart",
    "*.freezed.dart",
    "*.pb.go",
    "*.pb.dart",
    "*.generated.*",
    "generated/*",
    "dist/*",
)
LOCKFILES = {
    "pubspec.lock",
    "poetry.lock",
    "uv.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "Cargo.lock",
    "go.sum",
}

# Validation accepts supplied comparisons, not unlimited source material.
MAX_VALIDATION_CONSTRAINTS = 1000
MAX_VALIDATION_PATHS = 4096
MAX_CONSTRAINT_PATHS = 128
MAX_VALIDATION_TEXT_CHARS = 1_000_000
MAX_PATH_CHARS = 4096
MAX_SOURCE_READ_BYTES = 4_000_000


@dataclass(frozen=True)
class _AdvisoryValidationPacket(PatchConstraintValidationPacket):
    policy_coverage: str = "unresolved"
    mutation_authorized: bool = False
    edit_ready: bool = False
    source_identity_validated: bool = False


class PatchConstraintValidationService:
    """Bounded advisory comparisons for explicit typed file protections.

    This service does not call an LLM, web, retrieval, or git. It only compares
    caller-supplied constraints with caller-supplied changed_files / patch_diff.
    No result establishes policy completeness, source freshness or edit authority.
    """

    def validate_patch_against_constraints(
        self,
        constraints: PatchConstraintPacket | list[PatchConstraint] | dict[str, Any] | list[dict[str, Any]],
        *,
        project_path: str | None = None,
        changed_files: list[str] | None = None,
        patch_diff: str | None = None,
        strict: bool = False,
    ) -> PatchConstraintValidationPacket:
        warnings = [
            "Advisory validation only: policy coverage remains unresolved; satisfied means only the explicit supplied comparison, not mutation authorization or edit readiness.",
        ]
        try:
            task, normalized = self._normalize_constraints(constraints)
            files, path_errors = self._changed_path_evidence(changed_files, patch_diff, project_path)
            path_errors.extend(self._packet_scope_errors(constraints, project_path))
        except ValueError as exc:
            task = None
            normalized = [self._constraint_from_dict({"id": "validation-input", "type": "unknown", "source": "input"}, 0)]
            files, path_errors = [], [str(exc)]
        warnings.extend(path_errors)
        if not normalized:
            warnings.append("No constraints were supplied; empty validation is not an all-pass result.")
        if not files and not patch_diff:
            warnings.append("Validation is limited: provide changed_files or patch_diff for deterministic checks.")

        source_cache: dict[Path, bytes] = {}
        results = [self._validate_constraint(constraint, files, patch_diff, task, path_errors=path_errors, project_path=project_path, source_cache=source_cache) for constraint in normalized]
        satisfied = sum(1 for result in results if result.status == "satisfied")
        violated = sum(1 for result in results if result.status == "violated")
        unknown = sum(1 for result in results if result.status == "unknown")
        manual_review = sum(1 for result in results if result.status == "manual_review")
        unresolved = unknown + manual_review
        if strict and unresolved:
            warnings.append("strict mode: unresolved unknown/manual_review constraints require manual review")

        confidence = self._packet_confidence(total=len(normalized), satisfied=satisfied, violated=violated, unknown=unknown, manual_review=manual_review)
        return _AdvisoryValidationPacket(
            task=task,
            project_path=project_path,
            total_constraints=len(normalized),
            satisfied=satisfied,
            violated=violated,
            unknown=unknown,
            manual_review=manual_review,
            results=results,
            warnings=warnings,
            confidence=confidence,
        )

    def _validate_constraint(self, constraint: PatchConstraint, changed_files: list[str], patch_diff: str | None, task: str | None = None, *, path_errors: list[str] | None = None, project_path: str | None = None, source_cache: dict[Path, bytes] | None = None) -> PatchConstraintValidationResult:
        errors = list(path_errors or [])
        protected, protected_errors = self._protected_path_evidence(constraint.files, project_path=project_path)
        errors.extend(protected_errors)
        if constraint.type in {"generated_file", "forbidden_edit"}:
            matches = [path for path in changed_files if any(self._path_matches(path, pattern) for pattern in protected)]
            if constraint.type == "generated_file":
                matches = list(dict.fromkeys([*matches, *self._changed_generated_files(changed_files)]))
            if matches:
                reason = "generated file edit detected" if constraint.type == "generated_file" else "explicit protected file edit detected"
                if any(Path(path).name in LOCKFILES for path in matches):
                    reason = "explicit protected lockfile edit detected"
                if errors:
                    reason += "; additional path evidence unresolved: " + "; ".join(errors)[:512]
                return self._result(constraint, "violated", reason, matches, evidence=constraint.evidence)
            if errors:
                return self._result(constraint, "unknown", "invalid or incomplete changed/protected path evidence: " + "; ".join(errors)[:512], [], evidence=constraint.evidence)
            if constraint.type == "forbidden_edit" and not protected:
                return self._result(constraint, "unknown", "explicit protected files were not supplied; prose does not define protected targets", [], evidence=constraint.evidence)
            if changed_files:
                source_problem = self._source_problem(constraint, project_path, source_cache=source_cache)
                if source_problem:
                    return self._result(constraint, "unknown", source_problem, [], evidence=constraint.evidence)
                return self._result(constraint, "satisfied", "no supplied changed path matches the explicit typed file protection; not policy approval", [], evidence=constraint.evidence)
            return self._result(constraint, "unknown", "changed files unavailable for explicit file comparison", [], evidence=constraint.evidence)
        if constraint.type == "verification":
            return self._result(constraint, "unknown", "verification constraint requires explicit test evidence", [], evidence=constraint.evidence)
        if constraint.type in {"architecture", "behavior", "semantic", "manual_review", "source_of_truth"}:
            return self._result(
                constraint,
                "manual_review",
                "semantic constraint is not mechanically decidable from changed files or diff",
                [],
                evidence=constraint.evidence,
                remediation="Review the patch against the cited source before treating this constraint as satisfied.",
            )

        return self._result(constraint, "unknown", "constraint has no supported explicit mechanical comparison; literal text/version/symbol occurrences do not prove policy", [], evidence=constraint.evidence)

    def _normalize_constraints(self, constraints: PatchConstraintPacket | list[PatchConstraint] | dict[str, Any] | list[dict[str, Any]]) -> tuple[str | None, list[PatchConstraint]]:
        task: str | None = None
        raw_constraints: Any
        if isinstance(constraints, PatchConstraintPacket):
            task = constraints.task
            raw_constraints = constraints.constraints
        elif isinstance(constraints, dict):
            task = constraints.get("task")
            raw_constraints = constraints.get("constraints") or []
        else:
            raw_constraints = constraints

        if not isinstance(raw_constraints, list):
            raise ValueError("invalid_constraints: expected an explicit constraint list")
        if len(raw_constraints) > MAX_VALIDATION_CONSTRAINTS:
            raise ValueError("input_limit:constraints")
        if task is not None and (not isinstance(task, str) or len(task) > MAX_VALIDATION_TEXT_CHARS):
            raise ValueError("input_limit:task")
        normalized: list[PatchConstraint] = []
        for index, raw in enumerate(raw_constraints or []):
            if isinstance(raw, PatchConstraint):
                if (
                    all(isinstance(getattr(raw, field), str) for field in ("id", "type", "instruction", "source", "severity", "confidence", "evidence"))
                    and all(isinstance(getattr(raw, field), list) for field in ("files", "symbols", "source_refs", "evidence_snippets"))
                ):
                    normalized.append(raw)
                else:
                    normalized.append(self._constraint_from_dict({"id": f"invalid-constraint-{index + 1}", "type": "unknown"}, index))
            elif isinstance(raw, dict):
                try:
                    normalized.append(self._constraint_from_dict(raw, index))
                except ValueError:
                    normalized.append(self._constraint_from_dict({"id": f"invalid-constraint-{index + 1}", "type": "unknown"}, index))
            else:
                normalized.append(self._constraint_from_dict({"id": f"invalid-constraint-{index + 1}", "type": "unknown"}, index))
        if sum(len(str(value)) for constraint in normalized for value in asdict(constraint).values()) > MAX_VALIDATION_TEXT_CHARS:
            raise ValueError("input_limit:constraint_material")
        return task, normalized

    @staticmethod
    def _constraint_from_dict(raw: dict[str, Any], index: int) -> PatchConstraint:
        for field in ("files", "symbols", "source_refs", "evidence_snippets"):
            if raw.get(field) is not None and not isinstance(raw[field], list):
                raise ValueError(f"invalid_constraint:{field}")
        return PatchConstraint(
            id=str(raw.get("id") or f"constraint-{index + 1}"),
            type=str(raw.get("type") or "unknown"),
            instruction=str(raw.get("instruction") or ""),
            source=str(raw.get("source") or ""),
            severity=str(raw.get("severity") or "info"),
            confidence=str(raw.get("confidence") or "low"),
            evidence=str(raw.get("evidence") or ""),
            symbols=list(raw.get("symbols") or []),
            files=list(raw.get("files") or []),
            source_refs=list(raw.get("source_refs") or []),
            evidence_snippets=list(raw.get("evidence_snippets") or []),
        )

    def _normalize_changed_files(self, changed_files: list[str] | None, patch_diff: str | None) -> list[str]:
        return self._changed_path_evidence(changed_files, patch_diff, None)[0]

    @staticmethod
    def _packet_scope_errors(constraints: Any, project_path: str | None) -> list[str]:
        if isinstance(constraints, PatchConstraintPacket):
            declared_root, index_state = constraints.project_path, constraints.index_state
        elif isinstance(constraints, dict):
            declared_root, index_state = constraints.get("project_path"), constraints.get("index_state")
        else:
            return []
        errors: list[str] = []
        if declared_root is not None:
            try:
                if not isinstance(declared_root, str) or not declared_root or not project_path or Path(declared_root).expanduser().resolve() != Path(project_path).expanduser().resolve():
                    errors.append("source_scope:packet_project_mismatch_or_unverified")
            except (OSError, RuntimeError, ValueError, TypeError):
                errors.append("source_scope:invalid_packet_project")
        if index_state:
            # This DTO carries no index verifier. Local byte comparisons never
            # certify supplied library/version/snapshot/freshness/index claims.
            errors.append("source_scope:index_state_not_verified")
        return errors

    @staticmethod
    def _relative_path(value: Any, *, pattern: bool = False) -> str:
        if not isinstance(value, str) or not value or len(value) > MAX_PATH_CHARS:
            raise ValueError("invalid_path:empty_or_type_or_length")
        if any(ord(char) < 32 for char in value) or value != value.strip():
            raise ValueError("invalid_path:control_or_whitespace")
        normalized = value.replace("\\", "/")
        if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
            raise ValueError("invalid_path:absolute")
        if ".." in normalized.split("/"):
            raise ValueError("invalid_path:traversal")
        if not pattern and any(char in normalized for char in "*?[]"):
            raise ValueError("invalid_path:nonliteral_changed_path")
        parts = [part for part in normalized.split("/") if part not in {"", "."}]
        if not parts:
            raise ValueError("invalid_path:empty")
        return "/".join(parts)

    @classmethod
    def _protected_path_evidence(cls, values: Any, *, project_path: str | None = None) -> tuple[list[str], list[str]]:
        if not isinstance(values, list) or len(values) > MAX_CONSTRAINT_PATHS:
            return [], ["input_limit_or_type:protected_paths"]
        paths: list[str] = []
        errors: list[str] = []
        for value in values:
            try:
                path = cls._relative_path(value, pattern=True)
                # A wildcard is an explicit supplied pattern, not a filesystem locator.
                if project_path is not None and not any(char in path for char in "*?["):
                    cls._bound_literal_path(Path(project_path).expanduser().resolve(), path)
                if path not in paths:
                    paths.append(path)
            except (OSError, RuntimeError, ValueError, TypeError) as exc:
                errors.append(str(exc))
        return paths, errors

    @staticmethod
    def _bound_literal_path(root: Path, path: str) -> Path:
        current = root
        for part in path.split("/"):
            current = current / part
            if current.is_symlink():
                raise ValueError("invalid_path:symlink")
        resolved = current.resolve()
        if not resolved.is_relative_to(root):
            raise ValueError("invalid_path:root_escape")
        return resolved

    @staticmethod
    def _path_matches(path: str, pattern: str) -> bool:
        if not any(char in pattern for char in "*?["):
            return path == pattern
        return fnmatch.fnmatchcase(path, pattern) or ("/" not in pattern and fnmatch.fnmatchcase(Path(path).name, pattern))

    @classmethod
    def _changed_path_evidence(cls, changed_files: Any, patch_diff: Any, project_path: str | None) -> tuple[list[str], list[str]]:
        if changed_files is not None and not isinstance(changed_files, list):
            raise ValueError("invalid_changed_files:expected_list")
        if len(changed_files or []) > MAX_VALIDATION_PATHS:
            raise ValueError("input_limit:changed_files")
        if patch_diff is not None and (not isinstance(patch_diff, str) or len(patch_diff) > MAX_VALIDATION_TEXT_CHARS):
            raise ValueError("input_limit_or_type:patch_diff")
        paths, errors = cls._diff_paths(patch_diff)
        paths = [*(changed_files or []), *paths]
        if len(paths) > MAX_VALIDATION_PATHS:
            raise ValueError("input_limit:changed_paths")
        if sum(len(value) for value in paths if isinstance(value, str)) > MAX_VALIDATION_TEXT_CHARS:
            raise ValueError("input_limit:changed_path_material")
        root = None
        if project_path is not None:
            if not isinstance(project_path, str) or not project_path or len(project_path) > MAX_PATH_CHARS:
                raise ValueError("invalid_project_path")
            try:
                root = Path(project_path).expanduser().resolve()
            except (OSError, RuntimeError, ValueError):
                raise ValueError("invalid_project_path") from None
        out: list[str] = []
        for value in paths:
            try:
                path = cls._relative_path(value)
                if root is not None:
                    cls._bound_literal_path(root, path)
                if path not in out:
                    out.append(path)
            except (OSError, RuntimeError, ValueError) as exc:
                errors.append(str(exc))
        errors = list(dict.fromkeys(str(error)[:200] for error in errors))
        if len(errors) > 20:
            errors = [*errors[:20], "additional invalid path diagnostics omitted by diagnostic budget"]
        return out, errors

    @staticmethod
    def _files_from_diff(patch_diff: str | None) -> list[str]:
        return PatchConstraintValidationService._diff_paths(patch_diff)[0]

    @staticmethod
    def _diff_paths(patch_diff: str | None) -> tuple[list[str], list[str]]:
        files: list[str] = []
        errors: list[str] = []
        in_hunk = False
        for line in (patch_diff or "").splitlines():
            if line.startswith("diff --git "):
                in_hunk = False
                try:
                    if '"' in line and "\\" in line:
                        raise ValueError
                    fields = shlex.split(line)
                    if len(fields) != 4 or not fields[2].startswith("a/") or not fields[3].startswith("b/"):
                        raise ValueError
                    files.extend([fields[2][2:], fields[3][2:]])
                except ValueError:
                    errors.append("invalid_diff:git_paths")
            elif line.startswith("@@"):
                in_hunk = True
            elif not in_hunk and line.startswith(("+++ ", "--- ")):
                value = line[4:].split("\t", 1)[0]
                if value == "/dev/null":
                    continue
                if value.startswith('"'):
                    try:
                        if "\\" in value:
                            raise ValueError
                        fields = shlex.split(value)
                        if len(fields) != 1:
                            raise ValueError
                        value = fields[0]
                    except ValueError:
                        errors.append("invalid_diff:quoted_path")
                        continue
                prefix = "b/" if line.startswith("+++") else "a/"
                if value.startswith(prefix):
                    files.append(value[2:])
                else:
                    errors.append("invalid_diff:path_prefix")
        return list(dict.fromkeys(files)), errors

    @staticmethod
    def _is_generated_path(path: str) -> bool:
        normalized = path.replace("\\", "/")
        name = Path(normalized).name
        return any(fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(normalized, pattern) or f"/{pattern.rstrip('/*')}/" in f"/{normalized}/" for pattern in GENERATED_PATTERNS)

    def _changed_generated_files(self, changed_files: list[str]) -> list[str]:
        return [file for file in changed_files if self._is_generated_path(file)]

    @staticmethod
    def _changed_lockfiles(changed_files: list[str]) -> list[str]:
        return [file for file in changed_files if Path(file).name in LOCKFILES]

    @classmethod
    def _source_problem(cls, constraint: PatchConstraint, project_path: str | None, *, source_cache: dict[Path, bytes] | None = None) -> str | None:
        """Verify only an explicit local file-byte pin and literal source span.

        Generic content_hash/sha256/canonical/snapshot hints have no defined
        domain in this DTO and cannot certify indexed provenance or freshness.
        """
        if not project_path:
            return "source identity unresolved: no explicit project root"
        try:
            root = Path(project_path).expanduser().resolve()
            source = cls._relative_path(constraint.source)
            path = cls._bound_literal_path(root, source)
            refs = constraint.source_refs
            snippets = constraint.evidence_snippets
            if not isinstance(refs, list) or not isinstance(snippets, list) or not refs or not snippets:
                return "source identity unresolved: explicit file-byte pin and source span required"
            for ref in refs:
                if not isinstance(ref, dict) or ref.get("kind") != "source" or ref.get("path") != source:
                    return "source identity unresolved: unsupported source reference"
                if set(ref) - {"path", "kind", "file_bytes_sha256", "line_start", "line_end"}:
                    return "source identity unresolved: unsupported provenance/hash domain"
                pin = ref.get("file_bytes_sha256")
                if not isinstance(pin, str) or re.fullmatch(r"[a-f0-9]{64}", pin) is None:
                    return "source identity unresolved: explicit file-byte hash required"
            if not path.is_file() or path.stat().st_size > MAX_VALIDATION_TEXT_CHARS:
                return "source identity unresolved: missing or oversized source"
            cache = source_cache if source_cache is not None else {}
            if path in cache:
                content = cache[path]
            else:
                if sum(len(value) for value in cache.values()) + path.stat().st_size > MAX_SOURCE_READ_BYTES:
                    return "source identity unresolved: aggregate read budget exceeded"
                content = cls._read_source_bytes(root, source, MAX_VALIDATION_TEXT_CHARS + 1)
                if len(content) + sum(len(value) for value in cache.values()) > MAX_SOURCE_READ_BYTES:
                    return "source identity unresolved: aggregate read budget exceeded"
                cache[path] = content
            if len(content) > MAX_VALIDATION_TEXT_CHARS:
                return "source identity unresolved: source exceeds read budget"
            digest = hashlib.sha256(content).hexdigest()
            lines = content.decode("utf-8").splitlines(keepends=True)
            for ref in refs:
                if ref.get("file_bytes_sha256") != digest:
                    return "source identity unresolved: missing or mismatched file-byte hash"
                start, end = ref.get("line_start"), ref.get("line_end")
                if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
                    return "source identity unresolved: invalid source span"
                matching = [item for item in snippets if isinstance(item, dict) and item.get("path") == source and item.get("line_start") == start and item.get("line_end") == end]
                span_text = "".join(lines[start - 1:end])
                for ending in ("\r\n", "\n", "\r"):
                    if span_text.endswith(ending):
                        span_text = span_text[:-len(ending)]
                        break
                if len(matching) != 1 or matching[0].get("text") != span_text:
                    return "source identity unresolved: literal span does not match current source bytes"
            if len(snippets) != len(refs):
                return "source identity unresolved: unbound evidence snippets"
        except (OSError, RuntimeError, ValueError, UnicodeError):
            return "source identity unresolved: source/path/read failure"
        return None

    @staticmethod
    def _read_source_bytes(root: Path, source: str, limit: int) -> bytes:
        """Anchor every open beneath the explicit root, without following links."""
        if not all(hasattr(os, name) for name in ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK")) or os.open not in os.supports_dir_fd:
            raise OSError("secure readroot is unsupported on this platform")
        descriptors: list[int] = []
        try:
            directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            descriptors.append(os.open(root, directory_flags))
            parts = source.split("/")
            for part in parts[:-1]:
                descriptors.append(os.open(part, directory_flags, dir_fd=descriptors[-1]))
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptors[-1])
            descriptors.append(fd)
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise OSError("source is not a regular file")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                return stream.read(limit)
        finally:
            for fd in reversed(descriptors):
                os.close(fd)

    @staticmethod
    def _result(constraint: PatchConstraint, status: str, reason: str, files: list[str], *, evidence: str | None, remediation: str | None = None) -> PatchConstraintValidationResult:
        return PatchConstraintValidationResult(
            constraint_id=constraint.id,
            status=status,
            reason=reason,
            files=files,
            evidence=evidence,
            constraint_type=constraint.type,
            source_refs=constraint.source_refs,
            remediation=remediation or PatchConstraintValidationService._remediation_for_status(status, constraint),
        )

    @staticmethod
    def _remediation_for_status(status: str, constraint: PatchConstraint) -> str | None:
        if status == "violated":
            if constraint.type == "generated_file":
                return "Revert hand edits to generated files and regenerate them from source-of-truth inputs if needed."
            return "Change the patch to comply with the cited constraint or document an explicit exception for review."
        if status in {"unknown", "manual_review"}:
            return "Provide decisive diff/test/source evidence before treating this constraint as satisfied."
        return None

    @staticmethod
    def _packet_confidence(*, total: int, satisfied: int, violated: int, unknown: int, manual_review: int = 0) -> str:
        if total == 0:
            return "low"
        # Confidence describes a bounded supplied comparison, never full policy
        # or provenance certification. Unverified source hints cannot make it high.
        if satisfied or violated:
            return "medium"
        return "low"

    @staticmethod
    def to_dict(packet: PatchConstraintValidationPacket) -> dict[str, Any]:
        return asdict(packet)
