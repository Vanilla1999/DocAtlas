#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import venv
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterator

import httpx

from eval.agent_developer_v1.installed_mcp_benchmark import run_benchmark
from eval.agent_developer_v1.installed_mcp_contract import (
    ArtifactIdentity,
    PlannerOutputError,
    PROJECT_TOKEN,
    ScriptedPlanner,
)
from scripts.openai_live_support import (
    OpenAILiveHTTPError,
    retry_delay_seconds,
    should_retry_openai_response,
)
from scripts.opencode_chat_support import (
    DEFAULT_OPENCODE_MODEL,
    OPENCODE_VARIANT,
    REPORT_MODEL,
    OpenCodeJSONClient,
    OpenCodeModelOutputError,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "eval"
    / "agent_developer_v1"
    / "results"
    / "installed-mcp-benchmark.json"
)
DEFAULT_OPENAI_MODEL = "gpt-5.6-luna"
DEFAULT_API_BASE = "https://api.openai.com/v1"
REASONING_EFFORT = "medium"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: int = 300,
) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed exit={completed.returncode}: "
            f"{' '.join(command[:4])}: {completed.stdout[-1200:]}"
        )
    return completed.stdout.strip()


def _source_commit(explicit: str | None) -> str:
    value = (
        explicit.strip()
        if explicit
        else _run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, timeout=30)
    )
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("source commit must be a lowercase 40-character SHA")
    return value


def _venv_paths(root: Path) -> tuple[Path, Path]:
    if os.name == "nt":
        return (
            root / "Scripts" / "python.exe",
            root / "Scripts" / "doc-atlas.exe",
        )
    return root / "bin" / "python", root / "bin" / "doc-atlas"


