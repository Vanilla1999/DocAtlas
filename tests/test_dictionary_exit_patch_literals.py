from dataclasses import asdict
from types import SimpleNamespace

import pytest

from docmancer.docs.application.patch_constraints_service import PatchConstraintsService
from docmancer.docs.application.patch_constraint_validation_service import PatchConstraintValidationService
from docmancer.docs.application.patch_review_service import PatchReviewService


def _service():
    return PatchConstraintsService(SimpleNamespace(
        read_project_metadata=lambda _: SimpleNamespace(docs_candidates=[], dependencies=[]),
    ))


@pytest.mark.parametrize("question", [
    "закрыть меню", "close menu", "hide drawer", "быстрая информация",
    "quick info", "scan doc", "сканирование документов",
])
def test_prose_does_not_generate_api_names(question, tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "menu.dart").write_text(
        "void closeMenu() {}\nvoid openInfo() {}\nvoid goToScanDocInit() {}\n",
    )
    service = _service()
    assert service._symbol_candidates(question, tmp_path, []) == []
    assert service._term_variants(question) == [question]


@pytest.mark.parametrize("symbol", ["closeMenu", "openInfo", "goToScanDocInit", "onTap", "read", "Widget"])
def test_explicit_literal_symbols_are_not_stopword_filtered(symbol, tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "symbols.dart").write_text(f"object.{symbol}();\n")
    candidates = _service()._symbol_candidates(f"Inspect `{symbol}`", tmp_path, [])
    assert [item["matched_symbol"] for item in candidates] == [symbol]
    assert candidates[0]["source"] == "src/symbols.dart"
    assert candidates[0]["line"] == 1


def test_literal_match_does_not_select_other_call_on_same_line(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "menu.dart").write_text("object.closeMenu(); other.unrelated();\n")
    service = _service()
    assert service._symbol_candidates("`closeMenu`", tmp_path, [])[0]["matched_symbol"] == "closeMenu"
    assert service._symbol_candidates("`close`", tmp_path, []) == []
    assert service._symbol_candidates("`closemenu`", tmp_path, []) == []
    assert service._symbol_from_line('print("closeMenu"); other.unrelated();', ["closeMenu"]) is None
    assert service._symbol_from_line("// object.closeMenu();", ["closeMenu"]) is None
    assert service._symbol_from_line("# object.closeMenu()", ["closeMenu"]) is None


def test_prose_does_not_establish_policy_or_owner(tmp_path):
    (tmp_path / "ARCHITECTURE.md").write_text(
        "MenuService owns policy. Providers must delegate to MenuService.\n"
        "Do not duplicate policy. Generated files must be regenerated with build_runner.\n",
    )
    packet = _service().get_patch_constraints("close menu", project_path=str(tmp_path), changed_files=["src/menu.dart"])
    assert not packet.source_of_truth_rules
    assert not any(item.type == "architecture" for item in packet.constraints)
    assert not any(item.source == "ARCHITECTURE.md" for item in packet.constraints)
    assert any("Policy coverage unresolved" in warning for warning in packet.warnings)
    assert packet.next_actions[0]["type"] == "manual_review_required"


def test_empty_literal_request_is_not_universal_source_match():
    service = _service()
    assert not service._source_relevant_to_task("README.md", "arbitrary text")
    service._question = "`closeMenu`"
    assert service._source_relevant_to_task("docs/menu.md", "closeMenu")
    assert not service._source_relevant_to_task("README.md", "unrelated policy")


def test_generated_and_lockfile_guards_survive(tmp_path):
    (tmp_path / "package-lock.json").write_text('{"packages":{"node_modules/example":{"version":"1.2.3"}}}')
    changed = ["src/model.g.dart", "package-lock.json"]
    packet = _service().get_patch_constraints("Inspect `example`", project_path=str(tmp_path), changed_files=changed, max_tokens=4000)
    assert packet.dependency_contracts[0].symbols == ["example", "1.2.3"]
    validation = PatchConstraintValidationService().validate_patch_against_constraints(packet, changed_files=changed, strict=True)
    assert validation.violated >= 2
    assert validation.unknown + validation.manual_review > 0


@pytest.mark.parametrize("budget", [80, 120, 500, 1200])
def test_budget_limited_packet_does_not_authorize_edits(budget, tmp_path):
    packet = _service().get_patch_constraints("close menu", project_path=str(tmp_path), max_tokens=budget, max_constraints=2)
    assert packet.token_estimate <= budget
    assert len(packet.constraints) <= 2
    assert packet.next_actions[0]["type"] == "manual_review_required"
    validation = asdict(PatchConstraintValidationService().validate_patch_against_constraints(packet, changed_files=["src/menu.dart"]))
    coverage = PatchReviewService._constraint_coverage_payload(asdict(packet), validation)
    decision = PatchReviewService._review_summary_advisory_decision_payload({}, {}, coverage)
    assert decision["requires_manual_review"]
    assert decision["mutation_authorized"] is False


def test_symbol_scan_cannot_escape_project_root(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside.dart"
    outside.write_text("void closeMenu() {}\n")
    (root / "src").mkdir()
    (root / "src" / "escape.dart").symlink_to(outside)
    assert _service()._symbol_candidates("`closeMenu`", root, ["../outside.dart"]) == []


def test_review_aliases_and_lowvalue_vocabulary_removed():
    tokens = PatchReviewService._task_symbol_tokens("быстрая информация close menu scan doc")
    assert "openinfo" not in tokens
    assert "closemenu" not in tokens
    assert "gotoscandocinit" not in tokens
    assert not PatchReviewService._is_low_value_symbol_candidate({"matched_symbol": "onTap", "confidence": "medium", "evidence": "object.onTap();"}, "unrelated")


def test_review_categories_use_types_not_policy_prose():
    item = {"type": "project_convention", "instruction": "provider owns policy generated lockfile test version docs", "source": "docs/policy.md"}
    assert PatchReviewService._coverage_categories_for_constraint(item, None) == []
    unknown = {"constraint_id": "x", "status": "unknown", "reason": "unrecognized prose"}
    triage = PatchReviewService._unknown_triage([unknown], [])
    assert triage[0]["code"] == "manual_review_required"
    assert triage[0]["requires_manual_review"]


def test_empty_review_is_not_approval():
    coverage = PatchReviewService._constraint_coverage_payload({}, {})
    decision = PatchReviewService._review_summary_advisory_decision_payload({}, {}, coverage)
    assert coverage["policy_coverage"] == "unresolved"
    assert coverage["mutation_authorized"] is False
    assert decision["requires_manual_review"]
    assert decision["show_warning_badge"]
    assert "safe_to_merge" in decision["claims_avoided"]
    forged = {"policy_coverage": "resolved", "total_constraints": 10, "covered_count": 10}
    assert PatchReviewService._review_summary_advisory_decision_payload({}, {}, forged)["requires_manual_review"]
