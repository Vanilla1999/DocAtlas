from __future__ import annotations

import json
import re
from pathlib import Path

from eval.task_level.task33_validation import (
    PROTOCOL_PATH,
    _check_boundaries,
    _check_cell_result,
    _check_runner_usage,
    _check_worker_usage,
    build_artifact_manifest,
    load_protocol,
    validate_task33c_run,
)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_frozen_protocol_matches_live_evaluation_contract():
    protocol = load_protocol()

    assert protocol["task_id"] == "decisive_nbo_cross_module_gate_large_001"
    assert len(protocol["conditions"]) == 4
    assert protocol["provider_input_token_limit"] == 7_000
    assert set(protocol["provider_profiles"]) == {"github-models", "openai-api"}
    assert protocol["provider_profiles"]["openai-api"]["credential_environment"] == "OPENAI_API_KEY"
    assert protocol["provider_profiles"]["openai-api"]["model"] == "gpt-4o-mini-2024-07-18"
    assert protocol["provider_request_budget"] == (
        len(protocol["conditions"]) * protocol["agent_turn_limit"] + 8 + 8 + 1
    )
    assert "@sha256:" in protocol["container"]["base_image"]
    assert all("@" in action and len(action.rsplit("@", 1)[1]) == 40 for action in protocol["github_actions"].values())


def test_workflows_split_untrusted_pr_from_model_permission():
    protocol = load_protocol()
    root = Path(__file__).parents[2]
    pr = (root / ".github/workflows/task33c-pr-checks.yml").read_text(encoding="utf-8")
    causal = (root / ".github/workflows/task33c-actions-probe.yml").read_text(encoding="utf-8")

    assert "pull_request:" in pr
    assert "models: read" not in pr
    assert "persist-credentials: false" in pr
    assert "pull_request:" not in causal
    assert "workflow_dispatch:" in causal
    assert "environment: task33c-causal-pilot" in causal
    assert "models: read" in causal
    assert "FROM --platform=linux/amd64 ${TASK33C_BASE_IMAGE}" in causal
    assert "@sha256:" in causal
    assert "--require-hashes" in causal
    assert protocol["container"]["requirements_sha256"] in causal
    assert protocol["container"]["base_image"] in causal
    assert "eval/task_level/results/task33c_github_models_${{ github.run_id }}/" not in causal
    assert protocol["github_actions"]["checkout"] in pr and protocol["github_actions"]["checkout"] in causal
    assert protocol["github_actions"]["setup_python"] in pr and protocol["github_actions"]["setup_python"] in causal
    assert protocol["github_actions"]["upload_artifact"] in causal
    for workflow in (pr, causal):
        uses = re.findall(r"uses:\s*([^\s]+)", workflow)
        assert uses
        assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", value) for value in uses)


def test_artifact_manifest_is_allowlist_only_and_rejects_symlinks(tmp_path: Path):
    _write(tmp_path / "metadata.json", {"safe": True})
    _write(tmp_path / "task" / "condition" / "repeat_0" / "result.json", {"safe": True})
    _write(tmp_path / "task" / "condition" / "repeat_0" / "env" / "installed.json", {"ignored": True})
    (tmp_path / "unexpected.txt").write_text("not evidence", encoding="utf-8")
    (tmp_path / "linked.json").symlink_to(tmp_path / "metadata.json")

    manifest = build_artifact_manifest(tmp_path)

    assert [item["path"] for item in manifest["files"]] == [
        "metadata.json",
        "task/condition/repeat_0/result.json",
    ]
    assert "unexpected.txt" in manifest["rejected"]
    assert "linked.json:symlink" in manifest["rejected"]
    assert all("/env/" not in item["path"] for item in manifest["files"])


