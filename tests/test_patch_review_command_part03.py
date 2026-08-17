"""Split tests from test_patch_review_command.py; shared helpers remain in the façade module."""
from tests import _shared_test_patch_review_command as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

def test_patch_review_advisory_decision_is_non_blocking_and_escalates_violations_and_unknowns():
    base_quality = {
        "signals": [],
        "violated_count": 0,
        "unknown_count": 0,
        "actionable_items_total_count": 1,
    }
    base_actions = {"actionable_items": [{"constraint_id": "action"}], "violations": []}

    clean_action = PatchReviewService._review_summary_advisory_decision_payload(base_quality, base_actions)
    assert clean_action["should_attach_comment"] is True
    assert clean_action["show_warning_badge"] is False
    assert clean_action["highlight_violations"] is False
    assert clean_action["requires_manual_review"] is False
    assert clean_action["reason_codes"] == ["actionable_items_present"]
    assert clean_action["unknown_triage_codes"] == []
    assert clean_action["unknown_triage_counts"] == {}
    assert clean_action["coverage_counts"] == {"covered": 0, "unknown_manual": 0}

    violation = PatchReviewService._review_summary_advisory_decision_payload(
        {**base_quality, "violated_count": 1, "actionable_items_total_count": 0},
        {"actionable_items": [], "violations": [{"constraint_id": "policy"}]},
    )
    assert violation["should_attach_comment"] is True
    assert violation["show_warning_badge"] is True
    assert violation["highlight_violations"] is True
    assert violation["requires_manual_review"] is True
    assert violation["reason_codes"] == ["violations_present"]

    unknown = PatchReviewService._review_summary_advisory_decision_payload(
        {
            **base_quality,
            "unknown_count": 2,
            "actionable_items_total_count": 0,
            "unknown_triage": [
                {"code": "missing_test_evidence", "count": 1, "requires_manual_review": True},
                {"code": "low_risk_unknown", "count": 1, "requires_manual_review": True},
            ],
        },
        {"actionable_items": [], "violations": []},
    )
    assert unknown["should_attach_comment"] is True
    assert unknown["show_warning_badge"] is True
    assert unknown["highlight_violations"] is False
    assert unknown["requires_manual_review"] is True
    assert unknown["reason_codes"] == ["manual_review_required"]
    assert unknown["unknown_triage_codes"] == ["missing_test_evidence", "low_risk_unknown"]
    assert unknown["unknown_triage_counts"] == {"missing_test_evidence": 1, "low_risk_unknown": 1}

    coverage_unknown = PatchReviewService._review_summary_advisory_decision_payload(
        {**base_quality, "actionable_items_total_count": 0},
        {"actionable_items": [], "violations": []},
        {"covered_count": 1, "unknown_manual_count": 2},
    )
    assert coverage_unknown["should_attach_comment"] is True
    assert coverage_unknown["requires_manual_review"] is True
    assert coverage_unknown["reason_codes"] == ["manual_review_required"]
    assert coverage_unknown["coverage_counts"] == {"covered": 1, "unknown_manual": 2}

    violation_and_unknown = PatchReviewService._review_summary_advisory_decision_payload(
        {**base_quality, "violated_count": 1, "unknown_count": 1, "actionable_items_total_count": 0},
        {"actionable_items": [], "violations": [{"constraint_id": "policy"}]},
    )
    assert violation_and_unknown["highlight_violations"] is True
    assert violation_and_unknown["requires_manual_review"] is True
    assert violation_and_unknown["reason_codes"] == ["violations_present", "manual_review_required"]
    assert violation_and_unknown["unknown_triage_codes"] == []
    assert violation_and_unknown["unknown_triage_counts"] == {}
    assert violation_and_unknown["semantics"] == "advisory_non_blocking_only"
    assert violation_and_unknown["claims_avoided"] == [
        "safe_to_merge",
        "correctness_proof",
        "test_or_human_review_replacement",
    ]
    assert "safe_to_merge" not in violation_and_unknown


