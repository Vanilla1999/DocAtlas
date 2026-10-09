"""P1.5 public retrieval of frozen facts with explicit source provenance."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from eval.agent_developer_v1.current_retrieval_runtime import (
    RUNTIME_REQUIRED_PATHS, authority_errors, build_runtime_manifest,
    bytes_sha256, canonical_json, sha256_json, verify_runtime_manifest,
)
from eval.agent_developer_v1.mixed_retrieval_runtime import (
    INFRASTRUCTURE_MEMBER, INFRASTRUCTURE_TEXT, REQUEST_BINDINGS,
    capture_mixed_source_read, expected_request, project_documents,
)

PROTOCOL = "mixed-evidence-provenance-retrieval-v2"
SCHEMA_VERSION = 2
FROZEN_PROTOCOL_SHA256 = "4559d02bd17977965dc8b7baf19471b3a00d56f5ee09dc37fc6de341aa757d71"
REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT = REPO_ROOT / "eval" / "agent_developer_v1"
PROTECTED_PROOF_ROLES = frozenset({"project_rule", "implementation_fact", "dependency_fact", "document_statement"})
HEX64 = re.compile(r"[0-9a-f]{64}")
# Independent frozen oracle input; do not import the transport fixture constant.
PROTOCOL_CONTROL_TEXT = "User-agent: *\nDisallow:\n"
P15_RUNTIME_PATHS = (RUNTIME_REQUIRED_PATHS - {"eval/agent_developer_v1/paraphrase_robustness.py"}) | {
    "eval/agent_developer_v1/mixed_provenance.py",
    "eval/agent_developer_v1/mixed_retrieval_runtime.py",
    "eval/agent_developer_v1/finite_http_fixture.py",
    "docmancer/docs/interfaces/mcp/prefetch_tools.py",
    "docmancer/docs/application/docs_manifest_service.py",
    "docmancer/docs/application/docs_prefetch_service.py",
    "docmancer/docs/application/library_refresh_policy.py",
    "docmancer/docs/manifest_contract.py",
    "docmancer/docs/fetch_policy.py",
    "docmancer/docs/fetch_transport.py",
    "docmancer/docs/infrastructure/agent_index_gateway.py",
    "docmancer/core/_sqlite_store_part01.py",
    "docmancer/agent.py",
}


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("P1.5 requires a JSON object")
    return value


def _validate_protocol(protocol: dict) -> None:
    if sha256_json(protocol) != FROZEN_PROTOCOL_SHA256:
        raise ValueError("P1.5 frozen questions, facts, roles or negatives changed")
    if (protocol.get("schema_version") != 1 or protocol.get("protocol") != "mixed-evidence-provenance-v1"
            or len(protocol.get("cases") or ()) != 7
            or sum(case["expected_supported"] for case in protocol["cases"]) != 5
            or sum(len(case["expected_assignment_sources"]) for case in protocol["cases"]) != 6):
        raise ValueError("P1.5 frozen corpus identity mismatch")


def expected_migration(protocol: dict) -> dict:
    _validate_protocol(protocol)
    return {
        "schema_version": 1,
        "protocol": "mixed-provenance-current-contract-migration-v1",
        "frozen_protocol_sha256": FROZEN_PROTOCOL_SHA256,
        "historical_report_sha256": "542ab4377d0ce5473dfffe0eced0331eff22fa2e31af1f65b4ff0f1680da7e47",
        "current_report_protocol": PROTOCOL,
        "lookup_queries": [],
        "authority": "source_facts_never_answer_or_edit_permission",
        "remote_input": "original_frozen_urls_and_text_at_dns_http_boundary",
        "remote_preparation": "actual_public_manifest_job_and_record_specific_index",
        "atomic_library_staging_claimed": False,
        "cost_policy": "measure_and_minimize_without_fixed_output_ceiling",
        "project_source_representation": {
            "committed_child_class": "project_file", "snapshot_context_class": "project_doc",
            "child_binding": "same_path_stable_chunk_generation",
            "project_owner": "explicit_request_project_identity",
            "scope": "project", "authority": "source_of_truth",
        },
        "library_source_representation": {
            "snapshot_top": "raw_candidate_fields",
            "snapshot_metadata": "raw_candidate_metadata_fields",
            "join_rule": "all_present_claims_must_agree",
            "content_hash_alias": "stored_content_hash_equals_display_content_hash",
            "version_alias": "candidate_version_equals_resolved_version",
            "coordinates": "exact_integer_char_byte_line_pairs_and_scalar_edges",
            "child_binding": "same_path_stable_chunk_generation_and_full_lineage",
            "exactness": "top_boolean_metadata_boolean_or_sqlite_integer_exact_true_required",
        },
        "infrastructure_member": {
            "path": INFRASTRUCTURE_MEMBER, "text": INFRASTRUCTURE_TEXT,
            "only_when": "no_authored_project_document",
            "purpose": "explicit_cold_member_store_grant_not_question_evidence",
        },
        "protocol_control_member": {
            "text": PROTOCOL_CONTROL_TEXT,
            "purpose": "explicit_finite_http_prerequisite_not_question_evidence",
            "indexing_contract": "all_explicit_members_are_indexed",
            "may_satisfy_original_fact": False,
            "may_be_model_visible": False,
        },
        "crosswalk": [{
            "id": case["id"], "question": case["question"],
            "historical_expected_supported": case["expected_supported"],
            "historical_public_requirements": case["public_requirements"],
            "historical_required_evidence_paths": case.get("required_evidence_paths") or [],
            "host_request_binding": REQUEST_BINDINGS[case["id"]],
            "required_full_fact_sources": case["expected_assignment_sources"],
            "protocol_control_members": [{
                "target_id": row["id"],
                "path_or_url": f"https://{urlsplit(row['source']).hostname}/robots.txt",
                "source_text_sha256": hashlib.sha256(PROTOCOL_CONTROL_TEXT.encode()).hexdigest(),
            } for row in case["candidates"] if row["source_class"] != "project_file"],
            "current_obligation": (
                "all_original_allowed_source_facts_visible_and_bound"
                if case["expected_supported"] else "no_wrong_role_source_credited_and_no_authority"
            ),
            "source_role_mapping": [{
                "path_or_url": row["source"], "source_class": row["source_class"],
                "historical_authority": row["authority"],
                "source_text_sha256": hashlib.sha256(row["text"].encode()).hexdigest(),
                "current_lane": "project" if row["source_class"] == "project_file" else "separate_library_record",
                "may_satisfy_original_fact": row["source"] in case["expected_assignment_sources"],
            } for row in case["candidates"]],
        } for case in protocol["cases"]],
    }


def load_protocol() -> dict:
    protocol = load_json(ROOT / "mixed_provenance_protocol.json")
    _validate_protocol(protocol)
    if load_json(ROOT / "mixed_provenance_contract_migration.json") != expected_migration(protocol):
        raise ValueError("P1.5 reviewed contract migration drift")
    return protocol


def _hash(value) -> bool:
    return isinstance(value, str) and HEX64.fullmatch(value) is not None


def _library_identity(row: dict) -> tuple[str, str, str, str]:
    if row["source_class"] == "dependency_docs":
        return "tenacity", "python", "8.2.3", "python:tenacity@8.2.3:reference"
    name = "p15-" + row["id"]
    return name, "web", "latest", f"web:{name}@latest:reference"


def _stored_errors(rows, documents: dict[str, str]) -> list[str]:
    """Independent byte/range oracle for observed committed active children."""
    if not isinstance(rows, list) or not rows:
        return ["missing_committed_children"]
    errors, seen, paths = [], set(), set()
    for row in rows:
        if not isinstance(row, dict):
            errors.append("stored_child_not_object")
            continue
        key = (row.get("generation_id"), row.get("stable_chunk_id"))
        if any(not isinstance(value, str) or not value for value in key) or key in seen:
            errors.append("stored_child_identity")
            continue
        seen.add(key)
        path, text = row.get("path"), row.get("display_text")
        if not isinstance(path, str) or path not in documents or not isinstance(text, str) or not text:
            errors.append("stored_child_source")
            continue
        paths.add(path)
        raw = documents[path]
        cs, ce, bs, be, ls, le = (row.get(key) for key in (
            "char_start", "char_end", "byte_start", "byte_end", "line_start", "line_end"))
        if (not all(type(value) is int for value in (cs, ce, bs, be, ls, le))
                or not (0 <= cs <= ce <= len(raw) and 0 <= bs <= be <= len(raw.encode()))
                or not (1 <= ls <= le <= len(raw.splitlines()))):
            errors.append("stored_child_coordinates")
        elif (raw[cs:ce] != text or raw.encode()[bs:be] != text.encode()
              or text not in "".join(raw.splitlines(keepends=True)[ls - 1:le])):
            errors.append("stored_child_bytes")
        if (row.get("display_content_hash") != hashlib.sha256(text.encode()).hexdigest()
                or row.get("source_content_hash") != hashlib.sha256(raw.encode()).hexdigest()):
            errors.append("stored_child_hash")
        if any(not isinstance(row.get(key), str) or not row[key]
               for key in ("parent_logical_id", "source_identity")):
            errors.append("stored_parent_identity")
    if paths != set(documents):
        errors.append("stored_member_roster")
    for path, fact in documents.items():
        if not any(isinstance(row, dict) and row.get("path") == path
                   and isinstance(row.get("display_text"), str) and fact in row["display_text"] for row in rows):
            errors.append("stored_frozen_fact_missing")
    return sorted(set(errors))


def preparation_errors(case: dict, observation: dict) -> list[str]:
    errors = []
    prepared = observation.get("preparation") or {}
    local = project_documents(case)
    expected_paths = sorted(local)
    project = prepared.get("project") or {}
    if (project.get("expected_paths") != expected_paths or project.get("indexed_paths") != expected_paths
            or project.get("excluded_or_failed_paths") != [] or project.get("unexpected_paths") != []):
        errors.append("finite_project_preparation")
    errors.extend(_stored_errors(prepared.get("project_stored_children"), local))
    external = prepared.get("external") or {}
    remote = [row for row in case["candidates"] if row["source_class"] != "project_file"]
    manifest, records, job = external.get("manifest") or {}, external.get("records"), external.get("job")
    targets = manifest.get("targets")
    if (manifest.get("version") != 2 or not isinstance(targets, list) or not isinstance(records, list)
            or len(targets) != len(remote) or len(records) != len(remote)
            or any(not isinstance(row, dict) for row in targets + records)
            or [row.get("id") for row in targets if isinstance(row, dict)] != [row["id"] for row in remote]
            or [row.get("target_id") for row in records if isinstance(row, dict)] != [row["id"] for row in remote]):
        return sorted(set([*errors, "finite_remote_roster"]))
    if remote and (not isinstance(job, dict) or job.get("tool") != "docs_status" or job.get("action") != "job"
                   or job.get("status") != "succeeded" or not isinstance(job.get("job_id"), str) or not job["job_id"]):
        errors.append("public_remote_job_not_successful")
    if not remote and job is not None:
        errors.append("unexpected_remote_job")
    for frozen, target, record in zip(remote, targets, records):
        name, ecosystem, version, library_id = _library_identity(frozen)
        official = frozen["source_class"] == "dependency_docs"
        url = frozen["source"]
        source, scope = target.get("source") or {}, target.get("scope") or {}
        if (target.get("identity") != {"kind": "package", "ecosystem": ecosystem, "name": name}
                or target.get("version") != {"policy": "exact" if official else "rolling", "requested": version}
                or source != {"type": "reference", "url": url, "format": "direct-text",
                              "authority": "official_project" if official else "community",
                              "version_binding": "exact" if official else "unversioned"}
                or scope != {"coverage": "bounded",
                             "seed_urls": [url, f"https://{urlsplit(url).hostname}/robots.txt"],
                             "allowed_domains": [urlsplit(url).hostname],
                             "path_prefixes": list(dict.fromkeys([urlsplit(url).path or "/", "/robots.txt"])),
                             "max_pages": 2}):
            errors.append("remote_target_binding")
        if (record.get("name") != name or record.get("ecosystem") != ecosystem
                or record.get("version") != version or record.get("library_id") != library_id
                or record.get("source_type") != "reference" or record.get("docs_url") != url
                or record.get("status") != "available"):
            errors.append("prepared_registry_identity")
        if official and (record.get("resolved_version") != "8.2.3" or record.get("docs_snapshot_exact") is not True):
            errors.append("prepared_exact_version_binding")
        stored_children = record.get("stored_children")
        errors.extend(_stored_errors(stored_children, {
            url: frozen["text"],
            f"https://{urlsplit(url).hostname}/robots.txt": PROTOCOL_CONTROL_TEXT,
        }))
        if isinstance(stored_children, list) and any(
            isinstance(child, dict) and child.get("library_id") != library_id for child in stored_children
        ):
            errors.append("prepared_member_library_identity")
        if official and isinstance(stored_children, list) and any(
            isinstance(child, dict) and (
                child.get("resolved_version") != version
                or type(child.get("docs_snapshot_exact")) not in (bool, int)
                or child.get("docs_snapshot_exact") != 1
            ) for child in stored_children
        ):
            errors.append("prepared_member_exact_version_binding")
    network = observation.get("network_input") or {}
    urls = {row["source"]: row["text"] for row in remote}
    hosts = {urlsplit(url).hostname for url in urls}
    allowed = set(urls) | {f"https://{host}/robots.txt" for host in hosts}
    expected_hashes = {url: hashlib.sha256(text.encode()).hexdigest() for url, text in urls.items()}
    expected_controls = {
        f"https://{host}/robots.txt": hashlib.sha256(PROTOCOL_CONTROL_TEXT.encode()).hexdigest()
        for host in hosts
    }
    events = network.get("events")
    if (network.get("execution") != "frozen_dns_http_input"
            or network.get("document_sha256") != expected_hashes
            or network.get("infrastructure_sha256") != expected_controls or not isinstance(events, list)):
        errors.append("frozen_network_input_identity")
    else:
        fetched = set()
        for event in events:
            if not isinstance(event, dict) or event.get("phase") != "preparation":
                errors.append("read_time_or_unattributed_network")
            elif event.get("kind") == "dns":
                if event.get("host") not in hosts:
                    errors.append("unselected_dns_host")
            elif event.get("kind") == "http":
                if event.get("url") not in allowed:
                    errors.append("unselected_http_url")
                fetched.add(event.get("url"))
            else:
                errors.append("unknown_network_event")
        if not allowed <= fetched:
            errors.append("missing_frozen_http_read")
    return sorted(set(errors))


def _library_source_lineage(binding: dict) -> tuple[dict, list[str]]:
    """Read the documented library DTO; contradictory raw claims always fail."""
    top = binding.get("lineage", {})
    nested = binding.get("metadata_lineage", {})
    if not isinstance(top, dict) or not isinstance(nested, dict):
        return {}, ["source_lineage_malformed"]
    errors = []

    def same(key, left, right):
        if key == "docs_snapshot_exact":
            return (type(left) in (bool, int) and type(right) in (bool, int)
                    and left in (0, 1) and right in (0, 1) and left == right)
        return type(left) is type(right) and left == right

    for key in top.keys() & nested.keys():
        if not same(key, top[key], nested[key]):
            errors.append("library_lineage_conflict:" + key)
    lineage = {**nested, **top}
    for canonical, alias in (("resolved_version", "version"), ("display_content_hash", "content_hash")):
        if canonical in lineage and alias in lineage and not same(canonical, lineage[canonical], lineage[alias]):
            errors.append("library_lineage_conflict:" + canonical)
        if canonical not in lineage and alias in lineage:
            lineage[canonical] = lineage[alias]
    # The public candidate flag is a bool; SQLite-backed metadata also uses 0/1.
    if "docs_snapshot_exact" in top and type(top["docs_snapshot_exact"]) is not bool:
        errors.append("library_exact_snapshot_shape")
    if "docs_snapshot_exact" in nested and (
        type(nested["docs_snapshot_exact"]) not in (bool, int) or nested["docs_snapshot_exact"] not in (0, 1)
    ):
        errors.append("library_exact_snapshot_shape")
    for dimension in ("char", "byte", "line"):
        start, end, packed = dimension + "_start", dimension + "_end", dimension + "_span"
        floor = 1 if dimension == "line" else 0
        pairs = []
        for raw in (top, nested):
            if start in raw or end in raw:
                if (start not in raw or end not in raw
                        or type(raw[start]) is not int or type(raw[end]) is not int
                        or not floor <= raw[start] <= raw[end]):
                    errors.append("library_span_shape:" + dimension)
                else:
                    pairs.append([raw[start], raw[end]])
            if packed in raw:
                span = raw[packed]
                if (not isinstance(span, list) or len(span) != 2
                        or any(type(value) is not int for value in span)
                        or not floor <= span[0] <= span[1]):
                    errors.append("library_span_shape:" + dimension)
                else:
                    pairs.append(span)
        if not pairs:
            errors.append("library_span_missing:" + dimension)
        elif any(pair != pairs[0] for pair in pairs[1:]):
            errors.append("library_span_conflict:" + dimension)
        if pairs:
            lineage.setdefault(start, pairs[0][0])
            lineage.setdefault(end, pairs[0][1])
    return lineage, sorted(set(errors))


def source_errors(case: dict, observation: dict) -> list[str]:
    payload = observation.get("public_payload") or {}
    if not isinstance(payload, dict):
        return ["public_payload_not_object"]
    sources = payload.get("sources")
    errors = []
    if "sources" not in payload and payload.get("status") == "insufficient_evidence":
        sources = []
    if not isinstance(sources, list):
        errors.append("sources_not_list")
        sources = []
    bindings = observation.get("bindings") or {}
    if not isinstance(bindings, dict):
        return [*errors, "binding_map_malformed"]
    facts = {row["source"]: row for row in case["candidates"]}
    prepared = observation.get("preparation") or {}
    records = (prepared.get("external") or {}).get("records") or []
    seen = set()
    request = REQUEST_BINDINGS[case["id"]]
    for source in sources:
        if not isinstance(source, dict):
            errors.append("source_not_object")
            continue
        evidence_id = source.get("evidence_id")
        if not isinstance(evidence_id, str) or not evidence_id or evidence_id in seen:
            errors.append("source_evidence_identity")
            continue
        seen.add(evidence_id)
        path, snippet = source.get("path_or_url"), source.get("snippet")
        frozen = facts.get(path) if isinstance(path, str) else None
        if frozen is None or not isinstance(snippet, str) or not snippet:
            errors.append("source_outside_frozen_facts")
            continue
        binding = bindings.get(evidence_id) or {}
        if not isinstance(binding, dict):
            errors.append("source_binding_malformed")
            continue
        material, lineage = binding.get("candidate_hash_material"), binding.get("lineage") or {}
        if not isinstance(lineage, dict):
            errors.append("source_lineage_malformed")
            continue
        if binding.get("projected_source") != source:
            errors.append("different_same_call_source_binding")
        if not isinstance(material, dict) or set(material) != {"path", "section", "content", "snippet", "version"}:
            errors.append("missing_candidate_hash_material")
            continue
        if (material["path"] != path or (material["section"] or "document") != source.get("section")
                or source.get("content_sha256") != sha256_json(material)
                or source.get("version_binding") != (material["version"] or "unversioned")):
            errors.append("candidate_identity_hash_or_version")
        for value in (material["content"], material["snippet"], snippet):
            if value is not None and (not isinstance(value, str) or value not in frozen["text"]):
                errors.append("candidate_bytes_not_from_frozen_source")
        if not material["content"] and not material["snippet"]:
            errors.append("empty_candidate_material")
        local = frozen["source_class"] == "project_file"
        if local:
            stored = prepared.get("project_stored_children") or []
            if (not request.get("project") or lineage.get("project_identity") != observation.get("project_identity")
                    or lineage.get("source_class") != "project_doc" or lineage.get("doc_scope") != "project"
                    or lineage.get("authority") != "source_of_truth"):
                errors.append("different_project_scope_or_authority")
            if payload.get("kind") == "docs_context" and any(
                source.get(key) != value for key, value in {
                    "project_identity": observation.get("project_identity"), "scope": "project",
                    "authority": "source_of_truth", "line_start": lineage.get("line_start"),
                    "line_end": lineage.get("line_end"),
                }.items()
            ):
                errors.append("different_public_project_binding")
        else:
            lineage, lineage_errors = _library_source_lineage(binding)
            errors.extend(lineage_errors)
            _, _, version, library_id = _library_identity(frozen)
            matching = [row for row in records if row.get("library_id") == library_id]
            stored = matching[0].get("stored_children") or [] if len(matching) == 1 else []
            if (request.get("library") != library_id or lineage.get("library_id") != library_id
                    or lineage.get("canonical_id") != library_id or lineage.get("doc_scope") != "library"
                    or lineage.get("source_class") != "library_doc" or lineage.get("resolved_version") != version
                    or type(lineage.get("docs_snapshot_exact")) not in (bool, int)
                    or lineage.get("docs_snapshot_exact") != 1):
                errors.append("different_library_identity_or_exact_snapshot")
        candidates = [row for row in stored if isinstance(row, dict) and (
            row.get("path") == path and row.get("stable_chunk_id") == lineage.get("stable_chunk_id")
            and row.get("generation_id") == lineage.get("generation_id")
        )]
        fields = ("parent_logical_id", "source_identity", "source_content_hash", "display_text",
                  "display_content_hash", "char_start", "char_end", "byte_start", "byte_end", "line_start", "line_end")
        if len(candidates) != 1 or any(lineage.get(key) != candidates[0].get(key) for key in fields):
            errors.append("source_not_bound_to_committed_child")
        # The project context DTO has a distinct class from its committed
        # source member. Both exact representations and the same owner are
        # required; accepting either string at either stage would erase trust.
        if local and len(candidates) == 1:
            committed = candidates[0]
            if (committed.get("source_class") != "project_file"
                    or committed.get("project_identity") != observation.get("project_identity")
                    or committed.get("doc_scope") != "project"
                    or committed.get("authority") != "source_of_truth"):
                errors.append("different_committed_project_scope_or_authority")
        display = lineage.get("display_text")
        if not isinstance(display, str) or snippet not in display:
            errors.append("visible_source_outside_committed_window")
    if set(bindings) != seen:
        errors.append("binding_roster_mismatch")
    return sorted(set(errors))


def score_observation(case: dict, observation: dict, *, expected_execution="public_fixture_runtime") -> dict:
    payload = observation.get("public_payload") or {}
    if not isinstance(payload, dict):
        payload = {}
    rows = payload.get("sources") if isinstance(payload.get("sources"), list) else []
    integrity = source_errors(case, observation)
    preparation = preparation_errors(case, observation)
    authority = authority_errors(payload)
    identity = observation.get("project_identity")
    request = expected_request(case, identity)
    calls = observation.get("service_requests") or []
    counts = observation.get("observer_counts") or {}
    before, after = observation.get("state_before") or {}, observation.get("state_after") or {}
    local = project_documents(case)
    external = (observation.get("preparation") or {}).get("external") or {}
    expected_indices = {"project", *(row.get("library_id") for row in external.get("records") or [] if isinstance(row, dict))}
    fact_by_path = {row["source"]: row["text"] for row in case["candidates"]}
    required = case["expected_assignment_sources"]
    full_fact_sources = sorted(path for path in required if any(
        isinstance(row, dict) and row.get("path_or_url") == path
        and isinstance(row.get("snippet"), str) and fact_by_path[path] in row["snippet"] for row in rows
    ))
    covered, missing = payload.get("covered_query_ids") or [], payload.get("missing_query_ids") or []
    query_ids_valid = (
        isinstance(covered, list) and isinstance(missing, list)
        and all(isinstance(value, str) for value in covered + missing)
        and len(covered) == len(set(covered)) and len(missing) == len(set(missing))
        and not set(covered) & set(missing) and set(covered + missing) <= {"query-original"}
    )
    status = payload.get("status")
    expected_kind = "docs_answer" if REQUEST_BINDINGS[case["id"]].get("library") else "docs_context"
    shape = (
        payload.get("kind") == expected_kind and status in {"ok", "insufficient_evidence"}
        and (status != "ok" or (bool(rows) and payload.get("context_available") is True
                               and payload.get("answer_policy") == "cite_only"))
        and (status != "ok" or expected_kind != "docs_context"
             or (payload.get("context_status") == "ready" and payload.get("support_status") == "retrieval_only"))
        and (status != "ok" or expected_kind != "docs_answer" or payload.get("retrieval_only") is True)
        and (status != "insufficient_evidence" or (not rows and payload.get("context_available") is False))
    )
    estimates = payload.get("estimated_tokens")
    checks = {
        "runtime_completed": observation.get("execution") == expected_execution and observation.get("error") is None,
        "request_identity": (
            observation.get("request") == request and isinstance(identity, str)
            and re.fullmatch(r"local:[0-9a-f]{64}", identity) is not None
            and len(calls) == 1 and all(calls[0].get(key) == value for key, value in request.items())
        ),
        "one_public_retrieval_and_validation": (
            type(counts.get("retrieval_calls")) is int and counts["retrieval_calls"] == 1
            and type(counts.get("validation_calls")) is int and counts["validation_calls"] == 1
        ),
        "no_lookup_or_write_injection": (
            len(calls) == 1 and calls[0].get("lookup_queries") == []
            and all(calls[0].get(key) is False for key in ("prepare_project_docs", "allow_network", "force_refresh"))
        ),
        "finite_public_preparation": not preparation,
        "read_only": (
            before == after and bool(before.get("generation"))
            and before.get("document_sha256") == {path: hashlib.sha256(text.encode()).hexdigest() for path, text in local.items()}
            and _hash(before.get("catalog_sha256")) and _hash(before.get("registry_records_sha256"))
            and isinstance(before.get("index_sha256"), dict) and set(before["index_sha256"]) == expected_indices
            and all(_hash(value) for value in before["index_sha256"].values())
        ),
        "current_context_shape": bool(shape),
        "no_answer_or_edit_authority": not authority,
        "source_integrity": not integrity,
        "query_attribution": bool(query_ids_valid),
        "required_full_facts": full_fact_sources == sorted(required),
        "negative_source_precision": case["expected_supported"] or not rows,
        "output_cost_observed": type(estimates) is int and estimates >= 0,
    }
    return {
        "required_full_fact_sources": list(required), "visible_full_fact_sources": full_fact_sources,
        "reported_original_query_covered": "query-original" in covered,
        "source_errors": integrity, "preparation_errors": preparation, "authority_errors": authority,
        "output_cost": {"source_count": len(rows), "public_utf8_bytes": len(canonical_json(payload).encode()),
                        "reported_estimated_tokens": estimates},
        "checks": checks, "failed_checks": [key for key, value in checks.items() if value is not True],
        "passed": all(value is True for value in checks.values()),
    }


def _case_row(case: dict, observation: dict) -> dict:
    return {
        "id": case["id"], "question": case["question"],
        "historical_expected_supported": case["expected_supported"],
        "historical_public_requirements": deepcopy(case["public_requirements"]),
        "historical_required_evidence_paths": list(case.get("required_evidence_paths") or []),
        "historical_expected_assignment_sources": list(case["expected_assignment_sources"]),
        "frozen_candidates": [{key: row[key] for key in ("id", "source", "text", "authority", "source_class")}
                              for row in case["candidates"]],
        "observation": observation, "assessment": score_observation(case, observation),
    }


def _summary(rows: list[dict]) -> dict:
    return {
        "case_count": len(rows), "passed_count": sum(row["assessment"]["passed"] for row in rows),
        "failed_case_ids": [row["id"] for row in rows if not row["assessment"]["passed"]],
        "required_full_fact_count": sum(len(row["historical_expected_assignment_sources"]) for row in rows),
        "verified_full_fact_count": sum(len(row["assessment"]["visible_full_fact_sources"])
                                       for row in rows if row["assessment"]["checks"]["source_integrity"]),
        "positive_case_count": sum(row["historical_expected_supported"] for row in rows),
        "negative_case_count": sum(not row["historical_expected_supported"] for row in rows),
        "negative_false_context": sum(not row["assessment"]["checks"]["negative_source_precision"] for row in rows),
        "unauthorized_answer_or_edit_count": sum(not row["assessment"]["checks"]["no_answer_or_edit_authority"] for row in rows),
        "runtime_error_count": sum(row["observation"].get("error") is not None for row in rows),
        "output_source_count": sum(row["assessment"]["output_cost"]["source_count"] for row in rows),
        "output_public_utf8_bytes": sum(row["assessment"]["output_cost"]["public_utf8_bytes"] for row in rows),
    }


CLAIM_BOUNDARY = {
    "current_public_fixture_reads": True, "frozen_questions_facts_roles_changed": False,
    "answer_or_edit_permission": False, "inferred_role_proof_claimed": False,
    "remote_content_is_frozen_fixture": True, "live_official_documentation_verified": False,
    "atomic_library_staging_proven": False, "autonomous_agent_truth_proven": False,
    "installed_client_delivery_proven": False, "historical_report_resealed": False,
    "output_cost_policy": "measure_and_minimize_without_fixed_output_ceiling",
}


def derive_from_paths(*, repo_root: Path, protocol_path: Path, model_path: Path | None = None) -> dict:
    protocol = load_json(protocol_path)
    _validate_protocol(protocol)
    if protocol != load_protocol():
        raise ValueError("P1.5 input differs from the frozen repository corpus")
    rows = []
    with TemporaryDirectory(prefix="docatlas-p15-") as temporary:
        for case in protocol["cases"]:
            try:
                observation = capture_mixed_source_read(case, Path(temporary) / case["id"])
            except Exception as exc:
                import traceback
                traceback.print_exc()
                observation = {"execution": "public_fixture_runtime",
                               "error": {"type": type(exc).__name__, "message": str(exc)},
                               "public_payload": {}, "bindings": {}}
            rows.append(_case_row(case, observation))
    try:
        runtime = build_runtime_manifest(repo_root, required_paths=P15_RUNTIME_PATHS)
        runtime_error = None
    except ValueError as exc:
        runtime, runtime_error = None, str(exc)
    summary = _summary(rows)
    return {
        "schema_version": SCHEMA_VERSION, "protocol": PROTOCOL,
        "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip(),
        "source_identities": {
            "frozen_protocol_sha256": sha256_json(protocol),
            "migration_sha256": sha256_json(load_json(ROOT / "mixed_provenance_contract_migration.json")),
            "runtime": runtime, "runtime_error": runtime_error,
        },
        "summary": summary, "cases": rows,
        "passed": summary["passed_count"] == 7 and runtime_error is None,
        "claim_boundary": deepcopy(CLAIM_BOUNDARY),
    }


def verify_report(report: dict) -> None:
    protocol = load_protocol()
    if report.get("schema_version") != SCHEMA_VERSION or report.get("protocol") != PROTOCOL:
        raise ValueError("P1.5 current report identity mismatch")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    if report.get("code_commit") != commit:
        raise ValueError("P1.5 commit identity differs from current checkout")
    rows = report.get("cases")
    if not isinstance(rows, list) or [row.get("id") for row in rows if isinstance(row, dict)] != [case["id"] for case in protocol["cases"]]:
        raise ValueError("P1.5 frozen case roster drift")
    for case, row in zip(protocol["cases"], rows):
        if not isinstance(row.get("observation"), dict) or row != _case_row(case, row["observation"]):
            raise ValueError("P1.5 frozen case identity or source/fact assessment drift")
    summary = _summary(rows)
    if report.get("summary") != summary:
        raise ValueError("P1.5 source/fact mismatches are hidden or invented")
    identities = report.get("source_identities") or {}
    if (identities.get("frozen_protocol_sha256") != FROZEN_PROTOCOL_SHA256
            or identities.get("migration_sha256") != sha256_json(load_json(ROOT / "mixed_provenance_contract_migration.json"))):
        raise ValueError("P1.5 frozen protocol or migration binding drift")
    if identities.get("runtime_error") is None:
        verify_runtime_manifest(identities.get("runtime"), REPO_ROOT, required_paths=P15_RUNTIME_PATHS)
    elif identities.get("runtime") is not None or not isinstance(identities["runtime_error"], str):
        raise ValueError("P1.5 inconsistent runtime error")
    if report.get("passed") is not (summary["passed_count"] == 7 and identities.get("runtime_error") is None):
        raise ValueError("P1.5 gate decision drift")
    if report.get("claim_boundary") != CLAIM_BOUNDARY:
        raise ValueError("P1.5 report overclaims its evidence boundary")


validate_report = verify_report
