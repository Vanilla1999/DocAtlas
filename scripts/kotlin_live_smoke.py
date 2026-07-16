#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any, Callable
from urllib.parse import urlparse

from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import call_docs_tool_payload


QUESTION = "coroutines launch async example with code"
VERSION = "1.8.1"
SOURCE_URL = "https://github.com/Kotlin/kotlinx.coroutines/blob/1.8.1/docs/topics/coroutines-basics.md"
TERMINAL = {"succeeded", "partial", "failed", "cancelled", "interrupted"}


def validate_artifact(artifact: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "schema_version", "mode", "command", "docatlas_commit", "source_ref", "elapsed_ms",
        "terminal_status", "citations", "requested_version", "resolved_version",
        "canonical_source_identity", "query", "code_match", "recorded_at",
    }
    missing = sorted(required - artifact.keys())
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")
    if artifact.get("schema_version") != "kotlin-smoke-1.0":
        errors.append("unsupported schema_version")
    if artifact.get("mode") not in {"fixture", "live"}:
        errors.append("mode must be fixture or live")
    if artifact.get("terminal_status") not in {"succeeded", "partial"}:
        errors.append("terminal_status must be succeeded or partial")
    citations = artifact.get("citations")
    if not isinstance(citations, list) or not citations or not all(isinstance(item, str) for item in citations):
        errors.append("citations must be a non-empty string list")
    elif not all(_is_pinned_source(item) for item in citations):
        errors.append("citations must reference the pinned official Kotlin source")
    if artifact.get("query") != QUESTION:
        errors.append("query does not match the acceptance question")
    if artifact.get("code_match") is not True:
        errors.append("code_match must be true")
    if artifact.get("requested_version") != VERSION:
        errors.append(f"requested_version must be {VERSION}")
    if artifact.get("resolved_version") != VERSION:
        errors.append(f"resolved_version must be {VERSION}")
    if not _is_pinned_identity(artifact.get("canonical_source_identity")):
        errors.append("canonical_source_identity must bind the pinned official Kotlin source")
    if artifact.get("mode") == "live" and artifact.get("docatlas_commit") == "unknown":
        errors.append("live mode must record the DocAtlas commit")
    if not isinstance(artifact.get("elapsed_ms"), int) or artifact.get("elapsed_ms", -1) < 0:
        errors.append("elapsed_ms must be a non-negative integer")
    return errors


def _is_pinned_source(value: str) -> bool:
    parsed = urlparse(value)
    path = parsed.path.rstrip("/")
    if parsed.hostname == "github.com":
        return path.startswith(
            f"/Kotlin/kotlinx.coroutines/blob/{VERSION}/"
        )
    if parsed.hostname == "raw.githubusercontent.com":
        return path.startswith(f"/Kotlin/kotlinx.coroutines/{VERSION}/")
    return False


def _looks_like_kotlin_code(value: str) -> bool:
    lowered = value.casefold()
    has_required_api = "launch" in lowered or (
        "async" in lowered and "await" in lowered
    )
    code_markers = ("```", "{", "}", "(", ")", "val ", "fun ", ".await")
    return has_required_api and any(marker in lowered for marker in code_markers)


