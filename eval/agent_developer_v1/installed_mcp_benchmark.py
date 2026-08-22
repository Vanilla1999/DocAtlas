from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import jsonschema
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from eval.agent_developer_v1.installed_mcp_contract import (
    ArtifactIdentity,
    EventLog,
    EXPECTED_TOOLS,
    Planner,
    PlannerOutputError,
    REPORT_SCHEMA_VERSION,
    action_envelope_schema,
    benchmark_policy_error,
    feedback_message,
    materialize_project_token,
    messages_for_task,
    model_action_record,
    redact,
    result_summary,
    safe_usage,
    schema_digest,
    schema_error_message,
    sha256_json,
    tool_catalog,
    tool_payload,
    validate_envelope,
    validate_tool_arguments,
    PROTOCOL,
)
from eval.agent_developer_v1.model_benchmark import (
    _report_record,
    load_public_tasks,
    model_task_view,
    score_task,
)
import scripts.run_agent_developer_gate as oracle_gate


async def _call_tool(
    session: ClientSession,
    tool_name: str,
    arguments: dict[str, Any],
) -> tuple[Any, dict[str, Any]]:
    result = await session.call_tool(tool_name, arguments)
    return result, tool_payload(result)


async def _run_task(
    *,
    public_task: dict[str, Any],
    oracle_task: dict[str, Any],
    planner: Planner,
    server_command: str,
    artifact: ArtifactIdentity,
    max_schema_repairs: int,
) -> dict[str, Any]:
    events = EventLog()
    records: list[dict[str, Any]] = []
    usage_rows: list[dict[str, Any]] = []
    planning_errors: list[str] = []
    schema_repairs = 0
    failure_stages: list[str] = []

    with TemporaryDirectory(
        prefix=f"docatlas-installed-{public_task['id']}-"
    ) as raw:
        root = Path(raw)
        project = root / "project"
        fixture = oracle_gate.PROJECTS_ROOT / str(public_task["fixture"])
        shutil.copytree(fixture, project)
        home = root / "docatlas-home"
        user_home = root / "user-home"
        home.mkdir()
        user_home.mkdir()

        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env.pop("DOCMANCER_HOME", None)
        env.update(
            {
                "HOME": str(user_home),
                "USERPROFILE": str(user_home),
                "DOCATLAS_HOME": str(home),
                "DOCMANCER_OFFLINE": "1",
                "NO_PROXY": "*",
            }
        )
        params = StdioServerParameters(
            command=server_command,
            args=["mcp", "docs-serve"],
            env=env,
            cwd=str(root),
        )
        events.add(
            "server_start",
            {
                "command": "doc-atlas",
                "args": ["mcp", "docs-serve"],
                "artifact_sha256": artifact.artifact_sha256,
                "source_commit": artifact.source_commit,
            },
        )

        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                catalog = tool_catalog(await session.list_tools())
                names = tuple(row["name"] for row in catalog)
                if names != EXPECTED_TOOLS:
                    raise RuntimeError(
                        f"installed public tool inventory mismatch: {names!r}"
                    )
                schema_sha = schema_digest(catalog)
                events.add(
                    "mcp_tools_list",
                    {
                        "tool_names": list(names),
                        "schema_sha256": schema_sha,
                        "tool_count": len(names),
                    },
                )

                bootstrap_args = {
                    "action": "sync_project_docs",
                    "project_path": str(project),
                    "with_vectors": False,
                }
                bootstrap_result, bootstrap_payload = await _call_tool(
                    session,
                    "prepare_docs",
                    bootstrap_args,
                )
                events.add(
                    "host_bootstrap",
                    {
                        "tool_name": "prepare_docs",
                        "arguments": redact(bootstrap_args, project),
                        "is_error": bool(
                            getattr(bootstrap_result, "isError", False)
                        ),
                        "result_sha256": sha256_json(
                            redact(bootstrap_payload, project)
                        ),
                        "summary": result_summary(bootstrap_payload, project),
                    },
                )
                if bool(getattr(bootstrap_result, "isError", False)):
                    raise RuntimeError("installed project-doc bootstrap failed")
                if str(bootstrap_payload.get("status") or "") in {
                    "error",
                    "failed",
                }:
                    raise RuntimeError(
                        "installed project-doc bootstrap returned "
                        f"{bootstrap_payload.get('status')!r}"
                    )

                mutation = oracle_task.get("mutation_before_calls")
                if isinstance(mutation, dict):
                    target = project / str(mutation.get("path") or "")
                    if not target.is_file():
                        raise RuntimeError(
                            f"fixture mutation target is missing: {target.name}"
                        )
                    append = str(mutation.get("append") or "")
                    with target.open("a", encoding="utf-8") as stream:
                        stream.write(append)
                    events.add(
                        "fixture_mutation",
                        {
                            "relative_path": str(
                                mutation.get("path") or ""
                            ),
                            "append_sha256": hashlib.sha256(
                                append.encode("utf-8")
                            ).hexdigest(),
                        },
                    )

                messages = messages_for_task(
                    public_task,
                    catalog,
                    model_task_view=model_task_view(public_task),
                )
                max_context_calls = int(
                    public_task["max_get_docs_context_calls"]
                )
                max_turns = max_context_calls + 4 + max_schema_repairs
                docs_status_calls = 0
                prepare_calls = 0

                for turn in range(1, max_turns + 1):
                    request_sha = sha256_json(messages)
                    events.add(
                        "model_request",
                        {
                            "turn": turn,
                            "provider_id": planner.provider_id,
                            "model": planner.model,
                            "variant": planner.variant,
                            "request_payload_sha256": request_sha,
                            "tool_schema_sha256": schema_sha,
                        },
                    )
                    try:
                        action, usage = planner.choose(
                            messages,
                            output_schema=action_envelope_schema(),
                            purpose=(
                                "Choose the next installed DocAtlas MCP tool "
                                "call or finish action"
                            ),
                        )
                    except PlannerOutputError as exc:
                        failure_stages.append("model_format")
                        usage_rows.append(
                            {"turn": turn, **safe_usage(exc.usage)}
                        )
                        events.add(
                            "model_format_failure",
                            {
                                "turn": turn,
                                "error": str(exc)[:600],
                                "usage": safe_usage(exc.usage),
                            },
                        )
                        planning_errors.append(
                            "model output failed the outer action contract"
                        )
                        break

                    usage_rows.append({"turn": turn, **safe_usage(usage)})
                    events.add(
                        "model_output",
                        {
                            "turn": turn,
                            "output_sha256": sha256_json(action),
                            "usage": safe_usage(usage),
                        },
                    )
                    try:
                        validate_envelope(action)
                    except (jsonschema.ValidationError, TypeError) as exc:
                        failure_stages.append("model_format")
                        events.add(
                            "model_format_failure",
                            {
                                "turn": turn,
                                "error": schema_error_message(exc),
                            },
                        )
                        planning_errors.append(
                            "model output failed the outer action contract"
                        )
                        break

                    if str(action["kind"]) == "finish":
                        events.add(
                            "finish",
                            {
                                "turn": turn,
                                "reason_sha256": hashlib.sha256(
                                    str(action["reason"]).encode("utf-8")
                                ).hexdigest(),
                            },
                        )
                        records.append(
                            {
                                "tool": "finish",
                                "action": {
                                    "action": "finish",
                                    "reason": str(action["reason"]),
                                },
                                "payload": None,
                                "project_path": str(project),
                            }
                        )
                        break

                    tool_name = str(action["tool_name"])
                    model_arguments = dict(action["arguments"])
                    redacted_args = redact(model_arguments, project)
                    events.add(
                        "tool_attempt",
                        {
                            "turn": turn,
                            "tool_name": tool_name,
                            "arguments": redacted_args,
                            "arguments_sha256": sha256_json(redacted_args),
                        },
                    )

                    try:
                        validate_tool_arguments(
                            tool_name,
                            model_arguments,
                            catalog,
                        )
                    except (
                        jsonschema.ValidationError,
                        jsonschema.SchemaError,
                    ) as exc:
                        failure_stages.append("mcp_schema")
                        events.add(
                            "mcp_schema_failure",
                            {
                                "turn": turn,
                                "tool_name": tool_name,
                                "error": schema_error_message(exc),
                            },
                        )
                        if schema_repairs >= max_schema_repairs:
                            planning_errors.append(
                                "MCP argument schema remained invalid after "
                                "the bounded repair budget"
                            )
                            break
                        schema_repairs += 1
                        messages.extend(
                            [
                                {
                                    "role": "assistant",
                                    "content": json.dumps(
                                        action,
                                        ensure_ascii=False,
                                        sort_keys=True,
                                    ),
                                },
                                {
                                    "role": "user",
                                    "content": (
                                        "The attempted MCP call was rejected "
                                        "by the exact public input schema. "
                                        "Repair it once without changing the "
                                        "task. Error: "
                                        + schema_error_message(exc)
                                    ),
                                },
                            ]
                        )
                        continue

                    materialized = materialize_project_token(
                        model_arguments,
                        project,
                    )
                    policy_error = benchmark_policy_error(
                        tool_name,
                        materialized,
                    )
                    if policy_error:
                        failure_stages.append("harness_policy")
                        events.add(
                            "harness_policy_failure",
                            {
                                "turn": turn,
                                "tool_name": tool_name,
                                "error": policy_error,
                            },
                        )
                        planning_errors.append(policy_error)
                        break

                    if tool_name == "get_docs_context":
                        current_calls = sum(
                            record.get("tool") == "get_docs_context"
                            for record in records
                        )
                        if current_calls >= max_context_calls:
                            planning_errors.append(
                                "model attempted to exceed the "
                                "get_docs_context call budget"
                            )
                            failure_stages.append("budget")
                            break
                    elif tool_name == "docs_status":
                        docs_status_calls += 1
                        if docs_status_calls > 1:
                            planning_errors.append(
                                "model attempted more than one docs_status call"
                            )
                            failure_stages.append("budget")
                            break
                    elif tool_name == "prepare_docs":
                        prepare_calls += 1
                        if prepare_calls > 1:
                            planning_errors.append(
                                "model attempted more than one prepare_docs call"
                            )
                            failure_stages.append("budget")
                            break

                    try:
                        result, payload = await _call_tool(
                            session,
                            tool_name,
                            materialized,
                        )
                    except Exception as exc:
                        failure_stages.append("server_validation")
                        events.add(
                            "server_validation_failure",
                            {
                                "turn": turn,
                                "tool_name": tool_name,
                                "error_type": exc.__class__.__name__,
                                "error_sha256": hashlib.sha256(
                                    str(exc).encode("utf-8")
                                ).hexdigest(),
                            },
                        )
                        planning_errors.append(
                            "installed MCP call failed: "
                            f"{exc.__class__.__name__}"
                        )
                        break

                    is_error = bool(getattr(result, "isError", False))
                    events.add(
                        "tool_result",
                        {
                            "turn": turn,
                            "tool_name": tool_name,
                            "is_error": is_error,
                            "payload_sha256": sha256_json(
                                redact(payload, project)
                            ),
                            "summary": result_summary(payload, project),
                        },
                    )
                    if is_error:
                        failure_stages.append("server_validation")
                        planning_errors.append(
                            f"installed MCP returned an error for {tool_name}"
                        )
                        break

                    records.append(
                        {
                            "tool": tool_name,
                            "action": model_action_record(
                                tool_name,
                                materialized,
                                project,
                            ),
                            "payload": payload,
                            "project_path": str(project),
                        }
                    )
                    messages.extend(
                        [
                            {
                                "role": "assistant",
                                "content": json.dumps(
                                    action,
                                    ensure_ascii=False,
                                    sort_keys=True,
                                ),
                            },
                            feedback_message(
                                tool_name=tool_name,
                                payload=payload,
                                project=project,
                            ),
                        ]
                    )

                    partial = score_task(oracle_task, records)
                    if partial["passed"]:
                        break
                    context_count = sum(
                        record.get("tool") == "get_docs_context"
                        for record in records
                    )
                    if (
                        context_count >= max_context_calls
                        and tool_name not in {
                            "docs_status",
                            "prepare_docs",
                        }
                    ):
                        break

                score = score_task(oracle_task, records)
                score["errors"] = planning_errors + list(
                    score.get("errors") or ()
                )
                score["passed"] = bool(
                    score["passed"] and not planning_errors
                )
                score = redact(score, project)
                events.add(
                    "task_complete",
                    {
                        "passed": score["passed"],
                        "context_call_count": score.get(
                            "context_call_count",
                            0,
                        ),
                        "false_supported": score.get(
                            "false_supported",
                            0,
                        ),
                        "forbidden_source_contamination": score.get(
                            "forbidden_source_contamination",
                            0,
                        ),
                        "failure_stages": sorted(set(failure_stages)),
                    },
                )
                return {
                    "task_id": str(public_task["id"]),
                    "passed": score["passed"],
                    "score": score,
                    "trajectory": [
                        _report_record(record) for record in records
                    ],
                    "usage": usage_rows,
                    "events": events.rows(),
                    "failure_stages": sorted(set(failure_stages)),
                    "schema_repair_count": schema_repairs,
                    "mcp_schema_sha256": schema_sha,
                }