def test_patch_review_advisory_decision_exposes_unknown_triage_counts_for_bot_badges():
    decision = PatchReviewService._review_summary_advisory_decision_payload(
        {
            "signals": [],
            "violated_count": 0,
            "unknown_count": 3,
            "actionable_items_total_count": 0,
            "unknown_triage": [
                {"code": "manual_review_required", "count": 2, "requires_manual_review": True},
                {"code": "missing_test_evidence", "count": 1, "requires_manual_review": True},
            ],
        },
        {"actionable_items": [], "violations": []},
    )

    assert decision["should_attach_comment"] is True
    assert decision["show_warning_badge"] is True
    assert decision["requires_manual_review"] is True
    assert decision["reason_codes"] == ["manual_review_required"]
    assert decision["unknown_triage_codes"] == ["manual_review_required", "missing_test_evidence"]
    assert decision["unknown_triage_counts"] == {
        "manual_review_required": 2,
        "missing_test_evidence": 1,
    }
    assert decision["semantics"] == "advisory_non_blocking_only"
    assert "safe_to_merge" not in decision


def test_fake_pr_bot_consumer_reconstructs_missing_triage_counts_for_v3_bundle(tmp_path: Path):
    out = tmp_path / "review-v3-additive-field-fallback"
    out.mkdir()
    manifest = {
        "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_manifest.json"],
        "summary_mode": "standard",
        "product_role": "non_blocking_pr_review_assistant",
        "claims_avoided": [
            "correctness_proof",
            "test_or_human_review_replacement",
            "broad_docatlas_superiority",
        ],
        "artifacts": [
            {
                "filename": "review_summary_bot_bundle.json",
                "kind": "bot_bundle",
                "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_bot_bundle.json"],
                "intended_consumers": ["pr_bot", "automation"],
                "safe_usage": "Use as a single-file bot integration entrypoint with advisory non-blocking decisions.",
            }
        ],
    }
    bundle = {
        "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_bot_bundle.json"],
        "summary_mode": "standard",
        "manifest": manifest,
        "quality": {
            "unknown_count": 2,
            "unknown_triage": [
                {"code": "missing_diff_evidence", "count": 1, "requires_manual_review": True, "examples": []},
                {"code": "missing_test_evidence", "count": 1, "requires_manual_review": True, "examples": []},
            ],
        },
        "actions": {"violations": []},
        "pr_comment": _fake_pr_bot_pr_comment_payload(),
        "trace": _fake_pr_bot_trace_payload(),
        "advisory_decision": {
            "should_attach_comment": True,
            "show_warning_badge": True,
            "highlight_violations": False,
            "requires_manual_review": True,
            "reason_codes": ["manual_review_required"],
            "unknown_triage_codes": ["missing_diff_evidence", "missing_test_evidence"],
            "semantics": "advisory_non_blocking_only",
            "claims_avoided": [
                "safe_to_merge",
                "correctness_proof",
                "test_or_human_review_replacement",
            ],
        },
        "claims_avoided": [
            "correctness_proof",
            "test_or_human_review_replacement",
            "broad_docatlas_superiority",
        ],
    }
    _write(out / "review_summary_manifest.json", json.dumps(manifest))
    _write(out / "review_summary_bot_bundle.json", json.dumps(bundle))

    consumer_decision = _fake_pr_bot_discover_output_dir(out)

    assert consumer_decision["status"] == "completed_patch_review_run"
    assert consumer_decision["requires_manual_review"] is True
    assert consumer_decision["reason_codes"] == ["manual_review_required"]
    assert consumer_decision["unknown_triage_codes"] == ["missing_diff_evidence", "missing_test_evidence"]
    assert consumer_decision["unknown_triage_counts"] == {
        "missing_diff_evidence": 1,
        "missing_test_evidence": 1,
    }
    assert "safe_to_merge" not in consumer_decision


