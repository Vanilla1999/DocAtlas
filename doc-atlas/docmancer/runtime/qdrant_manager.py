"""Managed local Qdrant lifecycle.

Owns binary acquisition, port selection, process start/stop, health-check,
and fallback to ``SqliteVecStore`` when a managed Qdrant cannot be brought up.

Resolution order in :func:`ensure_running`:
    1. Explicit ``DOCMANCER_QDRANT_URL`` (caller-supplied managed Qdrant).
    2. Live docmancer-owned process listed in ``runtime.json`` and healthy.
    3. Managed binary start (downloaded or ``DOCMANCER_QDRANT_BINARY``).
    4. ``SqliteVecStore`` fallback when start fails or platform unsupported.

Never reuse a foreign Qdrant on the expected port: the resolver checks for the
docmancer ownership sentinel via runtime state before reusing.
"""
from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import socket
import stat
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from filelock import FileLock

logger = logging.getLogger(__name__)

# Pinned Qdrant version that the artefact matrix was verified against in
# `docs/enterprise-local-rag-pipeline/local-rag-pipeline-todo.md` (Phase 0.0).
PINNED_QDRANT_VERSION = "1.14.1"
_RELEASE_URL_TMPL = "https://github.com/qdrant/qdrant/releases/download/v{ver}/{asset}"

# (system, machine_substring) -> (asset_name, archive_kind, binary_name_in_archive)
_ASSET_MATRIX: dict[tuple[str, str], tuple[str, str, str]] = {
    ("darwin", "arm64"): ("qdrant-aarch64-apple-darwin.tar.gz", "tar.gz", "qdrant"),
    ("darwin", "x86_64"): ("qdrant-x86_64-apple-darwin.tar.gz", "tar.gz", "qdrant"),
    ("linux", "aarch64"): ("qdrant-aarch64-unknown-linux-musl.tar.gz", "tar.gz", "qdrant"),
    ("linux", "arm64"): ("qdrant-aarch64-unknown-linux-musl.tar.gz", "tar.gz", "qdrant"),
    ("linux", "x86_64"): ("qdrant-x86_64-unknown-linux-gnu.tar.gz", "tar.gz", "qdrant"),
    ("linux", "amd64"): ("qdrant-x86_64-unknown-linux-gnu.tar.gz", "tar.gz", "qdrant"),
}

DEFAULT_PORT = 6333
PORT_SCAN_LIMIT = 32
HEALTH_TIMEOUT_S = 30
_OWNERSHIP_TOKEN = "docmancer-managed-qdrant"


@dataclass
class QdrantResolution:
    """Outcome of :func:`ensure_running` describing how the caller should connect."""

    url: str | None
    managed: bool
    fallback: bool = False
    reason: str = ""
    pid: int | None = None
    port: int | None = None


@dataclass
class _Paths:
    home: Path
    binary: Path
    version_manifest: Path
    runtime_json: Path
    pid_file: Path
    logs_dir: Path
    storage_dir: Path
    lock_file: Path
    artefacts_dir: Path

    @classmethod
    def for_home(cls, home: Path) -> "_Paths":
        return cls(
            home=home,
            binary=home / "qdrant",
            version_manifest=home / "version.json",
            runtime_json=home / "runtime.json",
            pid_file=home / "qdrant.pid",
            logs_dir=home / "logs",
            storage_dir=home / "storage",
            lock_file=home / ".lock",
            artefacts_dir=home / "artefacts",
        )


def _docmancer_home() -> Path:
    override = os.environ.get("DOCMANCER_HOME")
    if override:
        base = Path(override).expanduser()
    else:
        base = Path.home() / ".docmancer"
    return base / "qdrant"


