from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ATLAS_PROTOCOL = "agent-developer-first-divergence-v1"
ATLAS_SCHEMA_VERSION = 1
EXPECTED_FAILURE_COUNTS = {
    "selector_cardinality_invalid": 8,
    "question_specificity_mismatch": 2,
    "required_scope_sequence_mismatch": 1,
}


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _strings(values: Iterable[Any] | None) -> list[str]:
    return [str(value) for value in (values or ())]


def _signature(value: dict[str, Any]) -> dict[str, str]:
    mode = str(value.get("mode") or "")
    if mode == "dependency":
        return {"scope": "dependency"}
    result = {"scope": str(value.get("scope") or "")}
    for key in ("module", "module_path"):
        selected = str(value.get(key) or "")
        if selected:
            result[key] = selected
    return result


def _expected_steps(oracle: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for call in oracle.get("calls") or ():
        if not isinstance(call, dict):
            continue
        row: dict[str, Any] = {
            "tool": "get_docs_context",
            "signature": _signature(call),
            "question": str(call.get("question") or ""),
            "expected_status": str(
                call.get("target_expected_status")
                or call.get("baseline_expected_status")
                or ""
            ),
            "required_sources": sorted(
                _strings(
                    call.get("target_required_sources")
                    or call.get("required_sources")
                )
            ),
        }
        next_tool = str(call.get("target_next_action_tool") or "")
        if next_tool:
            row["expected_next_action_tool"] = next_tool
        if call.get("target_operational_reason_code"):
            row["expected_operational_reason_code"] = str(
                call["target_operational_reason_code"]
            )
        steps.append(row)

        recovery = call.get("target_recovery")
        if isinstance(recovery, dict):
            steps.append(
                {
                    "tool": "docs_status",
                    "action": "project",
                    "details": True,
                }
            )
            retry = recovery.get("retry")
            if isinstance(retry, dict):
                steps.append(
                    {
                        "tool": "get_docs_context",
                        "signature": _signature(retry),
                        "question": str(retry.get("question") or ""),
                        "expected_status": str(
                            retry.get("target_expected_status") or ""
                        ),
                        "required_sources": sorted(
                            _strings(retry.get("target_required_sources"))
                        ),
                    }
                )
    return steps


def _actual_steps(result: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for raw in result.get("trajectory") or ():
        if not isinstance(raw, dict):
            continue
        action = raw.get("action") if isinstance(raw.get("action"), dict) else {}
        row: dict[str, Any] = {
            "tool": str(raw.get("tool") or action.get("action") or ""),
            "status": raw.get("status"),
            "sources": sorted(_strings(raw.get("sources"))),
            "next_action_tool": raw.get("next_action_tool"),
            "operational_reason_code": raw.get("operational_reason_code"),
        }
        if row["tool"] == "get_docs_context":
            row["signature"] = _signature(action)
            row["question"] = str(action.get("question") or "")
        steps.append(row)
    return steps


def _request_evidence(result: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in result.get("usage") or () if isinstance(row, dict)]
    request_ids: list[str] = []
    for row in rows:
        direct = str(row.get("request_id") or "")
        if direct:
            request_ids.append(direct)
        nested = row.get("request_ids")
        if isinstance(nested, dict):
            request_ids.extend(
                str(value) for value in nested.values() if str(value)
            )
    return {
        "turn_count": len(rows),
        "request_ids": sorted(set(request_ids)),
        "input_tokens": sum(int(row.get("input_tokens") or 0) for row in rows),
        "output_tokens": sum(int(row.get("output_tokens") or 0) for row in rows),
        "reasoning_tokens": sum(
            int(row.get("reasoning_tokens") or 0) for row in rows
        ),
    }


def _secondary_failures(errors: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for error in errors:
        lowered = error.lower()
        if "missing required scope" in lowered:
            category = "planning"
        elif "next action" in lowered or "confirmation" in lowered:
            category = "recovery"
        elif "status=" in lowered or "required sources missing" in lowered:
            category = "retrieval"
        else:
            category = "validation"
        rows.append({"stage": category, "detail": error})
    return rows


def _selector_failure(
    task: dict[str, Any],
    oracle: dict[str, Any],
    result: dict[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    working_path = str(task.get("working_path") or "")
    return {
        "stage": "model_format",
        "failure_class": "selector_cardinality_invalid",
        "expected_step_index": 0,
        "actual_step_index": None,
        "model_visible_reason": (
            "The model-visible contract required exactly one of `module` or "
            "`module_path`, and the task already exposed working_path="
            f"{working_path!r}. The retained report records a selector "
            "cardinality error, but the rejected action body was not persisted, "
            "so it cannot prove whether both selectors or neither selector was sent."
        ),
        "server_side_reason": (
            "The planner action failed host-side validation before any MCP call; "
            "the installed/server retrieval path was never reached."
        ),
        "minimal_successful_repair": (
            "Derive the exact module root from the supplied working path, send "
            "only `module_path`, leave `module` empty, and retry the same first "
            "evidence question without widening scope."
        ),
        "repair_surface": "agent_or_host_argument_normalization",
        "public_api_change_required": False,
        "evidence": {
            "working_path": working_path,
            "required_scopes": oracle.get("required_scopes") or [],
            "report_errors": errors,
        },
    }


def _scope_sequence_failure(
    expected: list[dict[str, Any]],
    actual: list[dict[str, Any]],
    errors: list[str],
) -> dict[str, Any]:
    return {
        "stage": "planning",
        "failure_class": "required_scope_sequence_mismatch",
        "expected_step_index": 0,
        "actual_step_index": 0 if actual else None,
        "model_visible_reason": (
            "The task required both module-owned evidence and pinned dependency "
            "evidence within the published call budget, but the model began with "
            "dependency retrieval and omitted the required module step."
        ),
        "server_side_reason": (
            "The dependency call reached DocAtlas, but the evaluator rejected the "
            "trajectory before considering later recovery because the first required "
            "scope was absent. The returned recovery also differed from the frozen "
            "dependency-prefetch contract."
        ),
        "minimal_successful_repair": (
            "Use the first call for the exact module path, then make the dependency "
            "call. If dependency evidence is absent, follow the returned "
            "`prepare_docs(prefetch_project_dependency_docs)` confirmation boundary."
        ),
        "repair_surface": "agent_planning_sequence",
        "public_api_change_required": False,
        "evidence": {
            "expected_first_step": expected[0] if expected else None,
            "actual_first_step": actual[0] if actual else None,
            "report_errors": errors,
        },
    }


def _question_specificity_failure(
    expected: list[dict[str, Any]],
    actual: list[dict[str, Any]],
    errors: list[str],
) -> dict[str, Any]:
    expected_first = expected[0] if expected else {}
    actual_first = actual[0] if actual else {}
    return {
        "stage": "retrieval",
        "failure_class": "question_specificity_mismatch",
        "expected_step_index": 0,
        "actual_step_index": 0,
        "model_visible_reason": (
            "The model selected the correct scope but replaced the frozen exact "
            "technical-identity question with a broader prose request. The result "
            "contained no sources and remained insufficient."
        ),
        "server_side_reason": (
            "DocAtlas executed the schema-valid request. Candidate discovery/support "
            "did not establish the required exact source for the broader wording, so "
            "the server correctly failed closed instead of fabricating support."
        ),
        "minimal_successful_repair": (
            "Keep the same scope and ask the frozen exact-identifier question shown "
            "by the evaluator. No new tool or relaxed support rule is required."
        ),
        "repair_surface": "agent_question_formulation",
        "public_api_change_required": False,
        "evidence": {
            "expected_question": expected_first.get("question"),
            "actual_question": actual_first.get("question"),
            "actual_status": actual_first.get("status"),
            "actual_sources": actual_first.get("sources"),
            "report_errors": errors,
        },
    }


def classify_task(
    task: dict[str, Any],
    oracle: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    errors = _strings((result.get("score") or {}).get("errors"))
    expected = _expected_steps(oracle)
    actual = _actual_steps(result)

    if any(
        "module retrieval requires exactly one of module or module_path" in error
        for error in errors
    ):
        first = _selector_failure(task, oracle, result, errors)
    else:
        expected_context = next(
            (step for step in expected if step.get("tool") == "get_docs_context"),
            None,
        )
        actual_context = next(
            (step for step in actual if step.get("tool") == "get_docs_context"),
            None,
        )
        if (
            expected_context
            and actual_context
            and expected_context.get("signature") != actual_context.get("signature")
        ):
            first = _scope_sequence_failure(expected, actual, errors)
        elif (
            expected_context
            and actual_context
            and actual_context.get("status") == "insufficient_evidence"
            and expected_context.get("expected_status") == "ok"
            and not actual_context.get("sources")
        ):
            first = _question_specificity_failure(expected, actual, errors)
        else:
            first = {
                "stage": "evaluator",
                "failure_class": "unclassified_contract_mismatch",
                "expected_step_index": 0 if expected else None,
                "actual_step_index": 0 if actual else None,
                "model_visible_reason": (
                    "The retained report does not contain enough structured detail "
                    "for a narrower first-divergence classification."
                ),
                "server_side_reason": (
                    "The evaluator contract failed, but no supported rule identifies "
                    "a single earlier model, schema, retrieval, support, or recovery cause."
                ),
                "minimal_successful_repair": (
                    "Re-run this frozen task with the installed-MCP ledger and retain "
                    "the rejected action/result needed for causal classification."
                ),
                "repair_surface": "measurement",
                "public_api_change_required": False,
                "evidence": {"report_errors": errors},
            }

    return {
        "task_id": str(task.get("id") or ""),
        "task_class": str(task.get("class") or ""),
        "developer_task": str(task.get("developer_task") or ""),
        "working_path": str(task.get("working_path") or ""),
        "expected_trajectory": expected,
        "actual_trajectory": actual,
        "first_divergence": first,
        "secondary_failures": _secondary_failures(errors),
        "request_evidence": _request_evidence(result),
        "passed": bool(result.get("passed")),
    }


def build_atlas(
    public_tasks: dict[str, Any],
    oracle: dict[str, Any],
    report: dict[str, Any],
) -> dict[str, Any]:
    tasks = public_tasks.get("tasks")
    trajectories = oracle.get("trajectories")
    results = report.get("tasks")
    if not isinstance(tasks, list) or not isinstance(trajectories, list):
        raise ValueError("task/oracle corpus is malformed")
    if not isinstance(results, list):
        raise ValueError("model report is malformed")

    task_by_id = {str(row.get("id") or ""): row for row in tasks if isinstance(row, dict)}
    oracle_by_id = {
        str(row.get("id") or ""): row for row in trajectories if isinstance(row, dict)
    }
    result_by_id = {
        str(row.get("task_id") or ""): row for row in results if isinstance(row, dict)
    }
    ids = [str(row.get("id") or "") for row in tasks if isinstance(row, dict)]
    if len(ids) != 11 or len(set(ids)) != 11:
        raise ValueError(f"expected exactly 11 unique frozen tasks, found {len(ids)}")
    if set(ids) != set(oracle_by_id) or set(ids) != set(result_by_id):
        raise ValueError("task, oracle, and model-report identities differ")

    rows = [
        classify_task(task_by_id[task_id], oracle_by_id[task_id], result_by_id[task_id])
        for task_id in ids
    ]
    counts = Counter(
        str(row["first_divergence"]["failure_class"]) for row in rows
    )
    summary = {
        "task_count": len(rows),
        "passed_tasks": sum(bool(row["passed"]) for row in rows),
        "failure_class_counts": dict(sorted(counts.items())),
        "stage_counts": dict(
            sorted(
                Counter(
                    str(row["first_divergence"]["stage"]) for row in rows
                ).items()
            )
        ),
        "false_supported": int(report.get("false_supported") or 0),
        "forbidden_source_contamination": int(
            report.get("forbidden_source_contamination") or 0
        ),
    }
    atlas = {
        "schema_version": ATLAS_SCHEMA_VERSION,
        "protocol": ATLAS_PROTOCOL,
        "source": {
            "report_protocol": str(report.get("protocol") or ""),
            "provider_id": str(report.get("provider_id") or ""),
            "model": str(report.get("model") or ""),
            "report_sha256": sha256_json(report),
            "public_tasks_sha256": sha256_json(public_tasks),
            "oracle_sha256": sha256_json(oracle),
            "fresh_installed_provider_run_available": False,
            "fresh_run_blocker": "repository OPENAI_API_KEY is not configured",
        },
        "summary": summary,
        "findings": {
            "working_path_was_model_visible": True,
            "missing_working_path_is_established_root_cause": False,
            "public_api_change_is_justified_by_p1_2": False,
            "repeated_primary_class": "selector_cardinality_invalid",
            "repeated_primary_class_task_count": counts.get(
                "selector_cardinality_invalid", 0
            ),
        },
        "tasks": rows,
        "claim_boundary": {
            "historical_live_report_analyzed": True,
            "fresh_installed_live_report_analyzed": False,
            "autonomous_agent_truth_closed": False,
            "p1_3_candidates_remain_hypotheses": True,
        },
    }
    validate_atlas(atlas)
    return atlas


def validate_atlas(atlas: dict[str, Any]) -> None:
    if atlas.get("schema_version") != ATLAS_SCHEMA_VERSION:
        raise ValueError("first-divergence schema version mismatch")
    if atlas.get("protocol") != ATLAS_PROTOCOL:
        raise ValueError("first-divergence protocol mismatch")
    tasks = atlas.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 11:
        raise ValueError("first-divergence atlas must contain 11 tasks")
    ids = [str(row.get("task_id") or "") for row in tasks if isinstance(row, dict)]
    if len(ids) != 11 or len(set(ids)) != 11:
        raise ValueError("first-divergence task identities are incomplete")
    required = {
        "expected_trajectory",
        "actual_trajectory",
        "first_divergence",
        "secondary_failures",
        "request_evidence",
    }
    for row in tasks:
        if not isinstance(row, dict) or not required.issubset(row):
            raise ValueError("first-divergence task record is incomplete")
        divergence = row.get("first_divergence")
        if not isinstance(divergence, dict):
            raise ValueError("first-divergence record is malformed")
        for key in (
            "stage",
            "failure_class",
            "model_visible_reason",
            "server_side_reason",
            "minimal_successful_repair",
            "repair_surface",
            "public_api_change_required",
        ):
            if key not in divergence:
                raise ValueError(f"first-divergence record omitted {key}")
        if divergence.get("public_api_change_required") is not False:
            raise ValueError("P1.2 must not pre-authorize a public API change")

    counts = Counter(
        str(row["first_divergence"]["failure_class"]) for row in tasks
    )
    if dict(counts) != EXPECTED_FAILURE_COUNTS:
        raise ValueError(
            f"unexpected first-divergence distribution: {dict(counts)!r}"
        )
    summary = atlas.get("summary") or {}
    if summary.get("failure_class_counts") != dict(sorted(counts.items())):
        raise ValueError("first-divergence summary/count mismatch")
    if int(summary.get("false_supported") or 0) != 0:
        raise ValueError("historical atlas contains false support")
    if int(summary.get("forbidden_source_contamination") or 0) != 0:
        raise ValueError("historical atlas contains forbidden-source contamination")
    findings = atlas.get("findings") or {}
    if findings.get("public_api_change_is_justified_by_p1_2") is not False:
        raise ValueError("P1.2 cannot claim a public API decision")
    boundary = atlas.get("claim_boundary") or {}
    if boundary.get("autonomous_agent_truth_closed") is not False:
        raise ValueError("P1.2 cannot close Autonomous Agent Truth")


def render_markdown(atlas: dict[str, Any]) -> str:
    validate_atlas(atlas)
    summary = atlas["summary"]
    findings = atlas["findings"]
    source = atlas["source"]
    lines = [
        "# P1.2 — Agent Developer 0/11 first-divergence atlas",
        "",
        "## Evidence boundary",
        "",
        "This analysis is generated from the committed historical real-model "
        "Agent Developer report, the frozen public tasks, and the evaluator-only "
        "target trajectories. It does not reconstruct rejected model actions that "
        "the historical runner did not persist.",
        "",
        f"- provider: `{source['provider_id']}`",
        f"- model: `{source['model']}`",
        f"- tasks: `{summary['task_count']}`",
        f"- passed: `{summary['passed_tasks']}`",
        f"- false-supported: `{summary['false_supported']}`",
        "- forbidden-source contamination: "
        f"`{summary['forbidden_source_contamination']}`",
        "- fresh installed provider run: unavailable because the repository "
        "does not currently expose `OPENAI_API_KEY`",
        "",
        "## Repeated first divergences",
        "",
        "| Failure class | Tasks | Interpretation |",
        "|---|---:|---|",
    ]
    explanations = {
        "selector_cardinality_invalid": (
            "Host-side planner validation failed before MCP because the model "
            "did not satisfy the exactly-one module selector contract."
        ),
        "question_specificity_mismatch": (
            "The scope was correct, but broader wording did not retrieve/prove "
            "the exact frozen identity and DocAtlas failed closed."
        ),
        "required_scope_sequence_mismatch": (
            "The model began with dependency evidence and omitted the required "
            "module step before recovery."
        ),
    }
    for key, count in summary["failure_class_counts"].items():
        lines.append(f"| `{key}` | {count} | {explanations[key]} |")

    lines.extend(
        [
            "",
            "## Task atlas",
            "",
            "| Task | First stage | Failure class | Minimal repair |",
            "|---|---|---|---|",
        ]
    )
    for row in atlas["tasks"]:
        divergence = row["first_divergence"]
        repair = str(divergence["minimal_successful_repair"]).replace("|", "\\|")
        lines.append(
            f"| `{row['task_id']}` | `{divergence['stage']}` | "
            f"`{divergence['failure_class']}` | {repair} |"
        )

    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"The repeated class affects **{findings['repeated_primary_class_task_count']}/11** "
            "tasks and occurs before MCP/server retrieval. The historical tasks already "
            "included `working_path`, so the evidence does **not** establish missing "
            "working-path visibility as the root cause. It establishes selector "
            "cardinality/normalization as the dominant first divergence.",
            "",
            "P1.2 therefore authorizes only P1.3 benchmark ablations. It does not "
            "authorize a new public field, server-owned inference, a continuation "
            "token, broader retrieval, or relaxed support semantics.",
            "",
            "## Claim boundary",
            "",
            "- P1.2 analysis: complete for the committed historical 0/11 report.",
            "- Fresh installed provider capture: still pending an available provider credential.",
            "- Autonomous Agent Truth: not closed by this atlas.",
            "- Product maturity: remains Beta.",
            "",
        ]
    )
    return "\n".join(lines)
