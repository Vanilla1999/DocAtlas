"""Implementation shard 2 for impact."""
from __future__ import annotations

from ._impact_shared import *  # noqa: F401,F403

from ._impact_part01 import _bounded_text

def _bound_report(report: dict[str, Any]) -> dict[str, Any]:
    """Enforce the public serialized-output bound while retaining strongest evidence."""
    buckets = report.get("section_candidates") or {}
    report["bounds"]["serialized_bytes"] = 0
    omitted = report.setdefault("omitted", {})
    # Reserve space for final counters (`serialized_bytes`, omitted counts) so
    # adding the accounting itself cannot push the public payload over 32 KiB.
    target_bytes = _MAX_OUTPUT_BYTES - 512
    while len(json.dumps(report, ensure_ascii=False).encode("utf-8")) > target_bytes:
        removed = False
        impacts = report.get("impacts") or []
        if impacts:
            count = max(1, len(impacts) // 2)
            del impacts[-count:]
            omitted["impacts"] = omitted.get("impacts", 0) + count
            removed = True
            report["bounds"]["truncated"] = True
            report["bounds"]["output_truncated"] = True
        if removed:
            continue
        for bucket in ("unlikely", "review", "must_update"):
            values = buckets.get(bucket) or []
            if values:
                count = max(1, len(values) // 2)
                del values[-count:]
                omitted[f"section_candidates.{bucket}"] = omitted.get(f"section_candidates.{bucket}", 0) + count
                removed = True
                report["bounds"]["truncated"] = True
                report["bounds"]["output_truncated"] = True
                break
        if removed:
            continue
        changed = report.get("changed_files") or []
        if len(changed) > 20:
            count = max(1, (len(changed) - 20) // 2)
            del changed[-count:]
            omitted["changed_files"] = omitted.get("changed_files", 0) + count
            report["bounds"]["truncated"] = True
            report["bounds"]["output_truncated"] = True
            continue
        if _trim_auxiliary_report_list(report, omitted):
            report["bounds"]["truncated"] = True
            report["bounds"]["output_truncated"] = True
            continue
        report = _minimal_bounded_report(report, omitted)
        buckets = report["section_candidates"]
        break
    report["bounds"]["section_candidates_returned"] = sum(len(value or []) for value in buckets.values())
    for _ in range(2):
        report["bounds"]["serialized_bytes"] = len(json.dumps(report, ensure_ascii=False).encode("utf-8"))
    if report["bounds"]["serialized_bytes"] > _MAX_OUTPUT_BYTES:
        report = _minimal_bounded_report(report, omitted)
        report["bounds"]["section_candidates_returned"] = 0
        while _serialized_size(report) > _MAX_OUTPUT_BYTES:
            if report["changed_symbols"]:
                report["changed_symbols"].pop()
                omitted["changed_symbols"] = omitted.get("changed_symbols", 0) + 1
            elif report["changed_files"]:
                report["changed_files"].pop()
                omitted["changed_files"] = omitted.get("changed_files", 0) + 1
            else:
                # All remaining fields have fixed, bounded shapes. This branch
                # is a final guard against unusual JSON escaping behavior.
                report["project_path"] = ""
                report["summary"] = {}
                report["omitted"] = {"output_fields": 1}
                break
        for _ in range(2):
            report["bounds"]["serialized_bytes"] = _serialized_size(report)
    _refresh_continuation(report)
    if (report.get("bounds") or {}).get("output_truncated"):
        _invalidate_authoring_brief(report, "output_truncated")
    for _ in range(2):
        report["bounds"]["serialized_bytes"] = _serialized_size(report)
    return report


def _invalidate_authoring_brief(report: dict[str, Any], reason_code: str) -> None:
    brief = report.get("authoring_brief")
    if not isinstance(brief, dict):
        return
    evidence = brief.get("missing_evidence")
    if not isinstance(evidence, list):
        evidence = []
    if not any(
        (item.get("reason_code") if isinstance(item, dict) else item) == reason_code
        for item in evidence
    ):
        evidence.append({
            "reason_code": reason_code,
            "required_action": "rerun impact analysis with a narrower diff or the next candidate page",
        })
    brief.update({
        "status": "output_truncated" if brief.get("status") == "output_truncated" else "needs_evidence",
        "allowed_edits": [],
        "missing_evidence": evidence,
        "follow_up": {},
    })


def _trim_auxiliary_report_list(report: dict[str, Any], omitted: dict[str, int]) -> bool:
    locations: list[tuple[str, list[Any]]] = []
    metadata = report.get("section_metadata") or {}
    for key in (
        "reparsed_missing", "reparsed_stale", "indexed_current", "skipped_oversize", "truncated",
        "unsupported", "read_errors",
    ):
        locations.append((f"section_metadata.{key}", metadata.get(key) or []))
    for index, action in enumerate(report.get("next_actions") or []):
        locations.append((f"next_actions.{index}.paths", action.get("paths") or []))
    locations.extend([
        ("missing", report.get("missing") or []),
        ("warnings", report.get("warnings") or []),
        ("changed_symbols", report.get("changed_symbols") or []),
        ("diff_evidence.supported_paths", (report.get("diff_evidence") or {}).get("supported_paths") or []),
        ("diff_evidence.fallback_paths", (report.get("diff_evidence") or {}).get("fallback_paths") or []),
        ("authoring_brief.allowed_edits", (report.get("authoring_brief") or {}).get("allowed_edits") or []),
        ("authoring_brief.facts_to_verify", (report.get("authoring_brief") or {}).get("facts_to_verify") or []),
        ("authoring_brief.missing_evidence", (report.get("authoring_brief") or {}).get("missing_evidence") or []),
        ("sync.tombstones", (report.get("sync") or {}).get("tombstones") or []),
        ("sync.warnings", (report.get("sync") or {}).get("warnings") or []),
    ])
    for name, values in locations:
        if values:
            count = max(1, len(values) // 2)
            del values[-count:]
            omitted[name] = omitted.get(name, 0) + count
            return True
    return False


def _minimal_bounded_report(report: dict[str, Any], omitted: dict[str, int]) -> dict[str, Any]:
    """Last-resort shape for adversarially long individual fields."""
    raw_bounds = report.get("bounds") or {}
    bounds = {
        key: value
        for key, value in raw_bounds.items()
        if key in {
            "section_candidates_total", "section_candidates_returned", "candidate_offset", "candidate_limit",
            "candidate_evaluation_limit", "candidate_evaluation_truncated", "docs_candidates_total",
            "docs_candidates_analyzed", "docs_candidates_total_is_lower_bound", "docs_candidates_truncated",
            "truncated", "output_truncated", "max_section_candidates", "max_output_bytes", "serialized_bytes",
            "analysis_complete",
        }
        and isinstance(value, (int, float, bool))
    }
    if raw_bounds.get("continuation"):
        bounds["continuation"] = _bounded_text(raw_bounds["continuation"], 1024)
    if raw_bounds.get("continuation_reason"):
        bounds["continuation_reason"] = _bounded_text(raw_bounds["continuation_reason"], 128)
    if raw_bounds.get("incomplete_reasons"):
        bounds["incomplete_reasons"] = [
            _bounded_text(value, 128) for value in list(raw_bounds["incomplete_reasons"])[:16]
        ]
    bounds.update({"truncated": True, "output_truncated": True})
    compact = {
        "schema_version": report.get("schema_version"),
        "project_path": _bounded_text(report.get("project_path"), 256),
        "summary": {
            key: value
            for key, value in (report.get("summary") or {}).items()
            if key in {"changed_files", "code_files", "docs_updated", "docs_to_review", "missing_docs"}
            and isinstance(value, (int, float, bool))
        },
        "changed_files": [_bounded_text(value, 128) for value in list(report.get("changed_files") or [])[:20]],
        "changed_symbols": [_bounded_text(value, 128) for value in list(report.get("changed_symbols") or [])[:20]],
        "impacts": [],
        "section_candidates": {"must_update": [], "review": [], "unlikely": []},
        "bounds": bounds,
        "section_metadata": {
            "indexed_current": [], "reparsed_missing": [], "reparsed_stale": [],
            "skipped_oversize": [], "truncated": [],
        },
        "authoring_brief": {
            "schema_version": "documentation-update-brief-1",
            "status": "output_truncated",
            "allowed_edits": [],
            "facts_to_verify": [],
            "missing_evidence": [{
                "reason_code": "output_truncated",
                "required_action": "rerun impact analysis with a narrower diff or the next candidate page",
            }],
            "must_not_invent": ["Do not edit documentation until the impact report is rerun with a narrower diff."],
            "follow_up": {},
        },
        "next_actions": [],
        "diff_evidence": {"reason_code": "output_truncated"},
        "missing": [],
        "recommendation": "Output exceeded the safe bound; continue with the next candidate offset or narrow the diff.",
        "warnings": [],
        "omitted": omitted,
    }
    sync = report.get("sync") or {}
    if isinstance(sync, dict) and sync:
        compact["sync"] = {
            "status": _bounded_text(sync.get("status"), 64),
            "mode": _bounded_text(sync.get("mode"), 64),
            "message": _bounded_text(sync.get("message"), 512),
            "metrics": {
                key: value for key, value in (sync.get("metrics") or {}).items()
                if key in {"files_reprocessed", "sections_reprocessed", "derived_writes", "derived_deletes", "latency_ms"}
                and isinstance(value, (int, float, bool))
            },
            "tombstones": [],
            "warnings": [],
        }
    return compact


def _serialized_size(value: object) -> int:
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


def _refresh_continuation(report: dict[str, Any]) -> None:
    bounds = report.get("bounds") or {}
    offset = int(bounds.get("candidate_offset") or 0)
    returned = int(bounds.get("section_candidates_returned") or 0)
    total = int(bounds.get("section_candidates_total") or 0)
    evaluation_limit = int(bounds.get("candidate_evaluation_limit") or _MAX_SECTION_CANDIDATES_EVALUATED)
    evaluated_end = min(total, evaluation_limit)
    if offset + returned >= evaluated_end:
        bounds["continuation"] = None
        bounds["continuation_reason"] = (
            "evaluation_budget_exhausted_narrow_diff"
            if total > evaluated_end or bounds.get("candidate_evaluation_truncated")
            else "analysis_incomplete_narrow_diff"
            if not bounds.get("analysis_complete", True)
            else None
        )
        return
    next_offset = offset + returned
    limit = int(bounds.get("candidate_limit") or _MAX_SECTION_CANDIDATES)
    if returned == 0:
        limit = max(1, limit // 2)
    command = str(bounds.get("continuation") or "")
    if command:
        command = re.sub(r"--candidate-offset\s+\d+", f"--candidate-offset {next_offset}", command)
        command = re.sub(r"--candidate-limit\s+\d+", f"--candidate-limit {limit}", command)
    else:
        bounds["continuation"] = None
        bounds["continuation_reason"] = bounds.get("continuation_reason") or "output_truncated_rerun_narrower_page"
        return
    bounds["continuation"] = command
    bounds["continuation_reason"] = "next_candidate_page"


def _looks_like_doc_path(path: str) -> bool:
    normalized = str(path or "").replace("\\", "/").strip("/")
    if not normalized:
        return False
    file_path = Path(normalized)
    directory_parts = {part.lower() for part in file_path.parts[:-1]}
    if file_path.name in _DEPENDENCY_FILES and not directory_parts.intersection(DOC_DIRECTORIES):
        return False
    if file_path.suffix.lower() in DOC_FILE_EXTENSIONS:
        return True
    return file_path.name.lower() in ROOT_DOC_FILES


def _is_changed_doc_path(path: str, catalog_paths: set[str], catalog_authoritative: bool) -> bool:
    normalized = str(path or "").replace("\\", "/").strip("/")
    return normalized in catalog_paths if catalog_authoritative else _looks_like_doc_path(normalized)


def _matching_section_hints(
    sections: list[dict[str, object]], changed_paths: list[str], changed_symbols: list[str]
) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    for section in sections:
        paths = set(str(item) for item in section.get("mentioned_paths", []))
        symbols = set(str(item) for item in section.get("mentioned_symbols", []))
        path_evidence = [path for path in changed_paths if path in paths]
        symbol_evidence = [symbol for symbol in changed_symbols if symbol in symbols]
        if path_evidence:
            hints.append({
                "heading_path": list(section.get("heading_path", [])),
                "reason": "references_changed_path",
                "evidence": path_evidence,
            })
        if symbol_evidence:
            hints.append({
                "heading_path": list(section.get("heading_path", [])),
                "reason": "references_changed_symbol",
                "evidence": symbol_evidence,
            })
    return hints


def _recommendation(
    review_required: bool,
    missing: list[dict[str, Any]],
    incomplete_reasons: list[str] | None = None,
    *,
    docs_changed: bool = False,
) -> str:
    if incomplete_reasons:
        return "Analysis is incomplete; narrow the diff or documentation scope before concluding that no update is required."
    if missing:
        return "Create or link the missing module documentation, then review the affected docs before merge."
    if review_required:
        return "Review the listed docs for accuracy; no repository write is performed automatically."
    if docs_changed:
        return "Documentation changes were detected; verify deleted, renamed, or updated docs before merge."
    return "No maintained documentation changes are suggested by this diff."

__all__=['_bound_report', '_invalidate_authoring_brief', '_trim_auxiliary_report_list', '_minimal_bounded_report', '_serialized_size', '_refresh_continuation', '_looks_like_doc_path', '_is_changed_doc_path', '_matching_section_hints', '_recommendation']
