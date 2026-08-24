from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


MANIFEST_PROTOCOL = "docatlas-federated-product-truth-reopening-v2"
REPORT_PROTOCOL = "docatlas-federated-product-truth-candidate-report-v2"
SCHEMA_VERSION = 2
REPOSITORY_ORDER = (
    ("docatlas", "Vanilla1999/DocAtlas", "public"),
    ("hermes", "Vanilla1999/hermes-agent", "public"),
    ("lov", "Vanilla1999/lov", "private"),
)
SHA_RE = re.compile(r"[0-9a-f]{40}")
ABSOLUTE_PATH_RE = re.compile(
    r"(?:^|[\s'\"])(?:/tmp/|/home/|/Users/|[A-Za-z]:\\Users\\)",
)
PRIVATE_TASK_ALLOWED_KEYS = frozenset({"id", "fix_commit", "stage", "valid"})


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
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _mapping(value: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    result = value.get(key)
    if not isinstance(result, Mapping):
        raise ValueError(f"federated task pack omitted object: {key}")
    return result


def _validate_sha(value: Any, *, field: str) -> str:
    text = str(value or "")
    if SHA_RE.fullmatch(text) is None:
        raise ValueError(f"invalid full Git SHA for {field}")
    return text


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("federated manifest schema version mismatch")
    if manifest.get("protocol") != MANIFEST_PROTOCOL:
        raise ValueError("federated manifest protocol mismatch")
    if manifest.get("phase") != "P2_PRODUCT_TRUTH_REOPENING":
        raise ValueError("federated manifest phase mismatch")

    policy = _mapping(manifest, "selection_policy")
    expected_policy = {
        "repository_count": 3,
        "candidate_tasks_per_repository": 8,
        "candidate_task_count": 24,
        "task_origin": "single-parent historical fix candidate",
        "broken_base": "first parent of fix_commit",
        "gold_patch": "exact historical production-only diff of fix_commit or reviewed historical projection",
        "base_must_fail_regression": True,
        "hidden_red_requires_pytest_assertion_failure": True,
        "clean_gold_repetitions": 2,
        "real_model_oracle_required": True,
        "same_model_tools_and_hard_budgets": True,
        "model_workspace_exact_broken_snapshot": True,
        "model_git_and_benchmark_metadata_forbidden": True,
        "model_network_access_forbidden": True,
        "candidate_diff_scored_in_fresh_evaluator_worktree": True,
        "private_source_must_remain_in_source_repository": True,
    }
    if dict(policy) != expected_policy:
        raise ValueError("federated selection policy drift")

    repositories = manifest.get("repositories")
    if not isinstance(repositories, list) or len(repositories) != 3:
        raise ValueError("federated manifest must contain exactly three repositories")

    task_ids: set[str] = set()
    fix_commits: set[str] = set()
    observed_order: list[tuple[str, str, str]] = []
    for repository in repositories:
        if not isinstance(repository, Mapping):
            raise ValueError("federated repository row must be an object")
        repo_id = str(repository.get("id") or "")
        repo_name = str(repository.get("repository") or "")
        visibility = str(repository.get("visibility") or "")
        observed_order.append((repo_id, repo_name, visibility))
        _validate_sha(
            repository.get("frozen_inventory_head"),
            field=f"{repo_id}.frozen_inventory_head",
        )
        if repository.get("worker_attestation") != "pending":
            raise ValueError("source-repository worker attestation must remain pending")
        tasks = repository.get("tasks")
        if not isinstance(tasks, list) or len(tasks) != 8:
            raise ValueError(f"{repo_id} must contain exactly eight candidates")
        expected_prefix = repo_id.replace("_", "-") + "-hf-"
        for index, task in enumerate(tasks, start=1):
            if not isinstance(task, Mapping):
                raise ValueError(f"{repo_id} contains a non-object task")
            if visibility == "private" and set(task) != PRIVATE_TASK_ALLOWED_KEYS:
                raise ValueError("private task metadata exceeds the public allowlist")
            task_id = str(task.get("id") or "")
            if task_id != f"{expected_prefix}{index:03d}":
                raise ValueError(f"non-canonical task identity: {task_id}")
            if task_id in task_ids:
                raise ValueError("duplicate federated task identity")
            task_ids.add(task_id)
            fix_commit = _validate_sha(
                task.get("fix_commit"),
                field=f"{task_id}.fix_commit",
            )
            if fix_commit in fix_commits:
                raise ValueError("duplicate historical fix commit")
            fix_commits.add(fix_commit)
            if task.get("stage") != "source_control_pending":
                raise ValueError("candidate stage was promoted without source attestation")
            if task.get("valid") is not False:
                raise ValueError("candidate task was marked valid before controls")

    if tuple(observed_order) != REPOSITORY_ORDER:
        raise ValueError("federated repository identity/order drift")
    if len(task_ids) != 24:
        raise ValueError("federated manifest must contain exactly 24 unique tasks")

    boundary = _mapping(manifest, "claim_boundary")
    expected_boundary = {
        "source_repository_workers_required": True,
        "private_source_embedded": False,
        "model_execution_config_frozen": False,
        "valid_tasks": 0,
        "task_pack_ready": False,
        "real_model_oracle_authorized": False,
        "canary_authorized": False,
        "full_pilot_authorized": False,
        "product_truth_proven": False,
        "product_failure_proven": False,
        "product_maturity": "Beta",
    }
    if dict(boundary) != expected_boundary:
        raise ValueError("federated claim boundary drift")
    if ABSOLUTE_PATH_RE.search(canonical_json(manifest)):
        raise ValueError("federated manifest contains an absolute local path")


def build_report(manifest: Mapping[str, Any]) -> dict[str, Any]:
    validate_manifest(manifest)
    repositories = manifest["repositories"]
    rows = [
        {
            "id": repository["id"],
            "repository": repository["repository"],
            "visibility": repository["visibility"],
            "frozen_inventory_head": repository["frozen_inventory_head"],
            "candidate_tasks": len(repository["tasks"]),
            "worker_attestation": repository["worker_attestation"],
            "gold_controlled_tasks": 0,
            "real_model_oracle_tasks": 0,
            "valid_tasks": 0,
        }
        for repository in repositories
    ]
    report = {
        "schema_version": SCHEMA_VERSION,
        "protocol": REPORT_PROTOCOL,
        "manifest_protocol": manifest["protocol"],
        "manifest_sha256": sha256_json(manifest),
        "execution_status": "CORRECTED_INVENTORY_SOURCE_CONTROLS_PENDING",
        "summary": {
            "repositories": 3,
            "candidate_tasks": 24,
            "worker_attestations": 0,
            "gold_controlled_tasks": 0,
            "real_model_oracle_tasks": 0,
            "valid_tasks": 0,
            "required_valid_tasks": 24,
        },
        "repositories": rows,
        "privacy": {
            "private_repository": "Vanilla1999/lov",
            "private_source_embedded": False,
            "public_aggregate_may_contain": [
                "opaque_task_id",
                "full_commit_sha",
                "hashes",
                "bounded_status",
                "aggregate_counts",
            ],
            "source_paths_prompts_tests_and_patches_remain_source_local": True,
        },
        "isolation": {
            "exact_broken_snapshot_required": True,
            "git_and_benchmark_metadata_forbidden": True,
            "network_access_forbidden": True,
            "fresh_evaluator_worktree_required": True,
            "model_execution_config_frozen": False,
        },
        "decision": {
            "task_pack_ready": False,
            "real_model_oracle_authorized": False,
            "canary_authorized": False,
            "full_pilot_authorized": False,
            "product_truth_proven": False,
            "product_failure_proven": False,
            "product_maturity": "Beta",
            "next_step": "complete source controls and freeze exact model execution configuration",
        },
    }
    verify_report(report, manifest=manifest)
    return report


def verify_report(report: Mapping[str, Any], *, manifest: Mapping[str, Any]) -> None:
    validate_manifest(manifest)
    if report.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("federated report schema version mismatch")
    if report.get("protocol") != REPORT_PROTOCOL:
        raise ValueError("federated report protocol mismatch")
    if report.get("manifest_protocol") != MANIFEST_PROTOCOL:
        raise ValueError("federated report lost manifest identity")
    if report.get("manifest_sha256") != sha256_json(manifest):
        raise ValueError("federated report manifest digest mismatch")
    if report.get("execution_status") != "CORRECTED_INVENTORY_SOURCE_CONTROLS_PENDING":
        raise ValueError("federated report falsifies execution status")

    summary = _mapping(report, "summary")
    expected_summary = {
        "repositories": 3,
        "candidate_tasks": 24,
        "worker_attestations": 0,
        "gold_controlled_tasks": 0,
        "real_model_oracle_tasks": 0,
        "valid_tasks": 0,
        "required_valid_tasks": 24,
    }
    if dict(summary) != expected_summary:
        raise ValueError("federated report summary drift")

    repositories = report.get("repositories")
    if not isinstance(repositories, list) or len(repositories) != 3:
        raise ValueError("federated report repository rows missing")
    for expected, row in zip(manifest["repositories"], repositories, strict=True):
        if not isinstance(row, Mapping):
            raise ValueError("federated report repository row must be an object")
        expected_row = {
            "id": expected["id"],
            "repository": expected["repository"],
            "visibility": expected["visibility"],
            "frozen_inventory_head": expected["frozen_inventory_head"],
            "candidate_tasks": 8,
            "worker_attestation": "pending",
            "gold_controlled_tasks": 0,
            "real_model_oracle_tasks": 0,
            "valid_tasks": 0,
        }
        if dict(row) != expected_row:
            raise ValueError("federated report repository evidence drift")

    privacy = _mapping(report, "privacy")
    if privacy.get("private_repository") != "Vanilla1999/lov":
        raise ValueError("federated report private repository identity drift")
    if privacy.get("private_source_embedded") is not False:
        raise ValueError("federated report embeds private source")
    if privacy.get("source_paths_prompts_tests_and_patches_remain_source_local") is not True:
        raise ValueError("federated report lost the source-local privacy boundary")

    isolation = _mapping(report, "isolation")
    expected_isolation = {
        "exact_broken_snapshot_required": True,
        "git_and_benchmark_metadata_forbidden": True,
        "network_access_forbidden": True,
        "fresh_evaluator_worktree_required": True,
        "model_execution_config_frozen": False,
    }
    if dict(isolation) != expected_isolation:
        raise ValueError("federated report isolation contract drift")

    decision = _mapping(report, "decision")
    for key in (
        "task_pack_ready",
        "real_model_oracle_authorized",
        "canary_authorized",
        "full_pilot_authorized",
        "product_truth_proven",
        "product_failure_proven",
    ):
        if decision.get(key) is not False:
            raise ValueError(f"federated report overclaims {key}")
    if decision.get("product_maturity") != "Beta":
        raise ValueError("federated report promotes maturity")
    if decision.get("next_step") != "complete source controls and freeze exact model execution configuration":
        raise ValueError("federated report next-step drift")
    if ABSOLUTE_PATH_RE.search(canonical_json(report)):
        raise ValueError("federated report contains an absolute local path")


__all__ = [
    "MANIFEST_PROTOCOL",
    "REPORT_PROTOCOL",
    "SCHEMA_VERSION",
    "build_report",
    "canonical_json",
    "load_json",
    "sha256_json",
    "validate_manifest",
    "verify_report",
]
