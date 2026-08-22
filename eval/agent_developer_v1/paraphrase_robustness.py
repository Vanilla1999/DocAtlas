from __future__ import annotations

import json
import os
import shutil
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool
import scripts.run_agent_developer_gate as oracle_gate


PROTOCOL = "agent-developer-paraphrase-robustness-v1"
REPORT_PROTOCOL = "agent-developer-paraphrase-robustness-report-v1"
SCHEMA_VERSION = 1
CATEGORIES = (
    "exact_identifier",
    "behavior",
    "requirements",
    "policy",
    "typo",
    "alias",
    "negative_control",
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _validate_corpus(corpus: dict[str, Any]) -> None:
    if corpus.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("paraphrase corpus schema mismatch")
    if corpus.get("protocol") != PROTOCOL:
        raise ValueError("paraphrase corpus protocol mismatch")
    cases = corpus.get("cases")
    thresholds = corpus.get("thresholds")
    if not isinstance(cases, list) or len(cases) != 15:
        raise ValueError("paraphrase corpus must contain exactly 15 cases")
    if not isinstance(thresholds, dict) or set(thresholds) != set(CATEGORIES):
        raise ValueError("paraphrase thresholds must cover every category")
    seen: set[str] = set()
    counts: dict[str, int] = defaultdict(int)
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("paraphrase case must be an object")
        case_id = str(case.get("id") or "")
        category = str(case.get("category") or "")
        if not case_id or case_id in seen:
            raise ValueError(f"invalid or duplicate paraphrase case: {case_id!r}")
        seen.add(case_id)
        if category not in CATEGORIES:
            raise ValueError(f"unknown paraphrase category: {category!r}")
        counts[category] += 1
        if not str(case.get("question") or ""):
            raise ValueError(f"paraphrase case {case_id} has no question")
        if case.get("scope") not in {"project", "module", "all"}:
            raise ValueError(f"paraphrase case {case_id} has invalid scope")
        if case.get("scope") == "module" and not str(case.get("module_path") or ""):
            raise ValueError(f"paraphrase case {case_id} needs module_path")
        if case.get("positive") is True:
            if not str(case.get("required_source") or ""):
                raise ValueError(f"positive case {case_id} needs required_source")
            if not str(case.get("required_fragment") or ""):
                raise ValueError(f"positive case {case_id} needs required_fragment")
        elif case.get("positive") is not False:
            raise ValueError(f"case {case_id} must declare positive=true/false")
    if counts != {
        "exact_identifier": 2,
        "behavior": 2,
        "requirements": 2,
        "policy": 2,
        "typo": 2,
        "alias": 2,
        "negative_control": 3,
    }:
        raise ValueError(f"paraphrase category cardinality drift: {dict(counts)!r}")


def _case_arguments(case: dict[str, Any], project: Path) -> dict[str, Any]:
    arguments: dict[str, Any] = {
        "question": str(case["question"]),
        "project_path": str(project),
        "mode": "project",
        "scope": str(case["scope"]),
        "delivery_strategy": "bounded_direct",
        "prepare_project_docs": False,
        "packet_tokens": 1000,
    }
    module_path = str(case.get("module_path") or "")
    if module_path:
        arguments["module_path"] = module_path
    return arguments


def _run_case(
    case: dict[str, Any],
    *,
    project: Path,
    service: Any,
) -> dict[str, Any]:
    payload = handle_context_tool(
        "get_docs_context",
        _case_arguments(case, project),
        service,
    )
    status = str((payload or {}).get("status") or "")
    sources = sorted(oracle_gate._source_paths(payload))
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    forbidden = sorted(
        source
        for source in sources
        if source in {str(value) for value in case.get("forbidden_sources") or ()}
    )
    if case["positive"]:
        required_source = str(case["required_source"])
        required_fragment = str(case["required_fragment"])
        passed = (
            status == "ok"
            and required_source in sources
            and required_fragment in text
            and not forbidden
        )
        false_supported = 0
    else:
        required_source = None
        required_fragment = None
        passed = status != "ok" and not forbidden
        false_supported = int(status == "ok")
    return {
        "id": str(case["id"]),
        "category": str(case["category"]),
        "question": str(case["question"]),
        "scope": str(case["scope"]),
        "module_path": str(case.get("module_path") or "") or None,
        "positive": bool(case["positive"]),
        "status": status,
        "sources": sources,
        "required_source": required_source,
        "required_fragment": required_fragment,
        "forbidden_source_contamination": forbidden,
        "false_supported": false_supported,
        "passed": passed,
    }


def run_protocol(corpus: dict[str, Any]) -> dict[str, Any]:
    _validate_corpus(corpus)
    previous_home = os.environ.get("DOCMANCER_HOME")
    try:
        with TemporaryDirectory(prefix="docatlas-p1-paraphrase-") as raw:
            root = Path(raw)
            project = root / "project"
            fixture = oracle_gate.PROJECTS_ROOT / str(corpus["fixture"])
            shutil.copytree(fixture, project)
            os.environ["DOCMANCER_HOME"] = str(root / "home")
            service = oracle_gate._service(root)
            sync = service.sync_project_docs(str(project), with_vectors=False)
            if getattr(sync, "status", None) != "success":
                raise RuntimeError(
                    f"paraphrase fixture sync failed: {getattr(sync, 'status', None)!r}"
                )
            rows = [
                _run_case(case, project=project, service=service)
                for case in corpus["cases"]
            ]
    finally:
        if previous_home is None:
            os.environ.pop("DOCMANCER_HOME", None)
        else:
            os.environ["DOCMANCER_HOME"] = previous_home

    category_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        category_rows[str(row["category"])].append(row)
    metrics: dict[str, dict[str, Any]] = {}
    for category in CATEGORIES:
        selected = category_rows[category]
        passed = sum(bool(row["passed"]) for row in selected)
        metrics[category] = {
            "case_count": len(selected),
            "passed": passed,
            "rate": passed / len(selected) if selected else 0.0,
            "threshold": float(corpus["thresholds"][category]),
            "threshold_met": (
                passed / len(selected) if selected else 0.0
            ) >= float(corpus["thresholds"][category]),
        }
    false_supported = sum(int(row["false_supported"]) for row in rows)
    contamination = sum(
        bool(row["forbidden_source_contamination"]) for row in rows
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "protocol": REPORT_PROTOCOL,
        "fixture": str(corpus["fixture"]),
        "case_count": len(rows),
        "categories": metrics,
        "false_supported": false_supported,
        "forbidden_source_contamination": contamination,
        "all_thresholds_met": all(
            bool(metric["threshold_met"]) for metric in metrics.values()
        ),
        "cases": rows,
        "claim_boundary": {
            "candidate_discovery_and_support_adjudication_separated": True,
            "support_precision_relaxed": False,
            "public_api_changed": False,
            "autonomous_agent_truth_closed": False,
            "product_maturity": "Beta",
        },
    }
    validate_report(report)
    return report


def validate_report(report: dict[str, Any]) -> None:
    if report.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("paraphrase report schema mismatch")
    if report.get("protocol") != REPORT_PROTOCOL:
        raise ValueError("paraphrase report protocol mismatch")
    if int(report.get("case_count") or 0) != 15:
        raise ValueError("paraphrase report case count mismatch")
    categories = report.get("categories")
    if not isinstance(categories, dict) or set(categories) != set(CATEGORIES):
        raise ValueError("paraphrase report categories differ")
    cases = report.get("cases")
    if not isinstance(cases, list) or len(cases) != 15:
        raise ValueError("paraphrase report cases are incomplete")
    ids = [str(row.get("id") or "") for row in cases if isinstance(row, dict)]
    if len(ids) != 15 or len(set(ids)) != 15:
        raise ValueError("paraphrase report identities are incomplete")
    if int(report.get("false_supported") or 0) != 0:
        raise ValueError("paraphrase report contains false support")
    if int(report.get("forbidden_source_contamination") or 0) != 0:
        raise ValueError("paraphrase report contains forbidden-source contamination")
    if report.get("all_thresholds_met") is not True:
        raise ValueError("paraphrase robustness thresholds are not closed")
    for category, metric in categories.items():
        if not isinstance(metric, dict) or metric.get("threshold_met") is not True:
            raise ValueError(f"paraphrase category not closed: {category}")
        rate = float(metric.get("rate") or 0.0)
        threshold = float(metric.get("threshold") or 0.0)
        if rate < threshold:
            raise ValueError(f"paraphrase category rate drift: {category}")
    boundary = report.get("claim_boundary") or {}
    if boundary.get("support_precision_relaxed") is not False:
        raise ValueError("P1.4 cannot relax support precision")
    if boundary.get("public_api_changed") is not False:
        raise ValueError("P1.4 cannot claim a public API change")
    if boundary.get("autonomous_agent_truth_closed") is not False:
        raise ValueError("P1.4 cannot close Autonomous Agent Truth")
    if boundary.get("product_maturity") != "Beta":
        raise ValueError("P1.4 cannot promote product maturity")


def render_markdown(report: dict[str, Any]) -> str:
    validate_report(report)
    lines = [
        "# P1.4 — Paraphrase and proofability robustness",
        "",
        "## Result",
        "",
        "The protocol executes 15 frozen queries against the same reviewed project "
        "fixture and evaluates candidate discovery separately from final support. "
        "A positive case needs status `ok`, its exact allowed source, its expected "
        "fact fragment, and zero forbidden-source contamination. Negative controls "
        "must remain non-`ok`.",
        "",
        "| Category | Passed | Rate | Threshold |",
        "|---|---:|---:|---:|",
    ]
    for category in CATEGORIES:
        metric = report["categories"][category]
        lines.append(
            f"| `{category}` | {metric['passed']}/{metric['case_count']} | "
            f"{metric['rate']:.3f} | {metric['threshold']:.3f} |"
        )
    lines.extend(
        [
            "",
            f"- false-supported: `{report['false_supported']}`",
            "- forbidden-source contamination: "
            f"`{report['forbidden_source_contamination']}`",
            "",
            "## Claim boundary",
            "",
            "- Support precision and fail-closed semantics were not relaxed.",
            "- No public MCP/API change was made.",
            "- This provider-free robustness gate does not close Autonomous Agent Truth.",
            "- Product maturity remains Beta.",
            "",
        ]
    )
    return "\n".join(lines)
