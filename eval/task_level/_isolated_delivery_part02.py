"""Implementation shard 2 for isolated_delivery."""
from __future__ import annotations

from ._isolated_delivery_shared import *  # noqa: F401,F403

from ._isolated_delivery_part01 import DelegationEnvelope, HostEvidenceSnapshot, IsolatedDeliveryError, IsolatedWorker, IsolatedWorkerCapabilities, IsolatedWorkerOutput, WorkerUsage, _communicate_bounded, _file_sha256, _is_system_worker_path, _json_sha256, _limit_worker_resources

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


def missing_packet_evidence_paths(
    packet: dict[str, Any],
    evidence_items: tuple[dict[str, Any], ...],
    required_paths: tuple[str, ...],
) -> list[str]:
    cited_paths = {
        str(row.get("path") or "").strip().replace("\\", "/")
        for row in packet.get("source_of_truth", [])
        if isinstance(row, dict) and str(row.get("path") or "").strip()
    }
    evidence_paths = {
        str(item.get("path") or "").strip().replace("\\", "/")
        for item in evidence_items
    }
    return sorted(path for path in required_paths if path not in cited_paths or path not in evidence_paths)


def deliver_with_isolated_worker(
    *,
    worker: IsolatedWorker,
    envelope: DelegationEnvelope,
    evidence: HostEvidenceSnapshot,
    output_dir: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Validate one causal isolated compression handoff."""

    return _deliver_with_worker(
        worker=worker,
        envelope=envelope,
        evidence=evidence,
        output_dir=output_dir,
        timeout_seconds=timeout_seconds,
        evidence_tier="causal",
    )


def deliver_with_exploratory_worker(
    *,
    worker: IsolatedWorker,
    envelope: DelegationEnvelope,
    evidence: HostEvidenceSnapshot,
    output_dir: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Validate an explicitly non-causal exploratory compression handoff."""

    return _deliver_with_worker(
        worker=worker,
        envelope=envelope,
        evidence=evidence,
        output_dir=output_dir,
        timeout_seconds=timeout_seconds,
        evidence_tier="exploratory",
    )


def _deliver_with_worker(
    *,
    worker: IsolatedWorker,
    envelope: DelegationEnvelope,
    evidence: HostEvidenceSnapshot,
    output_dir: Path,
    timeout_seconds: int,
    evidence_tier: str,
) -> dict[str, Any]:
    envelope.validate()
    evidence.validate(envelope)
    if timeout_seconds < 1:
        raise IsolatedDeliveryError("invalid_worker_timeout")
    if evidence_tier not in {"causal", "exploratory"}:
        raise IsolatedDeliveryError("invalid_isolated_delivery_evidence_tier")
    capabilities = worker.capabilities
    if not isinstance(capabilities, IsolatedWorkerCapabilities):
        raise IsolatedDeliveryError("isolated_worker_capability_unverified")
    if evidence_tier == "causal" and not capabilities.verified:
        raise IsolatedDeliveryError("isolated_worker_capability_unverified")
    compressor_identity = str(worker.compressor_identity).strip()
    if not compressor_identity:
        raise IsolatedDeliveryError("missing_compressor_identity")
    capability_evidence = getattr(worker, "capability_evidence", None)
    expected_capability_status = (
        "verified" if evidence_tier == "causal" else "exploratory_unverified"
    )
    if (
        not isinstance(capability_evidence, dict)
        or capability_evidence.get("status") != expected_capability_status
    ):
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
    missing_paths = missing_packet_evidence_paths(
        packet, evidence.evidence_items, envelope.required_evidence_paths
    )
    if packet.get("status") != "insufficient_evidence" and missing_paths:
        raise IsolatedDeliveryError(
            "action_packet_missing_required_evidence_paths:" + ",".join(missing_paths)
        )
    target_surface = packet.get("target_surface") if isinstance(packet.get("target_surface"), dict) else {}
    target_paths = {
        str(row.get("path") or "").strip().replace("\\", "/")
        for row in target_surface.get("likely_files", [])
        if isinstance(row, dict)
    }
    required_target_files = {
        path for path in envelope.suspected_modules if Path(path).suffix
    }
    missing_modules = sorted(required_target_files - target_paths)
    if packet.get("status") != "insufficient_evidence" and missing_modules:
        raise IsolatedDeliveryError(
            "action_packet_missing_required_target_modules:" + ",".join(missing_modules)
        )
    if evidence.retrieval_issues and packet.get("status") != "insufficient_evidence":
        raise IsolatedDeliveryError("action_packet_ignored_host_retrieval_issues")

    packet_payload = dict(packet)
    usage = output.usage
    usage.validate()
    metrics = {
        "schema_version": 2,
        "strategy": "bounded_subagent",
        "evidence_tier": evidence_tier,
        "causal_claim_allowed": evidence_tier == "causal",
        "server_request_id_verified": bool(
            (usage.proof or {}).get("server_request_id_verified", evidence_tier == "causal")
        ),
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


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

__all__=['JsonSubprocessIsolatedWorker', 'missing_packet_evidence_categories', 'missing_packet_evidence_paths', 'deliver_with_isolated_worker', 'deliver_with_exploratory_worker', '_deliver_with_worker', 'persist_host_evidence', '_write_json']
