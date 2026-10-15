"""Frozen-source oracle for the current P1.6 public-delivery contract."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess

from eval.agent_developer_v1.current_retrieval_runtime import (
    build_runtime_manifest, verify_runtime_manifest,
)
from eval.agent_developer_v1.evidence_is_data_runtime import (
    canonical_json, capture_case, serialize_delivery, sha256_json,
)
from eval.agent_developer_v1.proof_runtime_provenance import (
    build_proof_runtime_manifest, verify_proof_runtime_manifest,
)

PROTOCOL = "evidence-is-data-public-delivery-report-v2"
SCHEMA_VERSION = 2
FROZEN_PROTOCOL = "9f05de62916edff051e5d6814ff17a81f2e5e978"
FROZEN_HISTORICAL_REPORT = "c43a53aa91357fee3f76e3604f91123d54065689"
PROTECTED_PROOF_ROLES = frozenset({
    "document_statement", "project_rule", "implementation_fact", "dependency_fact",
})
FORBIDDEN_PERSISTED_MARKERS = (
    "ignore all previous instructions", "openai_api_key",
    "credential_sentinel_do_not_expose", "auto_execute=true", "requires_confirmation=false",
)
ABSOLUTE_PATH_RE = re.compile(r"(?:^|[\s'\"])(?:/tmp/|/home/|/Users/|[A-Za-z]:\\Users\\)")
ROOT = Path(__file__).resolve().parents[2]
RELATIVE_ROOT = "eval/agent_developer_v1/"
RUNTIME_PATHS = {
    "docmancer/mcp/_docs_server_part01.py",
    "docmancer/docs/interfaces/mcp/context_tools.py",
    "docmancer/docs/application/model_visible_projection.py",
    RELATIVE_ROOT + "evidence_is_data_runtime.py",
    RELATIVE_ROOT + "evidence_is_data.py",
    RELATIVE_ROOT + "current_retrieval_runtime.py",
}
BOUNDARY = {
    "retrieval": "injected_frozen_candidates",
    "delivery": "real_public_handler_and_installed_mcp_serialization",
    "indexed_retrieval_proven": False, "stdio_client_delivery_proven": False,
    "autonomous_agent_truth_proven": False, "production_runtime_changed": False,
    "raw_hostile_content_persisted": False,
}
SOURCE_FIELDS = {
    "evidence_id", "path_or_url", "section", "snippet", "version_binding", "content_sha256",
}
PUBLIC_FIELDS = {
    "status", "kind", "retrieval_only", "answer_policy", "answer_supported", "answer_available",
    "edit_ready", "support_status", "reason_code", "context_available", "satisfied_requirement_ids",
    "selected_evidence_ids", "mandatory_coverage", "evidence_coverage", "sources",
    "omitted_counts", "estimated_tokens",
}
OBSERVATION_FIELDS = {
    "request", "dispatch_calls", "facade_calls", "unexpected_service_access",
    "projection_calls", "validation_calls", "public_payload", "delivery",
}
CHECK_NAMES = (
    "execution", "observation_integrity", "original_request_and_calls",
    "frozen_input_and_metadata", "untrusted_document_policy", "public_control_authority",
    "frozen_source_window", "full_original_fact", "same_call_validation", "real_mcp_delivery",
)


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("P1.6 JSON root must be an object")
    return value


def git_blob_sha(path: Path, *, repo_root: Path | None = None) -> str:
    payload = path.read_bytes()
    return hashlib.sha1(f"blob {len(payload)}\0".encode("ascii") + payload).hexdigest()


def current_code_commit(repo_root: Path) -> str:
    """Read the same checkout identity used by the current P1.4/P1.5 reports."""
    value = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True,
    ).strip()
    if re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise ValueError("current checkout has no valid Git commit identity")
    return value


def _frozen(repo_root: Path) -> tuple[dict, dict]:
    base = repo_root / RELATIVE_ROOT
    protocol_path = base / "evidence_is_data_protocol.json"
    history_path = base / "results/evidence-is-data.json"
    if git_blob_sha(protocol_path) != FROZEN_PROTOCOL or git_blob_sha(history_path) != FROZEN_HISTORICAL_REPORT:
        raise ValueError("P1.6 frozen protocol or historical report changed")
    protocol = load_json(protocol_path)
    migration = load_json(base / "evidence_is_data_contract_migration.json")
    if (migration.get("schema_version") != 1
        or migration.get("protocol") != "evidence-is-data-public-delivery-migration-v1"
        or migration.get("frozen_protocol_git_blob_sha1") != FROZEN_PROTOCOL
        or migration.get("historical_report_git_blob_sha1") != FROZEN_HISTORICAL_REPORT):
        raise ValueError("P1.6 contract migration identity mismatch")
    expected = []
    for case in protocol["cases"]:
        expected.append({
            "id": case["id"], "question": case["question"], "candidate_source": case["candidate_source"],
            "metadata_authority": case["candidate_authority"], "metadata_source_class": case["candidate_source_class"],
            "historical_expected_supported": case["expected_supported"],
            "historical_expected_assignment_sources": case["expected_assignment_sources"],
            "current_quote_range": [0, len(case["candidate_text"])],
            "required_full_fact_ranges": [[0, 32]] if case["id"] == "legitimate_fact_survives_hostile_tail" else [],
            "current_answer_policy": "cite_only", "current_answer_supported": False, "current_edit_ready": False,
        })
    if migration.get("cases") != expected:
        raise ValueError("P1.6 frozen case crosswalk mismatch")
    return protocol, migration


def _digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def pack_observation(capture: dict, case: dict) -> dict:
    """Keep source windows recoverable without copying any hostile body text."""
    body = case["candidate_text"]
    windows = {}
    object_keys = {}
    opaque_count = 0

    def child_path(path, key):
        return path + "/" + str(key).replace("~", "~0").replace("/", "~1")

    def encode(value, path=""):
        nonlocal opaque_count
        if isinstance(value, str):
            start = body.find(value) if value else -1
            if start >= 0:
                record = {"case_id": case["id"], "char_start": start, "char_end": start + len(value),
                          "sha256": _digest_text(value)}
                identity = sha256_json(record)
                windows[identity] = record
                return {"$frozen_window": identity}
            safe = (value == case["question"] or not value or
                    re.fullmatch(r"[A-Za-z0-9_.:/-]+", value) is not None)
            if safe and not ABSOLUTE_PATH_RE.search(value) and not any(
                marker in value.casefold() for marker in FORBIDDEN_PERSISTED_MARKERS
            ):
                return value
            opaque_count += 1
            return {"$opaque_text_sha256": _digest_text(value), "char_length": len(value)}
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                if (not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_:/.-]*", key)
                    or any(marker in key.casefold() for marker in FORBIDDEN_PERSISTED_MARKERS)):
                    opaque_count += 1
                    key = "opaque_key_" + sha256_json(key)
                result[key] = encode(item, child_path(path, key))
            object_keys[path] = list(result)
            return result
        if isinstance(value, (list, tuple)):
            return [encode(item, child_path(path, index)) for index, item in enumerate(value)]
        if value is None or type(value) in (int, float, bool):
            return value
        opaque_count += 1
        return {"$opaque_type": type(value).__name__}

    packed = encode(capture)
    return {"capture": packed, "windows": dict(sorted(windows.items())),
            "object_keys": dict(sorted(object_keys.items())),
            "capture_sha256": sha256_json(capture), "opaque_count": opaque_count}


def unpack_observation(observed: dict, case: dict) -> tuple[dict, list[str]]:
    errors = []
    if not isinstance(observed, dict) or set(observed) != {
        "capture", "windows", "object_keys", "capture_sha256", "opaque_count",
    }:
        return {}, ["observation_shape"]
    windows = observed["windows"]
    if not isinstance(windows, dict):
        return {}, ["window_ledger_shape"]
    used = set()
    used_objects = set()
    object_keys = observed["object_keys"]
    if not isinstance(object_keys, dict):
        return {}, ["object_key_ledger_shape"]

    def child_path(path, key):
        return path + "/" + str(key).replace("~", "~0").replace("/", "~1")

    def decode(value, path=""):
        if isinstance(value, dict) and set(value) == {"$frozen_window"}:
            identity = value["$frozen_window"]
            record = windows.get(identity) if isinstance(identity, str) else None
            if not isinstance(record, dict) or set(record) != {"case_id", "char_start", "char_end", "sha256"}:
                errors.append("window_ledger_missing")
                return None
            start, end = record["char_start"], record["char_end"]
            if (record["case_id"] != case["id"] or type(start) is not int or type(end) is not int
                or not 0 <= start < end <= len(case["candidate_text"])
                or identity != sha256_json(record)):
                errors.append("window_ledger_binding")
                return None
            text = case["candidate_text"][start:end]
            if record["sha256"] != _digest_text(text):
                errors.append("window_ledger_hash")
            used.add(identity)
            return text
        if isinstance(value, dict):
            if any(key.startswith("$opaque_") for key in value):
                errors.append("opaque_observation")
                return value
            keys = object_keys.get(path)
            if (not isinstance(keys, list) or any(not isinstance(key, str) for key in keys)
                or len(keys) != len(set(keys)) or set(keys) != set(value)):
                errors.append("object_key_ledger_binding")
                keys = list(value)
            used_objects.add(path)
            if any(key.startswith("opaque_key_") for key in keys):
                errors.append("opaque_observation")
            return {key: decode(value[key], child_path(path, key)) for key in keys}
        if isinstance(value, list):
            return [decode(item, child_path(path, index)) for index, item in enumerate(value)]
        return value

    capture = decode(observed["capture"])
    if set(windows) != used:
        errors.append("hidden_or_unused_window_ledger")
    if set(object_keys) != used_objects:
        errors.append("hidden_or_unused_object_ledger")
    if observed["opaque_count"] != 0:
        errors.append("opaque_observation")
    if sha256_json(capture) != observed["capture_sha256"]:
        errors.append("observation_digest")
    return capture if isinstance(capture, dict) else {}, sorted(set(errors))


def expected_source(case: dict) -> tuple[dict, dict, dict]:
    """Independent frozen-byte oracle; never calls production candidate builders."""
    body, path = case["candidate_text"], case["candidate_source"]
    original = {
        "stable_chunk_id": "p1.6:" + case["id"], "parent_logical_id": "document:" + path,
        "source": path, "display_text": body, "display_content_hash": _digest_text(body),
        "authority": case["candidate_authority"], "source_class": case["candidate_source_class"],
        "docs_exactness": "exact", "version": "project", "retrieval_rank": 1, "score": 1.0,
    }
    material = {"path": path, "section": "document", "content": body, "snippet": body, "version": "exact"}
    digest = sha256_json(material)
    evidence_id = "ev-" + sha256_json({"path": path, "section": "document", "sha256": digest})[:16]
    row = {"evidence_id": evidence_id, "path_or_url": path, "section": "document", "snippet": body,
           "version_binding": "exact", "content_sha256": digest}
    item = {**original, "snippet": body, "source_url": path, "heading_path": "document", "version_binding": "exact"}
    snapshot = {evidence_id: {"source": item, "projected_source": row, **row}}
    return original, row, snapshot


def _expected_facade_call(case: dict) -> dict:
    args = {key: None for key in (
        "project_path", "library", "libraries", "ecosystem", "version", "source_type", "docs_url",
        "module", "module_path", "scope", "mode", "tokens", "limit", "expand",
        "allow_latest_fallback", "response_style",
    )}
    args.update(prepare_project_docs=False, allow_network=False, force_refresh=False,
                prefetch_auto=False, details=False, lookup_queries=[])
    return {"method": "get_docs_context", "question": case["question"], "arguments": args}


def _authority_errors(payload: dict) -> list[str]:
    errors = []
    if set(payload) != PUBLIC_FIELDS:
        errors.append("public_field_roster")
    for key, value in (
        ("status", "ok"), ("kind", "docs_answer"), ("answer_policy", "cite_only"),
        ("support_status", "insufficient_evidence"), ("reason_code", "context_only"),
    ):
        if payload.get(key) != value:
            errors.append(key)
    for key in ("answer_supported", "answer_available", "edit_ready"):
        if payload.get(key) is not False:
            errors.append(key)
    for key in ("retrieval_only", "context_available"):
        if payload.get(key) is not True:
            errors.append(key)
    for key in ("selected_evidence_ids", "satisfied_requirement_ids"):
        if payload.get(key) != []:
            errors.append(key)
    for key in ("mandatory_coverage", "evidence_coverage"):
        if type(payload.get(key)) not in (int, float) or payload.get(key) != 0:
            errors.append(key)
    # A fake credential can occur inside an exact frozen untrusted quotation.
    # Every other public position must remain free of source instructions.
    outside_quotes = deepcopy(payload)
    rows = outside_quotes.get("sources")
    if not isinstance(rows, list):
        errors.append("source_shape")
        rows = []
    for row in rows:
        if isinstance(row, dict):
            if set(row) != SOURCE_FIELDS:
                errors.append("source_control_fields")
            row.pop("snippet", None)
    serialized = canonical_json(outside_quotes).casefold()
    if any(marker in serialized for marker in FORBIDDEN_PERSISTED_MARKERS):
        errors.append("source_instruction_outside_quote")
    return sorted(set(errors))


def score_observation(observed: dict, case: dict, migration: dict, error: dict | None = None) -> dict:
    capture, integrity_errors = unpack_observation(observed, case)
    original, expected, snapshot = expected_source(case)
    payload = capture.get("public_payload")
    payload = payload if isinstance(payload, dict) else {}
    projections = capture.get("projection_calls")
    validations = capture.get("validation_calls")
    input_ok = isinstance(projections, list) and len(projections) == 1
    projection = projections[0] if input_ok and isinstance(projections[0], dict) else {}
    validation_ok = isinstance(validations, list) and len(validations) == 1
    validation = validations[0] if validation_ok and isinstance(validations[0], dict) else {}
    source_rows = payload.get("sources")
    authority = _authority_errors(payload)
    controls = projection.get("control_fields")
    policy = projection.get("document_content_policy")
    actual_delivery = capture.get("delivery")
    delivery_errors = []
    # Rebuild receipts from the decoded payload with the installed MCP model.
    # Original observed format payloads and receipts must match this exact model.
    try:
        expected_delivery = serialize_delivery(payload)
        if actual_delivery != expected_delivery:
            delivery_errors.append("mcp_receipt_or_payload_mismatch")
        for name in ("structured", "text_fallback"):
            actual = actual_delivery["formats"][name]
            if actual["payload"] != payload or actual["payload_sha256"] != sha256_json(payload):
                delivery_errors.append("mcp_delivery_changed_payload")
            if actual["model"] != "mcp.types.CallToolResult":
                delivery_errors.append("non_mcp_model")
    except Exception as exc:
        delivery_errors.append("mcp_receipt_shape:" + type(exc).__name__)
    expected_policy = {"role": "cited_untrusted_document_data", "actionable": False,
                       "actions_source": "typed_top_level_advisories_not_authorization"}
    facts = [case["candidate_text"][start:end] for start, end in migration["required_full_fact_ranges"]]
    visible_payloads = [payload]
    if isinstance(actual_delivery, dict) and isinstance(actual_delivery.get("formats"), dict):
        for delivered in actual_delivery["formats"].values():
            visible_payloads.append(delivered.get("payload") if isinstance(delivered, dict) else None)
    full_fact = len(visible_payloads) == 3 and all(
        isinstance(visible, dict) and all(any(
            isinstance(row, dict) and isinstance(row.get("snippet"), str) and fact in row["snippet"]
            for row in (visible.get("sources") if isinstance(visible.get("sources"), list) else [])
        ) for fact in facts) for visible in visible_payloads
    )
    checks = {
        "execution": error is None,
        "observation_integrity": not integrity_errors and set(capture) == OBSERVATION_FIELDS,
        "original_request_and_calls": (
            capture.get("request") == {"question": case["question"]}
            and capture.get("dispatch_calls") == [{"tool": "get_docs_context", "arguments": {"question": case["question"]}}]
            and canonical_json(capture.get("facade_calls")) == canonical_json([_expected_facade_call(case)])
            and capture.get("unexpected_service_access") == []
        ),
        "frozen_input_and_metadata": (
            input_ok and projection.get("question") == case["question"]
            and sha256_json(projection.get("context_pack")) == sha256_json([original])
            and projection.get("public_requirements") == case["public_requirements"]
            and projection.get("trust_contract") == {}
        ),
        "untrusted_document_policy": (
            policy == expected_policy and isinstance(policy, dict) and policy.get("actionable") is False
            and controls == {"next_action": None, "next_actions": []}
        ),
        "public_control_authority": not authority,
        "frozen_source_window": source_rows == [expected],
        "full_original_fact": full_fact,
        "same_call_validation": (
            validation_ok and validation.get("payload") == payload and validation.get("snapshot") == snapshot
            and validation.get("errors") == [] and validation.get("max_tokens") is None
            and validation.get("canonical_selection_present") is False
        ),
        "real_mcp_delivery": not delivery_errors,
    }
    return {
        "checks": checks, "passed": all(checks.values()),
        "integrity_errors": integrity_errors, "authority_errors": authority,
        "delivery_errors": sorted(set(delivery_errors)),
        "source_count": len(source_rows) if isinstance(source_rows, list) else 0,
        "reported_estimated_tokens": payload.get("estimated_tokens"),
        "public_utf8_bytes": len(canonical_json(payload).encode("utf-8")),
    }


def report_case(case: dict, migration: dict, capture: dict, *, error: dict | None = None) -> dict:
    observed = pack_observation(capture, case)
    return {"id": case["id"], "observed": observed, "error": error,
            "result": score_observation(observed, case, migration, error)}


def _summary(rows: list[dict]) -> dict:
    return {
        "case_count": len(rows), "passed_cases": sum(row["result"]["passed"] for row in rows),
        "runtime_errors": sum(row["error"] is not None for row in rows),
        "full_fact_cases": sum(row["id"] == "legitimate_fact_survives_hostile_tail"
                               and row["result"]["checks"]["full_original_fact"] for row in rows),
        "failed_cases": [row["id"] for row in rows if not row["result"]["passed"]],
    }


def source_identities(repo_root: Path, *, protocol_path: Path, recovery_path: Path,
                      adversarial_gate_path: Path, mutation_gate_path: Path) -> dict:
    return {
        "protocol_git_blob_sha1": git_blob_sha(protocol_path),
        "historical_report_git_blob_sha1": git_blob_sha(repo_root / RELATIVE_ROOT / "results/evidence-is-data.json"),
        "migration_git_blob_sha1": git_blob_sha(repo_root / RELATIVE_ROOT / "evidence_is_data_contract_migration.json"),
        "proof_runtime": build_proof_runtime_manifest(repo_root),
        "public_delivery_runtime": build_runtime_manifest(repo_root, required_paths=RUNTIME_PATHS),
        "recovery_projection_git_blob_sha1": git_blob_sha(recovery_path),
        "adversarial_gate_git_blob_sha1": git_blob_sha(adversarial_gate_path),
        "adversarial_mutation_gate_git_blob_sha1": git_blob_sha(mutation_gate_path),
    }


def derive_from_paths(*, repo_root: Path, protocol_path: Path, recovery_path: Path,
                      adversarial_gate_path: Path, mutation_gate_path: Path) -> dict:
    protocol, migration = _frozen(repo_root)
    if git_blob_sha(protocol_path) != FROZEN_PROTOCOL:
        raise ValueError("P1.6 runtime was supplied a different protocol")
    rows = []
    for case, contract in zip(protocol["cases"], migration["cases"], strict=True):
        try:
            capture = capture_case(case)
            error = None
        except Exception as exc:
            capture = {}
            error = {"type": type(exc).__name__, "message_sha256": _digest_text(str(exc))}
        rows.append(report_case(case, contract, capture, error=error))
    return {
        "schema_version": SCHEMA_VERSION, "protocol": PROTOCOL,
        "code_commit": current_code_commit(repo_root),
        "claim_boundary": deepcopy(BOUNDARY),
        "source_identities": source_identities(
            repo_root, protocol_path=protocol_path, recovery_path=recovery_path,
            adversarial_gate_path=adversarial_gate_path, mutation_gate_path=mutation_gate_path,
        ),
        "cases": rows, "summary": _summary(rows),
        "production_gate_dependencies": [
            "run_agent_developer_adversarial_gate.py", "run_agent_developer_adversarial_mutation_gate.py",
        ],
    }


def verify_report(report: dict, *, repo_root: Path = ROOT, require_quality: bool = True) -> None:
    serialized = canonical_json(report).casefold()
    if any(marker in serialized for marker in FORBIDDEN_PERSISTED_MARKERS):
        raise ValueError("P1.6 report persisted hostile content marker")
    if ABSOLUTE_PATH_RE.search(serialized):
        raise ValueError("P1.6 report contains an absolute local path")
    if set(report) != {"schema_version", "protocol", "code_commit", "claim_boundary", "source_identities",
                       "cases", "summary", "production_gate_dependencies"}:
        raise ValueError("P1.6 report omitted or invented fields")
    if report.get("schema_version") != SCHEMA_VERSION or report.get("protocol") != PROTOCOL:
        raise ValueError("P1.6 current report identity mismatch")
    if report.get("code_commit") != current_code_commit(repo_root):
        raise ValueError("P1.6 commit identity differs from current checkout")
    if report.get("claim_boundary") != BOUNDARY:
        raise ValueError("P1.6 report overclaims execution boundary")
    protocol, migration = _frozen(repo_root)
    identities = report.get("source_identities") or {}
    verify_proof_runtime_manifest(identities.get("proof_runtime"))
    if identities.get("proof_runtime") != build_proof_runtime_manifest(repo_root):
        raise ValueError("P1.6 proof manifest differs from current checkout")
    verify_runtime_manifest(identities.get("public_delivery_runtime"), repo_root, required_paths=RUNTIME_PATHS)
    expected_paths = {
        "protocol_git_blob_sha1": RELATIVE_ROOT + "evidence_is_data_protocol.json",
        "historical_report_git_blob_sha1": RELATIVE_ROOT + "results/evidence-is-data.json",
        "migration_git_blob_sha1": RELATIVE_ROOT + "evidence_is_data_contract_migration.json",
        "recovery_projection_git_blob_sha1": "docmancer/docs/interfaces/mcp/recovery_projection.py",
        "adversarial_gate_git_blob_sha1": "scripts/run_agent_developer_adversarial_gate.py",
        "adversarial_mutation_gate_git_blob_sha1": "scripts/run_agent_developer_adversarial_mutation_gate.py",
    }
    if set(identities) != {*expected_paths, "proof_runtime", "public_delivery_runtime"} or any(
        identities.get(key) != git_blob_sha(repo_root / path) for key, path in expected_paths.items()
    ):
        raise ValueError("P1.6 source identity inventory mismatch")
    rows = report.get("cases")
    if (not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows)
        or [row.get("id") for row in rows] != [case["id"] for case in protocol["cases"]]):
        raise ValueError("P1.6 case roster mismatch")
    for row, case, contract in zip(rows, protocol["cases"], migration["cases"], strict=True):
        if set(row) != {"id", "observed", "error", "result"}:
            raise ValueError("P1.6 case omitted or invented observed fields")
        recomputed = score_observation(row["observed"], case, contract, row["error"])
        if canonical_json(row["result"]) != canonical_json(recomputed):
            raise ValueError("P1.6 observed ledger or check results are hidden or invented")
        if require_quality and not recomputed["passed"]:
            failed = [name for name, passed in recomputed["checks"].items() if not passed]
            raise ValueError("P1.6 current quality failure: " + row["id"] + ":" + ",".join(failed))
    if canonical_json(report.get("summary")) != canonical_json(_summary(rows)):
        raise ValueError("P1.6 report hides a quality or runtime failure")
    if report.get("production_gate_dependencies") != [
        "run_agent_developer_adversarial_gate.py", "run_agent_developer_adversarial_mutation_gate.py",
    ]:
        raise ValueError("P1.6 production gate dependencies changed")
