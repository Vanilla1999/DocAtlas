from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid
from typing import Any, Iterable

from filelock import FileLock, Timeout

from docmancer.core.storage_topology import StorageTopologyResolver


_QDRANT_OWNERSHIP_TOKEN = "docmancer-managed-qdrant"
_MAX_FINGERPRINT_ENTRIES = 100_000
_RECOGNIZED_DERIVED_DIRS = (
    "docs-indexes",
    "library-indexes",
    "embeddings-cache",
)


@dataclass(frozen=True)
class CleanupTarget:
    path: str
    kind: str
    fingerprint: str
    exists: bool
    size_bytes: int


@dataclass(frozen=True)
class IndexCleanupPlan:
    scope: str
    config_source: str
    storage_root: str
    db_path: str
    extracted_dir: str
    plan: list[str]
    targets: tuple[CleanupTarget, ...] = ()
    plan_digest: str = ""
    incomplete_reasons: tuple[str, ...] = ()
    blocking_reasons: tuple[str, ...] = ()


class IndexStorageCleanup:
    """Preview and safely remove only derived DocAtlas index state.

    ``clear-index`` is deliberately separate from the older, destructive
    ``doc-atlas clear`` command.  A cleanup plan is previewable, bounded to one
    resolved storage root, fingerprinted, and applied under an exclusive lock.
    Configuration files, MCP registrations, secrets, and unrelated files are
    never part of an index cleanup plan.
    """

    _SCOPES = {"project-local", "global"}

    def preview(
        self,
        *,
        scope: str,
        project_path: str | None = None,
        global_config: Any | None = None,
        global_config_source: str = "global_config",
        global_config_path: str | Path | None = None,
    ) -> IndexCleanupPlan:
        scope = str(scope or "").strip().casefold()
        if scope not in self._SCOPES:
            raise ValueError("scope must be exactly 'project-local' or 'global'")

        if scope == "project-local":
            if not project_path or not project_path.strip():
                raise ValueError("project_path is required for project-local cleanup")
            topology = StorageTopologyResolver().resolve(project_path)
            if topology.config_source != "project_local":
                raise ValueError("project_path must resolve to a project-local Docmancer config")
            root = (topology.project_path / ".docmancer").resolve(strict=False)
            config = topology.config
            config_source = topology.config_source
            config_base = (
                topology.config_path.parent
                if topology.config_path is not None else topology.project_path
            )
        else:
            if project_path:
                raise ValueError("project_path is not allowed for global cleanup")
            if global_config is None:
                raise ValueError("a resolved global Docmancer config is required for global cleanup")
            raw_config_path = (
                Path(global_config_path).expanduser().resolve(strict=False)
                if global_config_path is not None else None
            )
            raw_db = Path(global_config.index.db_path).expanduser()
            root_hint = (
                Path(os.environ["DOCMANCER_HOME"]).expanduser()
                if os.environ.get("DOCMANCER_HOME")
                else raw_config_path.parent
                if raw_config_path is not None
                else raw_db.parent
                if raw_db.is_absolute()
                else Path.home() / ".docmancer"
            )
            root = root_hint.resolve(strict=False)
            config = global_config
            config_source = global_config_source
            config_base = raw_config_path.parent if raw_config_path is not None else root

        self._validate_storage_root(root)
        db_path = self._configured_path(config.index.db_path, base=config_base)
        extracted_value = config.index.extracted_dir
        extracted_dir = (
            self._configured_path(extracted_value, base=config_base)
            if extracted_value
            else (db_path.parent / "extracted").resolve(strict=False)
        )
        self._require_within(root, db_path)
        self._require_within(root, extracted_dir)

        incomplete: list[str] = []
        blockers = self._live_process_blockers(root)
        candidates: list[tuple[Path, str, bool]] = [
            (db_path, "sqlite_index", True),
            (extracted_dir, "extracted_documents", True),
        ]
        for suffix in ("-wal", "-shm", "-journal"):
            sidecar = Path(f"{db_path}{suffix}")
            if sidecar.exists() or sidecar.is_symlink():
                candidates.append((sidecar, "sqlite_sidecar", False))

        for name in _RECOGNIZED_DERIVED_DIRS:
            candidate = (root / name).resolve(strict=False)
            if candidate.exists() or candidate.is_symlink():
                candidates.append((candidate, name.replace("-", "_"), False))

        embedding_cache = self._configured_path(config.embeddings.cache, base=config_base)
        if self._is_within(root, embedding_cache) and (
            embedding_cache.exists() or embedding_cache.is_symlink()
        ):
            candidates.append((embedding_cache, "embeddings_cache", False))

        vector = config.vector_store
        provider = str(vector.provider or "").casefold()
        if provider == "qdrant" and vector.url:
            incomplete.append("remote_qdrant_state_not_deleted")
        qdrant_home = (root / "qdrant").resolve(strict=False)
        if qdrant_home.exists() or qdrant_home.is_symlink():
            if self._owned_qdrant_home(qdrant_home):
                candidates.append((qdrant_home, "managed_qdrant", False))
            else:
                incomplete.append("unowned_local_qdrant_state_not_deleted")
        elif scope == "project-local" and provider == "qdrant" and not vector.url:
            shared_qdrant = (
                Path(os.environ.get("DOCMANCER_HOME") or (Path.home() / ".docmancer"))
                / "qdrant"
            ).expanduser().resolve(strict=False)
            if not self._is_within(root, shared_qdrant) and shared_qdrant.exists():
                incomplete.append("shared_local_qdrant_state_not_deleted")

        sqlite_vec_path = self._sqlite_vec_path(config, root, config_base=config_base)
        if sqlite_vec_path is not None and self._is_within(root, sqlite_vec_path):
            if sqlite_vec_path.exists() or sqlite_vec_path.is_symlink():
                candidates.append((sqlite_vec_path, "sqlite_vec", False))
            for suffix in ("-wal", "-shm", "-journal"):
                sidecar = Path(f"{sqlite_vec_path}{suffix}")
                if sidecar.exists() or sidecar.is_symlink():
                    candidates.append((sidecar, "sqlite_vec_sidecar", False))
        elif sqlite_vec_path is not None and sqlite_vec_path.exists():
            incomplete.append("shared_sqlite_vec_state_not_deleted")

        normalized = self._normalize_targets(root, candidates)
        targets = tuple(
            self._target_snapshot(path, kind)
            for path, kind, _include_missing in normalized
            if _include_missing or path.exists() or path.is_symlink()
        )
        plan_paths = [target.path for target in targets]
        digest = self._plan_digest(
            scope=scope,
            config_source=config_source,
            storage_root=root,
            targets=targets,
            incomplete_reasons=tuple(sorted(set(incomplete))),
            blocking_reasons=tuple(sorted(set(blockers))),
        )
        return IndexCleanupPlan(
            scope=scope,
            config_source=config_source,
            storage_root=str(root),
            db_path=str(db_path),
            extracted_dir=str(extracted_dir),
            plan=plan_paths,
            targets=targets,
            plan_digest=digest,
            incomplete_reasons=tuple(sorted(set(incomplete))),
            blocking_reasons=tuple(sorted(set(blockers))),
        )

    def apply(
        self,
        plan: IndexCleanupPlan,
        *,
        expected_plan_digest: str | None = None,
        allow_incomplete: bool = False,
    ) -> dict[str, Any]:
        root = Path(plan.storage_root).expanduser().resolve(strict=False)
        self._validate_storage_root(root)
        if expected_plan_digest and expected_plan_digest != plan.plan_digest:
            raise ValueError("cleanup plan digest does not match the confirmed preview")
        if plan.blocking_reasons:
            raise RuntimeError("index cleanup blocked: " + "; ".join(plan.blocking_reasons))
        if plan.incomplete_reasons and not allow_incomplete:
            raise RuntimeError(
                "index cleanup plan is incomplete: "
                + "; ".join(plan.incomplete_reasons)
                + "; rerun with allow_incomplete only if retaining that state is intentional"
            )

        lock_path = root.parent / f".{root.name}.index-cleanup.lock"
        lock = FileLock(str(lock_path), timeout=0)
        try:
            lock.acquire()
        except Timeout as exc:
            raise RuntimeError("another index cleanup is already running") from exc

        quarantine = root.parent / f".{root.name}.cleanup-trash-{uuid.uuid4().hex}"
        moved: list[tuple[Path, Path]] = []
        removed: list[str] = []
        quarantine_retained: str | None = None
        try:
            live_blockers = self._live_process_blockers(root)
            if live_blockers:
                raise RuntimeError("index cleanup blocked: " + "; ".join(live_blockers))
            self._validate_plan_is_current(plan)
            quarantine.mkdir(mode=0o700)
            try:
                for index, target in enumerate(plan.targets):
                    source = Path(target.path)
                    self._require_within(root, source.resolve(strict=False))
                    if not source.exists() and not source.is_symlink():
                        continue
                    destination = quarantine / f"{index:04d}-{source.name}"
                    source.rename(destination)
                    moved.append((source, destination))
                    removed.append(str(source))
            except Exception:
                for source, destination in reversed(moved):
                    if destination.exists() or destination.is_symlink():
                        source.parent.mkdir(parents=True, exist_ok=True)
                        destination.rename(source)
                if quarantine.exists():
                    shutil.rmtree(quarantine, ignore_errors=True)
                raise
            try:
                shutil.rmtree(quarantine)
            except OSError:
                # The index is already detached from its live paths. Keep the
                # same-filesystem quarantine for explicit manual removal rather
                # than claiming that rollback remained possible after deletion
                # began.
                quarantine_retained = str(quarantine)
        finally:
            lock.release()
            try:
                lock_path.unlink()
            except OSError:
                pass

        payload = self.payload(
            plan,
            status="applied_with_quarantine_retained" if quarantine_retained else "applied",
        )
        payload["removed"] = removed
        payload["quarantine_retained"] = quarantine_retained
        payload["retained_incomplete_state"] = list(plan.incomplete_reasons) if allow_incomplete else []
        return payload

    @staticmethod
    def payload(plan: IndexCleanupPlan, *, status: str = "preview") -> dict[str, Any]:
        return {**asdict(plan), "status": status}

    def _validate_plan_is_current(self, plan: IndexCleanupPlan) -> None:
        for target in plan.targets:
            current = self._target_snapshot(Path(target.path), target.kind)
            if current.fingerprint != target.fingerprint:
                raise RuntimeError(f"stale cleanup plan: target changed since preview: {target.path}")
        current_blockers = self._live_process_blockers(Path(plan.storage_root))
        current_digest = self._plan_digest(
            scope=plan.scope,
            config_source=plan.config_source,
            storage_root=Path(plan.storage_root),
            targets=plan.targets,
            incomplete_reasons=plan.incomplete_reasons,
            blocking_reasons=tuple(sorted(set(current_blockers))),
        )
        if current_digest != plan.plan_digest:
            raise RuntimeError("stale cleanup plan: storage or process state changed since preview")

    @classmethod
    def _normalize_targets(
        cls,
        root: Path,
        candidates: Iterable[tuple[Path, str, bool]],
    ) -> list[tuple[Path, str, bool]]:
        by_path: dict[Path, tuple[str, bool]] = {}
        for raw, kind, include_missing in candidates:
            path = raw.expanduser().resolve(strict=False)
            cls._require_within(root, path)
            prior = by_path.get(path)
            by_path[path] = (kind, include_missing or bool(prior and prior[1]))
        result: list[tuple[Path, str, bool]] = []
        # Preserve the caller's deterministic priority (primary DB first,
        # extracted documents second) for compatibility with the public CLI.
        # A parent target suppresses later nested targets so quarantine never
        # attempts to move the same bytes twice.
        for raw, _kind, _include_missing in candidates:
            path = raw.expanduser().resolve(strict=False)
            if path not in by_path:
                continue
            if any(parent == path or parent in path.parents for parent, _, _ in result):
                continue
            kind, include_missing = by_path.pop(path)
            result.append((path, kind, include_missing))
        return result

    @classmethod
    def _target_snapshot(cls, path: Path, kind: str) -> CleanupTarget:
        exists = path.exists() or path.is_symlink()
        fingerprint, size = cls._fingerprint(path)
        return CleanupTarget(
            path=str(path), kind=kind, fingerprint=fingerprint,
            exists=exists, size_bytes=size,
        )

    @classmethod
    def _fingerprint(cls, path: Path) -> tuple[str, int]:
        if not path.exists() and not path.is_symlink():
            return "missing", 0
        digest = hashlib.sha256()
        total = 0
        count = 0

        def add(entry: Path, relative: str) -> None:
            nonlocal total, count
            count += 1
            if count > _MAX_FINGERPRINT_ENTRIES:
                raise RuntimeError(f"cleanup target contains too many entries to fingerprint: {path}")
            stat = entry.lstat()
            mode = stat.st_mode
            size = stat.st_size if entry.is_file() and not entry.is_symlink() else 0
            total += size
            link = os.readlink(entry) if entry.is_symlink() else ""
            digest.update(
                f"{relative}\0{mode}\0{stat.st_size}\0{stat.st_mtime_ns}\0{link}\n".encode(
                    "utf-8", errors="surrogateescape"
                )
            )

        add(path, ".")
        if path.is_dir() and not path.is_symlink():
            for child in sorted(path.rglob("*"), key=lambda item: item.as_posix()):
                add(child, child.relative_to(path).as_posix())
        return digest.hexdigest(), total

    @staticmethod
    def _plan_digest(
        *,
        scope: str,
        config_source: str,
        storage_root: Path,
        targets: Iterable[CleanupTarget],
        incomplete_reasons: Iterable[str],
        blocking_reasons: Iterable[str],
    ) -> str:
        payload = {
            "scope": scope,
            "config_source": config_source,
            "storage_root": str(storage_root),
            "targets": [asdict(target) for target in targets],
            "incomplete_reasons": list(incomplete_reasons),
            "blocking_reasons": list(blocking_reasons),
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _configured_path(value: str | Path, *, base: Path) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = base / path
        return path.resolve(strict=False)

    @classmethod
    def _sqlite_vec_path(
        cls, config: Any, root: Path, *, config_base: Path,
    ) -> Path | None:
        provider = str(config.vector_store.provider or "").casefold()
        options = config.vector_store.options or {}
        configured = options.get("db_path")
        if configured:
            return cls._configured_path(str(configured), base=config_base)
        if provider == "sqlite-vec":
            return (root / "sqlite-vec.db").resolve(strict=False)
        return None

    @staticmethod
    def _owned_qdrant_home(path: Path) -> bool:
        runtime = path / "runtime.json"
        if not runtime.is_file():
            return False
        try:
            payload = json.loads(runtime.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return payload.get("ownership_token") == _QDRANT_OWNERSHIP_TOKEN

    @classmethod
    def _live_process_blockers(cls, root: Path) -> list[str]:
        if not root.exists() or not root.is_dir():
            return []
        blockers: list[str] = []
        pid_files = sorted({
            *root.glob("*.pid"),
            *root.glob("run/*.pid"),
            *root.glob("qdrant/*.pid"),
        })
        for pid_file in pid_files:
            try:
                pid = int(pid_file.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                continue
            if cls._pid_alive(pid):
                blockers.append(f"live process {pid} recorded by {pid_file}")
        return blockers

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True

    @staticmethod
    def _validate_storage_root(root: Path) -> None:
        root = root.expanduser().resolve(strict=False)
        dangerous = {
            Path(root.anchor).resolve(strict=False),
            Path.home().resolve(strict=False),
            Path.cwd().resolve(strict=False),
        }
        if root in dangerous or not root.name:
            raise ValueError(f"refusing dangerous Docmancer storage root: {root}")

    @staticmethod
    def _is_within(root: Path, target: Path) -> bool:
        return target == root or root in target.parents

    @classmethod
    def _require_within(cls, root: Path, target: Path) -> None:
        if not cls._is_within(root, target):
            raise ValueError(
                f"refusing cleanup target outside resolved Docmancer storage root: {target}"
            )
