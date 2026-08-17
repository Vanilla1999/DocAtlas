"""Split tests from test_patch_review_command.py; shared helpers remain in the façade module."""
from tests import _shared_test_patch_review_command as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

def test_patch_review_unknown_triage_examples_carry_source_evidence_for_bot_routing():
    constraints = {
        "constraints": [
            {
                "id": "open-designer-input",
                "type": "architecture",
                "instruction": "Получить инфо от дизайнера по новому виду кнопки вызова меню.",
                "source": "docs/menu.md",
                "confidence": "medium",
                "evidence": "Открытый вопрос по макету остается нерешенным.",
                "symbols": [],
                "files": [],
            }
        ],
        "symbol_candidates": [],
        "excluded_source_reasons": [],
    }
    validation = {
        "satisfied": 0,
        "violated": 0,
        "unknown": 1,
        "results": [
            {
                "constraint_id": "open-designer-input",
                "status": "unknown",
                "reason": "No decisive changed-file or diff evidence was found for this constraint.",
                "files": [],
            }
        ],
        "warnings": [],
    }

    quality = PatchReviewService._review_summary_quality_payload(
        "Review TSDB menu redesign",
        ["lib/presentation/menu_view.dart"],
        constraints,
        validation,
    )

    triage = {item["code"]: item for item in quality["unknown_triage"]}
    assert set(triage) == {"manual_review_required"}
    assert triage["manual_review_required"]["requires_manual_review"] is True
    assert triage["manual_review_required"]["examples"][0] == {
        "constraint_id": "open-designer-input",
        "reason": "No decisive changed-file or diff evidence was found for this constraint.",
        "source": "docs/menu.md",
        "instruction": "Получить инфо от дизайнера по новому виду кнопки вызова меню.",
        "evidence": "Открытый вопрос по макету остается нерешенным.",
        "confidence": "medium",
    }
    assert quality["unknown_count"] == 1
    assert quality["attachable"] != "yes"


def test_patch_review_unknown_triage_keeps_generic_design_and_manual_text_granular():
    constraints = {
        "constraints": [
            {
                "id": "design-doc-gap",
                "type": "source_of_truth",
                "instruction": "Follow the design system spacing rule.",
                "source": "docs/design.md",
                "confidence": "medium",
                "evidence": "Design tokens define menu spacing.",
                "symbols": [],
                "files": [],
            },
            {
                "id": "manual-retry-test-gap",
                "type": "behavior",
                "instruction": "Keep the manual retry command covered by tests.",
                "source": "docs/manual-retry.md",
                "confidence": "medium",
                "evidence": "Manual retry should remain available after service failures.",
                "symbols": [],
                "files": [],
            },
            {
                "id": "task-derived-return-flow",
                "type": "project_convention",
                "instruction": "Confirm the closed request returns to the Active list after reopen.",
                "source": "changed_files",
                "confidence": "medium",
                "evidence": "Task-derived requirement from changed files; patch review must find diff evidence before treating it as resolved.",
                "symbols": [],
                "files": ["lib/help_request_details.dart"],
            },
        ],
        "symbol_candidates": [],
        "excluded_source_reasons": [],
    }
    validation = {
        "satisfied": 0,
        "violated": 0,
        "unknown": 3,
        "results": [
            {"constraint_id": "design-doc-gap", "status": "unknown", "reason": "no direct diff evidence found", "files": []},
            {"constraint_id": "manual-retry-test-gap", "status": "unknown", "reason": "missing test evidence", "files": []},
            {
                "constraint_id": "task-derived-return-flow",
                "status": "unknown",
                "reason": "constraint not deterministically checkable from changed files",
                "files": ["lib/help_request_details.dart"],
            },
        ],
        "warnings": [],
    }

    quality = PatchReviewService._review_summary_quality_payload(
        "Review generic design documentation and manual retry coverage",
        ["lib/menu.dart"],
        constraints,
        validation,
    )

    triage = {item["code"]: item for item in quality["unknown_triage"]}
    assert set(triage) == {"missing_diff_evidence", "missing_test_evidence"}
    assert triage["missing_diff_evidence"]["count"] == 2
    assert triage["missing_diff_evidence"]["examples"][0] == {
        "constraint_id": "design-doc-gap",
        "reason": "no direct diff evidence found",
        "source": "docs/design.md",
        "instruction": "Follow the design system spacing rule.",
        "evidence": "Design tokens define menu spacing.",
        "confidence": "medium",
    }
    assert triage["missing_diff_evidence"]["examples"][1] == {
        "constraint_id": "task-derived-return-flow",
        "reason": "constraint not deterministically checkable from changed files",
        "source": "changed_files",
        "instruction": "Confirm the closed request returns to the Active list after reopen.",
        "evidence": "Task-derived requirement from changed files; patch review must find diff evidence before treating it as resolved.",
        "confidence": "medium",
    }
    assert triage["missing_test_evidence"]["examples"][0] == {
        "constraint_id": "manual-retry-test-gap",
        "reason": "missing test evidence",
        "source": "docs/manual-retry.md",
        "instruction": "Keep the manual retry command covered by tests.",
        "evidence": "Manual retry should remain available after service failures.",
        "confidence": "medium",
    }
    assert all(item["requires_manual_review"] for item in quality["unknown_triage"])
    assert "manual_review_required" in {signal["code"] for signal in quality["signals"]}


