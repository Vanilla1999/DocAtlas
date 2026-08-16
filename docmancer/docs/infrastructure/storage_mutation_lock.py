"""Cross-process coordination for index writers and destructive cleanup.

Two lock layers intentionally serve different purposes:

* :func:`storage_mutation_lock` serializes writers of one concrete SQLite
  database.
* writer leases + :func:`storage_cleanup_barrier` coordinate every derived
  index below one storage root without holding an exclusive OS lock during
  network fetches or staging work.

Lock inodes are persistent.  Deleting a lock file on release can split
contending processes across two inodes (one waiter still holds the old inode
while a newcomer creates/locks a new file), defeating mutual exclusion.
"""
from __future__ import annotations

from contextlib import contextmanager
import errno
import json
import os
from pathlib import Path
import sys
import time
from typing import Iterator
import uuid


class StorageMutationBusy(RuntimeError):
    """Raised when another writer/cleanup owns the same derived index."""


def storage_mutation_lock_path(db_path: str | Path) -> Path:
    database = Path(db_path).expanduser().resolve(strict=False)
    return database.parent / f".{database.name}.storage-mutation.lock"


def storage_cleanup_barrier_path(storage_identity: str | Path) -> Path:
    database = Path(storage_identity).expanduser().resolve(strict=False)
    return database.parent / f".{database.name}.cleanup-barrier.lock"


def storage_writer_lease_dir(storage_identity: str | Path) -> Path:
    database = Path(storage_identity).expanduser().resolve(strict=False)
    return database.parent / f".{database.name}.writer-leases"


def _open_lock_file(path: Path) -> int:
    flags = os.O_RDWR | os.O_CREAT
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if nofollow:
        flags |= nofollow
    return os.open(path, flags, 0o600)


def _try_lock(fd: int) -> bool:
    if sys.platform == "win32":  # pragma: win32 cover
        import msvcrt

        if os.fstat(fd).st_size == 0:
            os.write(fd, b"\0")
            os.fsync(fd)
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                return False
            raise
        return True

    import fcntl

    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        if exc.errno in {errno.EACCES, errno.EAGAIN}:
            return False
        raise
    return True


def _unlock(fd: int) -> None:
    if sys.platform == "win32":  # pragma: win32 cover
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(fd, fcntl.LOCK_UN)


@contextmanager
def _persistent_exclusive_lock(
    path: Path,
    *,
    identity: Path,
    timeout: float,
    operation: str,
    create_parent: bool,
) -> Iterator[Path]:
    if create_parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    elif not path.parent.is_dir():
        raise StorageMutationBusy(
            f"{operation} blocked: index storage does not exist for {identity}"
        )

    deadline = time.monotonic() + max(0.0, float(timeout))
    fd = _open_lock_file(path)
    acquired = False
    try:
        while True:
            if _try_lock(fd):
                acquired = True
                break
            if time.monotonic() >= deadline:
                raise StorageMutationBusy(
                    f"{operation} blocked: another index mutation is active for {identity}"
                )
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
        yield path
    finally:
        if acquired:
            _unlock(fd)
        os.close(fd)


@contextmanager
def storage_mutation_lock(
    db_path: str | Path,
    *,
    timeout: float = 0,
    operation: str = "index mutation",
    create_parent: bool = True,
) -> Iterator[Path]:
    """Acquire one persistent-inode exclusive lock for one concrete index."""

    identity = Path(db_path).expanduser().resolve(strict=False)
    with _persistent_exclusive_lock(
        storage_mutation_lock_path(identity),
        identity=identity,
        timeout=timeout,
        operation=operation,
        create_parent=create_parent,
    ) as path:
        yield path


@contextmanager
def storage_cleanup_barrier(
    storage_identity: str | Path,
    *,
    timeout: float = 0,
    operation: str = "index cleanup",
    create_parent: bool = True,
) -> Iterator[Path]:
    """Exclude writer-lease registration while a destructive operation runs."""

    identity = Path(storage_identity).expanduser().resolve(strict=False)
    with _persistent_exclusive_lock(
        storage_cleanup_barrier_path(identity),
        identity=identity,
        timeout=timeout,
        operation=operation,
        create_parent=create_parent,
    ) as path:
        yield path


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


def active_storage_writer_leases(storage_identity: str | Path) -> tuple[str, ...]:
    """Return live writer leases and remove leases whose owning process died.

    Callers that make a destructive decision should invoke this while holding
    :func:`storage_cleanup_barrier`, so a new writer cannot appear between the
    check and the mutation.
    """

    directory = storage_writer_lease_dir(storage_identity)
    if not directory.is_dir():
        return ()
    active: list[str] = []
    for lease in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(lease.read_text(encoding="utf-8"))
            pid = int(payload.get("pid") or 0)
            operation = str(payload.get("operation") or "index writer")
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            active.append(f"unreadable writer lease {lease}")
            continue
        if _pid_alive(pid):
            active.append(f"{operation} (pid {pid})")
            continue
        try:
            lease.unlink()
        except OSError:
            active.append(f"stale writer lease could not be removed: {lease}")
    try:
        directory.rmdir()
    except OSError:
        pass
    return tuple(active)


@contextmanager
def storage_writer_lease(
    storage_identity: str | Path,
    *,
    timeout: float = 0,
    operation: str = "index writer",
) -> Iterator[Path]:
    """Register a bounded writer without holding an exclusive lock for its work.

    Registration/removal are serialized against cleanup. Multiple writers may
    hold leases concurrently; cleanup holds the barrier, checks the lease set,
    and fails closed if any live writer exists.
    """

    identity = Path(storage_identity).expanduser().resolve(strict=False)
    directory = storage_writer_lease_dir(identity)
    lease: Path | None = None
    with storage_cleanup_barrier(
        identity, timeout=timeout, operation=f"{operation} registration",
    ):
        active_storage_writer_leases(identity)
        directory.mkdir(parents=True, exist_ok=True)
        lease = directory / f"{os.getpid()}-{uuid.uuid4().hex}.json"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        if nofollow:
            flags |= nofollow
        fd = os.open(lease, flags, 0o600)
        try:
            payload = {
                "pid": os.getpid(),
                "operation": operation,
                "created_at": time.time(),
            }
            os.write(fd, json.dumps(payload, sort_keys=True).encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
    try:
        yield lease
    finally:
        if lease is not None:
            with storage_cleanup_barrier(
                identity, timeout=max(5.0, float(timeout)), operation=f"{operation} release",
            ):
                try:
                    lease.unlink()
                except FileNotFoundError:
                    pass
                try:
                    directory.rmdir()
                except OSError:
                    pass


__all__ = [
    "StorageMutationBusy",
    "active_storage_writer_leases",
    "storage_cleanup_barrier",
    "storage_cleanup_barrier_path",
    "storage_mutation_lock",
    "storage_mutation_lock_path",
    "storage_writer_lease",
    "storage_writer_lease_dir",
]
