#!/usr/bin/env python3
"""Capture fixed questions through real stdio MCP, without generating LLM answers.

Run the harness outside the reviewed source checkout using its editable-install
Python. Only explicit local sync and get_docs_context are called. No returned
lifecycle action is executed, no gold is loaded, and no retry selects a winner.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval.tdd_question_inventory import inspect_source, load_cases, request_for

DIGEST = "12835d40de697b0c719181bba59f88b86c66d4337bcfce7fc92bb673d969836f"


def write_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def git(repo, *arguments):
    return subprocess.check_output(["git", "-C", str(repo), *arguments], text=True, timeout=90).strip()


def decode(result):
    if isinstance(result.structuredContent, dict):
        return result.structuredContent
    texts = [item.text for item in result.content if getattr(item, "type", None) == "text"]
    if len(texts) != 1:
        raise ValueError("Expected structured result or one JSON text fallback")
    payload = json.loads(texts[0])
    if not isinstance(payload, dict):
        raise ValueError("Expected an object result")
    return payload


def verify_install(repo, target):
    import docmancer
    expected = (repo / "docmancer/__init__.py").resolve()
    if Path(docmancer.__file__).resolve() != expected:
        raise ValueError("Wrong editable installation; keep harness outside the checkout")
    if git(repo, "rev-parse", "HEAD") != target:
        raise ValueError("Target commit mismatch")
    if git(repo, "status", "--porcelain", "--untracked-files=normal"):
        raise ValueError("Reviewed checkout is not clean")
    return {"commit": target, "imported_package": str(expected), "tree": git(repo, "rev-parse", "HEAD^{tree}")}


async def execute(args, cases, report):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens

    report["installation"] = verify_install(args.repo, args.target)
    for lane in ("direct", "assisted"):
        with tempfile.TemporaryDirectory(prefix="docatlas-fixed30-") as temporary:
            root = Path(temporary); project = root / "project"; home = root / "home"; home.mkdir()
            subprocess.run(["git", "clone", "--no-hardlinks", "--no-checkout", "--quiet", "--", str(args.repo), str(project)], check=True, timeout=90)
            git(project, "checkout", "--quiet", "--detach", args.target)
            env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "WINDIR", "LANG", "LC_ALL", "TMPDIR", "TEMP", "TMP") if k in os.environ}
            env.update(HOME=str(home), USERPROFILE=str(home), DOCATLAS_HOME=str(home / "state"),
                       DOCATLAS_OFFLINE="1", DOCATLAS_AUTO_VECTORS="0", NO_PROXY="*",
                       DOCATLAS_REGISTRY_API_URL="http://127.0.0.1:1")
            params = StdioServerParameters(command=sys.executable,
                args=["-c", "from docmancer.cli.__main__ import cli; cli()", "mcp", "docs-serve"], env=env, cwd=str(home))
            record = {"lane": lane, "results": []}; report["sessions"].append(record)
            write_report(args.output, report)
            async with stdio_client(params) as streams:
                async with ClientSession(*streams, read_timeout_seconds=timedelta(seconds=args.timeout)) as session:
                    await session.initialize()
                    tools = await session.list_tools(); record["tools_list"] = tools.model_dump(mode="json")
                    if {t.name for t in tools.tools} != {"get_docs_context", "prepare_docs", "docs_status"}:
                        raise ValueError("Unexpected default tool inventory")
                    preparation = await session.call_tool("prepare_docs", {
                        "action": "sync_project_docs", "project_path": str(project), "with_vectors": False,
                    })
                    record["preparation"] = preparation.model_dump(mode="json")
                    write_report(args.output, report)
                    if preparation.isError or decode(preparation).get("status") not in {"success", "ok", "ready"}:
                        raise RuntimeError("Local preparation failed; no approval or confirmation was bypassed")
                    for case in cases:
                        arguments = request_for(case, str(project), lane)
                        row = {"id": case["id"], "arguments": arguments, "semantic_assessment": "REQUIRES_REVIEW"}
                        record["results"].append(row); started = time.perf_counter()
                        try:
                            async with asyncio.timeout(args.timeout):
                                result = await session.call_tool("get_docs_context", arguments)
                            payload = decode(result)
                            row.update(execution_status="EXECUTED", seconds=time.perf_counter() - started,
                                       is_error=bool(result.isError), wire_result=result.model_dump(mode="json"), payload=payload)
                            row["source_checks"] = [inspect_source(s, project) for s in payload.get("sources", [])]
                            row["measured_budget_tokens"] = docs_context_budget_tokens(payload)
                            for check in row["source_checks"]:
                                if "file_sha256" in check:
                                    directory = args.output.parent / "source-snapshots"; directory.mkdir(exist_ok=True)
                                    source = project / check["path"]
                                    (directory / (check["file_sha256"] + ".txt")).write_bytes(source.read_bytes())
                        except Exception as error:
                            row.update(execution_status="CAPTURE_ERROR", error=f"{type(error).__name__}: {error}")
                            write_report(args.output, report)
                            raise
                        write_report(args.output, report)
                        print(lane, case["id"], payload.get("status"), payload.get("kind"), flush=True)
            record["tracked_changes_after"] = git(project, "diff", "--name-only", args.target)
            if record["tracked_changes_after"]:
                raise RuntimeError("A capture changed tracked files in its disposable project copy")
    report["installation_after"] = verify_install(args.repo, args.target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--target", required=True)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(); args.repo = args.repo.resolve(); args.output = args.output.resolve()
    if not re.fullmatch(r"[0-9a-f]{40}", args.target) or args.timeout <= 0:
        parser.error("Full lowercase commit SHA and positive timeout required")
    cases = load_cases(args.cases, DIGEST)
    report = {"schema_version": "tdd-question-capture-v1", "status": "RUNNING", "sessions": [],
              "target_commit": args.target, "questions_sha256": DIGEST,
              "utc_started": datetime.now(timezone.utc).isoformat(), "python": sys.version,
              "host_model_quality": "NOT_MEASURED", "runtime_hash_integrity": "NOT_MEASURED",
              "claim_boundary": "Actual stdio capture, no LLM final answer, no semantic score. Assisted lookups are source-informed diagnostic cues.",
              "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    code = 0
    try:
        asyncio.run(execute(args, cases, report)); report["status"] = "COMPLETE"
    except Exception as error:
        report["status"] = "INCOMPLETE" if report["sessions"] else "NOT_RUN"
        report["error"] = f"{type(error).__name__}: {error}"; print(report["error"], file=sys.stderr); code = 2
    finally:
        report["executed_question_calls"] = sum(r.get("execution_status") == "EXECUTED" for s in report["sessions"] for r in s["results"])
        report["utc_finished"] = datetime.now(timezone.utc).isoformat()
        write_report(args.output, report)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
