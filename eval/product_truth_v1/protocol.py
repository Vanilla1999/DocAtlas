from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

PROTOCOL_NAME = "docatlas-product-truth-v1"
SCHEMA_VERSION = 1
CONDITION_IDS = (
    "A_repo_only",
    "B_repo_plus_docatlas",
    "C_repo_plus_external_docs",
    "D_code_context_plus_docatlas",
)
SCHEMA_FILES = (
    "task.schema.json",
    "run.schema.json",
    "result.schema.json",
    "ledger.schema.json",
)
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


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def protocol_sha256(protocol: Mapping[str, Any]) -> str:
    payload = copy.deepcopy(dict(protocol))
    payload.pop("protocol_sha256", None)
    return sha256_json(payload)


def validate_protocol(protocol: Mapping[str, Any]) -> None:
    if protocol.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("P2 protocol schema version mismatch")
    if protocol.get("protocol") != PROTOCOL_NAME:
        raise ValueError("P2 protocol identity mismatch")
    if protocol.get("phase") != "P2_PRODUCT_TRUTH":
        raise ValueError("P2 protocol phase mismatch")
    if protocol.get("status") != "preregistered":
        raise ValueError("P2 protocol must remain preregistered")
    expected_digest = protocol_sha256(protocol)
    if protocol.get("protocol_sha256") != expected_digest:
        raise ValueError("P2 protocol digest mismatch")

    conditions = protocol.get("conditions")
    if not isinstance(conditions, list):
        raise ValueError("P2 conditions must be a list")
    ids = tuple(str(row.get("id") or "") for row in conditions if isinstance(row, dict))
    if ids != CONDITION_IDS:
        raise ValueError("P2 condition identities/order changed")
    if len(conditions) != len(ids):
        raise ValueError("P2 contains a non-object condition")

    design = _mapping(protocol, "benchmark_design")
    repositories = _positive_int(design, "repositories")
    tasks = _mapping(design, "tasks_per_repository")
    task_min = _positive_int(tasks, "minimum")
    task_max = _positive_int(tasks, "maximum")
    condition_count = _positive_int(design, "conditions")
    repeats = _positive_int(design, "repeats")
    models = _positive_int(design, "minimum_models")
    minimum = repositories * task_min * condition_count * repeats * models
    maximum = repositories * task_max * condition_count * repeats * models
    if (repositories, task_min, task_max, condition_count, repeats, models) != (
        3,
        8,
        10,
        4,
        3,
        2,
    ):
        raise ValueError("P2 full benchmark cardinality drift")
    if design.get("minimum_scored_runs") != minimum or minimum != 576:
        raise ValueError("P2 minimum run count is not 576")
    if design.get("maximum_scored_runs") != maximum or maximum != 720:
        raise ValueError("P2 maximum run count is not 720")
    if design.get("paired_analysis") is not True:
        raise ValueError("P2 must retain paired task-level analysis")
    if design.get("bootstrap_unit") != "task_cluster":
        raise ValueError("P2 bootstrap unit must remain the task cluster")
    if float(design.get("confidence_level") or 0.0) != 0.95:
        raise ValueError("P2 confidence level must remain 0.95")

    randomization = _mapping(design, "randomization")
    if randomization.get("unit") != "task_model_repeat_block":
        raise ValueError("P2 randomization unit drift")
    if randomization.get("condition_order") != "deterministic_balanced_permutation":
        raise ValueError("P2 condition randomization drift")
    if not str(randomization.get("seed") or ""):
        raise ValueError("P2 randomization seed is missing")

    canary = _mapping(protocol, "canary")
    canary_total = (
        _positive_int(canary, "repositories")
        * _positive_int(canary, "tasks")
        * _positive_int(canary, "conditions")
        * _positive_int(canary, "repeats")
        * _positive_int(canary, "models")
    )
    if canary_total != 16 or canary.get("scored_runs") != 16:
        raise ValueError("P2 canary must contain exactly 16 scored runs")
    if canary.get("product_claim_allowed") is not False:
        raise ValueError("P2 canary cannot support a product claim")

    validity = _mapping(protocol, "task_validity")
    if validity.get("required_positive_controls") != ["gold_patch", "oracle_evidence"]:
        raise ValueError("P2 task validity requires gold and oracle controls")
    gold = _mapping(validity, "gold_patch")
    for key in (
        "must_apply",
        "public_tests_must_pass",
        "hidden_tests_must_pass",
        "semantic_assertions_must_pass",
        "allowed_surface_only",
    ):
        if gold.get(key) is not True:
            raise ValueError(f"P2 gold control lost {key}")
    if gold.get("clean_repetitions") != 2:
        raise ValueError("P2 gold control must repeat in two clean worktrees")
    oracle = _mapping(validity, "oracle_evidence")
    for key in ("same_model_snapshot", "same_budgets", "same_coding_tools"):
        if oracle.get(key) is not True:
            raise ValueError(f"P2 oracle control lost {key}")
    if oracle.get("failure_disposition") != "model_or_task_invalid":
        raise ValueError("P2 oracle failure disposition drift")

    budgets = _mapping(protocol, "budgets")
    if budgets.get("hard_enforcement_required") is not True:
        raise ValueError("P2 requires hard budget enforcement")
    if budgets.get("same_within_task_model_repeat_block") is not True:
        raise ValueError("P2 budgets must be paired within each block")
    required_budget_fields = budgets.get("required_fields")
    if not isinstance(required_budget_fields, list) or len(required_budget_fields) != 7:
        raise ValueError("P2 budget field set is incomplete")

    outcome = _mapping(protocol, "primary_outcome")
    if outcome.get("id") != "correct_patch":
        raise ValueError("P2 primary outcome must remain correct_patch")
    definition = outcome.get("definition")
    if not isinstance(definition, list) or len(definition) != 6:
        raise ValueError("P2 correct-patch gate is incomplete")

    rules = _mapping(protocol, "decision_rules")
    correctness = _mapping(rules, "correctness_path")
    if float(correctness.get("minimum_absolute_correct_patch_gain") or 0.0) != 0.10:
        raise ValueError("P2 correctness gain threshold drift")
    if float(correctness.get("maximum_median_total_token_ratio") or 0.0) != 1.5:
        raise ValueError("P2 token guardrail drift")
    if float(correctness.get("maximum_p95_latency_ratio") or 0.0) != 2.0:
        raise ValueError("P2 latency guardrail drift")
    if correctness.get("safety_critical_regression_allowed") is not False:
        raise ValueError("P2 cannot allow a safety-critical regression")

    safety = _mapping(rules, "safety_path")
    if float(safety.get("minimum_correct_patch_noninferiority") or 0.0) != -0.03:
        raise ValueError("P2 safety-path noninferiority threshold drift")
    if float(safety.get("minimum_relative_unsupported_or_wrong_version_reduction") or 0.0) != 0.25:
        raise ValueError("P2 safety improvement threshold drift")
    if safety.get("safety_critical_regression_allowed") is not False:
        raise ValueError("P2 safety path cannot allow a critical regression")

    boundary = _mapping(protocol, "claim_boundary")
    for key in (
        "product_truth_proven",
        "stable_claim_allowed",
        "canary_can_support_product_claim",
        "public_api_change_authorized",
        "production_runtime_changed",
    ):
        if boundary.get(key) is not False:
            raise ValueError(f"P2 preregistration overclaims {key}")
    if boundary.get("product_maturity") != "Beta":
        raise ValueError("P2 preregistration cannot promote maturity")

    schema_files = protocol.get("schema_files")
    if not isinstance(schema_files, dict) or tuple(sorted(schema_files)) != tuple(sorted(SCHEMA_FILES)):
        raise ValueError("P2 schema inventory drift")
    if ABSOLUTE_PATH_RE.search(canonical_json(protocol)):
        raise ValueError("P2 protocol contains an absolute local path")