def test_patch_review_bot_bundle_keeps_generic_unknowns_granular_for_consumers(tmp_path: Path):
    repo = _repo(tmp_path)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _write(repo / "lib/presentation/menu_view.dart", "void buildMenu() {\n  renderDesignSystemSpacing();\n  runManualRetryCommand();\n}\n")
    out = tmp_path / "review-generic-unknowns"

    class FakeDocsService:
        def get_patch_constraints(self, *args: Any, **kwargs: Any) -> PatchConstraintPacket:
            return PatchConstraintPacket(
                task="Review generic design docs and manual retry coverage",
                constraints=[
                    PatchConstraint(
                        id="design-doc-gap",
                        type="source_of_truth",
                        instruction="Follow the design system spacing rule.",
                        source="docs/design.md",
                        severity="warning",
                        confidence="medium",
                        evidence="Design tokens define menu spacing.",
                    ),
                    PatchConstraint(
                        id="manual-retry-test-gap",
                        type="behavior",
                        instruction="Keep the manual retry command covered by tests.",
                        source="docs/manual-retry.md",
                        severity="warning",
                        confidence="medium",
                        evidence="Manual retry should remain available after service failures.",
                    ),
                ],
                confidence="medium",
            )

        def validate_patch_against_constraints(self, *args: Any, **kwargs: Any) -> PatchConstraintValidationPacket:
            return PatchConstraintValidationPacket(
                task="Review generic design docs and manual retry coverage",
                project_path=str(repo),
                total_constraints=2,
                unknown=2,
                results=[
                    PatchConstraintValidationResult(
                        constraint_id="design-doc-gap",
                        status="unknown",
                        reason="no direct diff evidence found",
                        files=[],
                    ),
                    PatchConstraintValidationResult(
                        constraint_id="manual-retry-test-gap",
                        status="unknown",
                        reason="missing test evidence",
                        files=[],
                    ),
                ],
                confidence="low",
            )

    PatchReviewService(cast(Any, FakeDocsService())).run(
        project_path=str(repo),
        task="Review generic design docs and manual retry coverage",
        output_dir=str(out),
    )

    quality = json.loads((out / "review_summary_quality.json").read_text(encoding="utf-8"))
    triage = {item["code"]: item for item in quality["unknown_triage"]}
    assert set(triage) == {"missing_diff_evidence", "missing_test_evidence"}
    assert triage["missing_diff_evidence"]["examples"][0] == {
        "constraint_id": "design-doc-gap",
        "reason": "no direct diff evidence found",
        "source": "docs/design.md",
        "instruction": "Follow the design system spacing rule.",
        "evidence": "Design tokens define menu spacing.",
        "confidence": "medium",
    }
    assert triage["missing_test_evidence"]["examples"][0] == {
        "constraint_id": "manual-retry-test-gap",
        "reason": "missing test evidence",
        "source": "docs/manual-retry.md",
        "instruction": "Keep the manual retry command covered by tests.",
        "evidence": "Manual retry should remain available after service failures.",
        "confidence": "medium",
    }
    assert "manual_review_required" in {signal["code"] for signal in quality["signals"]}

    consumer_decision = _fake_pr_bot_consume_manifest(out / "review_summary_manifest.json")
    assert consumer_decision["requires_manual_review"] is True
    assert "manual_review_required" in consumer_decision["reason_codes"]
    assert consumer_decision["unknown_triage_codes"] == ["missing_diff_evidence", "missing_test_evidence"]
    assert consumer_decision["unknown_triage_counts"] == {
        "missing_diff_evidence": 1,
        "missing_test_evidence": 1,
    }
    assert "manual_review_required" not in consumer_decision["unknown_triage_codes"]
    assert consumer_decision["unknown_count"] == 2
    assert consumer_decision["violation_count"] == 0


