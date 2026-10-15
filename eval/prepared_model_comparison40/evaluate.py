"""Offline scoring of frozen public packets; imports no DocAtlas/model code.

The oracle is the unchanged historical source-bound gold, not model scores or
retrieval coverage metadata. Read only saved artifacts and pinned source bytes.
Run only after the paired workload is complete; never repair gold from outputs.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import statistics
from typing import Any


MODES = ("budget", "mini")
HASH = re.compile(r"[0-9a-f]{64}\Z")
MEASUREMENT = {
    "gold": "Original gold line ranges; outer whitespace alone is trimmed.",
    "coverage": (
        "All characters of one complete alternative witness set must be covered "
        "by the union of verified public snippet spans from the matching source. "
        "Interior whitespace, headings, examples and wording remain unchanged."
    ),
    "ambiguous_placement": (
        "A snippet with multiple occurrences inside its declared line range is "
        "valid source text, but contributes only the intersection of its possible "
        "placements to coordinate coverage. No first-match occurrence is guessed."
    ),
    "negative": "All eight unanswerable cases require empty public sources.",
    "partial": "Only delivery of the documented part is scored for eight partial cases.",
    "wire": "UTF-8 bytes of json.dumps(public_payload, ensure_ascii=False), default separators.",
    "raw_hash": "Pinned file SHA-256 compared with prepare inventory and saved generation_sources hashes.",
    "projection_hash": "Public content_sha256 is a projection fingerprint, never the raw file hash.",
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(path: Path, errors: list[str], label: str) -> Any:
    try:
        return json.loads(path.read_bytes())
    except (OSError, ValueError, UnicodeError) as exc:
        errors.append(f"{label}: {type(exc).__name__}: {exc}")
        return None


def _artifact(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        return {"path": str(path), "bytes": len(raw), "sha256": _sha(raw)}
    except OSError as exc:
        return {"path": str(path), "error": f"{type(exc).__name__}: {exc}"}


def _frozen_inputs(run_dir: Path, corpus_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    errors: list[str] = []
    manifest = _json(run_dir / "RUN_MANIFEST.json", errors, "run_manifest")
    if not isinstance(manifest, dict):
        return {}, {"pass": False, "checked_files": 0, "errors": errors + ["run_manifest_not_object"]}
    expected = manifest.get("inputs_sha256")
    if not isinstance(expected, dict) or not expected:
        return manifest, {"pass": False, "checked_files": 0, "errors": errors + ["frozen_input_hashes_missing"]}
    repository = corpus_dir.parent.parent
    checked = 0
    for relative, digest in expected.items():
        path = PurePosixPath(relative)
        if path.is_absolute() or ".." in path.parts or not isinstance(digest, str) or not HASH.fullmatch(digest):
            errors.append(f"invalid_frozen_input_entry:{relative}")
            continue
        artifact = _artifact(repository / path)
        checked += 1
        if artifact.get("sha256") != digest:
            errors.append(f"frozen_input_hash_mismatch_or_missing:{relative}")
    for name in ("questions.json", "gold_spans.json", "source_plan.json", "source-manifest.json", "evaluate.py", "run.py"):
        relative = (corpus_dir / name).relative_to(repository).as_posix()
        if relative not in expected:
            errors.append(f"required_evaluation_input_not_frozen:{relative}")
    cap = manifest.get("final_json_cap")
    if type(cap) is not int or cap <= 0:
        errors.append("invalid_frozen_final_json_cap")
    if manifest.get("question_count") != 40 or manifest.get("arms") != list(MODES):
        errors.append("frozen_run_design_mismatch")
    return manifest, {"pass": not errors, "checked_files": checked, "errors": errors}


def _raw_hash(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.removeprefix("sha256:")
    return value if HASH.fullmatch(value) else None


def _relative(value: Any, project_root: str) -> str | None:
    """Lexical canonical containment; never open files in a recorded fixture root."""
    if not isinstance(value, str) or not value or "\\" in value or "://" in value:
        return None
    path = PurePosixPath(value)
    if ".." in path.parts or not project_root:
        return None
    root = PurePosixPath(project_root)
    if not root.is_absolute() or ".." in root.parts:
        return None
    if path.is_absolute():
        try:
            path = path.relative_to(root)
        except ValueError:
            return None
    return path.as_posix() if path.parts and path.as_posix() != "." else None


def _union(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(intervals):
        if start >= end:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def _uncovered(start: int, end: int, intervals: list[tuple[int, int]]) -> list[list[int]]:
    missing: list[list[int]] = []
    cursor = start
    for left, right in _union(intervals):
        if right <= cursor or left >= end:
            continue
        if left > cursor:
            missing.append([cursor, min(left, end)])
        cursor = max(cursor, min(right, end))
    if cursor < end:
        missing.append([cursor, end])
    return missing


def _occurrences(content: str, snippet: str, start: int, end: int) -> list[tuple[int, int]]:
    found: list[tuple[int, int]] = []
    cursor = start
    while cursor <= end - len(snippet):
        location = content.find(snippet, cursor, end)
        if location < 0:
            break
        found.append((location, location + len(snippet)))
        cursor = location + 1
    return found


def _prepare(group: str, run_dir: Path, corpus_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    record = _json(run_dir / "preparation" / f"{group}.json", errors, "preparation")
    if not isinstance(record, dict):
        record = {}
        errors.append("preparation_not_object")
    root = record.get("root")
    if not isinstance(root, str) or not PurePosixPath(root).is_absolute() or ".." in PurePosixPath(root).parts:
        errors.append("invalid_prepared_project_root")
        root = ""
    inventory = record.get("inventory")
    if not isinstance(inventory, dict):
        errors.append("inventory_not_object")
        inventory = {}
    documents = inventory.get("documents")
    if not isinstance(documents, list):
        errors.append("inventory_documents_not_list")
        documents = []
    declared: dict[str, dict[str, Any]] = {}
    for item in documents:
        if not isinstance(item, dict):
            errors.append("invalid_inventory_document")
            continue
        path = _relative(item.get("path"), root)
        if path is None or path in declared:
            errors.append(f"invalid_or_duplicate_inventory_path:{item.get('path')}")
        else:
            declared[path] = item
    snapshots = record.get("snapshot_sources")
    snapshot_measured = isinstance(snapshots, list)
    if not snapshot_measured:
        errors.append("published_snapshot_inventory_missing")
    snapshot_by_path: dict[str, dict[str, Any]] = {}
    for item in snapshots if snapshot_measured else []:
        if not isinstance(item, dict):
            errors.append("invalid_snapshot_source")
            continue
        path = _relative(item.get("path", item.get("source")), root)
        if path is None or path in snapshot_by_path:
            errors.append(f"invalid_or_duplicate_snapshot_path:{item.get('path')}")
        else:
            snapshot_by_path[path] = item
    source_root = corpus_dir / "sources" / group
    sources: dict[str, dict[str, Any]] = {}
    if not source_root.is_dir():
        errors.append("pinned_source_directory_missing")
    for path in sorted(source_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source_root).as_posix()
        raw = path.read_bytes()
        try:
            content = raw.decode("utf-8")
        except UnicodeError as exc:
            errors.append(f"invalid_pinned_utf8:{relative}:{exc}")
            continue
        digest = _sha(raw)
        source_errors: list[str] = []
        item = declared.get(relative)
        if item is None or _raw_hash(item.get("content_sha256")) != digest:
            source_errors.append("prepare_inventory_raw_hash_mismatch_or_missing")
        snap = snapshot_by_path.get(relative)
        if snapshot_measured:
            if snap is None or _raw_hash(snap.get("content_sha256")) != digest:
                source_errors.append("published_snapshot_raw_hash_mismatch_or_missing")
            elif snap.get("generation_id") != inventory.get("generation_id"):
                source_errors.append("published_snapshot_generation_mismatch")
            if snap is not None:
                if _relative(snap.get("source"), root) != relative:
                    source_errors.append("published_snapshot_absolute_source_mismatch")
                metadata = snap.get("metadata")
                if (not isinstance(metadata, dict)
                        or _raw_hash(metadata.get("project_doc_content_hash")) != digest):
                    source_errors.append("published_snapshot_metadata_raw_hash_mismatch")
        lines = content.splitlines(keepends=True)
        offsets = [0]
        for line in lines:
            offsets.append(offsets[-1] + len(line))
        sources[relative] = {
            "content": content, "raw": raw, "line_offsets": offsets,
            "sha256": digest, "bytes": len(raw), "errors": source_errors,
        }
        errors.extend(f"{relative}:{error}" for error in source_errors)
    if set(declared) != set(sources):
        errors.append("prepare_inventory_paths_differ_from_pinned_corpus")
    if snapshot_measured and set(snapshot_by_path) != set(sources):
        errors.append("published_snapshot_paths_differ_from_pinned_corpus")
    return {
        "group": group, "root": root, "sources": sources, "errors": errors,
        "generation_id": inventory.get("generation_id"),
        "snapshot_raw_hash_verification": "MEASURED" if snapshot_measured else "NOT_MEASURED",
        "inventory_artifact": _artifact(run_dir / "preparation" / f"{group}.json"),
    }


def _source_rows(payload: dict[str, Any], prepared: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, list[tuple[int, int]]], list[str]]:
    errors: list[str] = []
    rows = payload.get("sources", [])
    if not isinstance(rows, list):
        return [], {}, ["public_sources_not_list"]
    verified: list[dict[str, Any]] = []
    intervals: dict[str, list[tuple[int, int]]] = {}
    evidence_ids: set[str] = set()
    expected_identity = "local:" + _sha(prepared["root"].encode("utf-8"))
    for index, row in enumerate(rows):
        issues: list[str] = []
        result: dict[str, Any] = {"source_index": index}
        if not isinstance(row, dict):
            issues.append("source_not_object")
            row = {}
        relative = _relative(row.get("path_or_url"), prepared["root"])
        result.update(path_or_url=row.get("path_or_url"), relative_path=relative,
                      evidence_id=row.get("evidence_id"), line_start=row.get("line_start"),
                      line_end=row.get("line_end"), projection_fingerprint=row.get("content_sha256"))
        source = prepared["sources"].get(relative)
        if source is None:
            issues.append("source_path_outside_allowed_project_corpus")
        if row.get("scope") != "project":
            issues.append("source_scope_not_project")
        if row.get("authority") != "source_of_truth":
            issues.append("source_authority_not_source_of_truth")
        if row.get("version_binding") != "unversioned":
            issues.append("source_version_binding_differs_from_unversioned_fixture_catalog")
        if row.get("project_identity") != expected_identity:
            issues.append("source_project_identity_mismatch")
        fingerprint = row.get("content_sha256")
        if not isinstance(fingerprint, str) or not HASH.fullmatch(fingerprint):
            issues.append("invalid_projection_fingerprint")
        evidence_id = row.get("evidence_id")
        if not isinstance(evidence_id, str) or not evidence_id or evidence_id in evidence_ids:
            issues.append("missing_or_duplicate_evidence_id")
        else:
            evidence_ids.add(evidence_id)
        snippet = row.get("snippet")
        if not isinstance(snippet, str) or not snippet:
            issues.append("empty_or_invalid_snippet")
        placements: list[tuple[int, int]] = []
        if source is not None:
            result["pinned_raw_file_sha256"] = source["sha256"]
            issues.extend(source["errors"])
            start, end = row.get("line_start"), row.get("line_end")
            offsets = source["line_offsets"]
            if type(start) is not int or type(end) is not int or not 1 <= start <= end < len(offsets):
                issues.append("declared_line_range_invalid")
            elif isinstance(snippet, str) and snippet:
                span_start, span_end = offsets[start - 1], offsets[end]
                try:
                    exact_bytes = snippet.encode("utf-8") in source["content"][span_start:span_end].encode("utf-8")
                except UnicodeError:
                    exact_bytes = False
                if not exact_bytes:
                    issues.append("snippet_not_exact_raw_substring_in_declared_lines")
                else:
                    placements = _occurrences(source["content"], snippet, span_start, span_end)
        guaranteed: list[tuple[int, int]] = []
        if not issues and placements:
            left = max(span[0] for span in placements)
            right = min(span[1] for span in placements)
            if left < right:
                guaranteed.append((left, right))
                intervals.setdefault(relative, []).append((left, right))
        result.update(
            integrity_pass=not issues, errors=issues,
            possible_occurrences=[list(span) for span in placements],
            ambiguous_placement=len(placements) > 1,
            guaranteed_coverage_intervals=[list(span) for span in guaranteed],
        )
        errors.extend(f"source[{index}]:{issue}" for issue in issues)
        verified.append(result)
    return verified, intervals, errors


def _continuations(payload: dict[str, Any], prepared: dict[str, Any]) -> list[str]:
    """Validate advertised source targets, without dereferencing capabilities."""
    errors: list[str] = []
    targets = payload.get("read_next", [])
    if not isinstance(targets, list):
        return ["public_read_next_not_list"]
    identity = "local:" + _sha(prepared["root"].encode("utf-8"))
    for index, target in enumerate(targets):
        if not isinstance(target, dict):
            errors.append(f"read_next[{index}]:not_object")
            continue
        relative = _relative(target.get("path"), prepared["root"])
        source = prepared["sources"].get(relative)
        if source is None:
            errors.append(f"read_next[{index}]:path_outside_allowed_project_corpus")
            continue
        if _raw_hash(target.get("snapshot_sha256")) != source["sha256"]:
            errors.append(f"read_next[{index}]:raw_snapshot_hash_mismatch")
        if target.get("project_identity") != identity:
            errors.append(f"read_next[{index}]:project_identity_mismatch")
        start, end = target.get("line_start"), target.get("line_end")
        if (type(start) is not int or type(end) is not int
                or not 1 <= start <= end < len(source["line_offsets"])):
            errors.append(f"read_next[{index}]:line_range_invalid")
    return errors


def _gold(case: dict[str, Any], oracle: dict[str, Any], prepared: dict[str, Any], intervals: dict[str, list[tuple[int, int]]]) -> dict[str, Any]:
    claims: list[dict[str, Any]] = []
    missing_witnesses: list[str] = []
    errors: list[str] = []
    for claim in oracle.get("required_claims", []):
        claim_id = claim["id"]
        alternatives: list[dict[str, Any]] = []
        for set_index, witness_set in enumerate(claim.get("witness_sets", [])):
            parts: list[dict[str, Any]] = []
            for part_index, part in enumerate(witness_set.get("parts", [])):
                witness_id = f"{case['id']}/{claim_id}/set-{set_index}/part-{part_index}"
                relative = part["path"]
                source = prepared["sources"].get(relative)
                item = {"witness_id": witness_id, "path": relative,
                        "line_start": part["line_start"], "line_end": part["line_end"], "covered": False}
                offsets = source["line_offsets"] if source else []
                first, last = part["line_start"], part["line_end"]
                if source is None or not 1 <= first <= last < len(offsets):
                    errors.append(f"invalid_original_gold_range:{witness_id}")
                else:
                    start, end = offsets[first - 1], offsets[last]
                    raw_quote = source["content"][start:end]
                    left_trim = len(raw_quote) - len(raw_quote.lstrip())
                    right_trim = len(raw_quote) - len(raw_quote.rstrip())
                    start += left_trim
                    end -= right_trim
                    if start >= end:
                        errors.append(f"empty_original_gold_range:{witness_id}")
                    else:
                        absent = _uncovered(start, end, intervals.get(relative, []))
                        item.update(char_start=start, char_end=end, expected_characters=end-start,
                                    covered_characters=end-start-sum(b-a for a, b in absent),
                                    missing_char_ranges=absent, covered=not absent,
                                    raw_quote_sha256=_sha(raw_quote.encode("utf-8")),
                                    trimmed_quote_sha256=_sha(source["content"][start:end].encode("utf-8")))
                if not item["covered"]:
                    missing_witnesses.append(witness_id)
                parts.append(item)
            alternatives.append({"set_index": set_index, "covered": bool(parts) and all(p["covered"] for p in parts), "parts": parts})
        claims.append({"claim_id": claim_id, "documented": bool(alternatives),
                       "covered": any(w["covered"] for w in alternatives), "witness_sets": alternatives})
    documented = [claim for claim in claims if claim["documented"]]
    return {
        "claims": claims, "required_claim_count": len(claims),
        "documented_claim_count": len(documented),
        "covered_documented_claim_count": sum(claim["covered"] for claim in documented),
        "all_documented_claims_covered": bool(documented) and all(claim["covered"] for claim in documented),
        "missing_documented_claim_ids": [claim["claim_id"] for claim in documented if not claim["covered"]],
        "unavailable_requested_claim_ids": [claim["claim_id"] for claim in claims if not claim["documented"]],
        "missing_witness_ids": missing_witnesses, "errors": errors,
    }


def _selection(value: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(value, list):
        errors.append("selection_receipts_not_list")
        value = []
    statuses: list[str] = []
    candidate_counts: list[int] = []
    top_ks: list[int] = []
    ordered_pools: list[Any] = []
    ordered_universes: list[Any] = []
    totals: dict[str, int | float] = {key: 0 for key in (
        "model_forward_attempts", "model_forwards", "model_input_tokens", "tokenized_input_tokens",
        "model_load_attempts", "model_loads", "model_load_seconds", "inference_seconds", "tokenization_seconds",
    )}
    for receipt in value:
        if not isinstance(receipt, dict) or not isinstance(receipt.get("selection"), dict):
            errors.append("malformed_selection_receipt")
            continue
        selection = receipt["selection"]
        statuses.append(str(selection.get("status")))
        for field, target in (("candidate_count", candidate_counts), ("top_k", top_ks)):
            number = selection.get(field)
            if type(number) is int:
                target.append(number)
        for field in totals:
            number = selection.get(field)
            if type(number) in (int, float) and math.isfinite(number):
                totals[field] += number
        for field, target in (("pool", ordered_pools), ("complete_candidates", ordered_universes)):
            candidates = receipt.get(field)
            if not isinstance(candidates, list) or not all(isinstance(c, dict) for c in candidates):
                errors.append(f"malformed_selection_{field}")
                target.append(None)
                continue
            target.append({"question": receipt.get("question"), "candidates": [
                {key: c.get(key) for key in ("id", "source", "path", "span", "text_sha256")}
                for c in candidates
            ]})
    def stable_hash(obj: Any) -> str:
        return _sha(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return {
        "receipt_count": len(value), "statuses": statuses, "candidate_counts": candidate_counts,
        "top_ks": top_ks, "competition_observed": any(
            receipt.get("selection", {}).get("candidate_count", 0) > receipt.get("selection", {}).get("top_k", 0)
            for receipt in value if isinstance(receipt, dict) and isinstance(receipt.get("selection"), dict)
            and type(receipt["selection"].get("candidate_count")) is int
            and type(receipt["selection"].get("top_k")) is int
        ),
        "ordered_pool_signature_sha256": stable_hash(ordered_pools),
        "ordered_universe_signature_sha256": stable_hash(ordered_universes),
        "signature_fields": ["question", "id", "source", "path", "span", "text_sha256"],
        "errors": errors, **totals,
    }


def _case(case: dict[str, Any], oracle: dict[str, Any], mode: str, run_dir: Path, prepared: dict[str, Any], final_cap: Any) -> dict[str, Any]:
    directory = run_dir / "calls" / case["id"] / mode
    errors: list[str] = []
    payload = _json(directory / "public-payload.json", errors, "public_payload")
    metadata = _json(directory / "metadata.json", errors, "metadata")
    diagnostic_errors: list[str] = []
    selections = _json(directory / "selection.json", diagnostic_errors, "selection")
    if not isinstance(payload, dict):
        errors.append("public_payload_not_object")
        payload = {}
    if payload.get("kind") != "docs_context":
        errors.append("public_payload_not_docs_context")
    if not isinstance(metadata, dict):
        errors.append("metadata_not_object")
        metadata = {}
    for field, expected in (("case_id", case["id"]), ("mode", mode), ("question", case["question"]), ("project_root", prepared["root"])):
        if metadata.get(field) != expected:
            errors.append(f"metadata_{field}_mismatch")
    if metadata.get("error") or metadata.get("status") != "returned":
        errors.append("call_metadata_reports_error_or_incomplete_execution")
    request = metadata.get("public_request")
    if not isinstance(request, dict):
        errors.append("public_request_not_object")
    else:
        for field, expected in (("question", case["question"]), ("project_path", prepared["root"]), ("scope", "project")):
            if request.get(field) != expected:
                errors.append(f"public_request_{field}_mismatch")
    source_rows, intervals, source_errors = _source_rows(payload, prepared)
    errors.extend(source_errors)
    errors.extend(_continuations(payload, prepared))
    errors.extend(f"preparation:{error}" for error in prepared["errors"])
    retrieval_only = all(payload.get(key) is False for key in ("answer_supported", "answer_available", "edit_ready"))
    if not retrieval_only:
        errors.append("retrieval_only_false_flags_not_preserved")
    gold = _gold(case, oracle, prepared, intervals)
    errors.extend(gold["errors"])
    selection = _selection(selections)
    diagnostic_errors.extend(selection["errors"])
    if metadata.get("observation_errors"):
        diagnostic_errors.append("runner_observer_reported_errors")
    if metadata.get("observation_calls") != selection["receipt_count"]:
        diagnostic_errors.append("observer_call_count_differs_from_saved_receipts")
    payload_artifact = _artifact(directory / "public-payload.json")
    try:
        wire = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        wire_metrics = {"whole_wire_bytes": len(wire), "whole_wire_utf8_quarter_proxy": (len(wire)+3)//4,
                        "whole_wire_sha256": _sha(wire)}
        if payload_artifact.get("sha256") != _sha(wire):
            errors.append("saved_payload_bytes_differ_from_declared_public_wire_serialization")
        if metadata.get("wire_sha256") != _sha(wire) or metadata.get("wire_utf8_bytes") != len(wire):
            errors.append("saved_wire_hash_or_byte_count_mismatch")
        if metadata.get("utf8_quarter_proxy") != (len(wire)+3)//4:
            errors.append("saved_wire_utf8_proxy_mismatch")
    except (ValueError, UnicodeError) as exc:
        errors.append(f"public_payload_wire_encoding_error:{exc}")
        wire_metrics = {"whole_wire_bytes": None, "whole_wire_utf8_quarter_proxy": None}
    named_tokens = metadata.get("codec_o200k_base")
    byte_proxy = wire_metrics["whole_wire_utf8_quarter_proxy"]
    budget_measured = type(final_cap) is int and final_cap > 0 and type(named_tokens) is int and named_tokens >= 0 and type(byte_proxy) is int
    within_budget = max(byte_proxy, named_tokens) <= final_cap if budget_measured else None
    if within_budget is not True:
        errors.append("final_wire_budget_exceeded_or_unverified")
    if metadata.get("within_wire_budget") is not within_budget:
        errors.append("saved_wire_budget_verdict_mismatch")
    clean = not errors
    kind = case["answerability"]
    return {
        "case_id": case["id"], "mode": mode, "project_group": case["project_group"],
        "question": case["question"], "answerability": kind,
        "expected_response": oracle.get("expected_response"), "call_status": metadata.get("status"),
        "call_error": metadata.get("error"), "valid_public_call_and_integrity": clean,
        "errors": errors, "diagnostic_errors": diagnostic_errors,
        "selection_cost_accounting_complete": not diagnostic_errors,
        "public_status": payload.get("status"), "public_source_count": len(source_rows),
        "verified_source_count": sum(row["integrity_pass"] for row in source_rows),
        "source_integrity": source_rows, "retrieval_only_flags_pass": retrieval_only,
        "snapshot_raw_hash_verification": prepared["snapshot_raw_hash_verification"],
        "strict_positive_pass": clean and gold["all_documented_claims_covered"] if kind == "within_budget" else None,
        "strict_partial_documented_pass": clean and gold["all_documented_claims_covered"] if kind == "partial" else None,
        "strict_empty_source_pass": clean and not source_rows and payload.get("context_available") is False if kind == "unanswerable" else None,
        "gold": gold, "selection": selection, **wire_metrics,
        "codec_o200k_base": metadata.get("codec_o200k_base"),
        "wire_budget_limit": final_cap, "within_wire_budget": within_budget,
        "public_estimated_tokens": payload.get("estimated_tokens"),
        "elapsed_seconds": metadata.get("elapsed_seconds"),
        "process_cpu_seconds": metadata.get("process_cpu_seconds"),
        "artifacts": {name: _artifact(directory / name) for name in ("public-payload.json", "metadata.json", "selection.json", "trace.jsonl")},
        "semantic_context_sufficiency": "NOT_MEASURED",
        "semantic_source_relevance": "NOT_MEASURED",
        "generated_answer_correctness": "NOT_MEASURED",
    }


def _stats(values: list[Any]) -> dict[str, Any]:
    numbers = sorted(value for value in values if type(value) in (int, float) and math.isfinite(value))
    return {"count": len(numbers), "sum": sum(numbers),
            "median": statistics.median(numbers) if numbers else None,
            "p95_nearest_rank": numbers[max(0, math.ceil(len(numbers)*0.95)-1)] if numbers else None}


def evaluate(run_dir: Path, corpus_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    questions_file = _json(corpus_dir / "questions.json", errors, "frozen_questions")
    oracle_file = _json(corpus_dir / "gold_spans.json", errors, "frozen_gold")
    if errors or not isinstance(questions_file, dict) or not isinstance(oracle_file, dict):
        raise ValueError("Cannot load frozen questions/gold: " + "; ".join(errors))
    cases = questions_file["cases"]
    oracles = {row["id"]: row for row in oracle_file["cases"]}
    if len(cases) != 40 or len({c["id"] for c in cases}) != 40 or set(oracles) != {c["id"] for c in cases}:
        raise ValueError("The frozen workload must contain exactly the original 40 matching case IDs")
    if Counter(c["answerability"] for c in cases) != {"within_budget": 24, "partial": 8, "unanswerable": 8}:
        raise ValueError("The frozen workload must retain 24 positive, 8 partial and 8 unanswerable cases")
    manifest, input_verification = _frozen_inputs(run_dir, corpus_dir)
    groups = {group: _prepare(group, run_dir, corpus_dir) for group in sorted({c["project_group"] for c in cases})}
    rows = [_case(case, oracles[case["id"]], mode, run_dir, groups[case["project_group"]], manifest.get("final_json_cap")) for case in cases for mode in MODES]
    lookup = {(row["case_id"], row["mode"]): row for row in rows}
    pairs: list[dict[str, Any]] = []
    for case in cases:
        left, right = lookup[(case["id"], "budget")], lookup[(case["id"], "mini")]
        pair_errors: list[str] = []
        saved_pair = _json(run_dir / "pairs" / f"{case['id']}.json", pair_errors, "runner_pair")
        if not isinstance(saved_pair, dict):
            pair_errors.append("runner_pair_not_object")
            saved_pair = {}
        result = {"case_id": case["id"], "answerability": case["answerability"],
                  "both_calls_valid": left["valid_public_call_and_integrity"] and right["valid_public_call_and_integrity"],
                  "runner_pair_record": saved_pair, "runner_pair_errors": pair_errors,
                  "pool_signatures_equal": left["selection"]["ordered_pool_signature_sha256"] == right["selection"]["ordered_pool_signature_sha256"],
                  "universe_signatures_equal": left["selection"]["ordered_universe_signature_sha256"] == right["selection"]["ordered_universe_signature_sha256"],
                  "pool_signature_comparison_valid": not left["diagnostic_errors"] and not right["diagnostic_errors"],
                  "competition_observed": left["selection"]["competition_observed"] or right["selection"]["competition_observed"]}
        prerequisites = {
            "frozen_inputs_unchanged": input_verification["pass"],
            "prepared_source_identity_verified": not groups[case["project_group"]]["errors"],
            "both_public_calls_returned": left["call_status"] == right["call_status"] == "returned",
            "saved_pair_identity_matches": saved_pair.get("case_id") == case["id"] and saved_pair.get("question") == case["question"],
            "saved_pair_complete": not pair_errors,
            "runner_preselection_inputs_equal": saved_pair.get("same_preselection_inputs") is True,
            "runner_observation_complete": saved_pair.get("observation_ok") is True,
            "runner_pair_status_accepted": saved_pair.get("status") in ("paired", "not_reached_both"),
            "runner_receipt_cardinality_valid": saved_pair.get("receipt_cardinality_ok") is True,
            "runner_public_success_both": saved_pair.get("public_success_both") is True,
            "runner_pool_universe_exclusions_equal": all(
                isinstance(saved_pair.get("inputs", {}).get(field), dict)
                and saved_pair["inputs"][field].get("equal") is True
                for field in ("pool", "complete_candidates", "excluded")
            ) if isinstance(saved_pair.get("inputs"), dict) else False,
            "independent_pool_signatures_equal": result["pool_signatures_equal"],
            "independent_universe_signatures_equal": result["universe_signatures_equal"],
            "selection_signatures_observed": result["pool_signature_comparison_valid"],
            "database_unchanged": saved_pair.get("database_unchanged") is True,
            "project_files_unchanged": saved_pair.get("project_files_unchanged") is True,
        }
        result["comparison_prerequisites"] = prerequisites
        result["comparable_pair"] = all(prerequisites.values())
        result["comparison_exclusion_reasons"] = [key for key, passed in prerequisites.items() if not passed]
        for metric in ("strict_positive_pass", "strict_partial_documented_pass", "strict_empty_source_pass"):
            before, after = left[metric], right[metric]
            if before is not None:
                result.update(metric=metric, budget_pass=before, mini_pass=after,
                              transition="gain" if not before and after else "loss" if before and not after else "both_pass" if before and after else "both_fail")
        pairs.append(result)
    summaries: dict[str, Any] = {}
    for mode in MODES:
        selected = [row for row in rows if row["mode"] == mode]
        summaries[mode] = {
            "expected_calls": 40, "valid_public_calls_and_integrity": sum(row["valid_public_call_and_integrity"] for row in selected),
            "wire_budget": {"cases": 40, "pass": sum(row["within_wire_budget"] is True for row in selected),
                            "fail": sum(row["within_wire_budget"] is False for row in selected),
                            "unverified": sum(row["within_wire_budget"] is None for row in selected)},
            "positive": {"cases": 24, "strict_full_gold_delivery_pass": sum(row["strict_positive_pass"] is True for row in selected)},
            "partial": {"cases": 8, "documented_part_delivery_pass": sum(row["strict_partial_documented_pass"] is True for row in selected)},
            "unanswerable": {"cases": 8, "strict_empty_source_pass": sum(row["strict_empty_source_pass"] is True for row in selected)},
            "all_documented_claims": sum(row["gold"]["documented_claim_count"] for row in selected),
            "covered_documented_claims": sum(row["gold"]["covered_documented_claim_count"] for row in selected),
            "competition_cases": sum(row["selection"]["competition_observed"] for row in selected),
            "selection_cost_accounting_complete": all(row["selection_cost_accounting_complete"] for row in selected),
            "calls_with_incomplete_selection_diagnostics": sum(not row["selection_cost_accounting_complete"] for row in selected),
            "selection_statuses": dict(Counter(status for row in selected for status in row["selection"]["statuses"])),
            "model_forwards": sum(row["selection"]["model_forwards"] for row in selected),
            "model_forward_attempts": sum(row["selection"]["model_forward_attempts"] for row in selected),
            "model_input_tokens": sum(row["selection"]["model_input_tokens"] for row in selected),
            "elapsed_seconds": _stats([row["elapsed_seconds"] for row in selected]),
            "process_cpu_seconds": _stats([row["process_cpu_seconds"] for row in selected]),
            "whole_wire_bytes": _stats([row["whole_wire_bytes"] for row in selected]),
            "whole_wire_utf8_quarter_proxy": _stats([row["whole_wire_utf8_quarter_proxy"] for row in selected]),
            "codec_o200k_base": _stats([row["codec_o200k_base"] for row in selected]),
        }
    return {
        "schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run_dir), "corpus_dir": str(corpus_dir),
        "question_count": 40, "expected_public_context_calls": 80,
        "measurement": MEASUREMENT, "summary": summaries,
        "frozen_input_verification": input_verification,
        "comparable_pairs": sum(pair["comparable_pair"] for pair in pairs),
        "uninterpretable_pairs": sum(not pair["comparable_pair"] for pair in pairs),
        "paired_transitions_by_answerability": {kind: dict(Counter(pair["transition"] for pair in pairs if pair["answerability"] == kind and pair["comparable_pair"]))
                                                  for kind in ("within_budget", "partial", "unanswerable")},
        "raw_outcome_transitions_not_causal": {kind: dict(Counter(pair["transition"] for pair in pairs if pair["answerability"] == kind))
                                              for kind in ("within_budget", "partial", "unanswerable")},
        "inputs": {name: _artifact(corpus_dir / name) for name in ("questions.json", "gold_spans.json", "source_plan.json", "source-manifest.json")},
        "preparation_integrity": {group: {key: value for key, value in prepared.items() if key != "sources"} for group, prepared in groups.items()},
        "cases": rows, "pairs": pairs,
        "limitations": [
            "Semantic context sufficiency, general source relevance and generated-answer correctness: NOT_MEASURED.",
            "Full historical gold range delivery is conservative; examples and framing inside the gold remain mandatory.",
            "Partial cases measure their documented part only; no complete-answer success is claimed.",
            "Negative empty-source failures remain failures even if an external generator could reject the premise.",
            "Public content_sha256 is checked for shape, not independently recomputed as a projection fingerprint.",
            "No source continuation URI is dereferenced; permissions and read-only state are not re-executed by this scorer.",
            "Snapshot hash checks rely on saved raw generation-source inventory, not a new live database read.",
            "Selection signature equality uses the declared fields; saved runner pair records retain its full comparison separately.",
            "Size proxies are not provider billing. Query latency excludes separately prepared model loading and indexing.",
            "The named o200k_base token count is a saved runner measurement; this stdlib-only scorer recomputes UTF-8 bytes independently.",
            "Comparable-pair transitions require identical preselection inputs and unchanged saved state; excluded pairs remain visible individually.",
            "The historical 40-question set is exposed and is not a new blind holdout.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--corpus-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Default: <run-dir>/evaluation.json")
    args = parser.parse_args()
    run_dir, corpus_dir = args.run_dir.resolve(), args.corpus_dir.resolve()
    output = args.output.resolve() if args.output else run_dir / "evaluation.json"
    report = evaluate(run_dir, corpus_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "summary": report["summary"], "paired_transitions_by_answerability": report["paired_transitions_by_answerability"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