def test_independent_validator_rejects_synthetic_self_reported_completeness(tmp_path: Path):
    protocol = load_protocol()
    profile = protocol["provider_profiles"]["github-models"]
    (tmp_path / PROTOCOL_PATH.name).write_bytes(PROTOCOL_PATH.read_bytes())
    import hashlib
    profile_hash = hashlib.sha256(
        json.dumps(profile, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    _write(tmp_path / "task33c_provider_selection.json", {
        "schema_version": 1,
        "profile_id": "github-models",
        "profile": profile,
        "profile_sha256": profile_hash,
    })
    _write(tmp_path / "task33c_pilot_plan.json", {
        "task_id": protocol["task_id"],
        "conditions": protocol["conditions"],
        "repeats": 1,
        "agent_turn_limit": protocol["agent_turn_limit"],
        "retrieval_call_budget": 1,
        "isolated_worker_attempt_budget": 1,
        "packet_token_budget": protocol["packet_token_budget"],
        "required_evidence_categories": protocol["required_evidence_categories"],
        "required_evidence_paths": protocol["required_evidence_paths"],
        "required_target_paths": protocol["required_target_paths"],
    })
    forged = [{
        "task_id": protocol["task_id"],
        "condition_id": condition,
        "repeat": 0,
        "model": protocol["model"],
        "runner_id": "github-models",
        "status": "success",
        "hidden_tests_passed": False,
        "metrics": {},
    } for condition in protocol["conditions"]]
    forged.append(dict(forged[0]))
    (tmp_path / "runs.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in forged), encoding="utf-8"
    )
    _write(tmp_path / "task33c_completeness.json", {
        "complete": True,
        "decision": "ENGINEERING_PILOT_COMPLETE",
        "errors": [],
    })

    result = validate_task33c_run(tmp_path)

    assert result["valid"] is False
    assert result["verdict"] == "INCONCLUSIVE"
    assert any(error.startswith("duplicate_cell:") for error in result["errors"])
    assert any("result_artifact_missing" in error for error in result["errors"])


def test_runner_usage_is_recomputed_and_rejects_bool_or_forged_totals(tmp_path: Path):
    protocol = load_protocol()
    profile = protocol["provider_profiles"]["github-models"]
    usage = {
        "provider": "github-models",
        "endpoint": profile["endpoint"],
        "model": profile["model"],
        "prompt_revision": protocol["runner_prompt_revision"],
        "turns": [{
            "request_id": "request-1",
            "request_ids": {"x-github-request-id": "request-1"},
            "request_payload_sha256": "a" * 64,
            "estimated_input_tokens": 100,
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 4,
                "total_tokens": 14,
                "prompt_tokens_details": {"cached_tokens": 2},
                "completion_tokens_details": {"reasoning_tokens": 1},
            },
        }],
    }
    _write(tmp_path / "github_models_usage.json", usage)
    row = {
        "metrics": {
            "input_tokens": 10,
            "output_tokens": 4,
            "cached_input_tokens": 2,
            "reasoning_tokens": 1,
        },
        "token_attribution": {"parent": {
            "input_tokens": 10,
            "output_tokens": 4,
            "cached_input_tokens": 2,
            "reasoning_tokens": 1,
        }},
    }
    errors: list[str] = []
    assert _check_runner_usage("lane", tmp_path, row, protocol, profile, set(), errors) == {"request-1"}
    assert errors == []

    usage["turns"][0]["usage"]["prompt_tokens"] = True
    _write(tmp_path / "github_models_usage.json", usage)
    errors = []
    _check_runner_usage("lane", tmp_path, row, protocol, profile, set(), errors)
    assert "lane:invalid_provider_usage" in errors
    assert "lane:provider_total_mismatch:input_tokens" in errors


def test_openai_usage_requires_the_frozen_server_request_header(tmp_path: Path):
    protocol = load_protocol()
    profile = protocol["provider_profiles"]["openai-api"]
    usage = {
        "provider": "openai-api",
        "endpoint": profile["endpoint"],
        "model": profile["model"],
        "prompt_revision": protocol["runner_prompt_revision"],
        "turns": [{
            "request_id": "openai-request",
            "request_ids": {"x-client-request-id": "forged-client-id"},
            "request_payload_sha256": "a" * 64,
            "estimated_input_tokens": 100,
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 4,
                "total_tokens": 14,
                "prompt_tokens_details": {"cached_tokens": 2},
                "completion_tokens_details": {"reasoning_tokens": 1},
            },
        }],
    }
    _write(tmp_path / "openai_api_usage.json", usage)
    row = {
        "metrics": {
            "input_tokens": 10,
            "output_tokens": 4,
            "cached_input_tokens": 2,
            "reasoning_tokens": 1,
        },
        "token_attribution": {"parent": {
            "input_tokens": 10,
            "output_tokens": 4,
            "cached_input_tokens": 2,
            "reasoning_tokens": 1,
        }},
    }
    errors: list[str] = []

    _check_runner_usage("lane", tmp_path, row, protocol, profile, set(), errors)

    assert "lane:provider_request_header_mismatch" in errors
    usage["turns"][0]["request_ids"]["x-request-id"] = "openai-request"
    _write(tmp_path / "openai_api_usage.json", usage)
    errors = []
    _check_runner_usage("lane", tmp_path, row, protocol, profile, set(), errors)
    assert errors == []