def _cited_code_sources(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        source = next(
            (
                item
                for key in ("source", "url", "citation", "path_or_url")
                if isinstance((item := value.get(key)), str)
            ),
            None,
        )
        evidence = next(
            (
                item
                for key in ("content", "snippet", "text", "answer")
                if isinstance((item := value.get(key)), str)
            ),
            None,
        )
        if source and evidence and _is_pinned_source(source) and _looks_like_kotlin_code(evidence):
            found.append(source)
        for item in value.values():
            found.extend(_cited_code_sources(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_cited_code_sources(item))
    return list(dict.fromkeys(found))


def _is_pinned_identity(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    return value == f"github:Kotlin/kotlinx.coroutines@{VERSION}" or _is_pinned_source(value)


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def run_smoke(
    call_tool: Callable[[str, dict[str, Any]], dict[str, Any]],
    *,
    mode: str,
    timeout_seconds: float,
    command: str,
) -> dict[str, Any]:
    if timeout_seconds <= 0 or timeout_seconds > 180:
        raise ValueError("timeout must be greater than zero and at most 180 seconds")
    previous_handler = None
    alarm_enabled = hasattr(signal, "setitimer")
    if alarm_enabled:
        previous_handler = signal.getsignal(signal.SIGALRM)
        signal.signal(
            signal.SIGALRM,
            lambda _signum, _frame: (_ for _ in ()).throw(
                TimeoutError(f"Kotlin smoke exceeded {timeout_seconds:g} seconds")
            ),
        )
        signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    try:
        return _run_smoke(call_tool, mode=mode, timeout_seconds=timeout_seconds, command=command)
    finally:
        if alarm_enabled:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)


def _run_smoke(
    call_tool: Callable[[str, dict[str, Any]], dict[str, Any]],
    *,
    mode: str,
    timeout_seconds: float,
    command: str,
) -> dict[str, Any]:
    started = time.monotonic()
    prepare_started = time.monotonic()
    prepared = call_tool(
        "prepare_docs",
        {
            "action": "prefetch_library_docs",
            "library": "kotlinx.coroutines",
            "ecosystem": "kotlin",
            "version": VERSION,
            "docs_url": SOURCE_URL,
            "force_refresh": True,
            "async": True,
        },
    )
    job_id = prepared.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise RuntimeError(f"prepare_docs did not return a job_id: {prepared.get('reason_code') or prepared.get('status')}")
    if time.monotonic() - prepare_started >= 1.0:
        raise RuntimeError("prepare_docs did not return job_id within one second")

    status: dict[str, Any] = {}
    while time.monotonic() - started < timeout_seconds:
        status = call_tool("docs_status", {"action": "job", "job_id": job_id})
        if status.get("status") in TERMINAL:
            break
        time.sleep(0.1)
    else:
        raise TimeoutError(f"Kotlin smoke exceeded {timeout_seconds:g} seconds")

    context = call_tool(
        "get_docs_context",
        {
            "question": QUESTION,
            "library": "kotlinx.coroutines",
            "ecosystem": "kotlin",
            "version": VERSION,
            "mode": "library",
            "response_style": "snippet-first",
            "output_mode": "full",
        },
    )
    citations = _cited_code_sources(context)
    if not citations:
        raise RuntimeError(
            "get_docs_context did not return cited code-bearing evidence from the pinned official Kotlin source"
        )
    identity = context.get("identity") if isinstance(context.get("identity"), dict) else {}
    resolved_version = context.get("resolved_version") or identity.get("resolved_version") or identity.get("version")
    canonical_source_identity = (
        context.get("canonical_source_identity")
        or identity.get("docs_url")
        or citations[0]
    )
    artifact = {
        "schema_version": "kotlin-smoke-1.0",
        "mode": mode,
        "command": command,
        "docatlas_commit": _git_commit(),
        "source_ref": "Kotlin/kotlinx.coroutines@1.8.1",
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "terminal_status": status.get("status"),
        "citations": citations[:20],
        "requested_version": VERSION,
        "resolved_version": resolved_version,
        "canonical_source_identity": canonical_source_identity,
        "query": QUESTION,
        "code_match": True,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    errors = validate_artifact(artifact)
    if errors:
        raise RuntimeError("invalid smoke result: " + "; ".join(errors))
    return artifact


def _fixture_call_tool() -> Callable[[str, dict[str, Any]], dict[str, Any]]:
    def call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "prepare_docs":
            return {"status": "pending", "job_id": "fixture-kotlin-job"}
        if name == "docs_status":
            return {"status": "partial", "job_id": arguments["job_id"], "failed_pages": 1}
        if name == "get_docs_context":
            return {
                "status": "success",
                "resolved_version": VERSION,
                "canonical_source_identity": "github:Kotlin/kotlinx.coroutines@1.8.1",
                "results": [{"source": SOURCE_URL, "content": "launch { async { 42 }.await() }"}],
            }
        raise AssertionError(name)
    return call


def _require_isolated_home(parser: argparse.ArgumentParser) -> None:
    configured = os.environ.get("DOCMANCER_HOME")
    if not configured:
        parser.error(
            "--mode live requires an explicit isolated DOCMANCER_HOME; "
            "use DOCMANCER_HOME=\"$(mktemp -d)\""
        )
    selected = Path(configured).expanduser().resolve()
    default_home = (Path.home() / ".docmancer").resolve()
    if selected == default_home:
        parser.error("--mode live refuses the default DocAtlas home; use a temporary isolated directory")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the bounded pinned Kotlin documentation smoke.")
    parser.add_argument("--mode", choices=("fixture", "live"), default="fixture")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    command = " ".join([Path(sys.argv[0]).name, *(argv if argv is not None else sys.argv[1:])])
    if args.mode == "fixture":
        caller = _fixture_call_tool()
    else:
        _require_isolated_home(parser)
        service = LibraryDocsService()
        caller = lambda name, payload: call_docs_tool_payload(name, payload, service)
    artifact = run_smoke(caller, mode=args.mode, timeout_seconds=args.timeout, command=command)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
