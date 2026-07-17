from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from docmancer.docs.application.action_packet import build_action_packet

from .execution import execute_pilot, run_canary, run_docatlas_tool_visibility_canary
from .isolated_delivery import (
    DelegationEnvelope,
    HostEvidenceSnapshot,
    IsolatedDeliveryError,
    IsolatedWorkerCapabilities,
    IsolatedWorkerOutput,
    TASK33_QUERY_DERIVATION,
    WorkerUsage,
    derive_task33_retrieval_query,
)
from .report import write_report
from .runner import BASE_PROMPT, load_tasks
from .runners.codex import CodexRunner
from .sandbox_execution import DockerCommandSandbox
from .schemas import RESULTS_ROOT
from .task33_local import _build_image, _prewarm_fixture_dependencies, _probe_retrieval
from .task33_pilot import (
    TASK33C_EXPLORATORY_SMOKE_CONDITIONS,
    TASK33C_PILOT_CONDITIONS,
    TASK33C_PILOT_TASK_ID,
)
from .task33_validation import PROTOCOL_PATH, load_protocol


DEFAULT_CODEX_MODEL = "gpt-5.3-codex-spark"
_CODEX_ENV_ALLOWLIST = (
    "LANG",
    "LC_ALL",
    "PATH",
    "SSL_CERT_DIR",
    "SSL_CERT_FILE",
    "TERM",
)


def _codex_failure_summary(stderr: str) -> str:
    tail = stderr[-2_000:]
    tail = re.sub(r"(?i)(Bearer\s+)[^\s]+", r"\1<redacted>", tail)
    tail = re.sub(
        r"(?i)((?:api[_-]?key|access[_-]?token|refresh[_-]?token)\s*[=:]\s*)[^\s]+",
        r"\1<redacted>",
        tail,
    )
    return tail.replace(str(Path.home()), "~").strip()


