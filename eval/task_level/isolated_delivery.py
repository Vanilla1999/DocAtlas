from __future__ import annotations

import hashlib
import json
import os
import signal
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from docmancer.docs.application.action_packet import (
    ACTION_PACKET_SCHEMA_VERSION,
    HARD_ACTION_PACKET_TOKENS,
    validate_action_packet,
)


class IsolatedDeliveryError(RuntimeError):
    """A fail-closed host capability or worker-result failure."""


@dataclass(frozen=True)
class IsolatedWorkerCapabilities:
    fresh_context: bool
    read_only_documentation: bool
    recursive_delegation_disabled: bool
    hard_timeout: bool
    token_accounting: bool

    @property
    def verified(self) -> bool:
        return all(asdict(self).values())


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
        if self.schema_version != 1:
            raise IsolatedDeliveryError("unsupported_delegation_schema")
        if self.packet_schema_version != ACTION_PACKET_SCHEMA_VERSION:
            raise IsolatedDeliveryError("unsupported_action_packet_schema")
        if not self.task_objective.strip() or len(self.task_objective) > 4_000:
            raise IsolatedDeliveryError("invalid_task_objective")
        if (
            not self.project_revision.strip() or not self.index_revision.strip()
            or len(self.project_revision) > 200 or len(self.index_revision) > 200
        ):
            raise IsolatedDeliveryError("missing_revision_identity")
        if not 128 <= self.token_budget <= HARD_ACTION_PACKET_TOKENS:
            raise IsolatedDeliveryError("invalid_token_budget")
        if not self.required_evidence_categories:
            raise IsolatedDeliveryError("missing_required_evidence_categories")
        for field_name in ("suspected_modules", "changed_files", "required_evidence_categories"):
            values = getattr(self, field_name)
            if (
                len(values) > 32 or len(set(values)) != len(values)
                or any(not value.strip() or value != value.strip() or len(value) > 500 for value in values)
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
        encoded = json.dumps(self.to_json(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class IsolatedWorkerOutput:
    packet: dict[str, Any]
    evidence_items: tuple[dict[str, Any], ...]
    retrieval_calls: int
    parent_visible_raw_retrieval: bool
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    raw_retrieval_tokens: int | None = None
    wall_time_seconds: float | None = None
    timed_out: bool = False


class IsolatedWorker(Protocol):
    capabilities: IsolatedWorkerCapabilities
    compressor_identity: str

    def run(self, envelope: DelegationEnvelope, *, timeout_seconds: int) -> IsolatedWorkerOutput:
        """Run exactly one fresh worker attempt under a host-enforced timeout."""


@dataclass(frozen=True)
class JsonSubprocessIsolatedWorker:
    """Host adapter for a fresh JSON-in/JSON-out compressor process.

    The command receives no repository path or parent transcript. Its working
    directory is a fresh read-only directory, and the entire process group is
    terminated on timeout. Model credentials and MCP configuration, when needed,
    must be supplied explicitly by the host in ``environment``.
    """

    command: tuple[str, ...]
    compressor_identity: str
    environment: dict[str, str]
    capabilities: IsolatedWorkerCapabilities
    max_output_bytes: int = 1_000_000
    root_sandbox_verified: bool = False

    def run(self, envelope: DelegationEnvelope, *, timeout_seconds: int) -> IsolatedWorkerOutput:
        if not self.command or not os.path.isabs(self.command[0]):
            raise IsolatedDeliveryError("worker_command_must_be_absolute")
        if not Path(self.command[0]).is_file():
            raise IsolatedDeliveryError("worker_command_not_found")
        if os.geteuid() == 0 and not self.root_sandbox_verified:
            raise IsolatedDeliveryError("isolated_worker_root_sandbox_unavailable")
        payload = json.dumps(envelope.to_json(), sort_keys=True)
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="docatlas-isolated-worker-") as temp_dir:
            temp_root = Path(temp_dir)
            temp_root.chmod(0o755)
            work_dir = temp_root / "work"
            work_dir.mkdir(mode=0o555)
            child_environment = dict(self.environment)
            source_home = child_environment.get("DOCMANCER_HOME")
            if source_home:
                source = Path(source_home)
                if not source.is_dir():
                    raise IsolatedDeliveryError("worker_doc_index_not_found")
                isolated_home = temp_root / "docmancer_home"
                shutil.copytree(source, isolated_home)
                for path in sorted(isolated_home.rglob("*"), reverse=True):
                    path.chmod(0o555 if path.is_dir() else 0o444)
                isolated_home.chmod(0o555)
                child_environment["DOCMANCER_HOME"] = str(isolated_home)
            process = subprocess.Popen(
                list(self.command),
                cwd=work_dir,
                env=child_environment,
                text=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            try:
                stdout, stderr = process.communicate(payload, timeout=timeout_seconds)
            except subprocess.TimeoutExpired as exc:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
                raise IsolatedDeliveryError("isolated_worker_timeout") from exc
            finally:
                for path in temp_root.rglob("*"):
                    if path.is_dir():
                        path.chmod(0o755)
        wall = round(time.monotonic() - started, 6)
        if process.returncode != 0:
            raise IsolatedDeliveryError(f"isolated_worker_failed:{process.returncode}")
        if len(stdout.encode("utf-8")) > self.max_output_bytes:
            raise IsolatedDeliveryError("isolated_worker_output_too_large")
        try:
            value = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise IsolatedDeliveryError("isolated_worker_output_not_json") from exc
        allowed = {
            "packet", "evidence_items", "retrieval_calls", "input_tokens", "output_tokens",
            "reasoning_tokens", "raw_retrieval_tokens", "wall_time_seconds",
        }
        if (
            not isinstance(value, dict) or set(value) - allowed
            or "packet" not in value or not isinstance(value.get("evidence_items"), list)
            or any(not isinstance(item, dict) for item in value["evidence_items"])
        ):
            raise IsolatedDeliveryError("isolated_worker_output_contract_violation")
        return IsolatedWorkerOutput(
            packet=value["packet"],
            evidence_items=tuple(value["evidence_items"]),
            retrieval_calls=value.get("retrieval_calls"),
            parent_visible_raw_retrieval=False,
            input_tokens=value.get("input_tokens"),
            output_tokens=value.get("output_tokens"),
            reasoning_tokens=value.get("reasoning_tokens"),
            raw_retrieval_tokens=value.get("raw_retrieval_tokens"),
            wall_time_seconds=value.get("wall_time_seconds", wall),
        )


def deliver_with_isolated_worker(
    *,
    worker: IsolatedWorker,
    envelope: DelegationEnvelope,
    output_dir: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Validate one isolated handoff and persist only parent-safe artifacts.

    The worker adapter owns process/session creation. This broker refuses adapters
    that cannot prove the boundaries required by Task 33C, invokes the adapter
    once, and never accepts raw retrieval in the parent-visible result.
    """

    envelope.validate()
    if timeout_seconds < 1:
        raise IsolatedDeliveryError("invalid_worker_timeout")
    if not worker.capabilities.verified:
        raise IsolatedDeliveryError("isolated_worker_capability_unverified")
    if not str(worker.compressor_identity).strip():
        raise IsolatedDeliveryError("missing_compressor_identity")

    output_dir.mkdir(parents=True, exist_ok=True)
    attempt_path = output_dir / "isolated_delivery_attempt.json"
    if attempt_path.exists():
        raise IsolatedDeliveryError("isolated_worker_attempt_already_consumed")
    _write_json(attempt_path, {
        "schema_version": 1,
        "status": "started",
        "attempts": 1,
        "envelope_fingerprint": envelope.fingerprint,
    })
    started = time.monotonic()
    try:
        output = worker.run(envelope, timeout_seconds=timeout_seconds)
    except IsolatedDeliveryError:
        raise
    except Exception as exc:
        raise IsolatedDeliveryError("isolated_worker_unexpected_failure") from exc
    broker_wall = round(time.monotonic() - started, 6)
    if output.timed_out or broker_wall > timeout_seconds or (
        output.wall_time_seconds is not None and output.wall_time_seconds > timeout_seconds
    ):
        raise IsolatedDeliveryError("isolated_worker_timeout")
    if output.retrieval_calls != 1:
        raise IsolatedDeliveryError("isolated_worker_must_retrieve_exactly_once")
    if output.parent_visible_raw_retrieval:
        raise IsolatedDeliveryError("raw_retrieval_crossed_parent_boundary")
    for field_name in (
        "input_tokens", "output_tokens", "reasoning_tokens", "raw_retrieval_tokens",
    ):
        value = getattr(output, field_name)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
            raise IsolatedDeliveryError(f"invalid_worker_{field_name}")

    errors = validate_action_packet(
        output.packet,
        evidence_items=output.evidence_items,
        max_tokens=envelope.token_budget,
    )
    if errors:
        raise IsolatedDeliveryError("invalid_action_packet:" + ";".join(errors))

    envelope_payload = envelope.to_json()
    packet_payload = dict(output.packet)
    metrics = {
        "schema_version": 1,
        "strategy": "bounded_subagent",
        "attempts": 1,
        "retrieval_calls": 1,
        "compressor_identity": worker.compressor_identity,
        "envelope_fingerprint": envelope.fingerprint,
        "parent_visible_raw_retrieval": False,
        "parent_packet_tokens": packet_payload["estimated_tokens"],
        "worker_input_tokens": output.input_tokens,
        "worker_output_tokens": output.output_tokens,
        "worker_reasoning_tokens": output.reasoning_tokens,
        "raw_retrieval_tokens": output.raw_retrieval_tokens,
        "worker_wall_time_seconds": output.wall_time_seconds,
        "broker_wall_time_seconds": broker_wall,
    }
    _write_json(output_dir / "isolated_delegation_envelope.json", envelope_payload)
    _write_json(output_dir / "action_packet.json", packet_payload)
    _write_json(output_dir / "isolated_delivery_metrics.json", metrics)
    _write_json(attempt_path, {
        "schema_version": 1,
        "status": "completed",
        "attempts": 1,
        "envelope_fingerprint": envelope.fingerprint,
    })
    return {"status": "success", "packet": packet_payload, "metrics": metrics}


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
