"""Split tests from test_patch_review_command.py; shared helpers remain in the façade module."""
from tests import _shared_test_patch_review_command as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})







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









