"""Split tests from test_patch_review_command.py; shared helpers remain in the façade module."""
from tests import _shared_test_patch_review_command as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})







def test_patch_review_writes_machine_readable_manifest(tmp_path: Path):
    repo = _repo(tmp_path)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _write(repo / "lib/presentation/menu_view.dart", "void buildMenu() {\n  menuNotifier.closeMenu();\n}\n")
    out = tmp_path / "review-manifest"

    result = CliRunner().invoke(
        cli,
        [
            "patch-review",
            "--project-path",
            str(repo),
            "--task",
            "Review menu navigation",
            "--summary-mode",
            "compact",
            "--summary-max-items",
            "2",
            "--output-dir",
            str(out),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    manifest = json.loads((out / "review_summary_manifest.json").read_text(encoding="utf-8"))
    manifest_artifacts = {item["filename"]: item for item in manifest["artifacts"]}
    assert "review_summary_manifest.json" in payload["artifacts"]
    assert payload["review_summary_manifest"] == manifest
    assert manifest["schema_version"] == PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_manifest.json"]
    assert manifest["summary_mode"] == "compact"
    assert manifest["product_role"] == "non_blocking_pr_review_assistant"
    assert [item["filename"] for item in manifest["artifacts"]] == payload["artifacts"]
    assert manifest_artifacts["review_summary.md"]["intended_consumers"] == ["human_reviewer"]
    assert manifest_artifacts["review_summary_quality.json"]["schema_version"] == payload["review_summary_quality"]["schema_version"]
    assert manifest_artifacts["review_summary_actions.json"]["schema_version"] == payload["review_summary_actions"]["schema_version"]
    assert manifest_artifacts["review_summary_pr_comment.json"]["schema_version"] == payload["review_summary_pr_comment"]["schema_version"]
    assert manifest_artifacts["review_summary_pr_comment.json"]["kind"] == "bot_pr_comment_payload"
    assert manifest_artifacts["review_summary_trace.json"]["schema_version"] == payload["review_summary_trace"]["schema_version"]
    assert manifest_artifacts["review_summary_trace.json"]["kind"] == "bot_traceability_metadata"
    assert manifest_artifacts["review_summary_bot_bundle.json"]["schema_version"] == payload["review_summary_bot_bundle"]["schema_version"]
    assert manifest_artifacts["review_summary_bot_bundle.json"]["kind"] == "bot_bundle"
    assert "without parsing markdown" in manifest_artifacts["review_summary_quality.json"]["safe_usage"]
    assert "without parsing markdown" in manifest_artifacts["review_summary_actions.json"]["safe_usage"]
    assert "correctness_proof" in manifest["claims_avoided"]


def test_patch_review_machine_readable_artifact_contracts(tmp_path: Path):
    repo = _repo(tmp_path)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _write(repo / "lib/presentation/menu_view.dart", "void buildMenu() {\n  menuNotifier.closeMenu();\n}\n")
    out = tmp_path / "review-contracts"

    result = CliRunner().invoke(
        cli,
        [
            "patch-review",
            "--project-path",
            str(repo),
            "--task",
            "Review menu navigation",
            "--summary-max-items",
            "2",
            "--output-dir",
            str(out),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    quality = payload["review_summary_quality"]
    actions = payload["review_summary_actions"]
    pr_comment = payload["review_summary_pr_comment"]
    trace = payload["review_summary_trace"]
    bot_bundle = payload["review_summary_bot_bundle"]
    coverage = payload["constraint_coverage"]
    manifest = payload["review_summary_manifest"]
    manifest_artifacts = {item["filename"]: item for item in manifest["artifacts"]}

    assert {
        "schema_version",
        "attachable",
        "summary_mode",
        "actionable_items_limit",
        "actionable_items_count",
        "actionable_items_total_count",
        "low_value_top_items_count",
        "unknown_bucket_count",
        "residual_memo_source_count",
        "satisfied_count",
        "violated_count",
        "unknown_count",
        "reasons",
        "signals",
        "unknown_triage",
        "unknown_buckets",
        "claims_avoided",
    } <= set(quality)
    assert quality["schema_version"] == PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_quality.json"]
    assert quality["schema_version"] == 2
    assert quality["attachable"] in {"yes", "maybe", "no"}
    for signal in quality["signals"]:
        assert {"code", "severity", "count", "message"} <= set(signal)
        assert signal["severity"] in {"info", "warning", "error"}
    for unknown_triage in quality["unknown_triage"]:
        assert {"code", "count", "requires_manual_review", "message", "examples"} <= set(unknown_triage)
        assert unknown_triage["code"] in {
            "missing_diff_evidence",
            "missing_test_evidence",
            "manual_review_required",
            "low_risk_unknown",
        }
        assert unknown_triage["requires_manual_review"] is True

    assert {
        "schema_version",
        "summary_mode",
        "actionable_items_limit",
        "actionable_items",
        "violations",
        "claims_avoided",
    } <= set(actions)
    assert actions["schema_version"] == PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_actions.json"]
    for item in actions["actionable_items"]:
        assert {
            "rank",
            "constraint_id",
            "instruction",
            "source",
            "type",
            "confidence",
            "evidence",
            "source_files",
            "symbols",
            "markdown",
            "evidence_markdown",
        } <= set(item)

    assert {"schema_version", "summary_mode", "product_role", "claims_avoided", "artifacts"} <= set(manifest)
    assert manifest["schema_version"] == PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_manifest.json"]
    for item in manifest["artifacts"]:
        assert {"filename", "kind", "schema_version", "intended_consumers", "safe_usage"} <= set(item)
    assert [item["filename"] for item in manifest["artifacts"]] == payload["artifacts"]
    assert PATCH_REVIEW_SCHEMA_VERSIONS == {
        "review_summary_manifest.json": manifest["schema_version"],
        "review_summary_quality.json": quality["schema_version"],
        "review_summary_actions.json": actions["schema_version"],
        "review_summary_pr_comment.json": pr_comment["schema_version"],
        "review_summary_trace.json": trace["schema_version"],
        "review_summary_bot_bundle.json": bot_bundle["schema_version"],
        "constraint_coverage.json": coverage["schema_version"],
    }
    assert {
        "schema_version",
        "summary_mode",
        "title",
        "attachable",
        "body",
        "body_markdown",
        "source_artifacts",
        "signals",
        "actionable_items",
        "violations",
        "claims_avoided",
    } <= set(pr_comment)
    assert pr_comment["schema_version"] == PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_pr_comment.json"]
    assert pr_comment["schema_version"] == 2
    assert pr_comment["body"] == pr_comment["body_markdown"]
    assert "DocAtlas patch review" in pr_comment["body_markdown"]
    assert "Non-blocking review context only" in pr_comment["body_markdown"]
    assert "review_summary_quality.json" in pr_comment["source_artifacts"]
    assert "review_summary_actions.json" in pr_comment["source_artifacts"]
    assert "constraint_coverage.json" in pr_comment["source_artifacts"]
    assert "Deterministic coverage:" in pr_comment["body_markdown"]
    assert {
        "schema_version",
        "summary_mode",
        "source_artifacts",
        "counts",
        "action_traces",
        "coverage_status_counts",
        "claims_avoided",
    } <= set(trace)
    assert trace["schema_version"] == PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_trace.json"]
    assert "constraints.json" in trace["source_artifacts"]
    assert "validation.json" in trace["source_artifacts"]
    assert "constraint_coverage.json" in trace["source_artifacts"]
    assert trace["coverage_status_counts"] == coverage["validation_status_counts"]
    assert trace["counts"]["action_traces"] == len(trace["action_traces"])
    for item in trace["action_traces"]:
        assert {
            "rank",
            "constraint_id",
            "source",
            "evidence",
            "validation_status",
            "validation_reason",
            "raw_constraint_artifact",
            "raw_validation_artifact",
        } <= set(item)
    assert {
        "schema_version",
        "summary_mode",
        "source_artifacts",
        "manifest",
        "quality",
        "actions",
        "coverage",
        "pr_comment",
        "trace",
        "advisory_decision",
        "claims_avoided",
    } <= set(bot_bundle)
    assert bot_bundle["schema_version"] == PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_bot_bundle.json"]
    assert bot_bundle["schema_version"] == 3
    assert manifest_artifacts["review_summary_quality.json"]["schema_version"] == quality["schema_version"]
    assert manifest_artifacts["review_summary_bot_bundle.json"]["schema_version"] == bot_bundle["schema_version"]
    assert manifest_artifacts["constraint_coverage.json"]["schema_version"] == coverage["schema_version"]
    assert manifest_artifacts["constraint_coverage.json"]["kind"] == "constraint_coverage_metadata"
    assert bot_bundle["quality"] == quality
    assert bot_bundle["actions"] == actions
    assert bot_bundle["coverage"] == coverage
    assert bot_bundle["pr_comment"] == pr_comment
    assert bot_bundle["trace"] == trace
    assert {
        "should_attach_comment",
        "show_warning_badge",
        "highlight_violations",
        "requires_manual_review",
        "reason_codes",
        "unknown_triage_codes",
        "unknown_triage_counts",
        "coverage_counts",
        "semantics",
        "claims_avoided",
    } <= set(bot_bundle["advisory_decision"])
    assert bot_bundle["advisory_decision"]["semantics"] == "advisory_non_blocking_only"
    assert bot_bundle["advisory_decision"]["coverage_counts"] == {
        "covered": coverage["covered_count"],
        "unknown_manual": coverage["unknown_manual_count"],
    }
    assert "safe_to_merge" not in bot_bundle["advisory_decision"]
    if bot_bundle["advisory_decision"]["should_attach_comment"]:
        assert bot_bundle["pr_comment"]["body"].strip()