def _aggregate(
    *,
    artifact: ArtifactIdentity,
    planner: Planner,
    selected: list[dict[str, Any]],
    task_results: list[dict[str, Any]],
    infrastructure_errors: list[str],
    max_schema_repairs: int,
) -> dict[str, Any]:
    passed = sum(bool(row["passed"]) for row in task_results)
    false_supported = sum(
        int(row["score"].get("false_supported") or 0)
        for row in task_results
    )
    contamination = sum(
        int(
            row["score"].get(
                "forbidden_source_contamination"
            )
            or 0
        )
        for row in task_results
    )
    schema_digests = sorted(
        {
            str(row.get("mcp_schema_sha256") or "")
            for row in task_results
            if row.get("mcp_schema_sha256")
        }
    )
    claim_boundary = (
        "public-installed-agent-evidence"
        if artifact.origin == "public-pypi"
        and artifact.public_release_verified
        else "pre-public-installed-harness"
    )
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "protocol": PROTOCOL,
        "claim_boundary": claim_boundary,
        "artifact": artifact.to_report(),
        "mcp": {
            "transport": "stdio",
            "server": ["doc-atlas", "mcp", "docs-serve"],
            "tool_inventory": list(EXPECTED_TOOLS),
            "schema_sha256": (
                schema_digests[0]
                if len(schema_digests) == 1
                else None
            ),
            "schema_digest_count": len(schema_digests),
        },
        "provider": {
            "provider_id": planner.provider_id,
            "model": planner.model,
            "variant": planner.variant,
        },
        "limits": {
            "max_schema_repairs": max_schema_repairs,
            "public_task_count": len(selected),
        },
        "task_count": len(selected),
        "executed_task_count": len(task_results),
        "passed_tasks": passed,
        "pass_rate": passed / len(selected) if selected else 0.0,
        "false_supported": false_supported,
        "forbidden_source_contamination": contamination,
        "infrastructure_errors": infrastructure_errors,
        "tasks": task_results,
        "privacy": {
            "raw_prompts_persisted": False,
            "raw_tool_results_persisted": False,
            "absolute_project_paths_persisted": False,
            "event_hash_chain": True,
        },
    }