def test_patch_review_bot_bundle_routes_open_design_unknowns_to_manual_review(tmp_path: Path):
    repo = _repo(tmp_path)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _write(repo / "lib/presentation/menu_view.dart", "void buildMenu() {\n  showMenuButton();\n}\n")
    out = tmp_path / "review-open-design-unknown"

    class FakeDocsService:
        def get_patch_constraints(self, *args: Any, **kwargs: Any) -> PatchConstraintPacket:
            return PatchConstraintPacket(
                task="Review TSDB menu redesign",
                constraints=[
                    PatchConstraint(
                        id="open-designer-input",
                        type="architecture",
                        instruction="Получить инфо от дизайнера по новому виду кнопки вызова меню.",
                        source="docs/menu.md",
                        severity="warning",
                        confidence="medium",
                        evidence="Открытый вопрос по макету остается нерешенным.",
                    )
                ],
                confidence="medium",
            )

        def validate_patch_against_constraints(self, *args: Any, **kwargs: Any) -> PatchConstraintValidationPacket:
            return PatchConstraintValidationPacket(
                task="Review TSDB menu redesign",
                project_path=str(repo),
                total_constraints=1,
                unknown=1,
                results=[
                    PatchConstraintValidationResult(
                        constraint_id="open-designer-input",
                        status="unknown",
                        reason="No decisive changed-file or diff evidence was found for this constraint.",
                        files=[],
                    )
                ],
                confidence="low",
            )

    PatchReviewService(cast(Any, FakeDocsService())).run(
        project_path=str(repo),
        task="Review TSDB menu redesign",
        output_dir=str(out),
    )

    quality = json.loads((out / "review_summary_quality.json").read_text(encoding="utf-8"))
    triage = {item["code"]: item for item in quality["unknown_triage"]}
    assert set(triage) == {"manual_review_required"}
    assert triage["manual_review_required"]["count"] == 1
    assert triage["manual_review_required"]["requires_manual_review"] is True

    consumer_decision = _fake_pr_bot_consume_manifest(out / "review_summary_manifest.json")
    assert consumer_decision["requires_manual_review"] is True
    assert "manual_review_required" in consumer_decision["reason_codes"]
    assert consumer_decision["unknown_triage_codes"] == ["manual_review_required"]
    assert consumer_decision["unknown_triage_counts"] == {"manual_review_required": 1}
    assert consumer_decision["unknown_triage_examples_by_code"] == {
        "manual_review_required": [
            {
                "constraint_id": "open-designer-input",
                "reason": "No decisive changed-file or diff evidence was found for this constraint.",
                "source": "docs/menu.md",
                "instruction": "Получить инфо от дизайнера по новому виду кнопки вызова меню.",
                "evidence": "Открытый вопрос по макету остается нерешенным.",
                "confidence": "medium",
            }
        ]
    }


