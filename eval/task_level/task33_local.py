from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from eval.task_level.execution import _prepare_shared_task33_evidence
from eval.task_level.github_models import (
    DEFAULT_OPENAI_MODEL,
    OPENAI_API_ENDPOINT,
    run_openai_api_capability_probe,
)
from eval.task_level.runner import load_tasks
from eval.task_level.sandbox_execution import DockerCommandSandbox
from eval.task_level.task33_pilot import (
    TASK33C_PILOT_TASK_ID,
    TASK33C_REQUIRED_EVIDENCE_CATEGORIES,
    TASK33C_REQUIRED_EVIDENCE_PATHS,
)
from eval.task_level.task33_validation import PROTOCOL_PATH, load_protocol


REQUIREMENTS_PATH = Path(__file__).with_name("task33c_evaluator_requirements.txt")
FIXTURE_TEMPLATE = Path(__file__).with_name("fixtures") / "templates" / TASK33C_PILOT_TASK_ID


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the frozen Task 33C OpenAI API preflight and optional local causal pilot"
    )
    parser.add_argument(
        "--run-causal-pilot",
        action="store_true",
        help="Run the one-attempt causal pilot after every preflight gate passes",
    )
    parser.add_argument("--skip-image-build", action="store_true")
    parser.add_argument("--image", default="docatlas-task33c-evaluator:local")
    parser.add_argument("--model", default=DEFAULT_OPENAI_MODEL)
    parser.add_argument(
        "--run-id",
        default=datetime.now(timezone.utc).strftime("task33c_local_openai_%Y%m%d_%H%M%S"),
    )
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--worker-timeout-seconds", type=int, default=90)
    parser.add_argument("--preflight-output", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)

    protocol = load_protocol()
    profile = (protocol.get("provider_profiles") or {}).get("openai-api") or {}
    if args.model != profile.get("model"):
        parser.error("--model must match frozen openai-api profile: " + str(profile.get("model")))
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        parser.error("OPENAI_API_KEY is required and is never persisted")
    if os.environ.get("TASK33C_OPENAI_ENDPOINT", OPENAI_API_ENDPOINT) != profile.get("endpoint"):
        parser.error("TASK33C_OPENAI_ENDPOINT must match the frozen openai-api endpoint")

    container = protocol["container"]
    requirement_hash = _sha256(REQUIREMENTS_PATH)
    if requirement_hash != container["requirements_sha256"]:
        raise SystemExit("Task 33C evaluator requirement lock hash mismatch")

    output = args.preflight_output or (
        Path("eval/task_level/results") / f"{args.run_id}_preflight"
    )
    output.mkdir(parents=True, exist_ok=False)
    causal_environment = {
        **os.environ,
        "DOCMANCER_OFFLINE": "1",
        "TASK33C_BASE_IMAGE": container["base_image"],
        "TASK33C_EVALUATOR_REQUIREMENTS_SHA256": requirement_hash,
        "TASK33C_TEST_CONTAINER_IMAGE": args.image,
        "TASK33C_REQUIRE_DOCKER_SANDBOX": "1",
        "TASK33C_OPENAI_MODEL": args.model,
        "TASK33C_OPENAI_ENDPOINT": str(profile["endpoint"]),
    }

    summary: dict[str, Any] = {
        "schema_version": 1,
        "status": "failed",
        "provider_profile": "openai-api",
        "model": args.model,
        "protocol_sha256": _sha256(PROTOCOL_PATH),
        "image": args.image,
        "base_image": container["base_image"],
        "requirements_sha256": requirement_hash,
        "run_causal_pilot_requested": args.run_causal_pilot,
        "checks": {},
    }
    try:
        if not args.skip_image_build:
            summary["checks"]["image_build"] = _build_image(args.image, container["base_image"])
        else:
            summary["checks"]["image_build"] = {"status": "skipped_by_user"}
        uv_cache = _prewarm_fixture_dependencies(output)
        causal_environment["UV_CACHE_DIR"] = str(uv_cache)
        summary["checks"]["fixture_dependency_prewarm"] = {"status": "verified"}

        provider = run_openai_api_capability_probe(
            os.environ["OPENAI_API_KEY"],
            model=args.model,
            endpoint=str(profile["endpoint"]),
        )
        _write_json(output / "openai-api-capability.json", provider)
        summary["checks"]["provider"] = provider

        boundary = DockerCommandSandbox(args.image).verify()
        _write_json(output / "docker-sandbox-canary.json", boundary)
        summary["checks"]["docker"] = boundary

        retrieval = _probe_retrieval(output)
        _write_json(output / "frozen-retrieval.json", retrieval)
        summary["checks"]["retrieval"] = retrieval

        verified = all(
            check.get("status") in {"verified", "skipped_by_user"}
            for check in summary["checks"].values()
        )
        if not verified:
            summary["status"] = "inconclusive"
            return 3
        summary["status"] = "verified"
        if not args.run_causal_pilot:
            return 0

        command = [
            sys.executable,
            "-m",
            "eval.task_level.runner",
            "--task33c-pilot",
            "--task33c-provider-profile",
            "openai-api",
            "--tasks",
            TASK33C_PILOT_TASK_ID,
            "--runner-factory",
            "eval.task_level.github_models:create_openai_api_runner",
            "--isolated-worker-factory",
            "eval.task_level.github_models:create_openai_api_worker",
            "--verify-runner",
            "--verify-docatlas-tool",
            "--model",
            args.model,
            "--timeout-seconds",
            str(args.timeout_seconds),
            "--isolated-worker-timeout-seconds",
            str(args.worker_timeout_seconds),
            "--run-id",
            args.run_id,
        ]
        completed = subprocess.run(command, env=causal_environment, check=False)
        summary["causal_runner_returncode"] = completed.returncode
        summary["causal_run_directory"] = f"eval/task_level/results/{args.run_id}"
        summary["status"] = "valid" if completed.returncode == 0 else "inconclusive"
        return completed.returncode
    except Exception as exc:
        summary["error"] = f"{exc.__class__.__name__}: {str(exc)[:2_000]}"
        return 3
    finally:
        _write_json(output / "preflight-summary.json", summary)


