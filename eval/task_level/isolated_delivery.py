from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import resource
import re
import selectors
import shutil
import signal
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from functools import cached_property
from pathlib import Path
from typing import Any, Callable, Protocol

from docmancer.docs.application.action_packet import (
    ACTION_PACKET_SCHEMA_VERSION,
    HARD_ACTION_PACKET_TOKENS,
    validate_action_packet,
)


class IsolatedDeliveryError(RuntimeError):
    """A fail-closed host capability or worker-result failure."""


_TASK33_QUERY_STOP_WORDS = frozenset({
    "after", "also", "and", "are", "can", "consistently", "continue", "decisions",
    "deferred", "do", "does", "fix", "for", "from", "have", "into", "local", "not",
    "one", "outcomes", "path", "paths", "reach", "related", "result", "shared", "so",
    "the", "through", "use", "users", "while", "with",
})
_TASK33_DOMAIN_DETAIL_TERMS = (
    "offline", "sync", "architecture", "partial", "handoff", "deferred",
)
TASK33_QUERY_DERIVATION = "task33c-domain-coverage-v3"


def derive_task33_retrieval_query(task_objective: str) -> str:
    """Derive a frozen project-doc query from the brief without evaluator hints."""

    if not isinstance(task_objective, str) or not task_objective.strip():
        raise IsolatedDeliveryError("invalid_task_objective_for_query_derivation")
    words = [
        token.casefold().strip("-_")
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", task_objective)
    ]
    candidates = [word for word in words if len(word) >= 4 and word not in _TASK33_QUERY_STOP_WORDS]
    counts = {word: candidates.count(word) for word in set(candidates)}
    selected: list[str] = []
    for word in candidates:
        if counts[word] >= 2 and word not in selected:
            selected.append(word)
    # Repeated domain terms anchor the query. Add at most two objective-owned
    # domain details so the query spans offline/sync behavior without turning
    # every narrative word into a completeness requirement.
    if selected:
        for word in _TASK33_DOMAIN_DETAIL_TERMS:
            if word in candidates and word not in selected:
                selected.append(word)
            if len(selected) >= 6:
                break
    else:
        for word in candidates:
            if word not in selected:
                selected.append(word)
            if len(selected) >= 6:
                break
    query = " ".join(selected[:6])
    if not query:
        raise IsolatedDeliveryError("task33_retrieval_query_derivation_empty")
    return query


@dataclass(frozen=True)
class IsolatedWorkerCapabilities:
    fresh_context: bool
    read_only_documentation: bool
    recursive_delegation_disabled: bool
    hard_timeout: bool
    token_accounting: bool
    host_owned_evidence: bool = False
    network_disabled: bool = False
    descendant_containment: bool = False

    @property
    def verified(self) -> bool:
        return all(value is True for value in asdict(self).values())


@dataclass(frozen=True)
class DelegationEnvelope:
    task_objective: str
    suspected_modules: tuple[str, ...]
    changed_files: tuple[str, ...]
    required_evidence_categories: tuple[str, ...]
    project_revision: str
    index_revision: str
    packet_schema_version: int = ACTION_PACKET_SCHEMA_VERSION
    token_budget: int = 1_500
    schema_version: int = 1

    def validate(self) -> None:
        if isinstance(self.schema_version, bool) or self.schema_version != 1:
            raise IsolatedDeliveryError("unsupported_delegation_schema")
        if isinstance(self.packet_schema_version, bool) or self.packet_schema_version != ACTION_PACKET_SCHEMA_VERSION:
            raise IsolatedDeliveryError("unsupported_action_packet_schema")
        if not isinstance(self.task_objective, str) or not self.task_objective.strip() or len(self.task_objective) > 1_000:
            raise IsolatedDeliveryError("invalid_task_objective")
        if (
            not isinstance(self.project_revision, str) or not isinstance(self.index_revision, str)
            or not self.project_revision.strip() or not self.index_revision.strip()
            or len(self.project_revision) > 200 or len(self.index_revision) > 200
        ):
            raise IsolatedDeliveryError("missing_revision_identity")
        if (
            isinstance(self.token_budget, bool) or not isinstance(self.token_budget, int)
            or not 128 <= self.token_budget <= HARD_ACTION_PACKET_TOKENS
        ):
            raise IsolatedDeliveryError("invalid_token_budget")
        if not isinstance(self.required_evidence_categories, tuple) or not self.required_evidence_categories:
            raise IsolatedDeliveryError("missing_required_evidence_categories")
        for field_name in ("suspected_modules", "changed_files", "required_evidence_categories"):
            values = getattr(self, field_name)
            if (
                not isinstance(values, tuple) or len(values) > 32
                or any(
                    not isinstance(value, str) or not value.strip()
                    or value != value.strip() or len(value) > 500
                    for value in values
                )
                or len(set(values)) != len(values)
            ):
                raise IsolatedDeliveryError(f"invalid_{field_name}")
        encoded = json.dumps(asdict(self), ensure_ascii=False, sort_keys=True).encode("utf-8")
        if len(encoded) > 12_000:
            raise IsolatedDeliveryError("delegation_envelope_too_large")

    def to_json(self) -> dict[str, Any]:
        self.validate()
        return {
            **asdict(self),
            "suspected_modules": list(self.suspected_modules),
            "changed_files": list(self.changed_files),
            "required_evidence_categories": list(self.required_evidence_categories),
        }

    @property
    def fingerprint(self) -> str:
        return _json_sha256(self.to_json())


