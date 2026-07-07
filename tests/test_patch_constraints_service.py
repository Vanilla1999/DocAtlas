from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from docmancer.docs.application.patch_constraints_service import PatchConstraintsService
from docmancer.docs.service import LibraryDocsService


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _workspace(tmp_path: Path, *, docs: str | None = None) -> Path:
    root = tmp_path / "repo"
    (root / "docs/adr").mkdir(parents=True)
    _write(
        root / "docs/architecture.md",
        docs
        or """
PermissionService owns permission policy and is the source of truth for permission decisions.
Provider delegates to PermissionService and must not duplicate policy maps.
Generated artifacts such as *.g.dart, *.freezed.dart, *.pb.go and *.pb.dart must not be edited by hand; update the source model and run build_runner/regenerate.
The application layer must not bypass the domain layer.
""",
    )
    _write(root / "docs/adr/0001-permissions.md", "ADR: Permission policy belongs in PermissionService; providers should not implement policy.\n")
    _write(root / "lib/modules/permission/domain/services/permission_service.dart", "class PermissionService {}\n")
    _write(root / "lib/modules/permission/presentation/providers/permission_provider.dart", "// provider\n")
    _write(root / "pubspec.yaml", "dependencies:\n  permission_handler: ^11.4.0\n")
    _write(root / "pubspec.lock", 'packages:\n  permission_handler:\n    dependency: "direct main"\n    source: hosted\n    version: "11.4.0"\n')
    return root


def _packet(root: Path, **kwargs):
    service = PatchConstraintsService(LibraryDocsService())
    return service.get_patch_constraints(
        question=kwargs.pop("question", "Update permission preflight without touching generated files or providers."),
        project_path=str(root),
        **kwargs,
    )


def _instructions(packet) -> str:
    return "\n".join(c.instruction for c in packet.constraints).lower()


def test_extracts_architecture_must_and_must_not_constraints(tmp_path: Path):
    packet = _packet(_workspace(tmp_path))
    text = _instructions(packet)
    assert "application layer" in text or "domain layer" in text
    assert any(c.severity == "must" and c.source.endswith("architecture.md") for c in packet.constraints)


def test_extracts_adr_constraints(tmp_path: Path):
    packet = _packet(_workspace(tmp_path))
    assert any("PermissionService" in c.instruction and "adr/0001" in c.source for c in packet.constraints)


def test_extracts_generated_file_constraint_from_docs(tmp_path: Path):
    packet = _packet(_workspace(tmp_path))
    assert any(c.type == "generated_file" and "generated" in c.instruction.lower() for c in packet.constraints)


def test_extracts_freezed_and_g_dart_forbidden_edits(tmp_path: Path):
    packet = _packet(_workspace(tmp_path))
    generated = next(c for c in packet.constraints if c.type == "generated_file")
    assert "*.g.dart" in generated.files
    assert "*.freezed.dart" in generated.files
    assert generated.severity == "must"


def test_extracts_source_of_truth_service_layer_constraint(tmp_path: Path):
    packet = _packet(_workspace(tmp_path))
    assert any(c.type == "source_of_truth" and "PermissionService" in c.instruction for c in packet.constraints)


def test_extracts_provider_must_delegate_constraint(tmp_path: Path):
    packet = _packet(_workspace(tmp_path))
    assert any(c.type == "architecture" and "Provider" in c.instruction and "PermissionService" in c.instruction for c in packet.constraints)


def test_extracts_no_duplicate_policy_constraint(tmp_path: Path):
    packet = _packet(_workspace(tmp_path))
    assert any(c.type == "forbidden_edit" and "duplicate policy" in c.instruction.lower() for c in packet.constraints)


def test_extracts_pinned_dependency_from_pubspec_lock(tmp_path: Path):
    packet = _packet(_workspace(tmp_path), question="Use permission_handler dependency")
    assert any(c.type == "dependency_version" and "permission_handler" in c.instruction and "11.4.0" in c.instruction for c in packet.constraints)


