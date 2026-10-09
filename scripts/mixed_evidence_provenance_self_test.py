#!/usr/bin/env python3
"""Six compact P1.5 oracle controls; no synthetic row is public-runtime proof."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
from pathlib import Path
from urllib.parse import urlsplit

from eval.agent_developer_v1.current_retrieval_runtime import bytes_sha256, sha256_json, verify_runtime_manifest
from eval.agent_developer_v1.finite_http_fixture import finite_target
from eval.agent_developer_v1.mixed_retrieval_runtime import REQUEST_BINDINGS, expected_request, project_documents
from eval.agent_developer_v1.mixed_provenance import (
    P15_RUNTIME_PATHS, PROTECTED_PROOF_ROLES, _stored_errors, load_json, load_protocol, score_observation, verify_report,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _child(path, text, *, identity, library_id=None, version=None):
    return {
        "stable_chunk_id": "unit-" + hashlib.sha256(path.encode()).hexdigest()[:16],
        "generation_id": "unit-generation", "parent_logical_id": "unit-parent:" + path,
        "source_identity": path, "source_content_hash": hashlib.sha256(text.encode()).hexdigest(),
        "path": path, "display_text": text, "display_content_hash": hashlib.sha256(text.encode()).hexdigest(),
        "char_start": 0, "char_end": len(text), "byte_start": 0, "byte_end": len(text.encode()),
        "line_start": 1, "line_end": len(text.splitlines()), "library_id": library_id,
        "resolved_version": version, "docs_snapshot_exact": bool(version == "8.2.3"),
        "project_identity": identity if library_id is None else None,
        "doc_scope": "project" if library_id is None else "library",
        "source_class": "project_file" if library_id is None else "library_doc",
        "authority": "source_of_truth" if library_id is None else None,
    }


def _control(case: dict, *, source_paths: list[str] | None = None) -> dict:
    """Independent fixture DTO, explicitly excluded from actual runtime evidence."""
    identity = "local:" + "1" * 64
    local = project_documents(case)
    children = [_child(path, fact, identity=identity) for path, fact in sorted(local.items())]
    remote = [row for row in case["candidates"] if row["source_class"] != "project_file"]
    targets = [finite_target(row) for row in remote]
    records, events = [], []
    for frozen, target in zip(remote, targets):
        name, ecosystem = target["identity"]["name"], target["identity"]["ecosystem"]
        version = target["version"]["requested"]
        library_id = f"{ecosystem}:{name}@{version}:reference"
        records.append({
            "target_id": frozen["id"], "library_id": library_id, "name": name, "ecosystem": ecosystem,
            "version": version, "resolved_version": version, "source_type": "reference",
            "docs_url": frozen["source"], "docs_snapshot_exact": version == "8.2.3", "status": "available",
            "stored_children": [
                _child(frozen["source"], frozen["text"], identity=identity, library_id=library_id, version=version),
                _child(f"https://{urlsplit(frozen['source']).hostname}/robots.txt", "User-agent: *\nDisallow:\n",
                       identity=identity, library_id=library_id, version=version),
            ],
        })
        events += [
            {"phase": "preparation", "kind": "dns", "host": urlsplit(frozen["source"]).hostname},
            {"phase": "preparation", "kind": "http", "url": frozen["source"]},
            {"phase": "preparation", "kind": "http", "url": f"https://{urlsplit(frozen['source']).hostname}/robots.txt"},
        ]
    sources, bindings = [], {}
    selected = case["expected_assignment_sources"] if source_paths is None else source_paths
    for index, path in enumerate(selected):
        frozen = next(row for row in case["candidates"] if row["source"] == path)
        candidates = children + [child for record in records for child in record["stored_children"]]
        stored = next(row for row in candidates if row["path"] == path)
        lineage = {key: deepcopy(value) for key, value in stored.items() if key != "path"}
        if stored["library_id"]:
            lineage["canonical_id"] = stored["library_id"]
        else:
            # Independent expected representation at the context DTO boundary.
            # The committed child above remains a project_file.
            lineage["source_class"] = "project_doc"
        material = {"path": path, "section": "unit-fixture", "content": frozen["text"],
                    "snippet": frozen["text"], "version": stored["resolved_version"] or "unversioned"}
        source = {
            "evidence_id": f"ev-unit-{index}", "path_or_url": path, "section": "unit-fixture",
            "snippet": frozen["text"], "version_binding": material["version"],
            "content_sha256": sha256_json(material),
        }
        if not REQUEST_BINDINGS[case["id"]].get("library"):
            source.update(project_identity=identity, authority="source_of_truth", scope="project",
                          line_start=stored["line_start"], line_end=stored["line_end"])
        sources.append(source)
        bindings[source["evidence_id"]] = {
            "projected_source": deepcopy(source), "candidate_hash_material": material, "lineage": lineage,
        }
    state = {
        "generation": "unit-generation", "catalog_sha256": "2" * 64,
        "document_sha256": {path: hashlib.sha256(text.encode()).hexdigest() for path, text in local.items()},
        "index_sha256": {"project": "3" * 64, **{row["library_id"]: "4" * 64 for row in records}},
        "registry_records_sha256": "5" * 64,
    }
    request = expected_request(case, identity)
    library = bool(REQUEST_BINDINGS[case["id"]].get("library"))
    return {
        "execution": "oracle_unit_control", "error": None, "project_identity": identity,
        "request": request,
        "service_requests": [{**request, "prepare_project_docs": False, "allow_network": False, "force_refresh": False}],
        "observer_counts": {"retrieval_calls": 1, "validation_calls": 1},
        "preparation": {
            "project": {"expected_paths": sorted(local), "indexed_paths": sorted(local),
                        "excluded_or_failed_paths": [], "unexpected_paths": []},
            "project_stored_children": children,
            "external": {
                "manifest": {"version": 2, "targets": targets}, "records": records,
                "job": {"tool": "docs_status", "action": "job", "job_id": "unit-job", "status": "succeeded"} if records else None,
            },
        },
        "network_input": {
            "execution": "frozen_dns_http_input",
            "document_sha256": {row["source"]: hashlib.sha256(row["text"].encode()).hexdigest() for row in remote},
            "infrastructure_sha256": {
                f"https://{urlsplit(row['source']).hostname}/robots.txt":
                hashlib.sha256(b"User-agent: *\nDisallow:\n").hexdigest() for row in remote
            },
            "events": events,
        },
        "state_before": state, "state_after": deepcopy(state),
        "public_payload": {
            "status": "ok" if sources else "insufficient_evidence", "kind": "docs_answer" if library else "docs_context",
            "context_available": bool(sources), "context_status": "ready" if sources else "insufficient_evidence",
            "support_status": "insufficient_evidence" if library else "retrieval_only",
            "retrieval_only": True, "answer_policy": "cite_only", "answer_supported": False,
            "answer_available": False, "edit_ready": False, "sources": sources, "estimated_tokens": 6000,
            "covered_query_ids": ["query-original"] if sources else [],
            "missing_query_ids": [] if sources else ["query-original"],
        },
        "bindings": bindings,
    }


def _case(case_id: str) -> dict:
    return next(case for case in load_protocol()["cases"] if case["id"] == case_id)


def _score(case, observation):
    return score_observation(case, observation, expected_execution="oracle_unit_control")


def test_exact_claim_local_assignments() -> None:
    protocol = load_protocol()
    assert len(protocol["cases"]) == 7
    assert sum(case["expected_supported"] for case in protocol["cases"]) == 5
    assert sum(len(case["expected_assignment_sources"]) for case in protocol["cases"]) == 6
    assert sum(not case["expected_supported"] for case in protocol["cases"]) == 2
    assert {row["proof_role"] for case in protocol["cases"] for row in case["public_requirements"]} == PROTECTED_PROOF_ROLES
    case = _case("two_claims_require_two_allowed_roles")
    observation = _control(case)
    result = _score(case, observation)
    assert result["passed"], result
    assert result["visible_full_fact_sources"] == sorted(case["expected_assignment_sources"])
    assert result["checks"]["output_cost_observed"]
    assert not score_observation(case, observation)["checks"]["runtime_completed"]


def test_provenance_gap_is_retained_but_not_hidden() -> None:
    case = _case("dependency_fact_prefers_dependency_docs")
    baseline = _control(case)
    assert _score(case, baseline)["passed"]
    for field, value in (
        ("library_id", "web:unrelated@8.2.3:reference"), ("resolved_version", "latest"),
        ("docs_snapshot_exact", False), ("generation_id", "another-generation"),
        ("source_content_hash", "0" * 64),
    ):
        changed = deepcopy(baseline)
        changed["bindings"]["ev-unit-0"]["lineage"][field] = value
        result = _score(case, changed)
        assert not result["checks"]["source_integrity"], field
        assert "source_integrity" in result["failed_checks"] and not result["passed"]
    changed = deepcopy(baseline)
    source = changed["public_payload"]["sources"][0]
    source["path_or_url"] = "docs/tenacity-notes.md"
    changed["bindings"]["ev-unit-0"]["projected_source"] = deepcopy(source)
    assert not _score(case, changed)["checks"]["source_integrity"]
    assert not _score(case, changed)["checks"]["required_full_facts"]


def test_support_gap_is_retained_but_not_hidden() -> None:
    negative = _case("project_rule_rejects_advisory_only")
    baseline = _control(negative)
    assert _score(negative, baseline)["passed"]
    for key, value in (("answer_supported", True), ("mutation_ready", True),
                       ("answer", "RetryPolicyLimit is five attempts.")):
        changed = deepcopy(baseline)
        changed["public_payload"][key] = value
        assert not _score(negative, changed)["checks"]["no_answer_or_edit_authority"], key
    wrong = _control(negative, source_paths=[negative["candidates"][0]["source"]])
    assert not _score(negative, wrong)["checks"]["negative_source_precision"]
    positive = _case("project_rule_prefers_canonical_policy")
    baseline = _control(positive)
    assert _score(positive, baseline)["passed"]
    cropped = deepcopy(baseline)
    source = cropped["public_payload"]["sources"][0]
    source["snippet"] = "RetryPolicyLimit is two"
    cropped["bindings"]["ev-unit-0"]["projected_source"] = deepcopy(source)
    result = _score(positive, cropped)
    assert result["checks"]["source_integrity"], result
    assert not result["checks"]["required_full_facts"]


def test_assignment_source_ledgers_fail_closed() -> None:
    # The independent range oracle must retain LF/CRLF and terminal blank lines.
    path = "docs/line-ending-control.md"
    for text in ("Whole first line.\n", "Whole first line.\r\nSecond whole line.\r\n",
                 "Whole first line.\n\n"):
        child = _child(path, text, identity="local:" + "1" * 64)
        assert _stored_errors([child], {path: text}) == []
    forged = deepcopy(child)
    forged["line_end"] = 1
    assert "stored_child_bytes" in _stored_errors([forged], {path: text})

    case = _case("document_statement_binds_exact_path")
    baseline = _control(case)
    raw = deepcopy(baseline)
    assert _score(case, baseline)["passed"]
    assert baseline == raw
    path = case["expected_assignment_sources"][0]
    # Keep the complete visible fact, its digest and same-call binding fixed.
    # A bad type at either side, including swapping both, must fail integrity.
    for stored_class, snapshot_class in (
        ("project_doc", "project_doc"), ("project_file", "project_file"),
        ("project_doc", "project_file"), ("external_advisory", "external_advisory"),
        (None, "project_doc"), ("project_file", None),
    ):
        changed = deepcopy(baseline)
        stored = next(row for row in changed["preparation"]["project_stored_children"] if row["path"] == path)
        stored["source_class"] = stored_class
        changed["bindings"]["ev-unit-0"]["lineage"]["source_class"] = snapshot_class
        result = _score(case, changed)
        assert changed["public_payload"] == baseline["public_payload"]
        assert result["checks"]["required_full_facts"] and result["checks"]["finite_public_preparation"]
        assert not result["checks"]["source_integrity"] and "source_integrity" in result["failed_checks"], (
            stored_class, snapshot_class, result)
        assert not result["passed"]
    for field, value in (("project_identity", "local:" + "9" * 64),
                         ("doc_scope", "library"), ("authority", "supporting")):
        changed = deepcopy(baseline)
        stored = next(row for row in changed["preparation"]["project_stored_children"] if row["path"] == path)
        stored[field] = value
        result = _score(case, changed)
        assert result["checks"]["required_full_facts"] and result["checks"]["finite_public_preparation"]
        assert "different_committed_project_scope_or_authority" in result["source_errors"]
        assert not result["checks"]["source_integrity"] and not result["passed"]
    wrong_document = _control(case, source_paths=["docs/release-notes.md"])
    assert _score(case, wrong_document)["checks"]["source_integrity"]
    assert not _score(case, wrong_document)["checks"]["required_full_facts"]
    missing = deepcopy(baseline)
    missing["bindings"] = {}
    assert not _score(case, missing)["checks"]["source_integrity"]
    orphan = deepcopy(baseline)
    orphan["bindings"]["orphan"] = {}
    assert "binding_roster_mismatch" in _score(case, orphan)["source_errors"]
    duplicate = deepcopy(baseline)
    duplicate["public_payload"]["sources"].append(deepcopy(duplicate["public_payload"]["sources"][0]))
    assert "source_evidence_identity" in _score(case, duplicate)["source_errors"]
    changed = deepcopy(baseline)
    changed["bindings"]["ev-unit-0"]["lineage"]["line_start"] = 2
    assert not _score(case, changed)["checks"]["source_integrity"]
    negative = _case("dependency_fact_rejects_project_guess_only")
    absent = _control(negative)
    del absent["public_payload"]["sources"]
    assert _score(negative, absent)["passed"]
    for value in (None, {}, False):
        malformed = deepcopy(absent)
        malformed["public_payload"]["sources"] = value
        assert "sources_not_list" in _score(negative, malformed)["source_errors"]
    absent["bindings"]["orphan"] = {}
    assert "binding_roster_mismatch" in _score(negative, absent)["source_errors"]


def test_claim_and_path_leak_fail_closed() -> None:
    case = _case("implementation_fact_rejects_external_claim")
    baseline = _control(case)
    assert _score(case, baseline)["passed"]
    changed = deepcopy(baseline)
    changed["public_payload"]["sources"][0]["path_or_url"] = "/home/user/private.md"
    assert not _score(case, changed)["checks"]["source_integrity"]
    changed = deepcopy(baseline)
    changed["service_requests"][0]["question"] += " and a different task"
    assert not _score(case, changed)["checks"]["request_identity"]
    changed = deepcopy(baseline)
    changed["service_requests"][0]["lookup_queries"] = ["borrowed lookup"]
    assert not _score(case, changed)["checks"]["no_lookup_or_write_injection"]
    changed = deepcopy(baseline)
    changed["public_payload"]["covered_query_ids"].append("query-lookup-1")
    assert not _score(case, changed)["checks"]["query_attribution"]
    changed = deepcopy(baseline)
    changed["state_after"]["index_sha256"]["project"] = "9" * 64
    assert not _score(case, changed)["checks"]["read_only"]
    for event in (
        {"phase": "read", "kind": "http", "url": case["candidates"][1]["source"]},
        {"phase": "preparation", "kind": "http", "url": "https://unexpected.example/source"},
    ):
        changed = deepcopy(baseline)
        changed["network_input"]["events"].append(event)
        assert not _score(case, changed)["checks"]["finite_public_preparation"]

    remote = next(row for row in case["candidates"] if row["source_class"] != "project_file")
    url = remote["source"]
    robots = f"https://{urlsplit(url).hostname}/robots.txt"
    for key, value in (
        ("seed_urls", [url]), ("seed_urls", [url, robots + "?unselected=1"]),
        ("seed_urls", [url, robots, "https://unexpected.example/robots.txt"]),
        ("path_prefixes", [urlsplit(url).path]), ("max_pages", 1),
        ("allowed_domains", [urlsplit(url).hostname, "unexpected.example"]),
    ):
        changed = deepcopy(baseline)
        changed["preparation"]["external"]["manifest"]["targets"][0]["scope"][key] = value
        assert "remote_target_binding" in _score(case, changed)["preparation_errors"], (key, value)
    changed = deepcopy(baseline)
    changed["network_input"]["infrastructure_sha256"][robots] = "0" * 64
    assert "frozen_network_input_identity" in _score(case, changed)["preparation_errors"]
    changed = deepcopy(baseline)
    changed["network_input"]["events"] = [
        event for event in changed["network_input"]["events"] if event.get("url") != robots
    ]
    assert "missing_frozen_http_read" in _score(case, changed)["preparation_errors"]
    for fault in ("missing", "body", "library"):
        changed = deepcopy(baseline)
        record = changed["preparation"]["external"]["records"][0]
        child = next(row for row in record["stored_children"] if row["path"] == robots)
        if fault == "missing":
            record["stored_children"].remove(child)
            expected = "stored_member_roster"
        elif fault == "body":
            replacement = "User-agent: x\nDisallow:\n"
            child.update(_child(robots, replacement, identity=baseline["project_identity"],
                                library_id=record["library_id"], version=record["version"]))
            expected = "stored_child_bytes"
        else:
            child["library_id"] = "web:unrelated@latest:reference"
            expected = "prepared_member_library_identity"
        assert expected in _score(case, changed)["preparation_errors"], fault

    # Even a correctly stored/hash-bound library protocol member is not a frozen
    # question candidate and must never receive citation or fact credit.
    library_case = _case("dependency_fact_prefers_dependency_docs")
    quoted = _control(library_case)
    record = quoted["preparation"]["external"]["records"][0]
    child = next(row for row in record["stored_children"] if row["path"].endswith("/robots.txt"))
    material = {"path": child["path"], "section": "unit-fixture", "content": child["display_text"],
                "snippet": child["display_text"], "version": "8.2.3"}
    source = {"evidence_id": "ev-protocol-control", "path_or_url": child["path"],
              "section": "unit-fixture", "snippet": child["display_text"],
              "version_binding": "8.2.3", "content_sha256": sha256_json(material)}
    lineage = {key: deepcopy(value) for key, value in child.items() if key != "path"}
    lineage["canonical_id"] = record["library_id"]
    quoted["public_payload"]["sources"].append(source)
    quoted["bindings"][source["evidence_id"]] = {
        "projected_source": deepcopy(source), "candidate_hash_material": material, "lineage": lineage,
    }
    assessed = _score(library_case, quoted)
    assert assessed["checks"]["finite_public_preparation"] and assessed["checks"]["required_full_facts"]
    assert "source_outside_frozen_facts" in assessed["source_errors"]
    assert not assessed["checks"]["source_integrity"] and not assessed["passed"]


def test_proof_runtime_shard_identity_fails_closed() -> None:
    rows = [{"path": path, "sha256": bytes_sha256(REPO_ROOT / path),
             "imported_as": [path.removesuffix(".py").replace("/", ".")]} for path in sorted(P15_RUNTIME_PATHS)]
    manifest = {"algorithm": "same-process-source-sha256-v1", "files": rows, "sha256": sha256_json(rows)}
    # Manifest-validator input, not a claim of actual source imports.
    verify_runtime_manifest(manifest, REPO_ROOT, required_paths=P15_RUNTIME_PATHS)
    changed = deepcopy(manifest)
    changed["files"][2]["sha256"] = "0" * 64
    for reseal in (False, True):
        if reseal:
            changed["sha256"] = sha256_json(changed["files"])
        try:
            verify_runtime_manifest(changed, REPO_ROOT, required_paths=P15_RUNTIME_PATHS)
        except ValueError:
            pass
        else:
            raise AssertionError("changed runtime bytes were accepted")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P1.5 source, scope and fact oracle controls")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    checks = (
        test_exact_claim_local_assignments, test_provenance_gap_is_retained_but_not_hidden,
        test_support_gap_is_retained_but_not_hidden, test_assignment_source_ledgers_fail_closed,
        test_claim_and_path_leak_fail_closed, test_proof_runtime_shard_identity_fails_closed,
    )
    for check in checks:
        check()
        print(f"PASS: {check.__name__}")
    if args.report:
        report = load_json(args.report)
        verify_report(report)
        print("PASS: current report integrity (quality verdict unchanged)")
        for field in ("summary", "case", "assessment", "boundary"):
            changed = deepcopy(report)
            if field == "summary":
                changed["summary"]["passed_count"] += 1
            elif field == "case":
                changed["cases"][0]["question"] += " different"
            elif field == "assessment":
                changed["cases"][0]["assessment"]["passed"] = not changed["cases"][0]["assessment"]["passed"]
            else:
                changed["claim_boundary"]["autonomous_agent_truth_proven"] = True
            try:
                verify_report(changed)
            except ValueError:
                pass
            else:
                raise AssertionError("report corruption was accepted: " + field)
    print(f"P1.5 oracle self-test: PASS ({len(checks)}/{len(checks)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
