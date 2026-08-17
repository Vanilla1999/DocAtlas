"""Implementation shard 4 for impact."""
from __future__ import annotations

from ._impact_shared import *  # noqa: F401,F403

from ._impact_part01 import _symbols_from_patch
from ._impact_part02 import _bound_report
from ._impact_part03 import _markdown_cell, analyze_docs_impact

def format_docs_impact_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "## DocAtlas documentation impact",
        "",
        f"Changed files: **{summary['changed_files']}** · docs updated: **{summary['docs_updated']}** · docs to review: **{summary['docs_to_review']}** · missing docs: **{summary['missing_docs']}**.",
        "",
    ]
    updated = [
        item for item in (report.get("impacts") or [])
        if item.get("status") in {"updated", "deleted", "renamed", "changed_or_deleted"}
    ]
    if updated:
        lines.extend(["### Documentation changed in this diff", ""])
        lines.extend(
            f"- `{_markdown_cell(item['path'])}` ({_markdown_cell(item.get('status', 'updated'))})"
            for item in updated
        )
        lines.append("")
    labels = {
        "must_update": "Must update",
        "review": "Review",
        "unlikely": "Unlikely to require an update",
    }
    for bucket in ("must_update", "review", "unlikely"):
        candidates = (report.get("section_candidates") or {}).get(bucket) or []
        if not candidates:
            continue
        lines.extend([f"### {labels[bucket]}", "", "| Document section | Confidence | Reason | Evidence |", "|---|---|---|---|"])
        for item in candidates:
            path = _markdown_cell(item["path"])
            heading = _markdown_cell(" > ".join(item.get("heading_path") or []) or "(document)")
            evidence = _markdown_cell(", ".join(str(value) for value in item.get("evidence") or []))
            lines.append(
                f"| `{path}` — `{heading}` | {_markdown_cell(item.get('confidence', 'unknown'))} | "
                f"{_markdown_cell(item.get('reason_code', 'unknown'))} | {evidence} |"
            )
        lines.append("")
    missing = report.get("missing") or []
    if missing:
        lines.extend(["### Documentation gaps", ""])
        for item in missing:
            lines.append(
                f"- `{_markdown_cell(item['module_path'])}` changed without module docs; "
                f"consider `{_markdown_cell(item['suggested_path'])}`."
            )
        lines.append("")
    brief = report.get("authoring_brief") or {}
    if brief:
        lines.extend(["### Host-model documentation update brief", ""])
        lines.append(f"Status: `{_markdown_cell(brief.get('status', 'unknown'))}`.")
        lines.append("")
        allowed_edits = brief.get("allowed_edits") or []
        if allowed_edits:
            lines.append("Allowed edits:")
            lines.extend(
                f"- `{_markdown_cell(item.get('path'))}` — `{_markdown_cell(' > '.join(item.get('heading_path') or []) or '(document)')}`"
                for item in allowed_edits
            )
            lines.append("")
        for value in brief.get("must_not_invent") or []:
            lines.append(f"- Do not invent: {_markdown_cell(value)}")
        if brief.get("must_not_invent"):
            lines.append("")
        follow_up = brief.get("follow_up") or {}
        if follow_up:
            lines.append(
                f"After review, call `{follow_up.get('tool')}` with "
                f"`{_markdown_cell(json.dumps(follow_up.get('arguments_patch') or {}, ensure_ascii=False, sort_keys=True))}`."
            )
            lines.append("")
    bounds = report.get("bounds") or {}
    if bounds.get("truncated"):
        lines.extend([
            "### Truncation notice",
            "",
            (
                f"Returned **{bounds.get('section_candidates_returned', 0)}** of "
                f"**{bounds.get('section_candidates_total', 0)}** candidate sections. "
                f"Analyzed **{bounds.get('docs_candidates_analyzed', 0)}** of "
                f"**{bounds.get('docs_candidates_total', 0)}** discovered docs."
            ),
            "",
        ])
        if bounds.get("continuation"):
            lines.extend([f"Continue with: `{bounds['continuation']}`", ""])
        elif bounds.get("continuation_reason"):
            lines.extend([f"Continuation unavailable: `{bounds['continuation_reason']}`.", ""])
        if bounds.get("incomplete_reasons"):
            reasons = ", ".join(str(value) for value in bounds["incomplete_reasons"])
            lines.extend([f"Incomplete analysis reasons: `{_markdown_cell(reasons)}`.", ""])
        if report.get("omitted"):
            omitted = ", ".join(f"{key}={value}" for key, value in sorted(report["omitted"].items()))
            lines.extend([f"Omitted: {omitted}", ""])
    evidence = report.get("diff_evidence") or {}
    if evidence:
        lines.extend([
            f"Diff evidence: confidence=`{evidence.get('symbol_confidence', 'unknown')}`, "
            f"reason=`{evidence.get('reason_code', 'unknown')}`.",
            "",
        ])
    actions = report.get("next_actions") or []
    if actions:
        lines.extend(["### Next actions", ""])
        for action in actions:
            lines.append(f"- `{action.get('tool', 'unknown')}` — `{action.get('reason_code', 'unknown')}`")
        lines.append("")
    sync = report.get("sync") or {}
    if sync:
        metrics = sync.get("metrics") or {}
        lines.extend([
            "### Incremental sync",
            "",
            f"Status: `{_markdown_cell(sync.get('status', 'unknown'))}`. {_markdown_cell(sync.get('message') or '')}",
            "",
            "Metrics: "
            f"files={metrics.get('files_reprocessed', 0)}, "
            f"sections={metrics.get('sections_reprocessed', 0)}, "
            f"writes={metrics.get('derived_writes', 0)}, "
            f"deletes={metrics.get('derived_deletes', 0)}, "
            f"latency_ms={metrics.get('latency_ms', 0)}.",
            "",
        ])
    lines.append(f"**Recommendation:** {report['recommendation']}")
    return "\n".join(lines)