@dataclass(frozen=True)
class CodexExploratoryWorker:
    """One-shot Codex OAuth selector for explicitly non-causal local experiments."""

    model: str = DEFAULT_CODEX_MODEL
    executable: str = "codex"
    temp_root: Path | None = None
    sandbox_mode: str = "read-only"
    compressor_identity: str = "codex-cli-exploratory-selector-v1"
    usage_verifier_identity: str = "codex-cli-jsonl-self-report-unverified-v1"

    @property
    def capabilities(self) -> IsolatedWorkerCapabilities:
        return IsolatedWorkerCapabilities(
            fresh_context=True,
            read_only_documentation=False,
            recursive_delegation_disabled=False,
            hard_timeout=True,
            token_accounting=False,
            host_owned_evidence=True,
            network_disabled=False,
            descendant_containment=False,
        )

    @property
    def capability_evidence(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "status": "exploratory_unverified",
            "boundary_type": "empty_temporary_workspace_codex_cli",
            "provider": "codex-oauth",
            "model": self.model,
            "fresh_context": "one ephemeral Codex exec invocation",
            "host_evidence_only": False,
            "server_request_id_verified": False,
            "provider_usage_verified": False,
            "warning": (
                "Codex CLI has no frozen Task 33C provider profile, server request ID proof, "
                "or verified tool-less sandbox; this adapter is exploratory only."
            ),
        }

    @property
    def command_fingerprint(self) -> str:
        return _json_sha256({
            "executable": shutil.which(self.executable) or self.executable,
            "model": self.model,
            "prompt_revision": self.compressor_identity,
        })

    @property
    def sandbox_identity(self) -> str:
        return f"codex-cli:empty-temporary-workspace:{self.sandbox_mode}:unverified"

    def run(
        self,
        envelope: DelegationEnvelope,
        evidence: HostEvidenceSnapshot,
        *,
        timeout_seconds: int,
    ) -> IsolatedWorkerOutput:
        envelope.validate()
        evidence.validate(envelope)
        executable = shutil.which(self.executable)
        if executable is None:
            raise IsolatedDeliveryError("codex_cli_not_found")
        if timeout_seconds < 1:
            raise IsolatedDeliveryError("invalid_worker_timeout")
        if self.sandbox_mode not in {"read-only", "danger-full-access"}:
            raise IsolatedDeliveryError("invalid_worker_sandbox")

        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["selected_indices"],
            "properties": {
                "selected_indices": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "minItems": min(3, len(evidence.evidence_items)),
                    "maxItems": min(6, len(evidence.evidence_items)),
                },
            },
        }
        prompt = (
            "You are an exploratory one-shot evidence selector. Do not run tools. "
            "Select only indices from the supplied immutable host evidence. Include every item needed "
            "to cover required evidence paths, categories, and target modules. Return only schema JSON.\n"
            + json.dumps(
                {
                    "objective": envelope.task_objective,
                    "required_evidence_categories": list(envelope.required_evidence_categories),
                    "required_evidence_paths": list(envelope.required_evidence_paths),
                    "required_target_modules": list(envelope.suspected_modules),
                    "evidence": [
                        {"index": index, "item": item}
                        for index, item in enumerate(evidence.evidence_items)
                    ],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )

        started = time.monotonic()
        root = str(self.temp_root) if self.temp_root is not None else None
        with tempfile.TemporaryDirectory(prefix="task33c-codex-selector-", dir=root) as raw:
            invocation_root = Path(raw)
            workspace = invocation_root / "workspace"
            workspace.mkdir()
            codex_home = invocation_root / "codex-home"
            _copy_codex_oauth(codex_home)
            schema_path = workspace / "selection.schema.json"
            schema_path.write_text(json.dumps(schema, sort_keys=True), encoding="utf-8")
            command = [
                executable,
                "exec",
                "--json",
                "--ephemeral",
                "--skip-git-repo-check",
                "--ignore-user-config",
                "--ignore-rules",
                "--sandbox",
                self.sandbox_mode,
                "-c",
                'shell_environment_policy.inherit="none"',
                "--cd",
                str(workspace),
                "--model",
                self.model,
                "--output-schema",
                str(schema_path),
                prompt,
            ]
            try:
                completed = _run_bounded_codex(
                    command,
                    cwd=workspace,
                    env=_codex_selector_environment(codex_home),
                    timeout_seconds=timeout_seconds,
                )
            finally:
                (codex_home / "auth.json").unlink(missing_ok=True)
        if completed.returncode != 0:
            raise IsolatedDeliveryError(
                "codex_exploratory_worker_failed:"
                + str(completed.returncode)
                + ":"
                + _codex_failure_summary(completed.stderr + "\n" + completed.stdout)
            )

        selection, usage, thread_id = _parse_codex_jsonl(completed.stdout)
        indices = selection.get("selected_indices")
        minimum = min(3, len(evidence.evidence_items))
        maximum = min(6, len(evidence.evidence_items))
        if (
            not isinstance(indices, list)
            or not minimum <= len(indices) <= maximum
            or any(isinstance(index, bool) or not isinstance(index, int) for index in indices)
            or len(set(indices)) != len(indices)
            or any(index < 0 or index >= len(evidence.evidence_items) for index in indices)
        ):
            raise IsolatedDeliveryError("codex_exploratory_worker_invalid_selection")

        selected = tuple(evidence.evidence_items[index] for index in indices)
        packet = build_action_packet(
            question=envelope.task_objective,
            context_pack=selected,
            trust_contract=evidence.trust_contract,
            max_tokens=envelope.token_budget,
            retrieval_issues=evidence.retrieval_issues,
        )
        input_tokens = _usage_int(usage, "input_tokens")
        output_tokens = _usage_int(usage, "output_tokens")
        if input_tokens is None or output_tokens is None:
            raise IsolatedDeliveryError("codex_exploratory_worker_missing_usage")
        reasoning_tokens = _usage_int(usage, "reasoning_output_tokens", required=False)
        client_thread_id = "client-thread:" + thread_id
        proof = {
            "schema_version": 1,
            "provider": "codex-oauth",
            "model": self.model,
            "request_id": client_thread_id,
            "codex_thread_id": thread_id,
            "request_id_kind": "client_thread_id",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "reasoning_tokens": reasoning_tokens,
            "measurement_source": "codex_cli_jsonl",
            "server_request_id_verified": False,
            "provider_usage_verified": False,
            "cached_input_tokens": _usage_int(usage, "cached_input_tokens", required=False),
            "selected_indices": indices,
        }
        return IsolatedWorkerOutput(
            packet=packet,
            usage=WorkerUsage(
                provider="codex-oauth",
                model=self.model,
                request_id=client_thread_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                reasoning_tokens=reasoning_tokens,
                proof=proof,
            ),
            wall_time_seconds=round(time.monotonic() - started, 6),
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a non-causal Task 33C local experiment through Codex CLI OAuth; "
            "results can never receive a VALID verdict"
        )
    )
    parser.add_argument("--run-exploratory-pilot", action="store_true")
    parser.add_argument(
        "--two-cell-smoke",
        action="store_true",
        help="Run only repo-only and bounded-direct with one runner canary.",
    )
    parser.add_argument(
        "--host-exploratory",
        action="store_true",
        help="Skip Docker and run Codex plus evaluator commands on the host; never causal or VALID.",
    )
    parser.add_argument("--model", default=DEFAULT_CODEX_MODEL)
    parser.add_argument("--image", default="docatlas-task33c-evaluator:local")
    parser.add_argument("--skip-image-build", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--worker-timeout-seconds", type=int, default=120)
    parser.add_argument(
        "--run-id",
        default=datetime.now(timezone.utc).strftime(
            "task33c_codex_exploratory_%Y%m%d_%H%M%S"
        ),
    )
    args = parser.parse_args(argv)
    if args.two_cell_smoke and not args.host_exploratory:
        parser.error("--two-cell-smoke requires --host-exploratory")
    selected_conditions = (
        TASK33C_EXPLORATORY_SMOKE_CONDITIONS
        if args.two_cell_smoke
        else TASK33C_PILOT_CONDITIONS
    )

    required = ("codex", "uv") if args.host_exploratory else ("codex", "docker", "uv")
    missing = [name for name in required if shutil.which(name) is None]
    if missing:
        parser.error("missing required executables: " + ", ".join(missing))
    if args.timeout_seconds < 1 or args.worker_timeout_seconds < 1:
        parser.error("timeouts must be positive")

    protocol = load_protocol()
    container = protocol["container"]
    preflight_dir = RESULTS_ROOT / f"{args.run_id}_preflight"
    preflight_dir.mkdir(parents=True, exist_ok=False)
    runtime_root = preflight_dir / "runtime"
    runtime_root.mkdir()
    os.environ["TASK33C_RUNTIME_ROOT"] = str(runtime_root.resolve())
    preflight: dict[str, Any] = {
        "schema_version": 1,
        "status": "failed",
        "evidence_tier": "exploratory",
        "verdict": "INCONCLUSIVE",
        "valid": False,
        "causal_claim_allowed": False,
        "execution_backend": "host_exploratory" if args.host_exploratory else "docker",
        "model": args.model,
        "protocol_sha256": hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest(),
        "frozen_protocol_modified": False,
        "checks": {},
    }
    try:
        if args.host_exploratory:
            preflight["checks"]["execution_backend"] = {
                "status": "exploratory_unisolated",
                "backend": "host",
                "docker_used": False,
                "causal_claim_allowed": False,
                "validator_eligible": False,
            }
        else:
            if args.skip_image_build:
                preflight["checks"]["image_build"] = {"status": "skipped_by_user"}
            else:
                preflight["checks"]["image_build"] = _build_image(
                    args.image, container["base_image"]
                )
            if preflight["checks"]["image_build"].get("status") not in {
                "verified",
                "skipped_by_user",
            }:
                preflight["status"] = "inconclusive_exploratory"
                return 3
        uv_cache = _prewarm_fixture_dependencies(preflight_dir)
        preflight["checks"]["fixture_dependency_prewarm"] = {"status": "verified"}
        if not args.host_exploratory:
            boundary = DockerCommandSandbox(args.image).verify()
            preflight["checks"]["docker"] = boundary
            if boundary.get("status") != "verified":
                preflight["status"] = "inconclusive_exploratory"
                return 3
        retrieval = _probe_retrieval(preflight_dir)
        preflight["checks"]["retrieval"] = retrieval
        if retrieval.get("status") != "verified":
            preflight["status"] = "inconclusive_exploratory"
            return 3
        selector_sandbox = "danger-full-access" if args.host_exploratory else "read-only"
        selector = (
            {
                "status": "not_required",
                "reason": "two_cell_smoke_has_no_isolated_worker_lane",
            }
            if args.two_cell_smoke
            else _probe_codex_selector(
                args.model,
                args.worker_timeout_seconds,
                sandbox_mode=selector_sandbox,
            )
        )
        preflight["checks"]["codex_oauth_selector"] = selector
        statuses = {
            check.get("status")
            for check in preflight["checks"].values()
            if isinstance(check, dict)
        }
        if statuses - {
            "verified",
            "skipped_by_user",
            "exploratory_verified",
            "exploratory_unisolated",
            "not_required",
        }:
            preflight["status"] = "inconclusive_exploratory"
            return 3
        preflight["status"] = "verified_exploratory"
        preflight["verdict"] = "READY_FOR_EXPLORATORY_RUN"
        if not args.run_exploratory_pilot:
            return 0

        run_environment = {
            "DOCMANCER_OFFLINE": "1",
            "TASK33C_BASE_IMAGE": str(container["base_image"]),
            "TASK33C_EVALUATOR_REQUIREMENTS_SHA256": str(
                container["requirements_sha256"]
            ),
            "UV_CACHE_DIR": str(uv_cache),
        }
        if args.host_exploratory:
            run_environment["TASK33C_REQUIRE_DOCKER_SANDBOX"] = "0"
        else:
            run_environment["TASK33C_TEST_CONTAINER_IMAGE"] = args.image
            run_environment["TASK33C_REQUIRE_DOCKER_SANDBOX"] = "1"
        os.environ.update(run_environment)
        run_dir = RESULTS_ROOT / args.run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        protocol_sha256_before = hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest()
        manifest = {
            "schema_version": 1,
            "classification": "EXPLORATORY_NON_CAUSAL",
            "validator_eligible": False,
            "causal_claim_allowed": False,
            "hard_turn_limit_verified": False,
            "provider_usage_verified": False,
            "server_request_ids_verified": False,
            "task_id": TASK33C_PILOT_TASK_ID,
            "conditions": list(selected_conditions),
            "repeats": 1,
            "two_cell_smoke": args.two_cell_smoke,
            "provider_call_cap": 3 if args.two_cell_smoke else None,
            "model": args.model,
            "protocol_sha256_before": protocol_sha256_before,
            "execution_backend": "host_exploratory" if args.host_exploratory else "docker",
            "host_execution_unisolated": args.host_exploratory,
            "parent_sandbox": (
                "danger-full-access" if args.host_exploratory else "workspace-write"
            ),
            "selector_sandbox": selector_sandbox,
        }
        _write_json(run_dir / "exploratory_manifest.json", manifest)
        runner = CodexRunner(
            sandbox_mode=(
                "danger-full-access" if args.host_exploratory else "workspace-write"
            ),
            inherit_environment=False,
        )
        runner_canary = run_canary(
            runner, args.model, args.timeout_seconds, run_dir / "runner_canary"
        )
        docatlas_canary = (
            {
                "status": "not_required",
                "reason": "two_cell_smoke_has_no_agent_tool_lane",
            }
            if args.two_cell_smoke
            else run_docatlas_tool_visibility_canary(
                runner,
                args.model,
                args.timeout_seconds,
                run_dir / "docatlas_tool_visibility_canary",
            )
        )
        _write_json(run_dir / "runner_canary.json", runner_canary)
        _write_json(run_dir / "docatlas_tool_visibility_canary.json", docatlas_canary)
        if (
            runner_canary.get("status") != "passed"
            or (
                not args.two_cell_smoke
                and docatlas_canary.get("docatlas_tool_visibility_verified") is not True
            )
        ):
            summary = {
                "schema_version": 1,
                "status": "inconclusive_exploratory",
                "verdict": "INCONCLUSIVE",
                "valid": False,
                "causal_claim_allowed": False,
                "runner_canary": runner_canary,
                "docatlas_canary": docatlas_canary,
            }
            _write_json(run_dir / "task33c_exploratory_summary.json", summary)
            return 3

        task = next(task for task in load_tasks() if task.task_id == TASK33C_PILOT_TASK_ID)
        results = execute_pilot(
            [task],
            list(selected_conditions),
            1,
            args.run_id,
            runner,
            args.model,
            args.timeout_seconds,
            BASE_PROMPT,
            isolated_worker=(
                None
                if args.two_cell_smoke
                else CodexExploratoryWorker(
                    model=args.model,
                    sandbox_mode=selector_sandbox,
                )
            ),
            isolated_worker_timeout_seconds=args.worker_timeout_seconds,
            evidence_tier="exploratory",
            evaluation_backend=(
                "host_exploratory" if args.host_exploratory else "docker"
            ),
        )
        summary = summarize_exploratory_results(
            results,
            expected_conditions=selected_conditions,
        )
        protocol_sha256_after = hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest()
        summary["runner_canary"] = runner_canary
        summary["docatlas_canary"] = docatlas_canary
        summary["protocol_sha256_before"] = protocol_sha256_before
        summary["protocol_sha256_after"] = protocol_sha256_after
        summary["protocol_unchanged"] = protocol_sha256_after == protocol_sha256_before
        if not summary["protocol_unchanged"]:
            summary["status"] = "inconclusive_exploratory"
            summary["verdict"] = "INCONCLUSIVE"
        _write_json(run_dir / "task33c_exploratory_summary.json", summary)
        metadata = {
            "environment": {
                "runner": "codex-cli-oauth",
                "model": args.model,
                "evidence_tier": "exploratory",
                "execution_backend": (
                    "host_exploratory" if args.host_exploratory else "docker"
                ),
            },
            "executive_result": summary["warning"],
            "decision": summary["verdict"],
            "claims_can_make": (
                f"The {len(selected_conditions)} local cells provide directional correctness, token, and latency metrics."
            ),
            "claims_cannot_make": (
                "This run cannot establish causal impact or receive a VALID Task 33C verdict."
            ),
            "failure_summary": (
                None if summary["status"] == "complete_exploratory"
                else "One or more exploratory cells were blocked or missing."
            ),
        }
        _write_json(run_dir / "metadata.json", metadata)
        write_report(run_dir, metadata, results)
        if _contains_auth_artifact(run_dir):
            summary["status"] = "inconclusive_exploratory"
            summary["verdict"] = "INCONCLUSIVE"
            summary["auth_artifact_detected"] = True
            _write_json(run_dir / "task33c_exploratory_summary.json", summary)
            return 3
        return 0 if summary["status"] == "complete_exploratory" else 3
    except Exception as exc:
        preflight["error"] = f"{exc.__class__.__name__}: {str(exc)[:2_000]}"
        preflight["status"] = "inconclusive_exploratory"
        return 3
    finally:
        _write_json(preflight_dir / "preflight-summary.json", preflight)


def _run_bounded_codex(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    stdout_path = cwd / "codex.stdout.jsonl"
    stderr_path = cwd / "codex.stderr.log"
    with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr_file:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            text=True,
            stdout=stdout_file,
            stderr=stderr_file,
            start_new_session=True,
        )
        try:
            returncode = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            os.killpg(process.pid, 9)
            process.wait()
            raise IsolatedDeliveryError("codex_exploratory_worker_timeout") from exc
    max_bytes = 2_000_000
    if stdout_path.stat().st_size > max_bytes or stderr_path.stat().st_size > max_bytes:
        raise IsolatedDeliveryError("codex_exploratory_worker_output_limit")
    return subprocess.CompletedProcess(
        command,
        returncode,
        stdout_path.read_text(encoding="utf-8"),
        stderr_path.read_text(encoding="utf-8"),
    )


def _copy_codex_oauth(destination: Path) -> None:
    source_home = Path(
        os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
    ).expanduser()
    source = source_home / "auth.json"
    if not source.is_file():
        raise IsolatedDeliveryError("codex_oauth_auth_missing")
    destination.mkdir(mode=0o700)
    target = destination / "auth.json"
    shutil.copy2(source, target)
    target.chmod(0o600)


def _codex_selector_environment(codex_home: Path) -> dict[str, str]:
    environment = {
        key: value
        for key in _CODEX_ENV_ALLOWLIST
        if (value := os.environ.get(key)) is not None
    }
    empty_home = codex_home.parent / "empty-home"
    empty_home.mkdir(mode=0o700)
    environment["CODEX_HOME"] = str(codex_home)
    environment["HOME"] = str(empty_home)
    return environment


def _probe_codex_selector(
    model: str,
    timeout_seconds: int,
    *,
    sandbox_mode: str = "read-only",
) -> dict[str, Any]:
    objective = "Preserve permission permission architecture and offline sync boundaries."
    envelope = DelegationEnvelope(
        task_objective=objective,
        suspected_modules=(),
        changed_files=(),
        required_evidence_categories=("project_docs",),
        required_evidence_paths=("docs/permission-architecture.md",),
        project_revision="codex-exploratory-probe",
        index_revision="codex-exploratory-probe",
    )
    evidence_items = tuple(
        {
            "path": path,
            "heading_path": "Probe",
            "authority": "canonical",
            "source_class": "project_doc",
            "instruction_trust": "trusted_project_policy",
            "content": content,
        }
        for path, content in (
            ("docs/permission-architecture.md", "Keep permission checks centralized."),
            ("docs/offline-sync.md", "Offline sync must preserve deferred work."),
            ("AGENTS.md", "Run focused tests after editing."),
        )
    )
    evidence = HostEvidenceSnapshot(
        query=derive_task33_retrieval_query(objective),
        objective_sha256=hashlib.sha256(objective.encode()).hexdigest(),
        query_derivation=TASK33_QUERY_DERIVATION,
        evidence_items=evidence_items,
        trust_contract={"selected": [], "rejected": [], "risky": []},
        retrieval_issues=(),
        evidence_categories=("project_docs",),
        project_revision=envelope.project_revision,
        index_revision=envelope.index_revision,
        response_status="success",
        raw_retrieval_tokens=30,
        retrieval_wall_time_seconds=0.0,
    )
    output = CodexExploratoryWorker(model=model, sandbox_mode=sandbox_mode).run(
        envelope, evidence, timeout_seconds=timeout_seconds
    )
    return {
        "status": "exploratory_verified",
        "model": output.usage.model,
        "input_tokens": output.usage.input_tokens,
        "output_tokens": output.usage.output_tokens,
        "reasoning_tokens": output.usage.reasoning_tokens,
        "measurement_source": "codex_cli_jsonl",
        "server_request_id_verified": False,
        "provider_usage_verified": False,
    }


def _contains_auth_artifact(root: Path) -> bool:
    return any(
        path.is_file() and path.name in {"auth.json", "credentials.json"}
        for path in root.rglob("*")
    )


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def summarize_exploratory_results(
    results: list[dict[str, Any]],
    *,
    expected_conditions: Iterable[str] | None = None,
) -> dict[str, Any]:
    blocked_statuses = {
        "condition_setup_failed",
        "runner_unavailable",
        "runner_failed",
        "timeout",
    }
    rows: dict[str, dict[str, Any]] = {}
    indexing_attribution_present: set[str] = set()
    for result in results:
        condition = str(result.get("condition_id") or "")
        raw_metrics = result.get("metrics")
        metrics: dict[str, Any] = raw_metrics if isinstance(raw_metrics, dict) else {}
        raw_budget = result.get("budget")
        budget: dict[str, Any] = raw_budget if isinstance(raw_budget, dict) else {}
        raw_attribution = result.get("token_attribution")
        attribution: dict[str, Any] = (
            raw_attribution if isinstance(raw_attribution, dict) else {}
        )
        raw_indexing = attribution.get("indexing")
        indexing: dict[str, Any] = raw_indexing if isinstance(raw_indexing, dict) else {}
        provider_input_tokens = indexing.get("provider_input_tokens")
        provider_output_tokens = indexing.get("provider_output_tokens")
        if (
            isinstance(indexing.get("status"), str)
            and isinstance(provider_input_tokens, int)
            and isinstance(provider_output_tokens, int)
            and isinstance(indexing.get("included_in_parent_budget"), bool)
        ):
            indexing_attribution_present.add(condition)
        rows[condition] = {
            "status": result.get("status"),
            "resolved": result.get("resolved"),
            "public_tests_passed": result.get("public_tests_passed"),
            "hidden_tests_passed": result.get("hidden_tests_passed"),
            "input_tokens": metrics.get("input_tokens"),
            "output_tokens": metrics.get("output_tokens"),
            "cached_input_tokens": metrics.get("cached_input_tokens"),
            "uncached_input_tokens": metrics.get("uncached_input_tokens"),
            "input_token_basis": budget.get("input_token_basis"),
            "indexing_provider_tokens": (
                provider_input_tokens + provider_output_tokens
                if isinstance(provider_input_tokens, int)
                and isinstance(provider_output_tokens, int)
                else None
            ),
            "indexing_provider_tokens_included": budget.get(
                "indexing_provider_tokens_included"
            ),
            "worker_input_tokens": metrics.get("worker_input_tokens"),
            "worker_output_tokens": metrics.get("worker_output_tokens"),
            "system_total_tokens": metrics.get("system_total_tokens"),
            "time_to_first_edit": None,
            "time_to_first_edit_reason": "codex_jsonl_not_stream_timed",
            "total_latency": metrics.get("total_latency"),
            "action_packet_tokens": metrics.get("action_packet_tokens"),
            "evidence_fingerprint": metrics.get("evidence_fingerprint"),
        }
    expected_order = list(expected_conditions or load_protocol()["conditions"])
    expected = set(expected_order)
    missing = sorted(expected - set(rows))
    missing_indexing_attribution = [
        condition
        for condition in expected_order
        if condition in rows and condition not in indexing_attribution_present
    ]
    blocked = sorted(
        condition
        for condition, row in rows.items()
        if row.get("status") in blocked_statuses
    )
    complete = not missing and not blocked and not missing_indexing_attribution
    return {
        "schema_version": 1,
        "status": "complete_exploratory" if complete else "inconclusive_exploratory",
        "verdict": "EXPLORATORY_NON_CAUSAL" if complete else "INCONCLUSIVE",
        "valid": False,
        "causal_claim_allowed": False,
        "provider_usage_verified": False,
        "server_request_ids_verified": False,
        "hard_turn_limit_verified": False,
        "missing_conditions": missing,
        "missing_indexing_attribution": missing_indexing_attribution,
        "blocked_conditions": blocked,
        "conditions": rows,
        "warning": (
            "Directional local evidence only. This summary is not accepted by "
            "task33_validation.py and cannot produce a VALID verdict."
        ),
    }


def _parse_codex_jsonl(stdout: str) -> tuple[dict[str, Any], dict[str, Any], str]:
    selection: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None
    thread_id = ""
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "thread.started" and isinstance(event.get("thread_id"), str):
            thread_id = event["thread_id"]
        item = event.get("item")
        if (
            event.get("type") == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == "agent_message"
            and isinstance(item.get("text"), str)
        ):
            try:
                candidate = json.loads(item["text"])
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                selection = candidate
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            usage = event["usage"]
    if selection is None or usage is None or not thread_id:
        raise IsolatedDeliveryError("codex_exploratory_worker_incomplete_jsonl")
    return selection, usage, thread_id


def _usage_int(usage: dict[str, Any], key: str, *, required: bool = True) -> int | None:
    value = usage.get(key)
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise IsolatedDeliveryError("codex_exploratory_worker_invalid_usage:" + key)
    return value


def _json_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())