def validate_repository(repo_root: Path) -> dict[str, Any]:
    root = repo_root / "eval" / "product_truth_v1"
    protocol_path = root / "protocol.lock.json"
    protocol = load_json(protocol_path)
    validate_protocol(protocol)

    validators: dict[str, Draft202012Validator] = {}
    for name in SCHEMA_FILES:
        path = root / "schemas" / name
        text = path.read_text(encoding="utf-8")
        expected = str(protocol["schema_files"][name])
        if sha256_text(text) != expected:
            raise ValueError(f"P2 schema digest mismatch: {name}")
        schema = json.loads(text)
        Draft202012Validator.check_schema(schema)
        validators[name] = Draft202012Validator(schema)

    samples = {
        "task.schema.json": load_json(root / "fixtures" / "sample-task.json"),
        "run.schema.json": load_json(root / "fixtures" / "sample-run.json"),
        "result.schema.json": load_json(root / "fixtures" / "sample-result.json"),
        "ledger.schema.json": load_json(root / "fixtures" / "sample-ledger.json"),
    }
    for name, sample in samples.items():
        errors = sorted(validators[name].iter_errors(sample), key=lambda row: list(row.path))
        if errors:
            raise ValueError(f"P2 sample rejected by {name}: {errors[0].message}")
        if sample.get("protocol_sha256") != protocol["protocol_sha256"]:
            raise ValueError(f"P2 sample protocol identity mismatch: {name}")

    validate_task_run_binding(samples["task.schema.json"], samples["run.schema.json"])
    validate_result_semantics(samples["result.schema.json"])
    validate_ledger(samples["ledger.schema.json"])
    return {
        "protocol_sha256": protocol["protocol_sha256"],
        "schema_count": len(validators),
        "sample_count": len(samples),
        "minimum_scored_runs": protocol["benchmark_design"]["minimum_scored_runs"],
        "maximum_scored_runs": protocol["benchmark_design"]["maximum_scored_runs"],
        "canary_scored_runs": protocol["canary"]["scored_runs"],
    }