def detect_platform() -> tuple[str, str] | None:
    """Return ``(asset, archive_kind)`` for the current platform or ``None``."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    key = (system, machine)
    spec = _ASSET_MATRIX.get(key)
    if spec is None:
        return None
    asset, kind, _ = spec
    return asset, kind


def _proc_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.connect((host, port))
            return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            return False


def _pick_port(start: int = DEFAULT_PORT, limit: int = PORT_SCAN_LIMIT) -> int:
    for offset in range(limit):
        candidate = start + offset
        if not _port_in_use(candidate):
            return candidate
    raise RuntimeError(f"No free port in range {start}..{start + limit - 1}")


def _wait_for_health(url: str, timeout_s: int = HEALTH_TIMEOUT_S) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/readyz", timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        try:
            with urllib.request.urlopen(f"{url}/", timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def _download_url(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=60) as resp, open(tmp, "wb") as fh:
        shutil.copyfileobj(resp, fh)
    tmp.replace(dest)


def _extract_binary(archive: Path, kind: str, dest_binary: Path) -> None:
    dest_binary.parent.mkdir(parents=True, exist_ok=True)
    if kind == "tar.gz":
        with tarfile.open(archive, "r:gz") as tf:
            members = [m for m in tf.getmembers() if m.isfile() and Path(m.name).name == "qdrant"]
            if not members:
                raise RuntimeError(f"qdrant binary not found in archive {archive}")
            member = members[0]
            f = tf.extractfile(member)
            if f is None:
                raise RuntimeError(f"could not read {member.name} from {archive}")
            dest_binary.write_bytes(f.read())
    elif kind == "zip":
        with zipfile.ZipFile(archive) as zf:
            for name in zf.namelist():
                if Path(name).name in {"qdrant", "qdrant.exe"}:
                    dest_binary.write_bytes(zf.read(name))
                    break
            else:
                raise RuntimeError(f"qdrant binary not found in archive {archive}")
    else:
        raise ValueError(f"unsupported archive kind: {kind}")
    dest_binary.chmod(dest_binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@dataclass
class QdrantManager:
    """Manages a single docmancer-owned local Qdrant process.

    Most callers should use :func:`ensure_running`; this class exposes the
    individual lifecycle steps for tests and the ``docmancer qdrant`` CLI.
    """

    home: Path = field(default_factory=_docmancer_home)

    def __post_init__(self) -> None:
        self.paths = _Paths.for_home(self.home)
        self.paths.home.mkdir(parents=True, exist_ok=True)
        self.paths.logs_dir.mkdir(parents=True, exist_ok=True)

    # ------------------ binary acquisition ------------------

    def resolve_binary(self) -> Path | None:
        """Return path to a usable Qdrant binary, or None if unavailable.

        Order: ``DOCMANCER_QDRANT_BINARY`` env var; pre-downloaded managed
        binary; download from GitHub release for supported platforms.
        """
        override = os.environ.get("DOCMANCER_QDRANT_BINARY")
        if override:
            p = Path(override).expanduser()
            if p.is_file():
                return p
            logger.warning("DOCMANCER_QDRANT_BINARY=%s does not exist", override)
            return None

        if self.paths.binary.is_file():
            return self.paths.binary

        spec = detect_platform()
        if spec is None:
            logger.info(
                "qdrant managed binary not available for %s/%s; using sqlite-vec fallback",
                platform.system(),
                platform.machine(),
            )
            return None

        asset, kind = spec
        url = _RELEASE_URL_TMPL.format(ver=PINNED_QDRANT_VERSION, asset=asset)
        archive_path = self.paths.artefacts_dir / asset
        try:
            logger.info("Downloading Qdrant %s from %s", PINNED_QDRANT_VERSION, url)
            _download_url(url, archive_path)
            _extract_binary(archive_path, kind, self.paths.binary)
        except Exception as exc:
            logger.warning("qdrant binary download/extract failed: %s", exc)
            return None
        finally:
            try:
                if archive_path.exists():
                    archive_path.unlink()
            except OSError:
                pass

        _write_json(
            self.paths.version_manifest,
            {
                "version": PINNED_QDRANT_VERSION,
                "asset": asset,
                "installed_at": int(time.time()),
            },
        )
        return self.paths.binary

    # ------------------ process state ------------------

    def status(self) -> dict:
        runtime = _read_json(self.paths.runtime_json) or {}
        pid = runtime.get("pid")
        port = runtime.get("port")
        url = runtime.get("url")
        alive = bool(pid and _proc_alive(int(pid)))
        owned = bool(runtime.get("ownership_token") == _OWNERSHIP_TOKEN)
        healthy = bool(url and _port_in_use(int(port))) if port else False
        return {
            "pid": pid,
            "port": port,
            "url": url,
            "alive": alive,
            "owned": owned,
            "healthy": healthy,
            "version": (_read_json(self.paths.version_manifest) or {}).get("version"),
        }

    def is_running(self) -> bool:
        st = self.status()
        return st["alive"] and st["owned"]

    # ------------------ start / stop ------------------

    def start(self, *, port: int | None = None) -> QdrantResolution:
        with FileLock(str(self.paths.lock_file)):
            existing = self.status()
            if existing["alive"] and existing["owned"]:
                url = existing["url"] or f"http://localhost:{existing['port']}"
                if _wait_for_health(url, timeout_s=2):
                    return QdrantResolution(
                        url=url,
                        managed=True,
                        reason="already-running",
                        pid=existing["pid"],
                        port=existing["port"],
                    )

            binary = self.resolve_binary()
            if binary is None:
                return QdrantResolution(
                    url=None,
                    managed=False,
                    fallback=True,
                    reason="no-binary-available",
                )

            chosen_port = port or _pick_port()
            if _port_in_use(chosen_port):
                # If a process is bound but is *us*, allow reuse via prior branch.
                # Otherwise this is foreign and we refuse the port.
                return QdrantResolution(
                    url=None,
                    managed=False,
                    fallback=True,
                    reason=f"port-{chosen_port}-occupied-by-foreign-process",
                )

            self.paths.storage_dir.mkdir(parents=True, exist_ok=True)
            self.paths.logs_dir.mkdir(parents=True, exist_ok=True)
            stdout_log = self.paths.logs_dir / "qdrant.stdout.log"
            stderr_log = self.paths.logs_dir / "qdrant.stderr.log"
            env = os.environ.copy()
            env["QDRANT__SERVICE__HTTP_PORT"] = str(chosen_port)
            env["QDRANT__STORAGE__STORAGE_PATH"] = str(self.paths.storage_dir)
            env["QDRANT__SERVICE__GRPC_PORT"] = str(chosen_port + 1)
            # Disable Qdrant's anonymous telemetry: the managed binary
            # otherwise opens an outbound connection to a Qdrant-operated
            # endpoint on first start, which triggers a macOS firewall
            # prompt. Honour caller override (e.g. for diagnostics).
            env.setdefault("QDRANT__TELEMETRY_DISABLED", "true")
            try:
                proc = subprocess.Popen(  # noqa: S603 - trusted binary path
                    [str(binary)],
                    cwd=str(self.paths.home),
                    stdout=open(stdout_log, "ab"),
                    stderr=open(stderr_log, "ab"),
                    stdin=subprocess.DEVNULL,
                    env=env,
                    start_new_session=True,
                )
            except OSError as exc:
                logger.warning("qdrant spawn failed: %s", exc)
                return QdrantResolution(
                    url=None,
                    managed=False,
                    fallback=True,
                    reason=f"spawn-failed: {exc}",
                )

            url = f"http://localhost:{chosen_port}"
            healthy = _wait_for_health(url, timeout_s=HEALTH_TIMEOUT_S)
            if not healthy:
                logger.warning("qdrant did not become healthy within %ds", HEALTH_TIMEOUT_S)
                try:
                    proc.terminate()
                except OSError:
                    pass
                return QdrantResolution(
                    url=None,
                    managed=False,
                    fallback=True,
                    reason="health-check-failed",
                )

            self.paths.pid_file.write_text(str(proc.pid), encoding="utf-8")
            _write_json(
                self.paths.runtime_json,
                {
                    "pid": proc.pid,
                    "port": chosen_port,
                    "url": url,
                    "ownership_token": _OWNERSHIP_TOKEN,
                    "started_at": int(time.time()),
                    "version": (_read_json(self.paths.version_manifest) or {}).get("version"),
                },
            )
            return QdrantResolution(
                url=url, managed=True, reason="started", pid=proc.pid, port=chosen_port
            )

    def stop(self) -> bool:
        with FileLock(str(self.paths.lock_file)):
            runtime = _read_json(self.paths.runtime_json) or {}
            if runtime.get("ownership_token") != _OWNERSHIP_TOKEN:
                return False
            pid = runtime.get("pid")
            if not pid or not _proc_alive(int(pid)):
                # clean stale state
                for p in (self.paths.pid_file, self.paths.runtime_json):
                    try:
                        p.unlink()
                    except FileNotFoundError:
                        pass
                return False
            try:
                os.kill(int(pid), 15)
            except OSError:
                return False
            for _ in range(20):
                if not _proc_alive(int(pid)):
                    break
                time.sleep(0.25)
            else:
                try:
                    os.kill(int(pid), 9)
                except OSError:
                    pass
            for p in (self.paths.pid_file, self.paths.runtime_json):
                try:
                    p.unlink()
                except FileNotFoundError:
                    pass
            return True


def ensure_running(*, port: int | None = None) -> QdrantResolution:
    """Resolve a Qdrant URL the caller should connect to.

    See module docstring for the resolution order. Callers should check
    ``QdrantResolution.fallback`` to decide whether to switch to
    ``SqliteVecStore``.
    """
    override_url = os.environ.get("DOCMANCER_QDRANT_URL")
    if override_url:
        return QdrantResolution(
            url=override_url,
            managed=False,
            reason="env-override",
        )

    mgr = QdrantManager()
    st = mgr.status()
    if st["alive"] and st["owned"]:
        url = st["url"] or f"http://localhost:{st['port']}"
        if _wait_for_health(url, timeout_s=2):
            return QdrantResolution(
                url=url,
                managed=True,
                reason="reuse-managed",
                pid=st["pid"],
                port=st["port"],
            )

    return mgr.start(port=port)


__all__ = [
    "ensure_running",
    "QdrantManager",
    "QdrantResolution",
    "PINNED_QDRANT_VERSION",
    "detect_platform",
]