def test_patch_review_surfaces_manual_review_validation_status(tmp_path: Path):
    repo = _repo(tmp_path)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _write(repo / "lib/presentation/menu_view.dart", "void buildMenu() {\n  showRedesignedMenu();\n}\n")
    out = tmp_path / "review-manual-status"

    class FakeDocsService:
        def get_patch_constraints(self, *args: Any, **kwargs: Any) -> PatchConstraintPacket:
            return PatchConstraintPacket(
                task="Review menu behavior",
                constraints=[
                    PatchConstraint(
                        id="menu-behavior",
                        type="behavior",
                        instruction="Keep menu behavior aligned with the designer-approved interaction.",
                        source="docs/menu.md",
                        severity="warning",
                        confidence="medium",
                        evidence="Designer approval is required for this interaction.",
                    )
                ],
                confidence="medium",
            )

        def validate_patch_against_constraints(self, *args: Any, **kwargs: Any) -> PatchConstraintValidationPacket:
            return PatchConstraintValidationPacket(
                task="Review menu behavior",
                project_path=str(repo),
                total_constraints=1,
                manual_review=1,
                results=[
                    PatchConstraintValidationResult(
                        constraint_id="menu-behavior",
                        status="manual_review",
                        reason="semantic constraint is not mechanically decidable from changed files or diff",
                        files=[],
                        remediation="Review designer approval before treating this as satisfied.",
                    )
                ],
                confidence="low",
            )

    PatchReviewService(cast(Any, FakeDocsService())).run(
        project_path=str(repo),
        task="Review menu behavior",
        output_dir=str(out),
    )

    quality = json.loads((out / "review_summary_quality.json").read_text(encoding="utf-8"))
    summary = (out / "review_summary.md").read_text(encoding="utf-8")
    consumer_decision = _fake_pr_bot_consume_manifest(out / "review_summary_manifest.json")

    assert quality["manual_review_count"] == 1
    assert quality["unknown_count"] == 0
    assert "manual_review: 1" in summary
    assert consumer_decision["requires_manual_review"] is True
    assert consumer_decision["unknown_triage_codes"] == ["manual_review_required"]


def test_patch_review_writes_machine_readable_action_items(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    _write(repo / "docs/architecture.md", "Generated files must not be edited by hand. Checkout buttons call launchCheckoutFlow before navigation.\n")
    _write(repo / "lib/payments/checkout_button.dart", "void renderCheckout() {}\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    _write(repo / "lib/payments/checkout_button.dart", "void renderCheckout() { launchCheckoutFlow(); }\n")
    out = tmp_path / "review-actions"

    result = CliRunner().invoke(
        cli,
        [
            "patch-review",
            "--project-path",
            str(repo),
            "--task",
            "Review checkout launch action",
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
    actions = json.loads((out / "review_summary_actions.json").read_text(encoding="utf-8"))
    actionable_markdown = _section((out / "review_summary.md").read_text(encoding="utf-8"), "Actionable PR checklist")
    assert "review_summary_actions.json" in payload["artifacts"]
    assert payload["review_summary_actions"] == actions
    assert actions["schema_version"] == PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_actions.json"]
    assert actions["actionable_items_limit"] == 2
    assert 0 < len(actions["actionable_items"]) <= 2
    assert any(item["instruction"] in actionable_markdown for item in actions["actionable_items"])
    assert all(item["constraint_id"] for item in actions["actionable_items"])
    assert [item["rank"] for item in actions["actionable_items"]] == list(range(1, len(actions["actionable_items"]) + 1))
    assert all(item["markdown"] in actionable_markdown for item in actions["actionable_items"])
    assert any(item["evidence"] and item["evidence"] in item["evidence_markdown"] for item in actions["actionable_items"])
    assert any("launchCheckoutFlow" in item["evidence"] for item in actions["actionable_items"] if item["evidence"])
    assert actions["claims_avoided"] == [
        "correctness_proof",
        "test_or_human_review_replacement",
        "broad_docatlas_superiority",
    ]


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