def test_extracts_pinned_dependency_from_pyproject_or_requirements(tmp_path: Path):
    root = _workspace(tmp_path)
    _write(root / "requirements.txt", "fastapi==0.115.6\n")
    _write(root / "pyproject.toml", '[project]\ndependencies = ["pydantic==2.10.4"]\n')
    packet = _packet(root, question="Update FastAPI dependency integration")
    assert any("fastapi" in c.instruction.lower() and "0.115.6" in c.instruction for c in packet.constraints)
    assert any("pydantic" in c.instruction.lower() and "2.10.4" in c.instruction for c in packet.constraints)


def test_extracts_pinned_dependency_from_package_lock(tmp_path: Path):
    root = _workspace(tmp_path)
    _write(root / "package-lock.json", '{"packages":{"node_modules/react":{"version":"18.2.0"}}}')
    packet = _packet(root, question="Update React dependency usage")
    assert any("react" in c.instruction.lower() and "18.2.0" in c.instruction for c in packet.constraints)


def test_extracts_lockfile_guardrail(tmp_path: Path):
    packet = _packet(_workspace(tmp_path))
    assert any(c.type == "forbidden_edit" and "lockfile" in c.instruction.lower() for c in packet.constraints)


def test_changed_files_raise_generated_file_constraint(tmp_path: Path):
    packet = _packet(_workspace(tmp_path), changed_files=["lib/foo/user.freezed.dart", "lib/foo/user.g.dart"])
    assert any(c.type == "generated_file" and c.source == "changed_files" for c in packet.constraints)


def test_changed_files_raise_provider_layer_constraint(tmp_path: Path):
    packet = _packet(_workspace(tmp_path), changed_files=["lib/modules/permission/presentation/providers/permission_provider.dart"])
    assert any(c.type == "architecture" and c.files for c in packet.constraints[:4])


def test_changed_files_raise_relevant_constraints(tmp_path: Path):
    packet = _packet(
        _workspace(tmp_path),
        changed_files=["lib/modules/permission/presentation/providers/permission_provider.dart"],
    )
    provider_positions = [idx for idx, c in enumerate(packet.constraints) if "provider" in c.instruction.lower()]
    assert provider_positions and provider_positions[0] < 4


