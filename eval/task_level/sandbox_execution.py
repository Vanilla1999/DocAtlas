from __future__ import annotations

import hashlib
import json
import os
import selectors
import shlex
import signal
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Sequence


_STDOUT_LIMIT = 1_000_000
_STDERR_LIMIT = 250_000


@dataclass(frozen=True)
class SandboxCommandResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    wall_time_seconds: float
    boundary: dict[str, object]

    @property
    def passed(self) -> bool:
        return self.returncode == 0


class DockerCommandSandbox:
    """Execute evaluator-owned commands without exposing host credentials or files.

    Only the ephemeral task workspace is mounted.  The container has no network,
    no additional capabilities, a read-only root filesystem, and bounded output,
    time, memory, and process counts.  A named container lets the host remove the
    entire PID namespace when a deadline or output ceiling is reached.
    """

    def __init__(self, image: str, *, docker: str = "docker") -> None:
        self.image = image.strip()
        self.docker = docker
        self._verification: dict[str, object] | None = None
        self._last_cleanup_verified = False

    @classmethod
    def from_environment(cls) -> DockerCommandSandbox:
        return cls(os.environ.get("TASK33C_TEST_CONTAINER_IMAGE", ""))

    def verify(self) -> dict[str, object]:
        if self._verification is not None:
            return dict(self._verification)
        if not self.image:
            return {"schema_version": 1, "status": "unavailable", "reason": "TASK33C_TEST_CONTAINER_IMAGE is unset"}
        try:
            inspected = subprocess.run(
                [self.docker, "image", "inspect", "--format", "{{.Id}}", self.image],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return {"schema_version": 1, "status": "unavailable", "reason": f"{exc.__class__.__name__}: {exc}"}
        if inspected.returncode != 0 or not inspected.stdout.strip():
            return {"schema_version": 1, "status": "unavailable", "reason": inspected.stderr[-2_000:]}

        with tempfile.TemporaryDirectory(prefix="task33c-sandbox-canary-") as raw_workspace:
            workspace = Path(raw_workspace)
            command = (
                "python", "-c",
                "import json,os,socket,pathlib,subprocess,time;"
                "root_ok=False;workspace_ok=False;net_ok=False;"
                "\ntry:pathlib.Path('/etc/task33c-write').write_text('x')"
                "\nexcept OSError:root_ok=True"
                "\ntry:pathlib.Path('/workspace/task33c-write').write_text('x')"
                "\nexcept OSError:workspace_ok=True"
                "\ntry:socket.create_connection(('1.1.1.1',53),.25)"
                "\nexcept OSError:net_ok=True"
                "\nchild=subprocess.Popen(['python','-c','import time;time.sleep(30)'],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);"
                "print(json.dumps({'root_read_only':root_ok,'network_denied':net_ok,"
                "'host_secret_absent':os.environ.get('GITHUB_TOKEN') is None and os.environ.get('TASK33C_SECRET_CANARY') is None,"
                "'workspace_read_only':pathlib.Path('/workspace').is_dir() and workspace_ok,"
                "'host_root_absent':not pathlib.Path('/host').exists(),'detached_pid':child.pid}))",
            )
            try:
                result = self._run(command, workspace, timeout_seconds=8)
                row = json.loads(result.stdout.strip().splitlines()[-1])
            except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError, TimeoutError, RuntimeError) as exc:
                return {
                    "schema_version": 1,
                    "status": "failed",
                    "image": self.image,
                    "image_id": inspected.stdout.strip(),
                    "reason": f"canary:{exc.__class__.__name__}:{exc}",
                }
            detached_container_removed = self._last_cleanup_verified
            output_limit_enforced = False
            output_container_removed = False
            timeout_enforced = False
            timeout_container_removed = False
            try:
                self._run(
                    ("python", "-c", f"import sys;sys.stdout.write('x'*{_STDOUT_LIMIT + 1})"),
                    workspace,
                    timeout_seconds=8,
                )
            except RuntimeError as exc:
                output_limit_enforced = "stdout exceeded" in str(exc)
                output_container_removed = self._last_cleanup_verified
            try:
                self._run(("python", "-c", "import time;time.sleep(5)"), workspace, timeout_seconds=0.5)
            except TimeoutError:
                timeout_enforced = True
                timeout_container_removed = self._last_cleanup_verified
        checks = {
            key: row.get(key) is True
            for key in ("root_read_only", "network_denied", "host_secret_absent", "workspace_read_only", "host_root_absent")
        }
        checks["detached_descendant_contained"] = (
            isinstance(row.get("detached_pid"), int)
            and not isinstance(row.get("detached_pid"), bool)
            and result.wall_time_seconds < 8
        )
        checks["output_limit_enforced"] = output_limit_enforced
        checks["timeout_enforced"] = timeout_enforced
        checks["container_removed_after_exit"] = all((
            detached_container_removed,
            output_container_removed,
            timeout_container_removed,
        ))
        self._verification = {
            "schema_version": 1,
            "status": "verified" if all(checks.values()) and result.returncode == 0 else "failed",
            "image": self.image,
            "image_id": inspected.stdout.strip(),
            "image_id_sha256": hashlib.sha256(inspected.stdout.strip().encode()).hexdigest(),
            "checks": checks,
            "container_exit_code": result.returncode,
            "containment": "docker_pid_namespace_removed_with_named_container",
            "environment_policy": "allowlist_only; host environment is never forwarded",
        }
        return dict(self._verification)

    def run(self, command: Sequence[str] | str, workspace: Path, timeout_seconds: float) -> SandboxCommandResult:
        boundary = self.verify()
        if boundary.get("status") != "verified":
            raise RuntimeError("Docker command sandbox is not verified")
        argv = tuple(shlex.split(command) if isinstance(command, str) else command)
        return self._run(normalize_python_test_command(argv), workspace, timeout_seconds=timeout_seconds, boundary=boundary)

    def _run(
        self,
        command: Sequence[str],
        workspace: Path,
        *,
        timeout_seconds: float,
        boundary: dict[str, object] | None = None,
    ) -> SandboxCommandResult:
        if timeout_seconds <= 0:
            raise TimeoutError("sandbox command deadline expired")
        self._last_cleanup_verified = False
        workspace = workspace.resolve()
        if not workspace.is_dir():
            raise ValueError("sandbox workspace does not exist")
        name = "task33c-" + uuid.uuid4().hex
        uid = os.getuid() if hasattr(os, "getuid") else 65534
        gid = os.getgid() if hasattr(os, "getgid") else 65534
        argv = [
            self.docker, "run", "--name", name, "--rm",
            "--network", "none", "--read-only", "--pids-limit", "128",
            "--memory", "1g", "--cpus", "2", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--user", f"{uid}:{gid}",
            "--tmpfs", f"/tmp:rw,nosuid,nodev,noexec,size=128m,uid={uid},gid={gid}",
            "--env", "HOME=/tmp", "--env", "PYTHONDONTWRITEBYTECODE=1",
            "--env", "PYTHONNOUSERSITE=1", "--env", "PYTEST_ADDOPTS=-p no:cacheprovider",
            "--workdir", "/workspace",
            "--mount", f"type=bind,src={workspace},dst=/workspace,readonly",
            self.image, *command,
        ]
        started = time.monotonic()
        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            env={"PATH": os.environ.get("PATH", "")},
        )
        stdout, stderr = bytearray(), bytearray()
        selector = selectors.DefaultSelector()
        assert process.stdout is not None and process.stderr is not None
        selector.register(process.stdout, selectors.EVENT_READ, (stdout, _STDOUT_LIMIT, "stdout"))
        selector.register(process.stderr, selectors.EVENT_READ, (stderr, _STDERR_LIMIT, "stderr"))
        failure: Exception | None = None
        try:
            while selector.get_map():
                remaining = timeout_seconds - (time.monotonic() - started)
                if remaining <= 0:
                    raise TimeoutError("sandbox command exceeded absolute deadline")
                for key, _mask in selector.select(min(remaining, 0.25)):
                    target, limit, label = key.data
                    chunk = os.read(key.fileobj.fileno(), 65_536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    target.extend(chunk)
                    if len(target) > limit:
                        raise RuntimeError(f"sandbox {label} exceeded {limit} bytes")
            remaining = timeout_seconds - (time.monotonic() - started)
            if remaining <= 0:
                raise TimeoutError("sandbox command exceeded absolute deadline")
            returncode = process.wait(timeout=remaining)
            if self._container_exists(name):
                self._remove_container(name)
                raise RuntimeError("sandbox container survived command completion")
            self._last_cleanup_verified = True
        except Exception as exc:
            failure = exc
            self._remove_container(name)
            self._last_cleanup_verified = not self._container_exists(name)
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            process.wait(timeout=10)
            if not self._last_cleanup_verified:
                raise RuntimeError("sandbox container cleanup could not be verified") from exc
            raise
        finally:
            selector.close()
            if failure is None and process.poll() is None:
                self._remove_container(name)
        return SandboxCommandResult(
            command=tuple(command),
            returncode=returncode,
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
            wall_time_seconds=round(time.monotonic() - started, 6),
            boundary=boundary or {},
        )

    def _remove_container(self, name: str) -> None:
        try:
            subprocess.run(
                [self.docker, "rm", "--force", name],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            pass

    def _container_exists(self, name: str) -> bool:
        try:
            inspected = subprocess.run(
                [self.docker, "container", "inspect", name],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return True
        return inspected.returncode == 0


def normalize_python_test_command(command: Sequence[str]) -> tuple[str, ...]:
    argv = tuple(command)
    if len(argv) >= 4 and argv[:3] == ("uv", "run", "--offline") and argv[3] == "pytest":
        return ("python", "-m", "pytest", *argv[4:])
    if argv and Path(argv[0]).name.startswith("python"):
        return ("python", *argv[1:])
    return argv


@lru_cache(maxsize=4)
def verified_task33_sandbox(image: str) -> tuple[DockerCommandSandbox, dict[str, object]]:
    sandbox = DockerCommandSandbox(image)
    return sandbox, sandbox.verify()


def persist_boundary(path: Path, boundary: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(boundary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
