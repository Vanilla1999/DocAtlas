from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from docmancer._version import __version__
from docmancer.core.product_identity import (
    LEGACY_CONFIG_NAME,
    PRIMARY_CONFIG_NAME,
    PRODUCT_ID,
    STATE_OWNER_FILENAME,
    STATE_SCHEMA_VERSION,
    inspect_state,
    ownership_payload,
)

MIGRATION_RECORD_FILENAME = "migration.json"
DEFAULT_MAX_FILES = 20_000
DEFAULT_MAX_BYTES = 10 * 1024 * 1024 * 1024


class HomeMigrationError(RuntimeError):
    """Raised when a home migration cannot be proven safe."""


@dataclass(frozen=True)
class MigrationEntry:
    source_relative: str
    target_relative: str
    size_bytes: int
    source_sha256: str
    target_sha256: str


@dataclass(frozen=True)
class HomeMigrationPlan:
    source: str
    target: str
    source_classification: str
    target_classification: str
    file_count: int
    total_source_bytes: int
    source_fingerprint: str
    plan_digest: str
    can_apply: bool
    reason: str | None
    entries: tuple[MigrationEntry, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["entries"] = [asdict(entry) for entry in self.entries]
        return payload


@dataclass(frozen=True)
class HomeMigrationResult:
    status: str
    source: str
    target: str
    plan_digest: str
    file_count: int
    total_source_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _rewrite_string(value: str, source: Path, target: Path) -> str:
    source_text = str(source)
    target_text = str(target)
    if value == source_text:
        return target_text
    prefix = source_text + os.sep
    if value.startswith(prefix):
        return target_text + os.sep + value[len(prefix):]
    legacy_tilde = "~/.docmancer"
    if value == legacy_tilde:
        return target_text
    if value.startswith(legacy_tilde + "/"):
        return target_text + os.sep + value[len(legacy_tilde) + 1 :].replace("/", os.sep)
    return value


def _rewrite_config_value(value: Any, source: Path, target: Path) -> Any:
    if isinstance(value, dict):
        return {key: _rewrite_config_value(item, source, target) for key, item in value.items()}
    if isinstance(value, list):
        return [_rewrite_config_value(item, source, target) for item in value]
    if isinstance(value, str):
        return _rewrite_string(value, source, target)
    return value


def _target_bytes(relative: Path, data: bytes, source: Path, target: Path) -> tuple[Path, bytes]:
    if relative.as_posix() != LEGACY_CONFIG_NAME:
        return relative, data
    try:
        loaded = yaml.safe_load(data.decode("utf-8")) or {}
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise HomeMigrationError(f"legacy config cannot be migrated safely: {exc}") from exc
    if not isinstance(loaded, dict):
        raise HomeMigrationError("legacy config cannot be migrated safely: root must be a mapping")
    rewritten = _rewrite_config_value(loaded, source, target)
    rendered = yaml.safe_dump(rewritten, sort_keys=False, allow_unicode=True).encode("utf-8")
    return Path(PRIMARY_CONFIG_NAME), rendered


def _enumerate_entries(
    source: Path,
    target: Path,
    *,
    max_files: int,
    max_bytes: int,
) -> tuple[tuple[MigrationEntry, ...], int]:
    entries: list[MigrationEntry] = []
    total = 0
    target_names: set[str] = set()
    for path in sorted(source.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(source)
        if relative.as_posix() == STATE_OWNER_FILENAME:
            continue
        if path.is_symlink():
            raise HomeMigrationError(f"legacy state contains symlink: {relative.as_posix()}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise HomeMigrationError(f"legacy state contains unsupported file type: {relative.as_posix()}")
        data = path.read_bytes()
        total += len(data)
        if len(entries) + 1 > max_files:
            raise HomeMigrationError(f"legacy state exceeds migration file limit ({max_files})")
        if total > max_bytes:
            raise HomeMigrationError(f"legacy state exceeds migration byte limit ({max_bytes})")
        target_relative, target_data = _target_bytes(relative, data, source, target)
        target_name = target_relative.as_posix()
        if target_name in {STATE_OWNER_FILENAME, MIGRATION_RECORD_FILENAME}:
            raise HomeMigrationError(f"legacy state collides with reserved migration file: {target_name}")
        if target_name in target_names:
            raise HomeMigrationError(f"legacy state maps multiple files to {target_name}")
        target_names.add(target_name)
        entries.append(
            MigrationEntry(
                source_relative=relative.as_posix(),
                target_relative=target_name,
                size_bytes=len(data),
                source_sha256=_sha256(data),
                target_sha256=_sha256(target_data),
            )
        )
    return tuple(entries), total


def _source_fingerprint(entries: tuple[MigrationEntry, ...]) -> str:
    payload = [
        [entry.source_relative, entry.size_bytes, entry.source_sha256]
        for entry in entries
    ]
    return _sha256(_canonical_json(payload))


def _plan_digest_payload(
    *,
    source: Path,
    target: Path,
    source_fingerprint: str,
    entries: tuple[MigrationEntry, ...],
) -> dict[str, Any]:
    return {
        "source": str(source),
        "target": str(target),
        "source_fingerprint": source_fingerprint,
        "entries": [asdict(entry) for entry in entries],
        "state_schema_version": STATE_SCHEMA_VERSION,
    }


def plan_home_migration(
    source: str | Path,
    target: str | Path,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> HomeMigrationPlan:
    raw_source = Path(source).expanduser()
    raw_target = Path(target).expanduser()
    if raw_source.is_symlink() or raw_target.is_symlink():
        raise HomeMigrationError("migration roots must not be symlinks")
    source_path = raw_source.resolve()
    target_path = raw_target.resolve()
    if source_path == target_path:
        raise HomeMigrationError("migration source and target must differ")
    if source_path in target_path.parents or target_path in source_path.parents:
        raise HomeMigrationError("migration source and target must not contain each other")

    source_state = inspect_state(source_path)
    target_state = inspect_state(target_path)
    eligible_source = source_state.classification in {"legacy_docatlas", "owned_docatlas"}
    eligible_target = target_state.classification in {"missing", "empty"}
    if not eligible_source:
        return HomeMigrationPlan(
            str(source_path), str(target_path), source_state.classification,
            target_state.classification, 0, 0, "", "", False,
            "source_not_proven_docatlas", (),
        )
    if not eligible_target:
        return HomeMigrationPlan(
            str(source_path), str(target_path), source_state.classification,
            target_state.classification, 0, 0, "", "", False,
            "target_not_empty_or_unowned", (),
        )

    entries, total = _enumerate_entries(
        source_path, target_path, max_files=max_files, max_bytes=max_bytes
    )
    fingerprint = _source_fingerprint(entries)
    digest = _sha256(_canonical_json(_plan_digest_payload(
        source=source_path,
        target=target_path,
        source_fingerprint=fingerprint,
        entries=entries,
    )))
    return HomeMigrationPlan(
        str(source_path), str(target_path), source_state.classification,
        target_state.classification, len(entries), total, fingerprint, digest,
        True, None, entries,
    )


def _migration_record(target: Path) -> dict[str, Any] | None:
    path = target / MIGRATION_RECORD_FILENAME
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _verify_target_file(path: Path, expected_sha256: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise HomeMigrationError(f"staged migration output missing or unsafe: {path}")
    if _sha256(path.read_bytes()) != expected_sha256:
        raise HomeMigrationError(f"staged migration hash mismatch: {path}")


def _already_applied(plan: HomeMigrationPlan) -> bool:
    source = Path(plan.source)
    target = Path(plan.target)
    state = inspect_state(target)
    if state.classification != "owned_docatlas":
        return False
    record = _migration_record(target) or {}
    if not (
        record.get("source") == plan.source
        and record.get("source_fingerprint") == plan.source_fingerprint
        and record.get("plan_digest") == plan.plan_digest
    ):
        return False
    current_entries, _ = _enumerate_entries(
        source, target, max_files=DEFAULT_MAX_FILES, max_bytes=DEFAULT_MAX_BYTES
    )
    if _source_fingerprint(current_entries) != plan.source_fingerprint:
        raise HomeMigrationError("legacy source changed after migration; refusing to report idempotent success")
    for entry in plan.entries:
        _verify_target_file(target / entry.target_relative, entry.target_sha256)
    return True


def apply_home_migration(plan: HomeMigrationPlan) -> HomeMigrationResult:
    if not plan.can_apply:
        raise HomeMigrationError(f"migration plan is not applicable: {plan.reason}")
    source = Path(plan.source)
    target = Path(plan.target)

    if target.exists() and _already_applied(plan):
        return HomeMigrationResult(
            "already_applied", plan.source, plan.target, plan.plan_digest,
            plan.file_count, plan.total_source_bytes,
        )

    fresh = plan_home_migration(source, target)
    if not fresh.can_apply or fresh.plan_digest != plan.plan_digest:
        raise HomeMigrationError("migration source/target changed after the reviewed plan")

    staging = target.parent / f".{target.name}.migration-{plan.plan_digest[:12]}"
    if staging.exists():
        raise HomeMigrationError(f"stale migration staging directory exists: {staging}")
    staging.mkdir(parents=True, exist_ok=False)
    try:
        by_source = {entry.source_relative: entry for entry in plan.entries}
        for source_relative, entry in by_source.items():
            source_file = source / source_relative
            data = source_file.read_bytes()
            if _sha256(data) != entry.source_sha256:
                raise HomeMigrationError(f"source changed while migrating: {source_relative}")
            relative = Path(source_relative)
            target_relative, target_data = _target_bytes(relative, data, source, target)
            if target_relative.as_posix() != entry.target_relative:
                raise HomeMigrationError(f"migration mapping changed for {source_relative}")
            destination = staging / target_relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(target_data)
            try:
                shutil.copystat(source_file, destination, follow_symlinks=False)
            except OSError:
                pass
            _verify_target_file(destination, entry.target_sha256)

        (staging / STATE_OWNER_FILENAME).write_text(
            json.dumps(ownership_payload(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        record = {
            "product_id": PRODUCT_ID,
            "state_schema_version": STATE_SCHEMA_VERSION,
            "migrated_by_version": __version__,
            "source": plan.source,
            "source_fingerprint": plan.source_fingerprint,
            "plan_digest": plan.plan_digest,
            "source_preserved": True,
        }
        (staging / MIGRATION_RECORD_FILENAME).write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        for entry in plan.entries:
            _verify_target_file(staging / entry.target_relative, entry.target_sha256)
        if inspect_state(staging).classification != "owned_docatlas":
            raise HomeMigrationError("staged migration ownership verification failed")

        if target.exists():
            target_state = inspect_state(target)
            if target_state.classification != "empty":
                raise HomeMigrationError("migration target changed before publish")
            target.rmdir()
        os.replace(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    if inspect_state(target).classification != "owned_docatlas":
        raise HomeMigrationError("published migration ownership verification failed")
    return HomeMigrationResult(
        "applied", plan.source, plan.target, plan.plan_digest,
        plan.file_count, plan.total_source_bytes,
    )


__all__ = [
    "DEFAULT_MAX_BYTES",
    "DEFAULT_MAX_FILES",
    "HomeMigrationError",
    "HomeMigrationPlan",
    "HomeMigrationResult",
    "MIGRATION_RECORD_FILENAME",
    "MigrationEntry",
    "apply_home_migration",
    "plan_home_migration",
]