@dataclass(frozen=True)
class HostEvidenceSnapshot:
    """Immutable retrieval result owned and counted by the benchmark host."""

    query: str
    objective_sha256: str
    query_derivation: str
    evidence_items: tuple[dict[str, Any], ...]
    trust_contract: dict[str, Any]
    retrieval_issues: tuple[str, ...]
    evidence_categories: tuple[str, ...]
    project_revision: str
    index_revision: str
    response_status: str
    raw_retrieval_tokens: int
    retrieval_wall_time_seconds: float
    retrieval_calls: int = 1
    schema_version: int = 1

    @property
    def fingerprint(self) -> str:
        return _json_sha256(self.to_json(include_content=True))

    def validate(self, envelope: DelegationEnvelope | None = None) -> None:
        if isinstance(self.schema_version, bool) or self.schema_version != 1:
            raise IsolatedDeliveryError("unsupported_host_evidence_schema")
        if not isinstance(self.query, str) or not self.query.strip() or len(self.query) > 1_000:
            raise IsolatedDeliveryError("invalid_host_retrieval_query")
        if not isinstance(self.objective_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", self.objective_sha256):
            raise IsolatedDeliveryError("invalid_host_objective_fingerprint")
        if self.query_derivation != TASK33_QUERY_DERIVATION:
            raise IsolatedDeliveryError("unsupported_host_query_derivation")
        if (
            isinstance(self.retrieval_calls, bool)
            or not isinstance(self.retrieval_calls, int)
            or self.retrieval_calls != 1
        ):
            raise IsolatedDeliveryError("host_must_retrieve_exactly_once")
        if not isinstance(self.response_status, str) or self.response_status != "success":
            raise IsolatedDeliveryError(f"host_retrieval_not_successful:{self.response_status}")
        if not isinstance(self.evidence_items, tuple) or not self.evidence_items:
            raise IsolatedDeliveryError("host_retrieval_returned_no_evidence")
        if any(not isinstance(item, dict) for item in self.evidence_items):
            raise IsolatedDeliveryError("invalid_host_evidence_item")
        if not isinstance(self.trust_contract, dict):
            raise IsolatedDeliveryError("invalid_host_trust_contract")
        if (
            not isinstance(self.retrieval_issues, tuple)
            or len(self.retrieval_issues) > 64
            or any(not isinstance(issue, str) or not issue.strip() or len(issue) > 1_000 for issue in self.retrieval_issues)
        ):
            raise IsolatedDeliveryError("invalid_host_retrieval_issues")
        if (
            isinstance(self.raw_retrieval_tokens, bool)
            or not isinstance(self.raw_retrieval_tokens, int)
            or self.raw_retrieval_tokens < 0
        ):
            raise IsolatedDeliveryError("invalid_host_raw_retrieval_tokens")
        if (
            isinstance(self.retrieval_wall_time_seconds, bool)
            or not isinstance(self.retrieval_wall_time_seconds, (int, float))
            or not math.isfinite(float(self.retrieval_wall_time_seconds))
            or self.retrieval_wall_time_seconds < 0
        ):
            raise IsolatedDeliveryError("invalid_host_retrieval_wall_time")
        if (
            not isinstance(self.project_revision, str) or not isinstance(self.index_revision, str)
            or not self.project_revision.strip() or not self.index_revision.strip()
        ):
            raise IsolatedDeliveryError("missing_host_revision_identity")
        if (
            not isinstance(self.evidence_categories, tuple) or not self.evidence_categories
            or any(not isinstance(category, str) or not category.strip() for category in self.evidence_categories)
            or len(set(self.evidence_categories)) != len(self.evidence_categories)
        ):
            raise IsolatedDeliveryError("invalid_host_evidence_categories")
        encoded = json.dumps(self.to_json(include_content=True), ensure_ascii=False, sort_keys=True).encode("utf-8")
        if len(encoded) > 2_000_000:
            raise IsolatedDeliveryError("host_evidence_snapshot_too_large")
        if envelope is not None:
            expected_objective_sha256 = hashlib.sha256(envelope.task_objective.encode("utf-8")).hexdigest()
            if self.objective_sha256 != expected_objective_sha256:
                raise IsolatedDeliveryError("host_objective_fingerprint_mismatch")
            if self.query != derive_task33_retrieval_query(envelope.task_objective):
                raise IsolatedDeliveryError("host_query_derivation_mismatch")
            if self.project_revision != envelope.project_revision or self.index_revision != envelope.index_revision:
                raise IsolatedDeliveryError("host_evidence_revision_mismatch")
            missing = sorted(set(envelope.required_evidence_categories) - set(self.evidence_categories))
            if missing:
                raise IsolatedDeliveryError("host_evidence_categories_missing:" + ",".join(missing))

    def manifest(self) -> dict[str, Any]:
        rows = []
        for index, item in enumerate(self.evidence_items):
            rows.append({
                "index": index,
                "path": _source_path(item),
                "section": _source_section(item),
                "content_sha256": hashlib.sha256(str(item.get("content") or "").encode("utf-8")).hexdigest(),
                "item_sha256": _json_sha256(item),
            })
        return {
            "schema_version": 1,
            "query_sha256": hashlib.sha256(self.query.encode("utf-8")).hexdigest(),
            "objective_sha256": self.objective_sha256,
            "query_derivation": self.query_derivation,
            "evidence_fingerprint": self.fingerprint,
            "evidence_categories": list(self.evidence_categories),
            "project_revision": self.project_revision,
            "index_revision": self.index_revision,
            "response_status": self.response_status,
            "retrieval_calls": self.retrieval_calls,
            "raw_retrieval_tokens": self.raw_retrieval_tokens,
            "retrieval_wall_time_seconds": self.retrieval_wall_time_seconds,
            "retrieval_issues": list(self.retrieval_issues),
            "items": rows,
        }

    def to_json(self, *, include_content: bool) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "query": self.query,
            "objective_sha256": self.objective_sha256,
            "query_derivation": self.query_derivation,
            "trust_contract": self.trust_contract,
            "retrieval_issues": list(self.retrieval_issues),
            "evidence_categories": list(self.evidence_categories),
            "project_revision": self.project_revision,
            "index_revision": self.index_revision,
            "response_status": self.response_status,
            "raw_retrieval_tokens": self.raw_retrieval_tokens,
            "retrieval_wall_time_seconds": self.retrieval_wall_time_seconds,
            "retrieval_calls": self.retrieval_calls,
        }
        if include_content:
            payload["evidence_items"] = list(self.evidence_items)
        else:
            payload["evidence_manifest"] = self.manifest()["items"]
        return payload

    def worker_payload(self, envelope: DelegationEnvelope) -> dict[str, Any]:
        self.validate(envelope)
        return {
            "schema_version": 1,
            "envelope": envelope.to_json(),
            "host_evidence": {
                "fingerprint": self.fingerprint,
                "items": list(self.evidence_items),
                "trust_contract": self.trust_contract,
                "retrieval_issues": list(self.retrieval_issues),
                "categories": list(self.evidence_categories),
            },
        }