def test_fake_pr_bot_consumer_treats_hidden_unknown_manual_review_signal_as_invalid_bundle_contract(
    tmp_path: Path,
    monkeypatch,
):
    out = tmp_path / "review-v3-missing-triage-details"
    out.mkdir()
    manifest = {
        "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_manifest.json"],
        "summary_mode": "standard",
        "product_role": "non_blocking_pr_review_assistant",
        "claims_avoided": [
            "correctness_proof",
            "test_or_human_review_replacement",
            "broad_docatlas_superiority",
        ],
        "artifacts": [
            {
                "filename": "review_summary_bot_bundle.json",
                "kind": "bot_bundle",
                "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_bot_bundle.json"],
                "intended_consumers": ["pr_bot", "automation"],
                "safe_usage": "Use as a single-file bot integration entrypoint with advisory non-blocking decisions.",
            }
        ],
    }
    bundle = {
        "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_bot_bundle.json"],
        "summary_mode": "standard",
        "manifest": manifest,
        "quality": {
            "unknown_count": 1,
            "unknown_triage": [],
        },
        "actions": {"violations": []},
        "pr_comment": _fake_pr_bot_pr_comment_payload(),
        "trace": _fake_pr_bot_trace_payload(),
        "advisory_decision": {
            "should_attach_comment": False,
            "show_warning_badge": False,
            "highlight_violations": False,
            "requires_manual_review": False,
            "reason_codes": [],
            "unknown_triage_codes": [],
            "semantics": "advisory_non_blocking_only",
            "claims_avoided": [
                "safe_to_merge",
                "correctness_proof",
                "test_or_human_review_replacement",
            ],
        },
        "claims_avoided": [
            "correctness_proof",
            "test_or_human_review_replacement",
            "broad_docatlas_superiority",
        ],
    }
    _write(out / "review_summary_manifest.json", json.dumps(manifest))
    _write(out / "review_summary_bot_bundle.json", json.dumps(bundle))
    _write(out / "review_summary.md", "stale human summary that must not be parsed for automation")
    original_read_text = Path.read_text

    def fail_if_markdown_is_read(path: Path, *args: Any, **kwargs: Any) -> str:
        if path.name == "review_summary.md":
            raise AssertionError("fake PR bot must not parse markdown when unknown signals are hidden")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_if_markdown_is_read)

    consumer_decision = _fake_pr_bot_discover_output_dir(out)

    _assert_fake_pr_bot_manual_fallback(consumer_decision, "invalid_bot_bundle_contract")
    assert "review_summary_bot_bundle.json" in consumer_decision["ignored_sibling_artifacts"]
    assert "review_summary.md" in consumer_decision["ignored_sibling_artifacts"]


