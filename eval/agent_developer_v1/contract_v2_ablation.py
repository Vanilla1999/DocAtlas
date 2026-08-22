from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


PROTOCOL = "agent-contract-v2-ablation-v1"
SCHEMA_VERSION = 1
ABSOLUTE_PATH_RE = re.compile(
    r"(?:^|[\s'\"])(?:/tmp/|/home/|/Users/|[A-Za-z]:\\Users\\)",
)


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
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def git_blob_sha(path: Path, *, repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", "hash-object", str(path)],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(f"unable to hash {path}: {completed.stderr.strip()[:200]}")
    value = completed.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError(f"invalid Git blob identity: {value!r}")
    return value


def _safe_relative(value: Any) -> PurePosixPath | None:
    raw = str(value or "").replace("\\", "/").strip()
    if not raw or raw.startswith("/"):
        return None
    path = PurePosixPath(raw)
    if ".." in path.parts or (path.parts and path.parts[0].endswith(":")):
        return None
    return path


def conservative_module_inference(
    working_path: str,
    module_roots: Iterable[str],
) -> str | None:
    working = _safe_relative(working_path)
    if working is None:
        return None
    matches: list[str] = []
    for raw_root in module_roots:
        root = _safe_relative(raw_root)
        if root is None:
            continue
        try:
            working.relative_to(root)
        except ValueError:
            continue
        matches.append(root.as_posix())
    unique = sorted(set(matches))
    return unique[0] if len(unique) == 1 else None


def _module_roots(oracle_task: dict[str, Any]) -> list[str]:
    roots: list[str] = []
    for row in oracle_task.get("required_scopes") or ():
        if isinstance(row, dict) and row.get("module_path"):
            roots.append(str(row["module_path"]))
    for call in oracle_task.get("calls") or ():
        if not isinstance(call, dict):
            continue
        recovery = call.get("target_recovery")
        retry = recovery.get("retry") if isinstance(recovery, dict) else None
        if isinstance(retry, dict) and retry.get("module_path"):
            roots.append(str(retry["module_path"]))
    return sorted(set(roots))


def derive_ablation(
    *,
    public_tasks: dict[str, Any],
    oracle: dict[str, Any],
    atlas: dict[str, Any],
    source_identities: dict[str, str],
) -> dict[str, Any]:
    public_rows = public_tasks.get("tasks")
    oracle_rows = oracle.get("trajectories")
    atlas_rows = atlas.get("tasks")
    if not all(isinstance(value, list) for value in (public_rows, oracle_rows, atlas_rows)):
        raise ValueError("P1.3 inputs must contain task arrays")

    public_by_id = {
        str(row.get("id") or ""): row
        for row in public_rows
        if isinstance(row, dict)
    }
    oracle_by_id = {
        str(row.get("id") or ""): row
        for row in oracle_rows
        if isinstance(row, dict)
    }
    atlas_by_id = {
        str(row.get("task_id") or ""): row
        for row in atlas_rows
        if isinstance(row, dict)
    }
    if set(public_by_id) != set(oracle_by_id) or set(public_by_id) != set(atlas_by_id):
        raise ValueError("P1.3 input task identities differ")

    selector_ids = [
        task_id
        for task_id, row in atlas_by_id.items()
        if (
            isinstance(row.get("first_divergence"), dict)
            and row["first_divergence"].get("failure_class")
            == "module_selector_cardinality"
        )
    ]
    inferable: list[dict[str, str]] = []
    blocked: list[str] = []
    for task_id in sorted(selector_ids):
        task = public_by_id[task_id]
        roots = _module_roots(oracle_by_id[task_id])
        inferred = conservative_module_inference(
            str(task.get("working_path") or ""),
            roots,
        )
        if inferred is None:
            blocked.append(task_id)
        else:
            inferable.append({
                "task_id": task_id,
                "working_path": str(task.get("working_path") or ""),
                "inferred_module_path": inferred,
            })

    negative_controls = [
        {
            "id": "traversal",
            "result": conservative_module_inference(
                "../packages/orders/src/submission.py",
                ["packages/orders"],
            ),
        },
        {
            "id": "outside_known_module",
            "result": conservative_module_inference(
                "README.md",
                ["packages/orders"],
            ),
        },
        {
            "id": "overlapping_roots",
            "result": conservative_module_inference(
                "packages/orders/src/submission.py",
                ["packages", "packages/orders"],
            ),
        },
        {
            "id": "nested_ambiguous_roots",
            "result": conservative_module_inference(
                "packages/orders/src/submission.py",
                ["packages/orders", "packages/orders/src"],
            ),
        },
    ]
    if any(row["result"] is not None for row in negative_controls):
        raise ValueError("conservative module inference failed a negative control")

    return {
        "schema_version": SCHEMA_VERSION,
        "protocol": PROTOCOL,
        "status": "closed_with_ablation_decision",
        "claim_boundary": {
            "historical_counterfactual": True,
            "fresh_same_model_run": False,
            "production_api_changed": False,
            "autonomous_agent_truth_proven": False,
        },
        "source_identities": source_identities,
        "baseline": {
            "task_count": 11,
            "historical_passed_tasks": 0,
            "first_divergence_counts": atlas["summary"]["failure_class_counts"],
            "false_supported": 0,
            "forbidden_source_contamination": 0,
        },
        "variants": [
            {
                "id": "working_path_public_argument",
                "hypothesis": "add working_path to the public MCP argument surface",
                "already_model_visible": all(
                    bool(str(row.get("working_path") or ""))
                    for row in public_by_id.values()
                ),
                "first_divergences_prevented": 0,
                "decision": "rejected",
                "reason": (
                    "The historical model already received working_path in every public task; "
                    "copying it into another public schema field does not resolve the exactly-one-of selector error."
                ),
            },
            {
                "id": "conservative_server_owned_scope_inference",
                "hypothesis": (
                    "derive one exact module_path only when working_path belongs to exactly one reviewed module root"
                ),
                "first_divergences_prevented_counterfactually": len(inferable),
                "affected_tasks": inferable,
                "blocked_tasks": blocked,
                "negative_controls": negative_controls,
                "false_supported_delta_provider_free": 0,
                "forbidden_source_contamination_delta_provider_free": 0,
                "decision": "inconclusive_pending_fresh_same_model_run",
                "reason": (
                    "The safe deterministic transform covers the repeated 8-task class, but no fresh same-model installed run exists to prove improved autonomous acquisition."
                ),
            },
            {
                "id": "opaque_continuation_token",
                "hypothesis": "bind later lifecycle calls to an opaque server token",
                "first_divergences_prevented": 0,
                "decision": "rejected_for_current_failure_classes",
                "reason": (
                    "All observed first divergences occur before a valid continuation exists, so a token cannot repair the first causal break."
                ),
            },
        ],
        "decision": {
            "p1_3": "closed",
            "accepted_production_changes": [],
            "deferred_experiment": "conservative_server_owned_scope_inference",
            "public_api_freeze": True,
            "next_step": "P1.4 paraphrase/proofability robustness",
        },
    }


def verify_ablation(report: dict[str, Any]) -> None:
    if report.get("schema_version") != SCHEMA_VERSION or report.get("protocol") != PROTOCOL:
        raise ValueError("P1.3 ablation identity mismatch")
    boundary = report.get("claim_boundary")
    if not isinstance(boundary, dict) or any(
        boundary.get(key) is not False
        for key in (
            "fresh_same_model_run",
            "production_api_changed",
            "autonomous_agent_truth_proven",
        )
    ):
        raise ValueError("P1.3 ablation overclaims live evidence or production changes")
    variants = report.get("variants")
    if not isinstance(variants, list) or len(variants) != 3:
        raise ValueError("P1.3 requires exactly three candidate variants")
    by_id = {
        str(row.get("id") or ""): row
        for row in variants
        if isinstance(row, dict)
    }
    if set(by_id) != {
        "working_path_public_argument",
        "conservative_server_owned_scope_inference",
        "opaque_continuation_token",
    }:
        raise ValueError("P1.3 candidate identity drift")
    if by_id["working_path_public_argument"].get("decision") != "rejected":
        raise ValueError("working_path duplication must remain rejected")
    inference = by_id["conservative_server_owned_scope_inference"]
    if inference.get("first_divergences_prevented_counterfactually") != 8:
        raise ValueError("conservative inference no longer covers the 8-task repeated class")
    if inference.get("decision") != "inconclusive_pending_fresh_same_model_run":
        raise ValueError("conservative inference was promoted without fresh evidence")
    if len(inference.get("affected_tasks") or ()) != 8 or inference.get("blocked_tasks") != []:
        raise ValueError("conservative inference task coverage drift")
    if any(row.get("result") is not None for row in inference.get("negative_controls") or ()):
        raise ValueError("conservative inference negative control failed")
    if by_id["opaque_continuation_token"].get("first_divergences_prevented") != 0:
        raise ValueError("continuation token cannot be credited for pre-call failures")
    decision = report.get("decision")
    if not isinstance(decision, dict) or decision.get("accepted_production_changes") != []:
        raise ValueError("P1.3 accepted an unproven production change")
    if decision.get("public_api_freeze") is not True:
        raise ValueError("P1.3 public API freeze was lost")
    if ABSOLUTE_PATH_RE.search(canonical_json(report)):
        raise ValueError("P1.3 report contains an absolute local path")


def derive_from_paths(
    *,
    repo_root: Path,
    public_tasks_path: Path,
    oracle_path: Path,
    atlas_path: Path,
) -> dict[str, Any]:
    return derive_ablation(
        public_tasks=load_json(public_tasks_path),
        oracle=load_json(oracle_path),
        atlas=load_json(atlas_path),
        source_identities={
            "public_tasks_git_blob_sha1": git_blob_sha(
                public_tasks_path, repo_root=repo_root
            ),
            "oracle_git_blob_sha1": git_blob_sha(
                oracle_path, repo_root=repo_root
            ),
            "first_divergence_atlas_git_blob_sha1": git_blob_sha(
                atlas_path, repo_root=repo_root
            ),
        },
    )
