#!/usr/bin/env python3
"""Measure current P1.5 facts and source provenance without resealing history."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

from eval.agent_developer_v1.mixed_provenance import derive_from_paths, verify_report

REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT = REPO_ROOT / "eval" / "agent_developer_v1"
DEFAULT_OUTPUT = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())) / "p1.5-current-provenance.json"


# Only render already captured evidence. Retrieved bodies stay in the saved
# report; these log diagnostics expose hashes, lengths and binding coordinates.
_BODY_FIELDS = frozenset({"content", "text", "display_text", "raw_document", "snippet",
                          "answer", "section", "title", "preview", "excerpt"})
_CHILD_FIELDS = ("parent_logical_id", "source_identity", "source_content_hash", "display_text",
                 "display_content_hash", "char_start", "char_end", "byte_start", "byte_end",
                 "line_start", "line_end")


def _body_free(value, *, field=""):
    if field in _BODY_FIELDS and isinstance(value, str):
        raw = value.encode("utf-8")
        return {"characters": len(value), "utf8_bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest()}
    if isinstance(value, dict):
        return {key: _body_free(item, field=key) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_body_free(item, field=field) for item in value]
    return value


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _rows(value):
    return value if isinstance(value, (list, tuple)) else ()


def _source_binding_diagnostics(observation: dict) -> list[dict]:
    """Compare saved snapshot lineage with saved committed same-path children.

    Lane and identity matches are reported separately from field mismatches.
    This does not choose a replacement source or alter the provenance oracle.
    """
    prepared = _mapping(observation.get("preparation"))
    stored = [("project", row) for row in _rows(prepared.get("project_stored_children"))]
    for record in _rows(_mapping(prepared.get("external")).get("records")):
        if isinstance(record, dict):
            stored.extend((record.get("library_id"), row) for row in _rows(record.get("stored_children")))
    bindings = _mapping(observation.get("bindings"))
    result = []
    for source in _rows(_mapping(observation.get("public_payload")).get("sources")):
        if not isinstance(source, dict):
            continue
        evidence_id = source.get("evidence_id")
        binding = _mapping(bindings.get(evidence_id)) if isinstance(evidence_id, str) else {}
        lineage = _mapping(binding.get("lineage"))
        same_path = []
        for lane, child in stored:
            if not isinstance(child, dict) or child.get("path") != source.get("path_or_url"):
                continue
            identity_matches = all(isinstance(lineage.get(key), str) and bool(lineage[key])
                                   and child.get(key) == lineage[key]
                                   for key in ("stable_chunk_id", "generation_id"))
            same_path.append({
                "storage_lane": lane, "identity_matches": identity_matches,
                "stored_child": _body_free(child),
                "field_mismatches": [{
                    "field": key, "lineage_present": key in lineage,
                    "snapshot_value": _body_free(lineage.get(key), field=key),
                    "stored_value": _body_free(child.get(key), field=key),
                } for key in _CHILD_FIELDS if lineage.get(key) != child.get(key)],
            })
        result.append({
            "evidence_id": evidence_id, "source_fields": _body_free(source),
            "binding_fields_present": sorted(binding), "lineage_fields_present": sorted(lineage),
            "snapshot_lineage": _body_free(lineage),
            "snapshot_metadata_lineage": _body_free(binding.get("metadata_lineage")),
            "comparison_basis": "raw_top_level_lineage_only",
            "projected_source": _body_free(binding.get("projected_source")),
            "same_call_source_equal": binding.get("projected_source") == source,
            "candidate_hash_material": _body_free(binding.get("candidate_hash_material")),
            "same_path_children": same_path,
        })
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure P1.5 original-question facts and explicit source provenance")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    historical = (ROOT / "results" / "mixed-evidence-provenance.json").resolve()
    if args.output.resolve() == historical:
        parser.error("current fixture evidence must not overwrite the historical P1.5 report")
    report = derive_from_paths(repo_root=REPO_ROOT, protocol_path=ROOT / "mixed_provenance_protocol.json")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verify_report(report)
    summary = report["summary"]
    print(f"P1.5 current provenance: {'PASS' if report['passed'] else 'FAIL'}; "
          f"cases={summary['passed_count']}/{summary['case_count']}; "
          f"complete_facts={summary['verified_full_fact_count']}/{summary['required_full_fact_count']}; "
          f"errors={summary['runtime_error_count']}; report={args.output}")
    for row in report["cases"]:
        assessment, observation = row["assessment"], row["observation"]
        if not assessment["passed"]:
            print(f"FAIL {row['id']}: {','.join(assessment['failed_checks'])}")
            before, after = observation.get("state_before") or {}, observation.get("state_after") or {}
            details = {
                "id": row["id"], "source_errors": assessment["source_errors"],
                "preparation_errors": assessment["preparation_errors"],
                "authority_errors": assessment["authority_errors"],
                "missing_full_fact_sources": sorted(set(assessment["required_full_fact_sources"])
                                                    - set(assessment["visible_full_fact_sources"])),
                "state_differences": [{"field": key, "before": before.get(key), "after": after.get(key)}
                                      for key in sorted(set(before) | set(after)) if before.get(key) != after.get(key)],
                "generation_before": before.get("generation"), "runtime_error": observation.get("error"),
                "output_cost": assessment["output_cost"],
                "request": observation.get("request"),
                "service_requests": observation.get("service_requests"),
                "service_returns": _body_free(observation.get("service_returns") or {}),
                "public_result": {key: value for key, value in _mapping(observation.get("public_payload")).items()
                                  if key in {"kind", "status", "reason_code", "operational_reason_code",
                                             "context_available", "answer_available", "answer_supported",
                                             "source_search_status", "disposition"}},
                "observer_counts": observation.get("observer_counts"),
                "project_identity": observation.get("project_identity"),
                "source_bindings": _source_binding_diagnostics(observation),
                "prepared_libraries": _body_free(_rows(_mapping(
                    _mapping(observation.get("preparation")).get("external")).get("records"))),
                "pipeline_diagnostics": _body_free(observation.get("pipeline_diagnostics") or {}),
            }
            print("DIAGNOSTICS " + json.dumps(details, ensure_ascii=False, sort_keys=True))
    if report["source_identities"]["runtime_error"]:
        print(f"FAIL runtime identity: {report['source_identities']['runtime_error']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
