"""Split tests from test_patch_review_command.py; shared helpers remain in the façade module."""
from tests import _shared_test_patch_review_command as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

@pytest.mark.parametrize(
    "bundle_override",
    [
        {"quality": None},
        {"advisory_decision": None},
        {"advisory_decision": {"semantics": "advisory_non_blocking_only"}},
        {"pr_comment": None},
        {"pr_comment": []},
        {"trace": None},
        {"trace": []},
        {"actions": {}},
        {"actions": {"violations": {}}},
        {"quality": {"unknown_count": "1", "unknown_triage": []}},
        {"quality": {"unknown_count": -1, "unknown_triage": []}},
        {"quality": {"unknown_count": 0, "unknown_triage": [], "violated_count": "1"}},
        {"quality": {"unknown_count": 0, "unknown_triage": [], "violated_count": -1}},
        {"quality": {"unknown_count": 0, "unknown_triage": [{"code": "missing_diff_evidence", "count": "1"}]}},
        {"quality": {"unknown_count": 0, "unknown_triage": [{"code": "missing_test_evidence", "count": -1}]}},
        {
            "quality": {"unknown_count": 1, "unknown_triage": [{"code": "missing_diff_evidence", "count": 1}]},
            "advisory_decision": {
                "should_attach_comment": True,
                "show_warning_badge": True,
                "highlight_violations": False,
                "requires_manual_review": True,
                "reason_codes": ["manual_review_required"],
                "unknown_triage_codes": ["missing_diff_evidence"],
                "unknown_triage_counts": {"missing_diff_evidence": True},
                "semantics": "advisory_non_blocking_only",
                "claims_avoided": [
                    "safe_to_merge",
                    "correctness_proof",
                    "test_or_human_review_replacement",
                ],
            },
        },
        {
            "quality": {"unknown_count": 1, "unknown_triage": [{"code": "missing_diff_evidence", "count": 1}]},
            "advisory_decision": {
                "should_attach_comment": True,
                "show_warning_badge": True,
                "highlight_violations": False,
                "requires_manual_review": True,
                "reason_codes": ["manual_review_required"],
                "unknown_triage_codes": ["missing_diff_evidence"],
                "unknown_triage_counts": {"missing_diff_evidence": 1.0},
                "semantics": "advisory_non_blocking_only",
                "claims_avoided": [
                    "safe_to_merge",
                    "correctness_proof",
                    "test_or_human_review_replacement",
                ],
            },
        },
        {
            "quality": {"unknown_count": 1, "unknown_triage": [{"code": "missing_diff_evidence", "count": 1}]},
            "advisory_decision": {
                "should_attach_comment": True,
                "show_warning_badge": True,
                "highlight_violations": False,
                "requires_manual_review": True,
                "reason_codes": ["manual_review_required"],
                "unknown_triage_codes": ["missing_diff_evidence"],
                "unknown_triage_counts": {"missing_diff_evidence": "1"},
                "semantics": "advisory_non_blocking_only",
                "claims_avoided": [
                    "safe_to_merge",
                    "correctness_proof",
                    "test_or_human_review_replacement",
                ],
            },
        },
        {
            "quality": {"unknown_count": 1, "unknown_triage": [{"code": "missing_diff_evidence", "count": 1}]},
            "advisory_decision": {
                "should_attach_comment": True,
                "show_warning_badge": True,
                "highlight_violations": False,
                "requires_manual_review": True,
                "reason_codes": ["manual_review_required"],
                "unknown_triage_codes": ["missing_diff_evidence"],
                "unknown_triage_counts": {"missing_diff_evidence": -1},
                "semantics": "advisory_non_blocking_only",
                "claims_avoided": [
                    "safe_to_merge",
                    "correctness_proof",
                    "test_or_human_review_replacement",
                ],
            },
        },
    ],
)
def test_fake_pr_bot_consumer_treats_malformed_referenced_bundle_contract_as_manual_review(
    tmp_path: Path,
    monkeypatch,
    bundle_override: dict[str, Any],
):
    out = tmp_path / "review-malformed-bundle-contract-fallback"
    out.mkdir()
    manifest = {
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
    bundle = {
        "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_bot_bundle.json"],
        "summary_mode": "standard",
        "manifest": manifest,
        "quality": {"unknown_count": 0, "unknown_triage": []},
        "actions": {"violations": []},
        "pr_comment": _fake_pr_bot_pr_comment_payload(),
        "trace": _fake_pr_bot_trace_payload(),
        "advisory_decision": {
            "should_attach_comment": False,
            "show_warning_badge": False,
            "highlight_violations": False,
            "requires_manual_review": False,
            "reason_codes": ["no_attachable_review_signal"],
            "unknown_triage_codes": [],
            "unknown_triage_counts": {},
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
    for key, value in bundle_override.items():
        if value is None:
            bundle.pop(key)
        else:
            bundle[key] = value
    _write(out / "review_summary_manifest.json", json.dumps(manifest))
    _write(out / "review_summary_bot_bundle.json", json.dumps(bundle))
    _write(out / "review_summary.md", "stale human summary that must not be parsed for automation")
    original_read_text = Path.read_text

    def fail_if_markdown_is_read(path: Path, *args: Any, **kwargs: Any) -> str:
        if path.name == "review_summary.md":
            raise AssertionError("fake PR bot must not parse markdown when manifest-referenced bundle contract is malformed")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_if_markdown_is_read)

    consumer_decision = _fake_pr_bot_discover_output_dir(out)

    _assert_fake_pr_bot_manual_fallback(consumer_decision, "invalid_bot_bundle_contract")
    assert "review_summary_bot_bundle.json" in consumer_decision["ignored_sibling_artifacts"]
    assert "review_summary.md" in consumer_decision["ignored_sibling_artifacts"]


@pytest.mark.parametrize(
    "bundle_override",
    [
        {
            "quality": {
                "unknown_count": 0,
                "unknown_triage": [],
                "violated_count": 1,
                "signals": [{"code": "violations_present", "severity": "error", "count": 1}],
            },
            "actions": {"violations": []},
            "advisory_decision": {
                "should_attach_comment": False,
                "show_warning_badge": False,
                "highlight_violations": False,
                "requires_manual_review": False,
                "reason_codes": ["no_attachable_review_signal"],
                "unknown_triage_codes": [],
                "unknown_triage_counts": {},
                "semantics": "advisory_non_blocking_only",
                "claims_avoided": [
                    "safe_to_merge",
                    "correctness_proof",
                    "test_or_human_review_replacement",
                ],
            },
        },
        {
            "quality": {
                "unknown_count": 0,
                "unknown_triage": [],
                "violated_count": 1,
                "signals": [{"code": "violations_present", "severity": "error", "count": 1}],
            },
            "actions": {
                "violations": [
                    {"constraint_id": "generated-file-policy", "reason": "Generated files must not be edited."}
                ]
            },
            "advisory_decision": {
                "should_attach_comment": True,
                "show_warning_badge": False,
                "highlight_violations": False,
                "requires_manual_review": False,
                "reason_codes": [],
                "unknown_triage_codes": [],
                "unknown_triage_counts": {},
                "semantics": "advisory_non_blocking_only",
                "claims_avoided": [
                    "safe_to_merge",
                    "correctness_proof",
                    "test_or_human_review_replacement",
                ],
            },
        },
    ],
)
def test_fake_pr_bot_consumer_treats_inconsistent_violation_bundle_contract_as_manual_review(
    tmp_path: Path,
    monkeypatch,
    bundle_override: dict[str, Any],
):
    out = tmp_path / "review-inconsistent-violation-contract-fallback"
    out.mkdir()
    manifest = {
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
    bundle = {
        "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_bot_bundle.json"],
        "summary_mode": "standard",
        "manifest": manifest,
        "quality": {"unknown_count": 0, "unknown_triage": [], "violated_count": 0, "signals": []},
        "actions": {"violations": []},
        "pr_comment": _fake_pr_bot_pr_comment_payload(),
        "trace": _fake_pr_bot_trace_payload(),
        "advisory_decision": {
            "should_attach_comment": False,
            "show_warning_badge": False,
            "highlight_violations": False,
            "requires_manual_review": False,
            "reason_codes": ["no_attachable_review_signal"],
            "unknown_triage_codes": [],
            "unknown_triage_counts": {},
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
    bundle.update(bundle_override)
    _write(out / "review_summary_manifest.json", json.dumps(manifest))
    _write(out / "review_summary_bot_bundle.json", json.dumps(bundle))
    _write(out / "review_summary.md", "stale human summary that must not be parsed for automation")
    original_read_text = Path.read_text

    def fail_if_markdown_is_read(path: Path, *args: Any, **kwargs: Any) -> str:
        if path.name == "review_summary.md":
            raise AssertionError("fake PR bot must not parse markdown when violation signals are inconsistent")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_if_markdown_is_read)

    consumer_decision = _fake_pr_bot_discover_output_dir(out)

    _assert_fake_pr_bot_manual_fallback(consumer_decision, "invalid_bot_bundle_contract")
    assert "review_summary_bot_bundle.json" in consumer_decision["ignored_sibling_artifacts"]
    assert "review_summary.md" in consumer_decision["ignored_sibling_artifacts"]


def test_patch_review_summary_uses_generic_task_terms_without_project_hardcoding():
    summary = PatchReviewService._review_summary(
        "Review checkout launch action",
        ["lib/payments/checkout_button.dart"],
        {
            "constraints": [
                {
                    "id": "generic-task-local",
                    "type": "source_of_truth",
                    "instruction": "Use launchCheckoutFlow for the changed payment button action.",
                    "source": "docs/payments.md",
                    "confidence": "medium",
                    "evidence": "Checkout buttons call launchCheckoutFlow before navigation.",
                    "symbols": ["launchCheckoutFlow"],
                    "files": [],
                },
                {
                    "id": "broad-architecture",
                    "type": "architecture",
                    "instruction": "Rules that must not be violated live in broad architecture docs.",
                    "source": "docs/architecture.md",
                    "confidence": "high",
                    "evidence": "Rules that must not be violated.",
                    "symbols": [],
                    "files": [],
                },
            ],
            "symbol_candidates": [],
            "excluded_source_reasons": [],
        },
        {"satisfied": 0, "violated": 0, "unknown": 0, "results": [], "warnings": []},
    )

    actionable = _section(summary, "Actionable PR checklist")
    manual = _section(summary, "Manual review context")
    assert "launchCheckoutFlow" in actionable
    assert "broad architecture" not in actionable.lower()
    assert "broad architecture" in manual.lower()


def test_patch_review_summary_puts_violations_first_even_when_broad_context():
    summary = PatchReviewService._review_summary(
        "Review current patch",
        ["lib/widget.dart"],
        {
            "constraints": [
                {
                    "id": "broad-violated",
                    "type": "architecture",
                    "instruction": "Broad architecture rule was violated and needs reviewer action.",
                    "source": "docs/architecture.md",
                    "confidence": "medium",
                    "evidence": "Rules that must not be violated.",
                    "symbols": [],
                    "files": [],
                },
                {
                    "id": "generated-guardrail",
                    "type": "generated_file",
                    "instruction": "Generated files must not be edited by hand.",
                    "source": "docs/architecture.md",
                    "confidence": "high",
                    "evidence": "Generated files must not be edited by hand.",
                    "symbols": [],
                    "files": [],
                },
            ],
            "symbol_candidates": [],
            "excluded_source_reasons": [],
        },
        {
            "satisfied": 0,
            "violated": 1,
            "unknown": 0,
            "results": [
                {"constraint_id": "broad-violated", "status": "violated", "reason": "policy code changed in UI", "files": ["lib/widget.dart"]}
            ],
            "warnings": [],
        },
        summary_max_items=2,
    )

    actionable_items = [line for line in _section(summary, "Actionable PR checklist").splitlines() if line.startswith("- ")]
    assert actionable_items[0].startswith("- Broad architecture rule was violated")
    assert "Generated files must not be edited" in actionable_items[1]
    assert "broad-violated: policy code changed in UI" in _section(summary, "Violations")


def test_patch_review_actions_demote_generic_symbols_below_task_missing_evidence():
    constraints = {
        "constraints": [
            {
                "id": "generic-title-symbol",
                "type": "symbol",
                "instruction": "Review the changed title handler for the task button.",
                "source": "lib/src/ui/help_request_details_screen/states/help_request_details_success_state.dart",
                "confidence": "high",
                "evidence": "Вернуть в работу -> title",
                "symbols": ["title"],
                "files": ["lib/src/ui/help_request_details_screen/states/help_request_details_success_state.dart"],
            },
            {
                "id": "generic-package-symbol-pair",
                "type": "source_of_truth",
                "instruction": "Task term `HELP` matches existing project symbol `package`; prefer reusing that source-attributed path before adding a new implementation.",
                "source": "lib/src/domain/services/help_requests_service.dart",
                "confidence": "high",
                "evidence": "import 'package:help_chat/src/data/models/help_add_new_comment_request_dto.dart';",
                "symbols": ["HELP", "package"],
                "files": ["lib/src/domain/services/help_requests_service.dart"],
            },
            {
                "id": "return-active-service-call",
                "type": "source_of_truth",
                "instruction": "Button 'Вернуть в работу' must send the request status 'Активная' to the service.",
                "source": "docs/help-chat-reopen-task.md",
                "confidence": "high",
                "evidence": "При нажатии приложение отправляет на сервис статус заявки 'Активная'.",
                "symbols": ["returnToActive"],
                "files": [],
            },
            {
                "id": "success-attachment-panel",
                "type": "source_of_truth",
                "instruction": "On successful return, hide buttons and show the attachments/comment/send panel.",
                "source": "docs/help-chat-reopen-task.md",
                "confidence": "high",
                "evidence": "Если успешно: кнопки скрываются; открывается панель с вложениями, вводом текста и кнопкой Отправить.",
                "symbols": ["attachmentPanel"],
                "files": [],
            },
        ],
        "symbol_candidates": [
            {
                "term": "Вернуть в работу",
                "matched_symbol": "title",
                "source": "lib/src/ui/help_request_details_screen/states/help_request_details_success_state.dart",
                "reason": "task text matched a generic UI title symbol",
                "evidence": "title: 'Вернуть в работу'",
            }
        ],
        "excluded_source_reasons": [],
    }
    validation = {
        "satisfied": 0,
        "violated": 0,
        "unknown": 3,
        "results": [
            {
                "constraint_id": "generic-title-symbol",
                "status": "unknown",
                "reason": "generic symbol match needs diff evidence",
                "files": ["lib/src/ui/help_request_details_screen/states/help_request_details_success_state.dart"],
            },
            {
                "constraint_id": "generic-package-symbol-pair",
                "status": "satisfied",
                "reason": "source-of-truth layer file changed",
                "files": ["lib/src/domain/services/help_requests_service.dart"],
            },
            {
                "constraint_id": "return-active-service-call",
                "status": "unknown",
                "reason": "missing diff evidence for required service status transition",
                "files": [],
            },
            {
                "constraint_id": "success-attachment-panel",
                "status": "unknown",
                "reason": "missing diff evidence for success UI transition",
                "files": [],
            },
        ],
        "warnings": [],
    }
    task = "Reopen HELP request: 'Вернуть в работу' must send status Активная, hide buttons, and show the attachment panel."

    actions = PatchReviewService._review_summary_actions_payload(
        task,
        ["lib/src/ui/help_request_details_screen/states/help_request_details_success_state.dart"],
        constraints,
        validation,
        summary_max_items=3,
    )
    summary = PatchReviewService._review_summary(
        task,
        ["lib/src/ui/help_request_details_screen/states/help_request_details_success_state.dart"],
        constraints,
        validation,
        summary_max_items=3,
    )

    action_ids = [item["constraint_id"] for item in actions["actionable_items"]]
    assert action_ids == ["return-active-service-call", "success-attachment-panel"]
    assert "generic-title-symbol" not in action_ids
    assert "generic-package-symbol-pair" not in action_ids
    assert actions["actionable_items"][0]["validation_status"] == "unknown"
    assert "title" not in _section(summary, "Actionable PR checklist")
    assert "package" not in _section(summary, "Actionable PR checklist")
    assert "symbol `title`" in _section(summary, "Low-confidence / noisy signals")


def test_patch_review_quality_attachable_uses_total_actionable_not_display_cap():
    constraints = {
        "constraints": [
            {
                "id": f"actionable-{index}",
                "type": "source_of_truth",
                "instruction": f"Apply checkout rule {index}.",
                "source": "docs/checkout.md",
                "confidence": "high",
                "evidence": f"checkout rule {index}",
                "symbols": [f"checkoutRule{index}"],
                "files": [],
            }
            for index in range(3)
        ],
        "symbol_candidates": [],
        "excluded_source_reasons": [],
    }
    validation = {"satisfied": 0, "violated": 0, "unknown": 0, "results": [], "warnings": []}

    quality = PatchReviewService._review_summary_quality_payload(
        "Review checkout rules",
        ["docs/checkout.md"],
        constraints,
        validation,
        summary_max_items=1,
    )

    assert quality["actionable_items_count"] == 1
    assert quality["actionable_items_total_count"] == 3
    assert quality["attachable"] == "yes"


def test_patch_review_pr_comment_lists_violations_separately_from_capped_actions():
    actions = {
        "actionable_items": [],
        "violations": [
            {"constraint_id": "policy-violation", "reason": "Provider policy moved into UI", "files": ["lib/widget.dart"]}
        ],
    }
    quality = {
        "attachable": "maybe",
        "signals": [{"code": "violations_present", "severity": "error", "count": 1}],
        "claims_avoided": ["correctness_proof"],
    }

    comment = PatchReviewService._review_summary_pr_comment_payload(
        actions,
        quality,
        {"covered_count": 0, "unknown_manual_count": 0},
        summary_mode="compact",
    )

    assert comment["violations"] == actions["violations"]
    assert comment["body"] == comment["body_markdown"]
    assert comment["body"].strip()
    assert "Violations:" in comment["body_markdown"]
    assert "policy-violation" in comment["body_markdown"]
    assert "Provider policy moved into UI" in comment["body_markdown"]


def test_patch_review_render_ready_markdown_escapes_mentions_backticks_and_truncates():
    item = PatchReviewService._actionable_item_payload(
        {
            "id": "unsafe-markdown",
            "instruction": "Ping @team and use `danger`" + "x" * 2500,
            "source": "docs/`unsafe`.md",
            "type": "source_of_truth",
            "confidence": "high",
            "evidence": "Evidence mentions @team and `danger`",
            "symbols": [],
            "files": [],
        },
        None,
        rank=1,
    )

    assert "@team" not in item["markdown"]
    assert "@\u200bteam" in item["markdown"]
    assert "\\`danger\\`" in item["markdown"]
    assert "[truncated]" in item["markdown"]
    assert "@team" not in item["evidence_markdown"]
    assert "\\`danger\\`" in item["evidence_markdown"]

    long_body = PatchReviewService._truncate_pr_comment("x" * 70_000)
    assert len(long_body) <= 60_000
    assert "Comment truncated for provider limits" in long_body