def test_worker_usage_is_bound_to_proof_and_unique_request(tmp_path: Path):
    protocol = load_protocol()
    profile = protocol["provider_profiles"]["github-models"]
    proof = {
        "schema_version": 1,
        "provider": "github-models",
        "endpoint": profile["endpoint"],
        "requested_model": protocol["model"],
        "model": protocol["model"],
        "prompt_revision": protocol["worker_prompt_revision"],
        "request_id": "worker-request",
        "input_tokens": 40,
        "output_tokens": 5,
        "reasoning_tokens": 0,
        "response_schema_sha256": "b" * 64,
        "request_payload_sha256": "c" * 64,
        "message_sha256": "d" * 64,
        "estimated_input_tokens": 32,
        "request_ids": {"x-github-request-id": "worker-request"},
        "evidence_fingerprint": "e" * 64,
        "usage": {
            "prompt_tokens": 40,
            "completion_tokens": 5,
            "total_tokens": 45,
            "prompt_tokens_details": {"cached_tokens": 0},
            "completion_tokens_details": {"reasoning_tokens": 0},
        },
    }
    import hashlib
    fingerprint = hashlib.sha256(
        json.dumps(proof, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    _write(tmp_path / "worker_usage_proof.json", proof)
    _write(tmp_path / "isolated_delivery_metrics.json", {
        "worker_provider": "github-models",
        "worker_model": protocol["model"],
        "worker_request_id": "worker-request",
        "worker_input_tokens": 40,
        "worker_output_tokens": 5,
        "worker_reasoning_tokens": 0,
        "worker_usage_proof_fingerprint": fingerprint,
        "evidence_fingerprint": "e" * 64,
    })
    row = {"metrics": {
        "worker_input_tokens": 40,
        "worker_output_tokens": 5,
        "worker_reasoning_tokens": 0,
    }}
    errors: list[str] = []

    assert _check_worker_usage(tmp_path, row, protocol, profile, set(), errors) == {"worker-request"}
    assert errors == []
    errors = []
    _check_worker_usage(tmp_path, row, protocol, profile, {"worker-request"}, errors)
    assert "docatlas_bounded_subagent:duplicate_or_missing_worker_request_id" in errors


def test_cell_validation_requires_independent_test_and_boundary_artifacts(tmp_path: Path):
    protocol = load_protocol()
    profile = protocol["provider_profiles"]["github-models"]
    evaluation = protocol["evaluation"]
    row = {
        "model": protocol["model"],
        "runner_id": "github-models",
        "forbidden_changes": [],
        "evaluation_contract": {"artifact_identity": {
            "fixture_sha256": evaluation["fixture_sha256"],
            "protocol_fixture_sha256": evaluation["protocol_fixture_sha256"],
            "oracle_sha256": evaluation["oracle_sha256"],
            "hidden_tests_sha256": evaluation["hidden_tests_sha256"],
            "external_context_sha256": evaluation["external_context_sha256"],
        }},
        "evaluation_execution": {
            "public_tests": {"status": "executed", "command": "public", "returncode": 0},
            "hidden_tests": {"status": "executed", "command": "hidden", "returncode": 0},
            "boundaries": {
                "runner": {"status": "verified", "image_id_sha256": "a" * 64},
                "evaluator": {"status": "verified", "image_id_sha256": "a" * 64},
            },
        },
    }
    errors: list[str] = []
    _check_cell_result("lane", tmp_path, row, protocol, profile, errors)
    assert "lane:public_tests_artifact_mismatch" in errors
    assert "lane:hidden_tests_artifact_mismatch" in errors

    _write(tmp_path / "runner_execution_boundary.json", row["evaluation_execution"]["boundaries"]["runner"])
    _write(tmp_path / "evaluator_execution_boundary.json", {"status": "verified", "image_id_sha256": "b" * 64})
    errors = []
    hashes = _check_boundaries("lane", tmp_path, row, errors)
    assert hashes == {"a" * 64}
    assert "lane:evaluator_boundary_artifact_mismatch" in errors