def test_fake_pr_bot_consumer_discovers_bundle_via_manifest_without_markdown_parsing(tmp_path: Path):
    repo = _repo(tmp_path)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _write(repo / "lib/generated/menu_state.g.dart", "// manual generated edit\n")
    out = tmp_path / "review-fake-consumer"

    result = CliRunner().invoke(
        cli,
        [
            "patch-review",
            "--project-path",
            str(repo),
            "--task",
            "Review generated artifact edit",
            "--output-dir",
            str(out),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    consumer_decision = _fake_pr_bot_consume_manifest(out / "review_summary_manifest.json")
    assert consumer_decision["attach_comment"] is True
    assert consumer_decision["show_warning_badge"] is True
    assert consumer_decision["highlight_violations"] is True
    assert consumer_decision["requires_manual_review"] is True
    assert "violations_present" in consumer_decision["reason_codes"]
    assert consumer_decision["violation_count"] > 0
    assert consumer_decision["violation_count"] + consumer_decision["unknown_count"] > 0


def test_patch_review_manifest_is_final_discovery_marker_when_bot_bundle_write_fails(tmp_path: Path, monkeypatch):
    repo = _repo(tmp_path)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _write(repo / "lib/generated/menu_state.g.dart", "// manual generated edit\n")
    out = tmp_path / "review-partial-write"
    original_write_json = PatchReviewService._write_json

    def fail_on_bot_bundle(path: Path, payload: Any) -> None:
        if path.name == "review_summary_bot_bundle.json":
            raise RuntimeError("simulated bot bundle write failure")
        original_write_json(path, payload)

    monkeypatch.setattr(PatchReviewService, "_write_json", staticmethod(fail_on_bot_bundle))

    with pytest.raises(RuntimeError, match="simulated bot bundle write failure"):
        PatchReviewService().run(
            project_path=str(repo),
            task="Review generated artifact edit",
            output_dir=str(out),
        )

    assert not (out / "review_summary_manifest.json").exists()
    assert not (out / "review_summary_bot_bundle.json").exists()
    assert (out / "review_summary_quality.json").exists()
    assert (out / "review_summary_actions.json").exists()


def test_patch_review_reused_output_dir_clears_stale_manifest_before_failed_run(tmp_path: Path, monkeypatch):
    repo = _repo(tmp_path)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _write(repo / "lib/generated/menu_state.g.dart", "// manual generated edit\n")
    out = tmp_path / "review-reused-output-dir"

    PatchReviewService().run(
        project_path=str(repo),
        task="Review generated artifact edit",
        output_dir=str(out),
    )
    manifest_path = out / "review_summary_manifest.json"
    assert manifest_path.exists()
    assert _fake_pr_bot_consume_manifest(manifest_path)["show_warning_badge"] is True
    original_write_json = PatchReviewService._write_json

    def fail_on_bot_bundle(path: Path, payload: Any) -> None:
        if path.name == "review_summary_bot_bundle.json":
            raise RuntimeError("simulated bot bundle write failure")
        original_write_json(path, payload)

    monkeypatch.setattr(PatchReviewService, "_write_json", staticmethod(fail_on_bot_bundle))

    with pytest.raises(RuntimeError, match="simulated bot bundle write failure"):
        PatchReviewService().run(
            project_path=str(repo),
            task="Review generated artifact edit",
            output_dir=str(out),
        )

    assert not manifest_path.exists()
    assert not list(out.glob(".review_summary_manifest.json.*.tmp"))
    assert (out / "review_summary_quality.json").exists()


def test_fake_pr_bot_consumer_treats_missing_manifest_as_no_completed_run(tmp_path: Path, monkeypatch):
    repo = _repo(tmp_path)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _write(repo / "lib/generated/menu_state.g.dart", "// manual generated edit\n")
    out = tmp_path / "review-missing-manifest-fallback"

    PatchReviewService().run(
        project_path=str(repo),
        task="Review generated artifact edit",
        output_dir=str(out),
    )
    completed_decision = _fake_pr_bot_discover_output_dir(out)
    assert completed_decision["status"] == "completed_patch_review_run"
    assert completed_decision["highlight_violations"] is True
    original_write_json = PatchReviewService._write_json

    def fail_on_bot_bundle(path: Path, payload: Any) -> None:
        if path.name == "review_summary_bot_bundle.json":
            raise RuntimeError("simulated bot bundle write failure")
        original_write_json(path, payload)

    monkeypatch.setattr(PatchReviewService, "_write_json", staticmethod(fail_on_bot_bundle))

    with pytest.raises(RuntimeError, match="simulated bot bundle write failure"):
        PatchReviewService().run(
            project_path=str(repo),
            task="Review generated artifact edit",
            output_dir=str(out),
        )

    assert not (out / "review_summary_manifest.json").exists()
    assert (out / "review_summary_bot_bundle.json").exists()
    assert (out / "review_summary.md").exists()
    original_read_text = Path.read_text

    def fail_if_direct_artifact_is_read(path: Path, *args: Any, **kwargs: Any) -> str:
        if path.name in {"review_summary_bot_bundle.json", "review_summary.md"}:
            raise AssertionError(f"fake PR bot must ignore sibling artifact without manifest: {path.name}")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_if_direct_artifact_is_read)

    consumer_decision = _fake_pr_bot_discover_output_dir(out)
    assert consumer_decision["status"] == "no_completed_patch_review_run"
    assert consumer_decision["attach_comment"] is False
    assert consumer_decision["show_warning_badge"] is True
    assert consumer_decision["highlight_violations"] is False
    assert consumer_decision["requires_manual_review"] is True
    assert consumer_decision["reason_codes"] == ["missing_manifest_completed_run_marker"]
    assert consumer_decision["semantics"] == "manual_fallback_not_pass"
    assert "safe_to_merge" not in consumer_decision
    assert "review_summary_bot_bundle.json" in consumer_decision["ignored_sibling_artifacts"]
    assert "review_summary.md" in consumer_decision["ignored_sibling_artifacts"]


def test_fake_pr_bot_consumer_treats_invalid_manifest_as_no_completed_run(tmp_path: Path, monkeypatch):
    out = tmp_path / "review-invalid-manifest-fallback"
    out.mkdir()
    _write(out / "review_summary_manifest.json", "{not valid json")
    _write(out / "review_summary_bot_bundle.json", json.dumps({"safe_to_merge": True}))
    _write(out / "review_summary.md", "stale human summary")
    original_read_text = Path.read_text

    def fail_if_sibling_artifact_is_read(path: Path, *args: Any, **kwargs: Any) -> str:
        if path.name in {"review_summary_bot_bundle.json", "review_summary.md"}:
            raise AssertionError(f"fake PR bot must ignore sibling artifact with invalid manifest: {path.name}")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_if_sibling_artifact_is_read)

    consumer_decision = _fake_pr_bot_discover_output_dir(out)
    assert consumer_decision["status"] == "no_completed_patch_review_run"
    assert consumer_decision["attach_comment"] is False
    assert consumer_decision["show_warning_badge"] is True
    assert consumer_decision["highlight_violations"] is False
    assert consumer_decision["requires_manual_review"] is True
    assert consumer_decision["reason_codes"] == ["invalid_manifest_completed_run_marker"]
    assert consumer_decision["semantics"] == "manual_fallback_not_pass"
    assert "safe_to_merge" not in consumer_decision
    assert "review_summary_bot_bundle.json" in consumer_decision["ignored_sibling_artifacts"]
    assert "review_summary.md" in consumer_decision["ignored_sibling_artifacts"]