def _download_public_wheel(*, root: Path, version: str) -> Path:
    download = root / "download"
    download.mkdir()
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--isolated",
            "--no-cache-dir",
            "--no-deps",
            "--only-binary=:all:",
            "--dest",
            str(download),
            f"doc-atlas=={version}",
        ],
        cwd=root,
        timeout=300,
    )
    wheels = sorted(download.glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(
            f"expected one public wheel, found {[path.name for path in wheels]!r}"
        )
    return wheels[0]


@contextmanager
def installed_artifact(
    *,
    wheel: Path | None,
    pypi_version: str | None,
    source_commit: str,
    public_release_verified: bool,
) -> Iterator[tuple[ArtifactIdentity, str]]:
    if (wheel is None) == (pypi_version is None):
        raise ValueError("provide exactly one of --wheel or --pypi-version")
    if public_release_verified and pypi_version is None:
        raise ValueError("--public-release-verified requires --pypi-version")

    with TemporaryDirectory(prefix="docatlas-installed-artifact-") as raw:
        root = Path(raw)
        selected = (
            wheel.resolve()
            if wheel is not None
            else _download_public_wheel(root=root, version=str(pypi_version))
        )
        if not selected.is_file():
            raise FileNotFoundError(selected)

        venv_root = root / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(venv_root)
        python_executable, cli = _venv_paths(venv_root)
        _run(
            [
                str(python_executable),
                "-m",
                "pip",
                "install",
                "--isolated",
                "--no-cache-dir",
                str(selected),
            ],
            cwd=root,
            timeout=600,
        )
        metadata = json.loads(
            _run(
                [
                    str(python_executable),
                    "-c",
                    (
                        "import importlib.metadata as m, json, platform;"
                        "print(json.dumps({'version':m.version('doc-atlas'),"
                        "'python':platform.python_version()}))"
                    ),
                ],
                cwd=root,
                timeout=60,
            )
        )
        version = str(metadata["version"])
        if pypi_version is not None and version != pypi_version:
            raise RuntimeError(
                f"installed public version {version!r} != {pypi_version!r}"
            )
        if not cli.is_file():
            raise RuntimeError(f"installed doc-atlas CLI is missing: {cli}")

        identity = ArtifactIdentity(
            origin="public-pypi" if pypi_version is not None else "reviewed-wheel",
            distribution="doc-atlas",
            version=version,
            artifact_filename=selected.name,
            artifact_sha256=_sha256(selected),
            source_commit=source_commit,
            python_version=str(metadata["python"]),
            cli_sha256=_sha256(cli),
            public_release_verified=public_release_verified,
        )
        yield identity, str(cli)


def _output_text(response: dict[str, Any]) -> str:
    chunks: list[str] = []
    for item in response.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if isinstance(content, dict) and content.get("type") == "output_text":
                chunks.append(str(content.get("text") or ""))
    return "".join(chunks)


def _strict_nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RuntimeError(f"OpenAI Responses usage omitted valid {name}")
    return value


class OpenAIInstalledPlanner:
    provider_id = "openai-api"
    variant = REASONING_EFFORT

    def __init__(
        self,
        token: str,
        *,
        model: str = DEFAULT_OPENAI_MODEL,
        api_base: str = DEFAULT_API_BASE,
    ) -> None:
        if not token.strip():
            raise ValueError("OPENAI_API_KEY is required")
        if model != DEFAULT_OPENAI_MODEL:
            raise ValueError(
                f"installed live benchmark is pinned to {DEFAULT_OPENAI_MODEL}"
            )
        self.model = model
        self._token = token
        self._api_base = api_base.rstrip("/")

    def choose(
        self,
        messages: list[dict[str, Any]],
        *,
        output_schema: dict[str, Any],
        purpose: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        payload = {
            "model": self.model,
            "input": messages,
            "reasoning": {"effort": REASONING_EFFORT},
            "max_output_tokens": 900,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "installed_mcp_action_v1",
                    "strict": True,
                    "schema": output_schema,
                }
            },
            "metadata": {"benchmark": purpose[:64]},
        }
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        response: httpx.Response | None = None
        for attempt in range(4):
            response = httpx.post(
                self._api_base + "/responses",
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                },
                content=serialized,
                timeout=120,
            )
            if response.status_code < 400:
                break
            if attempt < 3 and should_retry_openai_response(response):
                time.sleep(retry_delay_seconds(response, attempt))
                continue
            raise OpenAILiveHTTPError(response)
        assert response is not None
        if response.status_code >= 400:
            raise OpenAILiveHTTPError(response)

        request_id = str(response.headers.get("x-request-id") or "").strip()
        body = response.json()
        raw_usage = body.get("usage")
        if not request_id or not isinstance(raw_usage, dict):
            raise RuntimeError("OpenAI response omitted request identity or usage")
        input_tokens = _strict_nonnegative_int(
            raw_usage.get("input_tokens"),
            "input_tokens",
        )
        output_tokens = _strict_nonnegative_int(
            raw_usage.get("output_tokens"),
            "output_tokens",
        )
        details = raw_usage.get("output_tokens_details")
        reasoning_tokens = None
        if isinstance(details, dict) and details.get("reasoning_tokens") is not None:
            reasoning_tokens = _strict_nonnegative_int(
                details.get("reasoning_tokens"),
                "reasoning_tokens",
            )
        usage = {
            "request_id": request_id,
            "request_ids": {
                "x-request-id": request_id,
                "response-id": str(body.get("id") or ""),
            },
            "model": str(body.get("model") or self.model),
            "variant": REASONING_EFFORT,
            "reasoning_effort": REASONING_EFFORT,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "reasoning_tokens": reasoning_tokens,
            "request_payload_sha256": hashlib.sha256(serialized).hexdigest(),
            "estimated_input_tokens": max(1, len(serialized) // 4),
        }
        try:
            action = json.loads(_output_text(body))
        except json.JSONDecodeError as exc:
            raise PlannerOutputError(
                "OpenAI structured output was not valid JSON",
                usage=usage,
            ) from exc
        if not isinstance(action, dict):
            raise PlannerOutputError(
                "OpenAI structured output was not an object",
                usage=usage,
            )
        return action, usage


class OpenCodeInstalledPlanner:
    provider_id = "opencode-chat"
    model = REPORT_MODEL
    variant = OPENCODE_VARIANT

    def __init__(self, *, model_id: str = DEFAULT_OPENCODE_MODEL) -> None:
        self._client = OpenCodeJSONClient(model_id=model_id)

    def choose(
        self,
        messages: list[dict[str, Any]],
        *,
        output_schema: dict[str, Any],
        purpose: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        try:
            return self._client.complete_json(
                messages=messages,
                schema=output_schema,
                purpose=purpose,
            )
        except OpenCodeModelOutputError as exc:
            raise PlannerOutputError(
                "schema_invalid_after_format_repair",
                usage=exc.usage,
            ) from exc


def _scripted_plans() -> dict[str, list[dict[str, Any]]]:
    valid = {
        "kind": "tool_call",
        "tool_name": "get_docs_context",
        "arguments": {
            "question": "What is OrdersDraftStore?",
            "project_path": PROJECT_TOKEN,
            "mode": "project",
            "scope": "module",
            "module_path": "packages/orders",
        },
        "reason": "Retrieve the module-local storage contract.",
    }
    invalid = {
        **valid,
        "arguments": {
            key: value
            for key, value in valid["arguments"].items()
            if key != "question"
        },
        "reason": "Exercise exact-schema rejection before bounded repair.",
    }
    return {"module_definition_supported": [invalid, valid]}


def _planner(args: argparse.Namespace):
    if args.planner == "scripted":
        return ScriptedPlanner(_scripted_plans())
    if args.planner == "opencode":
        return OpenCodeInstalledPlanner(model_id=args.opencode_model)
    token = os.environ.get("OPENAI_API_KEY") or ""
    return OpenAIInstalledPlanner(
        token,
        model=args.openai_model,
        api_base=args.api_base,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a real coding model against an installed DocAtlas MCP server "
            "using the exact public tools/list schemas"
        )
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--wheel", type=Path)
    source.add_argument("--pypi-version")
    parser.add_argument(
        "--public-release-verified",
        action="store_true",
        help="mark PyPI origin as independently release-verified",
    )
    parser.add_argument("--source-commit")
    parser.add_argument(
        "--planner",
        choices=("scripted", "opencode", "openai"),
        default="opencode",
    )
    parser.add_argument("--opencode-model", default=DEFAULT_OPENCODE_MODEL)
    parser.add_argument("--openai-model", default=DEFAULT_OPENAI_MODEL)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--task", action="append", dest="tasks")
    parser.add_argument("--max-schema-repairs", type=int, default=1)
    parser.add_argument("--min-pass-rate", type=float, default=0.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    if not 0.0 <= args.min_pass_rate <= 1.0:
        parser.error("--min-pass-rate must be between 0 and 1")

    task_ids = set(args.tasks) if args.tasks else None
    if args.planner == "scripted" and task_ids is None:
        task_ids = {"module_definition_supported"}

    planner = _planner(args)
    commit = _source_commit(args.source_commit)
    with installed_artifact(
        wheel=args.wheel,
        pypi_version=args.pypi_version,
        source_commit=commit,
        public_release_verified=args.public_release_verified,
    ) as (artifact, server_command):
        report = run_benchmark(
            planner=planner,
            server_command=server_command,
            artifact=artifact,
            task_ids=task_ids,
            max_schema_repairs=args.max_schema_repairs,
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "Installed MCP Agent benchmark: "
        f"origin={report['artifact']['origin']}; "
        f"model={report['provider']['model']}; "
        f"{report['passed_tasks']}/{report['task_count']} pass; "
        f"false-supported={report['false_supported']}; "
        f"contamination={report['forbidden_source_contamination']}; "
        f"schema={report['mcp']['schema_sha256']}"
    )
    if report["infrastructure_errors"]:
        for error in report["infrastructure_errors"]:
            print(f"- infrastructure: {error}")
        return 2
    return 0 if float(report["pass_rate"]) >= args.min_pass_rate else 1


if __name__ == "__main__":
    raise SystemExit(main())