async def run_benchmark_async(
    *,
    planner: Planner,
    server_command: str,
    artifact: ArtifactIdentity,
    task_ids: set[str] | None = None,
    max_schema_repairs: int = 1,
) -> dict[str, Any]:
    if max_schema_repairs < 0 or max_schema_repairs > 2:
        raise ValueError("max_schema_repairs must be between 0 and 2")
    public_tasks = load_public_tasks()
    selected = [
        task
        for task in public_tasks
        if task_ids is None or str(task["id"]) in task_ids
    ]
    if task_ids is not None:
        missing = sorted(
            task_ids - {str(task["id"]) for task in selected}
        )
        if missing:
            raise ValueError(f"unknown task ids: {missing!r}")
    protocol = oracle_gate._load_protocol()
    oracle_by_id = {
        str(task["id"]): task for task in protocol["tasks"]
    }
    results: list[dict[str, Any]] = []
    infrastructure_errors: list[str] = []
    for task in selected:
        task_id = str(task["id"])
        try:
            results.append(
                await _run_task(
                    public_task=task,
                    oracle_task=oracle_by_id[task_id],
                    planner=planner,
                    server_command=server_command,
                    artifact=artifact,
                    max_schema_repairs=max_schema_repairs,
                )
            )
        except Exception as exc:
            infrastructure_errors.append(
                f"{task_id}: {exc.__class__.__name__}"
            )
            break
    return _aggregate(
        artifact=artifact,
        planner=planner,
        selected=selected,
        task_results=results,
        infrastructure_errors=infrastructure_errors,
        max_schema_repairs=max_schema_repairs,
    )


def run_benchmark(
    *,
    planner: Planner,
    server_command: str,
    artifact: ArtifactIdentity,
    task_ids: set[str] | None = None,
    max_schema_repairs: int = 1,
) -> dict[str, Any]:
    return asyncio.run(
        run_benchmark_async(
            planner=planner,
            server_command=server_command,
            artifact=artifact,
            task_ids=task_ids,
            max_schema_repairs=max_schema_repairs,
        )
    )