def bound_docs_impact_report(report: dict[str, Any]) -> dict[str, Any]:
    """Re-apply the public output contract after callers attach extra fields."""
    return _bound_report(report)


def evaluate_labeled_section_impact(project_path: str | Path, cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Measure must-update precision/recall for a deterministic labeled corpus."""
    true_positive = false_positive = false_negative = fallback_cases = 0
    automatic_symbol_cases = 0
    fallback_review_expected = fallback_review_matched = 0
    fallback_review_true_positive = fallback_review_false_positive = fallback_review_false_negative = 0
    for case in cases:
        patch = _labeled_case_patch(case)
        symbols, diagnostics = _symbols_from_patch(patch)
        if symbols:
            automatic_symbol_cases += 1
        if diagnostics.get("symbol_confidence") == "low":
            fallback_cases += 1
        report = analyze_docs_impact(
            project_path,
            [str(case["changed_file"])],
            diff_evidence={"symbols": symbols, "diagnostics": diagnostics},
        )
        predicted = {
            (item["path"], " > ".join(item.get("heading_path") or []))
            for item in report["section_candidates"]["must_update"]
        }
        expected = (
            {(str(case["expected_path"]), str(case["expected_heading"]))}
            if case.get("expected_impact") == "must_update"
            else set()
        )
        if case.get("expected_impact") == "review":
            fallback_review_expected += 1
            reviewed_paths = {item["path"] for item in report["section_candidates"]["review"]}
            expected_reviewed_paths = {str(case["expected_path"])}
            matched = reviewed_paths & expected_reviewed_paths
            if matched:
                fallback_review_matched += 1
            fallback_review_true_positive += len(matched)
            fallback_review_false_positive += len(reviewed_paths - expected_reviewed_paths)
            fallback_review_false_negative += len(expected_reviewed_paths - reviewed_paths)
        true_positive += len(predicted & expected)
        false_positive += len(predicted - expected)
        false_negative += len(expected - predicted)
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    fallback_precision = (
        fallback_review_true_positive / (fallback_review_true_positive + fallback_review_false_positive)
        if fallback_review_true_positive + fallback_review_false_positive else 0.0
    )
    fallback_recall = (
        fallback_review_true_positive / (fallback_review_true_positive + fallback_review_false_negative)
        if fallback_review_true_positive + fallback_review_false_negative else 0.0
    )
    return {
        "schema_version": "docs-impact-quality-1",
        "cases": len(cases),
        "must_update_precision": round(precision, 4),
        "must_update_recall": round(recall, 4),
        "minimum_precision": 0.75,
        "minimum_recall": 0.90,
        "passed": (
            precision >= 0.75
            and recall >= 0.90
            and (not fallback_review_expected or fallback_precision >= 0.75)
            and (not fallback_review_expected or fallback_recall >= 0.90)
        ),
        "conservative_fallback_cases": fallback_cases,
        "automatic_symbol_cases": automatic_symbol_cases,
        "fallback_review_expected": fallback_review_expected,
        "fallback_review_matched": fallback_review_matched,
        "fallback_review_precision": round(fallback_precision, 4),
        "fallback_review_recall": round(fallback_recall, 4),
        "counts": {"true_positive": true_positive, "false_positive": false_positive, "false_negative": false_negative},
    }


def _labeled_case_patch(case: dict[str, Any]) -> str:
    path = str(case["changed_file"])
    language = str(case.get("language") or "")
    old = str(case["old_symbol"])
    new = str(case["new_symbol"])
    if language == "python":
        old_line, new_line = f"def {old}():", f"def {new}():"
    elif language == "typescript":
        old_line, new_line = f"export class {old} {{}}", f"export class {new} {{}}"
    elif language == "dart":
        old_line, new_line = f"class {old} {{}}", f"class {new} {{}}"
    else:
        old_line, new_line = f"func {old}() {{}}", f"func {new}() {{}}"
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        f"@@ -1 +1 @@\n"
        f"-{old_line}\n"
        f"+{new_line}\n"
    )

__all__=['format_docs_impact_markdown', 'bound_docs_impact_report', 'evaluate_labeled_section_impact', '_labeled_case_patch']