def _build_image(image: str, base_image: str) -> dict[str, Any]:
    dockerfile = (
        f"FROM --platform=linux/amd64 {base_image}\n"
        "COPY eval/task_level/task33c_evaluator_requirements.txt /tmp/requirements.txt\n"
        "RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt\n"
    )
    completed = subprocess.run(
        ["docker", "build", "--pull", "--tag", image, "--file", "-", "."],
        input=dockerfile,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("evaluator image build failed: " + completed.stdout[-4_000:])
    inspected = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", image],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if inspected.returncode != 0 or not inspected.stdout.strip():
        raise RuntimeError("built evaluator image could not be inspected")
    image_id = inspected.stdout.strip()
    return {
        "status": "verified",
        "image_id": image_id,
        "image_id_sha256": hashlib.sha256(image_id.encode()).hexdigest(),
    }


def _prewarm_fixture_dependencies(output: Path) -> Path:
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError("uv is required for the frozen fixture dependency prewarm")
    cache = output.resolve() / "uv-cache"
    environment = {**os.environ, "UV_CACHE_DIR": str(cache)}
    with tempfile.TemporaryDirectory(prefix="task33c-prewarm-") as raw:
        project = Path(raw)
        shutil.copy2(FIXTURE_TEMPLATE / "pyproject.toml", project / "pyproject.toml")
        completed = subprocess.run(
            [uv, "sync", "--python", "3.14"],
            cwd=project,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    if completed.returncode != 0:
        raise RuntimeError("fixture dependency prewarm failed: " + completed.stdout[-4_000:])
    return cache


def _probe_retrieval(output: Path) -> dict[str, Any]:
    task = next(task for task in load_tasks() if task.task_id == TASK33C_PILOT_TASK_ID)
    with tempfile.TemporaryDirectory(prefix="task33c-local-retrieval-") as raw:
        evidence, preparation = _prepare_shared_task33_evidence(task, Path(raw), 0)
    paths = {str(item.get("path") or "") for item in evidence.evidence_items}
    missing_categories = sorted(
        set(TASK33C_REQUIRED_EVIDENCE_CATEGORIES) - set(evidence.evidence_categories)
    )
    missing_paths = sorted(set(TASK33C_REQUIRED_EVIDENCE_PATHS) - paths)
    verified = (
        evidence.response_status == "success"
        and evidence.retrieval_calls == 1
        and not evidence.retrieval_issues
        and bool(evidence.evidence_items)
        and not missing_categories
        and not missing_paths
    )
    return {
        "schema_version": 1,
        "status": "verified" if verified else "failed",
        "response_status": evidence.response_status,
        "query": evidence.query,
        "query_derivation": evidence.query_derivation,
        "retrieval_calls": evidence.retrieval_calls,
        "retrieval_issues": list(evidence.retrieval_issues),
        "evidence_count": len(evidence.evidence_items),
        "evidence_categories": list(evidence.evidence_categories),
        "evidence_fingerprint": evidence.fingerprint,
        "project_revision": evidence.project_revision,
        "index_revision": evidence.index_revision,
        "missing_required_categories": missing_categories,
        "missing_required_paths": missing_paths,
        "preparation_status": preparation.get("status"),
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