def test_fake_pr_bot_consumer_treats_unsupported_manifest_schema_as_no_completed_run(tmp_path: Path, monkeypatch):
    out = tmp_path / "review-unsupported-manifest-fallback"
    out.mkdir()
    _write(
        out / "review_summary_manifest.json",
        json.dumps(
            {
                "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_manifest.json"] + 1,
                "product_role": "non_blocking_pr_review_assistant",
                "claims_avoided": ["safe_to_merge"],
                "artifacts": [
                    {
                        "filename": "review_summary_bot_bundle.json",
                        "kind": "bot_bundle",
                        "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_bot_bundle.json"],
                        "intended_consumers": ["pr_bot", "automation"],
                        "safe_usage": "single-file bot integration entrypoint; advisory non-blocking only",
                    }
                ],
            }
        ),
    )
    _write(out / "review_summary_bot_bundle.json", json.dumps({"safe_to_merge": True}))
    _write(out / "review_summary.md", "stale human summary")
    original_read_text = Path.read_text

    def fail_if_sibling_artifact_is_read(path: Path, *args: Any, **kwargs: Any) -> str:
        if path.name in {"review_summary_bot_bundle.json", "review_summary.md"}:
            raise AssertionError(f"fake PR bot must ignore sibling artifact with unsupported manifest: {path.name}")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_if_sibling_artifact_is_read)

    consumer_decision = _fake_pr_bot_discover_output_dir(out)
    assert consumer_decision["status"] == "no_completed_patch_review_run"
    assert consumer_decision["attach_comment"] is False
    assert consumer_decision["show_warning_badge"] is True
    assert consumer_decision["highlight_violations"] is False
    assert consumer_decision["requires_manual_review"] is True
    assert consumer_decision["reason_codes"] == ["unsupported_manifest_schema_version"]
    assert consumer_decision["semantics"] == "manual_fallback_not_pass"
    assert "safe_to_merge" not in consumer_decision
    assert "review_summary_bot_bundle.json" in consumer_decision["ignored_sibling_artifacts"]
    assert "review_summary.md" in consumer_decision["ignored_sibling_artifacts"]


def test_fake_pr_bot_consumer_treats_missing_manifest_referenced_bundle_as_manual_review(tmp_path: Path, monkeypatch):
    out = tmp_path / "review-missing-bundle-fallback"
    out.mkdir()
    _write(
        out / "review_summary_manifest.json",
        json.dumps(
            {
                "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_manifest.json"],
                "summary_mode": "standard",
                "product_role": "non_blocking_pr_review_assistant",
                "claims_avoided": ["correctness_proof", "test_or_human_review_replacement"],
                "artifacts": [
                    {
                        "filename": "review_summary_bot_bundle.json",
                        "kind": "bot_bundle",
                        "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_bot_bundle.json"],
                        "intended_consumers": ["pr_bot", "automation"],
                        "safe_usage": "single-file bot integration entrypoint; advisory non-blocking only",
                    }
                ],
            }
        ),
    )
    _write(out / "review_summary.md", "stale human summary that must not be parsed for automation")
    original_read_text = Path.read_text

    def fail_if_markdown_is_read(path: Path, *args: Any, **kwargs: Any) -> str:
        if path.name == "review_summary.md":
            raise AssertionError("fake PR bot must not parse markdown when manifest-referenced bundle is missing")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_if_markdown_is_read)

    consumer_decision = _fake_pr_bot_discover_output_dir(out)

    assert consumer_decision["status"] == "no_completed_patch_review_run"
    assert consumer_decision["attach_comment"] is False
    assert consumer_decision["show_warning_badge"] is True
    assert consumer_decision["highlight_violations"] is False
    assert consumer_decision["requires_manual_review"] is True
    assert consumer_decision["reason_codes"] == ["missing_bot_bundle_artifact"]
    assert consumer_decision["semantics"] == "manual_fallback_not_pass"
    assert "safe_to_merge" not in consumer_decision
    assert "review_summary.md" in consumer_decision["ignored_sibling_artifacts"]