@dataclass(frozen=True)
class WorkerUsage:
    provider: str
    model: str
    request_id: str
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int | None = None
    proof: dict[str, Any] | None = None

    def validate(self) -> None:
        for key in ("provider", "model", "request_id"):
            value = getattr(self, key)
            if not isinstance(value, str) or not value.strip() or len(value) > 300:
                raise IsolatedDeliveryError(f"invalid_worker_usage_{key}")
        for key in ("input_tokens", "output_tokens", "reasoning_tokens"):
            value = getattr(self, key)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise IsolatedDeliveryError(f"invalid_worker_usage_{key}")
        if not isinstance(self.proof, dict) or self.proof.get("schema_version") != 1:
            raise IsolatedDeliveryError("missing_verified_worker_usage_proof")
        expected = {
            "provider": self.provider,
            "model": self.model,
            "request_id": self.request_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_tokens": self.reasoning_tokens,
        }
        if any(self.proof.get(key) != value for key, value in expected.items()):
            raise IsolatedDeliveryError("worker_usage_proof_mismatch")

    @property
    def proof_fingerprint(self) -> str:
        self.validate()
        return _json_sha256(self.proof)

    @classmethod
    def from_json(cls, value: Any) -> "WorkerUsage":
        if not isinstance(value, dict) or set(value) != {
            "provider", "model", "request_id", "input_tokens", "output_tokens", "reasoning_tokens", "proof",
        }:
            raise IsolatedDeliveryError("invalid_worker_usage_contract")
        for key in ("provider", "model", "request_id"):
            if not isinstance(value.get(key), str) or not value[key].strip() or len(value[key]) > 300:
                raise IsolatedDeliveryError(f"invalid_worker_usage_{key}")
        for key in ("input_tokens", "output_tokens", "reasoning_tokens"):
            item = value.get(key)
            if item is not None and (isinstance(item, bool) or not isinstance(item, int) or item < 0):
                raise IsolatedDeliveryError(f"invalid_worker_usage_{key}")
        if value["reasoning_tokens"] is None:
            reasoning = None
        else:
            reasoning = int(value["reasoning_tokens"])
        result = cls(
            provider=value["provider"],
            model=value["model"],
            request_id=value["request_id"],
            input_tokens=value["input_tokens"],
            output_tokens=value["output_tokens"],
            reasoning_tokens=reasoning,
            proof=value["proof"],
        )
        result.validate()
        return result