def test_changed_files_do_not_create_unsupported_high_confidence_constraint(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    packet = _packet(root, changed_files=["lib/modules/permission/presentation/providers/permission_provider.dart"])
    assert not any(c.confidence == "high" and "PermissionService" in c.instruction for c in packet.constraints)


def test_question_keywords_raise_relevant_dependency_constraint(tmp_path: Path):
    root = _workspace(tmp_path)
    _write(root / "package-lock.json", '{"packages":{"node_modules/react":{"version":"18.2.0"}}}')
    packet = _packet(root, question="Fix React dependency behavior")
    dep_positions = [idx for idx, c in enumerate(packet.constraints) if c.type == "dependency_version" and "react" in c.instruction.lower()]
    assert dep_positions and dep_positions[0] < 8


def test_suggested_checks_include_generated_and_lockfile_checks(tmp_path: Path):
    packet = _packet(_workspace(tmp_path), changed_files=["lib/foo/user.g.dart", "pubspec.lock"])
    checks = "\n".join(packet.suggested_checks).lower()
    import json, dataclasses
    print(f"\nDEBUG: suggested_checks={packet.suggested_checks!r}")
    print(f"DEBUG: checks={checks!r}")
    print(f"DEBUG: constraints count={len(packet.constraints)}")
    for c in packet.constraints:
        print(f"  [{c.type}] {c.id}: {c.instruction[:60]!r}")
    print(f"DEBUG: _dropped_non_actionable_constraints types: {packet.warnings}")
    print(f"DEBUG: token_budget: {packet.token_budget}")
    assert "generator" in checks or "generated" in checks
    assert "lockfile" in checks


def test_budget_keeps_must_high_confidence_constraints(tmp_path: Path):
    packet = _packet(_workspace(tmp_path), max_constraints=3, max_tokens=220)
    assert len(packet.constraints) <= 3
    assert all(c.severity == "must" for c in packet.constraints)
    assert all(c.confidence == "high" for c in packet.constraints)


def test_budget_emits_truncation_warning(tmp_path: Path):
    packet = _packet(_workspace(tmp_path), max_constraints=1, max_tokens=100)
    assert any("constraints truncated by budget" in warning for warning in packet.warnings)


def test_budget_drops_low_priority_constraints_first(tmp_path: Path):
    packet = _packet(_workspace(tmp_path), changed_files=["lib/foo/user.g.dart"], max_constraints=2, max_tokens=220)
    assert packet.constraints
    assert any(c.type == "generated_file" and c.source == "changed_files" for c in packet.constraints)
    assert all(c.confidence in {"high", "medium"} for c in packet.constraints)


def test_high_confidence_constraints_have_source_and_evidence(tmp_path: Path):
    packet = _packet(_workspace(tmp_path))
    high = [c for c in packet.constraints if c.confidence == "high"]
    assert high
    assert all(c.source and c.evidence for c in high)


def test_patch_contract_schema_v2_exposes_contract_metadata(tmp_path: Path):
    root = _workspace(tmp_path)
    packet = _packet(root, max_constraints=20, max_tokens=4000)

    assert packet.schema_version == "patch-contract-2.0"
    assert packet.contract_kind == "patch_contract"
    assert packet.contract_id and packet.contract_id.startswith("patch-contract-")
    assert packet.project_path == str(root.resolve())
    assert packet.generated_at
    assert packet.index_state["visible_source_count"] >= 1
    assert packet.token_budget["max_tokens"] == 4000
    assert packet.token_budget["token_estimate"] == packet.token_estimate
    assert any(action["type"] == "validate_patch_against_constraints" for action in packet.next_actions)


def test_patch_contract_schema_v2_constraint_items_keep_evidence_refs(tmp_path: Path):
    packet = _packet(_workspace(tmp_path), max_constraints=20, max_tokens=4000)
    high = next(c for c in packet.constraints if c.confidence == "high")

    assert high.source_refs == [{"path": high.source, "kind": "source"}]
    assert high.evidence_snippets
    assert high.evidence_snippets[0]["path"] == high.source
    assert high.evidence_snippets[0]["text"] == high.evidence


def test_does_not_invent_dependency_version_without_manifest(tmp_path: Path):
    root = tmp_path / "repo"
    _write(root / "docs/architecture.md", "PermissionService owns permission policy.\n")
    packet = _packet(root, question="Update nonexistent dependency frobnicator")
    assert not any("frobnicator" in c.instruction.lower() for c in packet.constraints)


def test_does_not_invent_service_owner_without_docs(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    packet = _packet(root, question="Move policy to PermissionService")
    assert not any(c.confidence == "high" and "PermissionService" in c.instruction for c in packet.constraints)


def test_path_heuristic_generated_inference_is_medium_not_high(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    packet = _packet(root, changed_files=["lib/foo/user.g.dart"])
    inferred = [c for c in packet.constraints if c.source == "changed_files" and c.type == "generated_file"]
    assert inferred and all(c.confidence == "medium" for c in inferred)
    assert all(c.severity == "should" for c in inferred)


def test_does_not_emit_hidden_or_benchmark_oracle_sources(tmp_path: Path):
    root = _workspace(tmp_path)
    _write(root / "eval/task_level/hidden_tests/oracles/README.md", "Hidden oracle: SecretService owns everything.\n")
    packet = _packet(root)
    payload = str({
        "constraints": asdict(packet)["constraints"],
        "sources": packet.sources,
        "ignored_generated_artifact_sources": packet.ignored_generated_artifact_sources,
        "excluded_source_reasons": packet.excluded_source_reasons,
    }).lower()
    assert "secretservice" not in payload
    assert "hidden_tests" not in payload
    assert "oracle" not in payload


def test_example_source_of_truth_statement_is_not_must_high_even_if_symbol_exists(tmp_path: Path):
    root = tmp_path / "repo"
    _write(
        root / "docs/capabilities.md",
        'The compiler can extract owner/source-of-truth instructions from statements like "PermissionService owns permission policy."\n',
    )
    _write(root / "lib/permission_service.py", "class PermissionService:\n    pass\n")

    packet = _packet(root, question="Patch permission behavior", max_constraints=20, max_tokens=4000)

    offenders = [
        c for c in packet.constraints
        if "PermissionService" in c.instruction and (c.severity == "must" or c.confidence == "high")
    ]
    assert not offenders


def test_markdown_table_rows_do_not_become_constraints(tmp_path: Path):
    root = tmp_path / "repo"
    _write(
        root / "docs/context7-docmancer-comparison.md",
        """# Comparison\n\n| Capability | Result |\n| --- | --- |\n| Compile patch constraints for agents | Return compact, source-attributed constraints |\n""",
    )

    packet = _packet(root, question="Compile patch constraints for agents", max_constraints=20, max_tokens=4000)

    payload = "\n".join(c.evidence + " " + c.instruction for c in packet.constraints)
    assert "Compile patch constraints for agents" not in payload


def test_research_and_comparison_docs_do_not_create_must_high_constraints(tmp_path: Path):
    root = tmp_path / "repo"
    _write(root / "docs/research/project-constraint-compiler-rfc.md", "ResearchService owns experimental compiler policy and must be the source of truth.\n")
    _write(root / "docs/context7-docmancer-comparison.md", "ComparisonService owns comparison policy and must be the source of truth.\n")
    _write(root / "research_service.py", "class ResearchService: pass\n")
    _write(root / "comparison_service.py", "class ComparisonService: pass\n")

    packet = _packet(root, question="Update compiler policy", max_constraints=20, max_tokens=4000)

    research_constraints = [
        c for c in packet.constraints
        if "ResearchService" in c.instruction or "ComparisonService" in c.instruction
    ]
    assert research_constraints
    assert all(not (c.severity == "must" and c.confidence == "high") for c in research_constraints)
    assert all("authority=low" in c.evidence or "downgrade=low_authority_source" in c.evidence for c in research_constraints)


def test_repo_artifact_paths_create_forbidden_edit_guardrail(tmp_path: Path):
    root = tmp_path / "repo"
    _write(root / "eval/task_level/results/run-1/constraints.json", "{}\n")
    _write(root / ".docatlas/patch-review/constraints.json", "{}\n")

    packet = _packet(root, question="Update app code", max_constraints=20, max_tokens=4000)

    assert packet.forbidden_edits
    guardrails = [c for c in packet.forbidden_edits if c.source == "repo_path_heuristics"]
    assert guardrails
    assert any("eval/task_level/results" in evidence for c in guardrails for evidence in [c.evidence])
    assert all(c.confidence == "medium" and c.severity == "should" for c in guardrails)


def test_final_token_budget_clamps_after_warnings(tmp_path: Path):
    root = _workspace(tmp_path)
    for idx in range(20):
        _write(root / f"docs/architecture-extra-{idx}.md", f"ExtraService{idx} owns policy and must be the source of truth for generated behavior.\n")
        _write(root / f"extra_service_{idx}.py", f"class ExtraService{idx}: pass\n")

    packet = _packet(root, max_constraints=50, max_tokens=1200)

    assert packet.token_estimate <= 1200
    assert packet.token_budget["token_estimate"] <= 1200


def test_grouped_constraints_are_views_of_all_constraints(tmp_path: Path):
    packet = _packet(_workspace(tmp_path))
    all_ids = {c.id for c in packet.constraints}
    assert all(c.id in all_ids for c in packet.forbidden_edits)
    assert all(c.id in all_ids for c in packet.dependency_contracts)
    assert all(c.id in all_ids for c in packet.source_of_truth_rules)


def test_ignores_dogfood_generated_artifacts_but_keeps_normal_research_docs(tmp_path: Path):
    root = _workspace(tmp_path)
    _write(root / "docs/research/docatlas-dogfood/task/constraints.md", "Dogfood artifact: FakeService owns menu policy.\n")
    _write(root / "docs/research/docatlas-dogfood/task/validation.json", '{"violated": 9, "evidence": "FakeService"}')
    _write(root / "docs/research/normal-architecture-note.md", "NormalResearchService owns research note policy.\n")

    packet = _packet(root, question="Update research note policy", max_constraints=20, max_tokens=4000)
    payload = str(asdict(packet))

    assert "FakeService" not in payload
    assert "NormalResearchService" in payload
    assert packet.excluded_source_count >= 2
    assert any("ignored_generated_artifact_sources" in warning for warning in packet.warnings)
    assert any(path.endswith("constraints.md") for path in packet.ignored_generated_artifact_sources)


def test_symbol_grounding_finds_task_local_source_symbols(tmp_path: Path):
    root = _workspace(tmp_path)
    _write(
        root / "lib/modules/menu/menu_line.dart",
        """
class MenuNotifier {
  void closeMenu() {}
}

class TabBrowserNotifier {
  void openInfo() {}
}

const quickInfoLabel = 'Быстрая информация';
""",
    )

    packet = _packet(
        root,
        question='Add "Быстрая информация" button and close menu before action using FAST_INFO',
        changed_files=["lib/modules/menu/menu_line.dart"],
        max_constraints=20,
        max_tokens=4000,
    )

    candidates = packet.symbol_candidates
    assert any(candidate["matched_symbol"] in {"openInfo", "quickInfoLabel"} for candidate in candidates)
    assert any(candidate["matched_symbol"] == "closeMenu" for candidate in candidates)
    assert all("docatlas-dogfood" not in candidate["source"] for candidate in candidates)


def test_patch_contract_exposes_repo_map_and_source_evidence_layer(tmp_path: Path):
    root = _workspace(tmp_path)
    _write(
        root / "lib/help_request_details_screen.dart",
        """
class HelpRequestDetailsScreen {}
final label = 'Вернуть в работу';
""",
    )

    packet = _packet(
        root,
        question='Reopen HELP request and show "Вернуть в работу" button.',
        changed_files=["lib/help_request_details_screen.dart"],
        max_constraints=20,
        max_tokens=4000,
    )

    assert any(item["source_class"] == "repo_map" and item["path"] == "lib/help_request_details_screen.dart" for item in packet.repo_map)
    evidence = [item for item in packet.source_evidence if item.get("evidence_class") == "source_snippet"]
    assert any(item["path"] == "lib/help_request_details_screen.dart" and item["line_start"] == 3 for item in evidence)
    grounded = [constraint for constraint in packet.constraints if constraint.id.startswith("source-evidence-")]
    assert grounded
    assert any(
        constraint.source_refs[0]["kind"] == "source_evidence" and constraint.source_refs[0]["line_start"] == 3
        for constraint in grounded
    )


def test_symbol_grounding_does_not_invent_without_source_match(tmp_path: Path):
    root = _workspace(tmp_path)

    packet = _packet(root, question="Use TotallyMissingBusinessThing", max_constraints=20, max_tokens=4000)

    assert not any(candidate["term"] == "TotallyMissingBusinessThing" for candidate in packet.symbol_candidates)


def test_symbol_grounding_demotes_broad_project_acronyms(tmp_path: Path):
    root = _workspace(tmp_path)
    _write(
        root / "lib/src/utils/help_request_strings.dart",
        """
class HelpAppStrings {}
const helpRequestReturnToWorkButton = 'Вернуть в работу';
""",
    )

    packet = _packet(
        root,
        question="Reopen HELP request and show the return-to-work button.",
        changed_files=["lib/src/utils/help_request_strings.dart"],
        max_constraints=20,
        max_tokens=4000,
    )

    help_candidates = [candidate for candidate in packet.symbol_candidates if candidate["term"] == "HELP"]
    assert help_candidates
    assert all(candidate["confidence"] == "low" for candidate in help_candidates)
    assert all(candidate["reason"].startswith("broad_acronym_demoted") for candidate in help_candidates)
    assert any(candidate["matched_symbol"] == "helpRequestReturnToWorkButton" for candidate in packet.symbol_candidates)
    help_constraints = [constraint for constraint in packet.constraints if constraint.id.startswith("symbol-candidate-help-")]
    assert help_constraints
    assert all(constraint.confidence == "low" for constraint in help_constraints)


def test_symbol_grounding_skips_cross_language_connector_fragments(tmp_path: Path):
    root = _workspace(tmp_path)
    _write(
        root / "lib/src/data/repositories/help_requests_repository.dart",
        """
class HelpRequestsRepository {
  Future<void> returnClosedRequestToActive(String requestNumber) async {}
  final label = 'Вернуть в работу and';
}
""",
    )

    packet = _packet(
        root,
        question="Reopen HELP request: show buttons Вернуть в работу and Создать новый запрос; return closed HELP sends status Активная.",
        changed_files=["lib/src/data/repositories/help_requests_repository.dart"],
        max_constraints=20,
        max_tokens=4000,
    )

    terms = {candidate["term"] for candidate in packet.symbol_candidates}
    assert "в работу and" not in terms
    assert any(candidate["matched_symbol"] == "returnClosedRequestToActive" for candidate in packet.symbol_candidates)


def test_symbol_grounding_skips_comment_only_phrase_matches(tmp_path: Path):
    root = _workspace(tmp_path)
    _write(
        root / "lib/src/ui/help_request_details_screen/cubit/help_request_details_cubit.dart",
        """
class HelpRequestDetailsCubit {
  /// Вернуть закрытую заявку HELP в работу.
  Future<void> returnClosedRequestToActive(String requestNumber) async {}

  /// Отправить комментарий.
  Future<void> sendComment(String text) async {}
}
""",
    )
    _write(
        root / "lib/src/utils/help_request_strings.dart",
        """
class HelpAppStrings {
  static const helpRequestReturnToWorkBtn = 'Вернуть в работу';
}
""",
    )

    packet = _packet(
        root,
        question='Reopen HELP request: show button "Вернуть в работу" and allow Отправить after success.',
        changed_files=["lib/src/ui/help_request_details_screen/cubit/help_request_details_cubit.dart"],
        max_constraints=20,
        max_tokens=4000,
    )

    assert not any(
        candidate["matched_symbol"] in {"Вернуть в работу", "Отправить"}
        for candidate in packet.symbol_candidates
    )
    assert any(candidate["matched_symbol"] == "helpRequestReturnToWorkBtn" for candidate in packet.symbol_candidates)


# Backward-compatible smoke names from the first production PR.
def test_generated_file_constraint_extraction(tmp_path: Path):
    test_extracts_generated_file_constraint_from_docs(tmp_path)


def test_source_of_truth_extraction(tmp_path: Path):
    test_extracts_source_of_truth_service_layer_constraint(tmp_path)


def test_pinned_dependency_extraction(tmp_path: Path):
    test_extracts_pinned_dependency_from_pubspec_lock(tmp_path)


def test_constraints_have_source_attribution(tmp_path: Path):
    packet = _packet(_workspace(tmp_path))
    assert packet.constraints
    assert all(c.source and c.evidence and c.confidence in {"high", "medium", "low"} for c in packet.constraints)


def test_budget_limits_keep_must_high_confidence_first(tmp_path: Path):
    test_budget_keeps_must_high_confidence_constraints(tmp_path)


def test_no_benchmark_oracle_hidden_test_leakage(tmp_path: Path):
    test_does_not_emit_hidden_or_benchmark_oracle_sources(tmp_path)

def test_drops_non_actionable_headings_tree_and_owner_noise(tmp_path: Path):
    root = _workspace(
        tmp_path,
        docs="""
# Architecture
Rules that must not be violated:
│ owns Shelf HttpServer
PermissionService owns permission policy and is the source of truth for permission decisions.
""",
    )

    packet = _packet(root)
    text = "\n".join([c.instruction for c in packet.constraints] + [c.evidence for c in packet.constraints])

    assert "Rules that must not be violated" not in text
    assert "Shelf HttpServer" not in text
    assert any("PermissionService" in c.instruction for c in packet.constraints)


def test_scan_doc_constraints_skip_unrelated_oidc_and_dart_tool_sources(tmp_path: Path):
    root = _workspace(tmp_path)
    _write(root / "docs/SCANDOC_WEB_CAMERA_API_PLAN.md", "ScanDocRunner owns ScanDoc initialization before Hive and must not be bypassed.\n")
    _write(root / "docs/EXTERNAL_OIDC_BROWSER_SELECTION_FIX_PLAN.md", "OidcBrowserSelector owns external auth WebView/browser policy and must be the source of truth.\n")
    _write(root / "packages/path_provider_nbo/.dart_tool/extension_discovery/README.md", "Hence, it should never be necessary to edit extension discovery metadata.\n")
    _write(root / "lib/scandoc_runner.dart", "class ScanDocRunner {}\n")
    _write(root / "lib/oidc_browser_selector.dart", "class OidcBrowserSelector {}\n")

    packet = _packet(
        root,
        question="Change ScanDoc WebView file chooser without bypassing ScanDocRunner initialization before Hive.",
        max_constraints=20,
        max_tokens=4000,
    )
    payload = str(asdict(packet))

    assert "ScanDocRunner" in payload
    assert "OidcBrowserSelector" not in payload
    assert ".dart_tool" not in payload