def test_fake_pr_bot_consumer_treats_invalid_manifest_referenced_bundle_as_manual_review(tmp_path: Path, monkeypatch):
    out = tmp_path / "review-invalid-bundle-fallback"
    out.mkdir()
    _write(
        out / "review_summary_manifest.json",
        json.dumps(
            {
                "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_manifest.json"],
                "summary_mode": "standard",
                "product_role": "non_blocking_pr_review_assistant",
                "claims_avoided": ["correctness_proof", "test_or_human_review_replacement"],
                "artifacts": [
                    {
                        "filename": "review_summary_bot_bundle.json",
                        "kind": "bot_bundle",
                        "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_bot_bundle.json"],
                        "intended_consumers": ["pr_bot", "automation"],
                        "safe_usage": "single-file bot integration entrypoint; advisory non-blocking only",
                    }
                ],
            }
        ),
    )
    _write(out / "review_summary_bot_bundle.json", "{not valid json")
    _write(out / "review_summary.md", "stale human summary that must not be parsed for automation")
    original_read_text = Path.read_text

    def fail_if_markdown_is_read(path: Path, *args: Any, **kwargs: Any) -> str:
        if path.name == "review_summary.md":
            raise AssertionError("fake PR bot must not parse markdown when manifest-referenced bundle is invalid")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_if_markdown_is_read)

    consumer_decision = _fake_pr_bot_discover_output_dir(out)

    assert consumer_decision["status"] == "no_completed_patch_review_run"
    assert consumer_decision["attach_comment"] is False
    assert consumer_decision["show_warning_badge"] is True
    assert consumer_decision["highlight_violations"] is False
    assert consumer_decision["requires_manual_review"] is True
    assert consumer_decision["reason_codes"] == ["invalid_bot_bundle_artifact"]
    assert consumer_decision["semantics"] == "manual_fallback_not_pass"
    assert "safe_to_merge" not in consumer_decision
    assert "review_summary_bot_bundle.json" in consumer_decision["ignored_sibling_artifacts"]
    assert "review_summary.md" in consumer_decision["ignored_sibling_artifacts"]


@pytest.mark.parametrize(
    "manifest",
    [
        {
            "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_manifest.json"],
            "summary_mode": "standard",
            "product_role": "non_blocking_pr_review_assistant",
            "claims_avoided": ["correctness_proof", "test_or_human_review_replacement"],
        },
        {
            "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_manifest.json"],
            "summary_mode": "standard",
            "product_role": "non_blocking_pr_review_assistant",
            "claims_avoided": ["correctness_proof", "test_or_human_review_replacement"],
            "artifacts": {"filename": "review_summary_bot_bundle.json"},
        },
        {
            "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_manifest.json"],
            "summary_mode": "standard",
            "product_role": "non_blocking_pr_review_assistant",
            "claims_avoided": ["correctness_proof", "test_or_human_review_replacement"],
            "artifacts": [{"kind": "bot_bundle"}],
        },
    ],
)
def test_fake_pr_bot_consumer_treats_malformed_supported_manifest_contract_as_manual_review(
    tmp_path: Path,
    monkeypatch,
    manifest: dict[str, Any],
):
    out = tmp_path / "review-malformed-supported-manifest-fallback"
    out.mkdir()
    _write(out / "review_summary_manifest.json", json.dumps(manifest))
    _write(out / "review_summary_bot_bundle.json", json.dumps({"safe_to_merge": True}))
    _write(out / "review_summary.md", "stale human summary that must not be parsed for automation")
    original_read_text = Path.read_text

    def fail_if_sibling_artifact_is_read(path: Path, *args: Any, **kwargs: Any) -> str:
        if path.name in {"review_summary_bot_bundle.json", "review_summary.md"}:
            raise AssertionError(f"fake PR bot must ignore sibling artifact with malformed manifest contract: {path.name}")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_if_sibling_artifact_is_read)

    consumer_decision = _fake_pr_bot_discover_output_dir(out)

    _assert_fake_pr_bot_manual_fallback(consumer_decision, "invalid_manifest_completed_run_marker")
    assert "review_summary_bot_bundle.json" in consumer_decision["ignored_sibling_artifacts"]
    assert "review_summary.md" in consumer_decision["ignored_sibling_artifacts"]