def validate_task_run_binding(task: Mapping[str, Any], run: Mapping[str, Any]) -> None:
    for field in ("task_id", "repository_id", "repository_revision", "fixture_sha256"):
        if task.get(field) != run.get(field):
            raise ValueError(f"P2 task/run identity mismatch: {field}")
    if task.get("budgets") != run.get("budgets"):
        raise ValueError("P2 task/run budgets differ")
    observed = _mapping(run, "budget_enforcement")
    budgets = _mapping(run, "budgets")
    limits = {
        "observed_turns": "max_turns",
        "observed_requests": "max_requests",
        "observed_input_tokens": "max_input_tokens",
        "observed_output_tokens": "max_output_tokens",
        "observed_wall_seconds": "max_wall_seconds",
        "observed_edit_calls": "max_edit_calls",
        "observed_test_runs": "max_test_runs",
    }
    for observed_key, budget_key in limits.items():
        if float(observed.get(observed_key) or 0) > float(budgets[budget_key]):
            raise ValueError(f"P2 run exceeded hard budget: {budget_key}")


def validate_result_semantics(result: Mapping[str, Any]) -> None:
    gates = _mapping(result, "gates")
    correct = all(gates.get(key) is True for key in (
        "patch_applied",
        "public_tests_passed",
        "hidden_tests_passed",
        "semantic_assertions_passed",
        "allowed_surface_only",
        "forbidden_surface_clean",
    ))
    if result.get("correct_patch") is not correct:
        raise ValueError("P2 correct_patch does not equal the six-gate outcome")
    safety = _mapping(result, "safety")
    if result.get("correct_patch") is True and any(
        int(safety.get(key) or 0) > 0
        for key in (
            "forbidden_source_contamination",
            "unauthorized_lifecycle_actions",
            "forbidden_file_touches",
            "privacy_violations",
        )
    ):
        raise ValueError("P2 correct patch contains a critical safety violation")
    if result.get("correct_patch") is True and result.get("failure_class") != "none":
        raise ValueError("P2 correct patch cannot carry a failure class")


def validate_ledger(ledger: Mapping[str, Any]) -> None:
    events = ledger.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("P2 ledger must contain events")
    previous = "0" * 64
    for index, event in enumerate(events):
        if not isinstance(event, Mapping):
            raise ValueError("P2 ledger event must be an object")
        if event.get("index") != index:
            raise ValueError("P2 ledger index drift")
        if event.get("previous_event_sha256") != previous:
            raise ValueError("P2 ledger hash chain is broken")
        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            raise ValueError("P2 ledger payload must be an object")
        payload_sha = sha256_json(payload)
        if event.get("payload_sha256") != payload_sha:
            raise ValueError("P2 ledger payload digest mismatch")
        core = {
            "index": index,
            "kind": event.get("kind"),
            "previous_event_sha256": previous,
            "payload_sha256": payload_sha,
        }
        expected_event_sha = sha256_json(core)
        if event.get("event_sha256") != expected_event_sha:
            raise ValueError("P2 ledger event digest mismatch")
        previous = expected_event_sha


def _mapping(value: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    child = value.get(key)
    if not isinstance(child, Mapping):
        raise ValueError(f"P2 object field is missing: {key}")
    return child


def _positive_int(value: Mapping[str, Any], key: str) -> int:
    raw = value.get(key)
    if isinstance(raw, bool) or not isinstance(raw, int) or raw <= 0:
        raise ValueError(f"P2 positive integer field is invalid: {key}")
    return raw


__all__ = [
    "CONDITION_IDS",
    "PROTOCOL_NAME",
    "SCHEMA_FILES",
    "canonical_json",
    "load_json",
    "protocol_sha256",
    "sha256_json",
    "validate_ledger",
    "validate_protocol",
    "validate_repository",
    "validate_result_semantics",
    "validate_task_run_binding",
]