@dataclass(frozen=True)
class IsolatedWorkerOutput:
    packet: dict[str, Any]
    usage: WorkerUsage
    wall_time_seconds: float


class IsolatedWorker(Protocol):
    capabilities: IsolatedWorkerCapabilities
    compressor_identity: str
    command_fingerprint: str
    sandbox_identity: str
    capability_evidence: dict[str, Any]
    usage_verifier_identity: str

    def run(
        self,
        envelope: DelegationEnvelope,
        evidence: HostEvidenceSnapshot,
        *,
        timeout_seconds: int,
    ) -> IsolatedWorkerOutput:
        """Compress host-owned evidence in one fresh sandboxed process."""


@dataclass(frozen=True)
class JsonSubprocessIsolatedWorker:
    """Bubblewrap-isolated JSON compressor with host-owned evidence input.

    The worker receives the delegation envelope plus a frozen evidence snapshot.
    It has no repository/index mount and cannot claim retrieval count or evidence.
    """

    command: tuple[str, ...]
    compressor_identity: str
    environment: dict[str, str]
    sandbox_executable: str = "/usr/bin/bwrap"
    max_output_bytes: int = 1_000_000
    max_error_bytes: int = 256_000
    max_input_bytes: int = 2_000_000
    memory_limit_bytes: int = 768 * 1024 * 1024
    process_limit: int = 64
    usage_verifier: Callable[[Any], WorkerUsage] | None = None
    usage_verifier_identity: str = ""

    @cached_property
    def capability_evidence(self) -> dict[str, Any]:
        return self._probe_sandbox()

    @property
    def capabilities(self) -> IsolatedWorkerCapabilities:
        available = self.capability_evidence.get("status") == "verified"
        usage_verified = available and callable(self.usage_verifier) and bool(self.usage_verifier_identity.strip())
        return IsolatedWorkerCapabilities(
            fresh_context=available,
            read_only_documentation=available,
            recursive_delegation_disabled=available,
            hard_timeout=available,
            token_accounting=usage_verified,
            host_owned_evidence=available,
            network_disabled=available,
            descendant_containment=available,
        )

    @property
    def command_fingerprint(self) -> str:
        executable = Path(self.command[0]).resolve() if self.command else Path("/")
        executable_hash = _file_sha256(executable) if executable.is_file() else "missing"
        return _json_sha256({"command": list(self.command), "executable_sha256": executable_hash})

    @property
    def sandbox_identity(self) -> str:
        sandbox = Path(self.sandbox_executable)
        return f"bubblewrap:{_file_sha256(sandbox) if sandbox.is_file() else 'missing'}"

    def run(
        self,
        envelope: DelegationEnvelope,
        evidence: HostEvidenceSnapshot,
        *,
        timeout_seconds: int,
    ) -> IsolatedWorkerOutput:
        envelope.validate()
        evidence.validate(envelope)
        if not self.capabilities.verified:
            raise IsolatedDeliveryError("isolated_worker_os_sandbox_unavailable")
        if not self.command or not os.path.isabs(self.command[0]):
            raise IsolatedDeliveryError("worker_command_must_be_absolute")
        executable = Path(self.command[0]).resolve()
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise IsolatedDeliveryError("worker_command_not_found")
        if not _is_system_worker_path(executable):
            raise IsolatedDeliveryError("worker_command_must_be_installed_outside_workspace")
        payload = json.dumps(evidence.worker_payload(envelope), ensure_ascii=False, sort_keys=True).encode("utf-8")
        if len(payload) > self.max_input_bytes:
            raise IsolatedDeliveryError("isolated_worker_input_too_large")

        started = time.monotonic()
        deadline = started + timeout_seconds
        with tempfile.TemporaryDirectory(prefix="docatlas-isolated-worker-") as temp_dir:
            empty_work = Path(temp_dir) / "empty-work"
            empty_work.mkdir(mode=0o700)
            sandbox_command = self._sandbox_command(executable, empty_work)
            child_environment = {
                "HOME": "/tmp",
                "LANG": "C.UTF-8",
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                **self.environment,
            }
            process = subprocess.Popen(
                sandbox_command,
                env=child_environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                bufsize=0,
                preexec_fn=_limit_worker_resources(
                    timeout_seconds=timeout_seconds,
                    memory_limit_bytes=self.memory_limit_bytes,
                    process_limit=self.process_limit,
                ),
            )
            stdout, _stderr = _communicate_bounded(
                process,
                payload,
                deadline=deadline,
                max_stdout_bytes=self.max_output_bytes,
                max_stderr_bytes=self.max_error_bytes,
            )
        wall = round(time.monotonic() - started, 6)
        if process.returncode != 0:
            raise IsolatedDeliveryError(f"isolated_worker_failed:{process.returncode}")
        try:
            value = json.loads(stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise IsolatedDeliveryError("isolated_worker_output_not_json") from exc
        if not isinstance(value, dict) or set(value) != {"packet", "usage"} or not isinstance(value["packet"], dict):
            raise IsolatedDeliveryError("isolated_worker_output_contract_violation")
        if self.usage_verifier is None:
            raise IsolatedDeliveryError("isolated_worker_usage_verifier_unavailable")
        try:
            usage = self.usage_verifier(value["usage"])
        except IsolatedDeliveryError:
            raise
        except Exception as exc:
            raise IsolatedDeliveryError("isolated_worker_usage_verification_failed") from exc
        usage.validate()
        return IsolatedWorkerOutput(
            packet=value["packet"],
            usage=usage,
            wall_time_seconds=wall,
        )

    def _probe_sandbox(self) -> dict[str, Any]:
        sandbox = Path(self.sandbox_executable)
        base = {
            "schema_version": 1,
            "sandbox_executable": str(sandbox),
            "sandbox_sha256": _file_sha256(sandbox) if sandbox.is_file() else "missing",
        }
        if not sandbox.is_absolute() or not sandbox.is_file() or not os.access(sandbox, os.X_OK):
            return {**base, "status": "unavailable", "reason": "sandbox_executable_unavailable"}
        python = Path("/usr/bin/python3")
        if not python.is_file():
            return {**base, "status": "unavailable", "reason": "sandbox_canary_python_unavailable"}
        canary = (
            "import json,os,pathlib,socket,subprocess;"
            "cwd_writable=True;"
            "\ntry: pathlib.Path('/work/canary').write_text('x')"
            "\nexcept OSError: cwd_writable=False"
            "\nnetwork_reachable=True; s=socket.socket(); s.settimeout(.2)"
            "\ntry: s.connect(('1.1.1.1',53))"
            "\nexcept OSError: network_reachable=False"
            "\nfinally: s.close()"
            "\nsubprocess.Popen(['/usr/bin/python3','-c','import time; time.sleep(30)'],start_new_session=True)"
            "\nprint(json.dumps({'cwd':os.getcwd(),'cwd_writable':cwd_writable,'workspace_visible':pathlib.Path('/workspace').exists(),'network_reachable':network_reachable,'detached_descendant_spawned':True}))"
        )
        started = time.monotonic()
        try:
            with tempfile.TemporaryDirectory(prefix="docatlas-sandbox-canary-") as temp_dir:
                empty_work = Path(temp_dir) / "empty-work"
                empty_work.mkdir(mode=0o700)
                process = subprocess.Popen(
                    self._sandbox_command(python, empty_work, command_tail=("-c", canary)),
                    env={"HOME": "/tmp", "LANG": "C.UTF-8", "PATH": "/usr/local/bin:/usr/bin:/bin"},
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True,
                    bufsize=0,
                )
                stdout, stderr = _communicate_bounded(
                    process,
                    b"",
                    deadline=time.monotonic() + 3,
                    max_stdout_bytes=16_384,
                    max_stderr_bytes=16_384,
                )
        except (OSError, IsolatedDeliveryError) as exc:
            return {
                **base,
                "status": "failed",
                "reason": exc.__class__.__name__ + ":" + str(exc)[:300],
                "wall_time_seconds": round(time.monotonic() - started, 6),
            }
        if process.returncode != 0:
            return {
                **base,
                "status": "failed",
                "reason": f"sandbox_canary_exit_{process.returncode}",
                "stderr": stderr.decode("utf-8", errors="replace")[:2_000],
                "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
                "wall_time_seconds": round(time.monotonic() - started, 6),
            }
        try:
            checks = json.loads(stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            checks = {}
        verified = checks == {
            "cwd": "/work",
            "cwd_writable": False,
            "workspace_visible": False,
            "network_reachable": False,
            "detached_descendant_spawned": True,
        }
        return {
            **base,
            "status": "verified" if verified else "failed",
            "reason": None if verified else "sandbox_canary_check_failed",
            "checks": checks,
            "wall_time_seconds": round(time.monotonic() - started, 6),
        }

    def _sandbox_command(
        self,
        executable: Path,
        empty_work: Path,
        *,
        command_tail: tuple[str, ...] | None = None,
    ) -> list[str]:
        command = [
            self.sandbox_executable,
            "--unshare-all",
            "--die-with-parent",
            "--new-session",
            "--proc", "/proc",
            "--dev", "/dev",
            "--ro-bind", str(empty_work), "/work",
            "--tmpfs", "/tmp",
            "--chdir", "/work",
        ]
        for root in ("/usr", "/bin", "/lib", "/lib64"):
            if Path(root).exists():
                command.extend(("--ro-bind", root, root))
        command.extend((str(executable), *(self.command[1:] if command_tail is None else command_tail)))
        return command


def missing_packet_evidence_categories(
    packet: dict[str, Any],
    evidence_items: tuple[dict[str, Any], ...],
    required_categories: tuple[str, ...],
) -> list[str]:
    packet_paths = {
        str(row.get("path") or "").strip().replace("\\", "/")
        for row in packet.get("source_of_truth", [])
        if isinstance(row, dict) and str(row.get("path") or "").strip()
    }
    available: set[str] = set()
    for item in evidence_items:
        path = str(item.get("path") or item.get("source") or "").strip().replace("\\", "/")
        if path not in packet_paths:
            continue
        source_class = str(item.get("source_class") or "").strip().lower()
        if source_class in {"project_doc", "project_docs"}:
            available.add("project_docs")
        if source_class in {"repo_map", "code_graph", "symbol", "symbols"}:
            available.add("symbols")
    return sorted(set(required_categories) - available)


def deliver_with_isolated_worker(
    *,
    worker: IsolatedWorker,
    envelope: DelegationEnvelope,
    evidence: HostEvidenceSnapshot,
    output_dir: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Validate one isolated compression handoff against host-owned evidence."""

    envelope.validate()
    evidence.validate(envelope)
    if timeout_seconds < 1:
        raise IsolatedDeliveryError("invalid_worker_timeout")
    capabilities = worker.capabilities
    if not isinstance(capabilities, IsolatedWorkerCapabilities) or not capabilities.verified:
        raise IsolatedDeliveryError("isolated_worker_capability_unverified")
    compressor_identity = str(worker.compressor_identity).strip()
    if not compressor_identity:
        raise IsolatedDeliveryError("missing_compressor_identity")
    capability_evidence = getattr(worker, "capability_evidence", None)
    if not isinstance(capability_evidence, dict) or capability_evidence.get("status") != "verified":
        raise IsolatedDeliveryError("isolated_worker_capability_evidence_unverified")
    try:
        capability_evidence = copy.deepcopy(capability_evidence)
        capability_evidence_bytes = json.dumps(
            capability_evidence, ensure_ascii=False, sort_keys=True
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise IsolatedDeliveryError("isolated_worker_capability_evidence_invalid") from exc
    if len(capability_evidence_bytes) > 100_000:
        raise IsolatedDeliveryError("isolated_worker_capability_evidence_too_large")
    usage_verifier_identity = str(getattr(worker, "usage_verifier_identity", "")).strip()
    if not usage_verifier_identity:
        raise IsolatedDeliveryError("isolated_worker_usage_verifier_unavailable")
    command_fingerprint = str(worker.command_fingerprint).strip()
    sandbox_identity = str(worker.sandbox_identity).strip()
    if not command_fingerprint or not sandbox_identity:
        raise IsolatedDeliveryError("isolated_worker_identity_incomplete")
    evidence_fingerprint = evidence.fingerprint

    output_dir.mkdir(parents=True, exist_ok=True)
    attempt_path = output_dir / "isolated_delivery_attempt.json"
    if attempt_path.exists():
        raise IsolatedDeliveryError("isolated_worker_attempt_already_consumed")
    _write_json(attempt_path, {
        "schema_version": 2,
        "status": "started",
        "attempts": 1,
        "envelope_fingerprint": envelope.fingerprint,
        "evidence_fingerprint": evidence.fingerprint,
    })
    started = time.monotonic()
    try:
        output = worker.run(envelope, evidence, timeout_seconds=timeout_seconds)
    except IsolatedDeliveryError:
        raise
    except Exception as exc:
        raise IsolatedDeliveryError("isolated_worker_unexpected_failure") from exc
    broker_wall = round(time.monotonic() - started, 6)
    if evidence.fingerprint != evidence_fingerprint:
        raise IsolatedDeliveryError("host_evidence_mutated_by_worker")
    if not isinstance(output, IsolatedWorkerOutput):
        raise IsolatedDeliveryError("isolated_worker_output_contract_violation")
    if (
        isinstance(output.wall_time_seconds, bool)
        or not isinstance(output.wall_time_seconds, (int, float))
        or not math.isfinite(float(output.wall_time_seconds))
        or output.wall_time_seconds < 0
        or broker_wall > timeout_seconds
        or output.wall_time_seconds > timeout_seconds
    ):
        raise IsolatedDeliveryError("isolated_worker_timeout")

    packet = output.packet
    if not isinstance(packet, dict) or not isinstance(output.usage, WorkerUsage):
        raise IsolatedDeliveryError("isolated_worker_output_contract_violation")
    objective = (
        packet.get("task_interpretation", {}).get("objective")
        if isinstance(packet.get("task_interpretation"), dict)
        else None
    )
    if objective != envelope.task_objective:
        raise IsolatedDeliveryError("action_packet_objective_mismatch")
    errors = validate_action_packet(
        packet,
        evidence_items=evidence.evidence_items,
        max_tokens=envelope.token_budget,
    )
    if errors:
        raise IsolatedDeliveryError("invalid_action_packet:" + ";".join(errors))
    cited_ids = {
        row.get("evidence_id")
        for row in packet.get("source_of_truth", [])
        if isinstance(row, dict) and isinstance(row.get("evidence_id"), str)
    }
    if packet.get("status") != "insufficient_evidence" and not cited_ids:
        raise IsolatedDeliveryError("action_packet_has_no_host_evidence")
    missing_categories = missing_packet_evidence_categories(
        packet,
        evidence.evidence_items,
        envelope.required_evidence_categories,
    )
    if packet.get("status") != "insufficient_evidence" and missing_categories:
        raise IsolatedDeliveryError(
            "action_packet_missing_required_evidence_categories:" + ",".join(missing_categories)
        )
    if evidence.retrieval_issues and packet.get("status") != "insufficient_evidence":
        raise IsolatedDeliveryError("action_packet_ignored_host_retrieval_issues")

    packet_payload = dict(packet)
    usage = output.usage
    usage.validate()
    metrics = {
        "schema_version": 2,
        "strategy": "bounded_subagent",
        "status": packet_payload["status"],
        "attempts": 1,
        "retrieval_calls": evidence.retrieval_calls,
        "compressor_identity": compressor_identity,
        "command_fingerprint": command_fingerprint,
        "sandbox_identity": sandbox_identity,
        "sandbox_capabilities": asdict(capabilities),
        "sandbox_canary": capability_evidence,
        "usage_verifier_identity": usage_verifier_identity,
        "worker_usage_proof_fingerprint": usage.proof_fingerprint,
        "envelope_fingerprint": envelope.fingerprint,
        "evidence_fingerprint": evidence_fingerprint,
        "project_revision": evidence.project_revision,
        "index_revision": evidence.index_revision,
        "parent_visible_raw_retrieval": False,
        "parent_packet_tokens": packet_payload["estimated_tokens"],
        "worker_provider": usage.provider,
        "worker_model": usage.model,
        "worker_request_id": usage.request_id,
        "worker_input_tokens": usage.input_tokens,
        "worker_output_tokens": usage.output_tokens,
        "worker_reasoning_tokens": usage.reasoning_tokens,
        "raw_retrieval_tokens": evidence.raw_retrieval_tokens,
        "retrieval_wall_time_seconds": evidence.retrieval_wall_time_seconds,
        "worker_wall_time_seconds": output.wall_time_seconds,
        "broker_wall_time_seconds": broker_wall,
    }
    persist_host_evidence(evidence, output_dir)
    _write_json(output_dir / "worker_usage_proof.json", usage.proof or {})
    _write_json(output_dir / "isolated_delegation_envelope.json", envelope.to_json())
    _write_json(output_dir / "action_packet.json", packet_payload)
    _write_json(output_dir / "isolated_delivery_metrics.json", metrics)
    _write_json(attempt_path, {
        "schema_version": 2,
        "status": "completed",
        "packet_status": packet_payload["status"],
        "attempts": 1,
        "envelope_fingerprint": envelope.fingerprint,
        "evidence_fingerprint": evidence.fingerprint,
    })
    return {"status": packet_payload["status"], "packet": packet_payload, "metrics": metrics}


def persist_host_evidence(evidence: HostEvidenceSnapshot, output_dir: Path) -> None:
    """Persist evaluator-only evidence and a content-addressed sanitized manifest."""

    evidence.validate()
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "host_evidence_manifest.json", evidence.manifest())
    _write_json(output_dir / "host_evidence_snapshot.json", evidence.to_json(include_content=True))
    sources = [
        {"path": row["path"], "section": row["section"], "content_sha256": row["content_sha256"]}
        for row in evidence.manifest()["items"]
        if row["path"]
    ]
    (output_dir / "context_sources.json").write_text(
        json.dumps(sources, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _communicate_bounded(
    process: subprocess.Popen[bytes],
    payload: bytes,
    *,
    deadline: float,
    max_stdout_bytes: int,
    max_stderr_bytes: int,
) -> tuple[bytes, bytes]:
    if process.stdin is None or process.stdout is None or process.stderr is None:
        _kill_process_group(process)
        raise IsolatedDeliveryError("isolated_worker_pipe_setup_failed")
    selector = selectors.DefaultSelector()
    streams = {
        process.stdin.fileno(): (process.stdin, "stdin"),
        process.stdout.fileno(): (process.stdout, "stdout"),
        process.stderr.fileno(): (process.stderr, "stderr"),
    }
    for fd, (stream, name) in streams.items():
        os.set_blocking(fd, False)
        selector.register(stream, selectors.EVENT_WRITE if name == "stdin" else selectors.EVENT_READ, name)
    sent = 0
    stdout = bytearray()
    stderr = bytearray()
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _kill_process_group(process)
                raise IsolatedDeliveryError("isolated_worker_timeout")
            events = selector.select(min(remaining, 0.1))
            if not events and process.poll() is not None:
                for stream in (process.stdout, process.stderr):
                    try:
                        chunk = os.read(stream.fileno(), 65_536)
                    except (BlockingIOError, OSError):
                        chunk = b""
                    target = stdout if stream is process.stdout else stderr
                    target.extend(chunk)
                    try:
                        selector.unregister(stream)
                    except (KeyError, ValueError):
                        pass
                if process.stdin in [key.fileobj for key in selector.get_map().values()]:
                    try:
                        selector.unregister(process.stdin)
                    except (KeyError, ValueError):
                        pass
                continue
            for key, _mask in events:
                name = key.data
                stream = key.fileobj
                if name == "stdin":
                    try:
                        written = os.write(stream.fileno(), payload[sent:sent + 65_536])
                    except BrokenPipeError:
                        written = 0
                        sent = len(payload)
                    sent += written
                    if sent >= len(payload):
                        selector.unregister(stream)
                        stream.close()
                else:
                    try:
                        chunk = os.read(stream.fileno(), 65_536)
                    except BlockingIOError:
                        continue
                    if not chunk:
                        selector.unregister(stream)
                        continue
                    target = stdout if name == "stdout" else stderr
                    target.extend(chunk)
                    limit = max_stdout_bytes if name == "stdout" else max_stderr_bytes
                    if len(target) > limit:
                        _kill_process_group(process)
                        raise IsolatedDeliveryError(f"isolated_worker_{name}_too_large")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _kill_process_group(process)
            raise IsolatedDeliveryError("isolated_worker_timeout")
        process.wait(timeout=remaining)
    except subprocess.TimeoutExpired as exc:
        _kill_process_group(process)
        raise IsolatedDeliveryError("isolated_worker_timeout") from exc
    finally:
        selector.close()
    return bytes(stdout), bytes(stderr)


def _kill_process_group(process: subprocess.Popen[Any]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _limit_worker_resources(*, timeout_seconds: int, memory_limit_bytes: int, process_limit: int):
    def apply() -> None:
        cpu = max(1, int(math.ceil(timeout_seconds)))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))
        resource.setrlimit(resource.RLIMIT_NPROC, (process_limit, process_limit))
        resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024 * 1024, 8 * 1024 * 1024))

    return apply


def _is_system_worker_path(path: Path) -> bool:
    allowed = (Path("/usr"), Path("/bin"))
    return any(path == root or root in path.parents for root in allowed)


def _source_path(item: dict[str, Any]) -> str:
    source = item.get("source") if isinstance(item.get("source"), dict) else {}
    return str(item.get("path") or source.get("path") or item.get("url") or source.get("url") or "")


def _source_section(item: dict[str, Any]) -> str:
    section = item.get("section") if isinstance(item.get("section"), dict) else {}
    return str(item.get("heading_path") or section.get("heading_path") or item.get("title") or section.get("title") or "")


def _json_sha256(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return "unavailable"
    return digest.hexdigest()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
