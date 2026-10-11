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


def test_changed_files_raise_generated_file_constraint(tmp_path: Path):
    packet = _packet(_workspace(tmp_path), changed_files=["lib/foo/user.freezed.dart", "lib/foo/user.g.dart"])
    assert any(c.type == "generated_file" and c.source == "changed_files" for c in packet.constraints)


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


def test_patch_constraints_code_graph_unresolved_external_is_low_confidence_hint(tmp_path: Path):
    root = tmp_path / "repo"
    _write(root / "docs/architecture.md", "External package integration is reviewed case by case.\n")
    _write(
        root / "lib/external_screen.dart",
        """
import 'package:external/foo.dart';

class ExternalScreen {}
""".strip()
        + "\n",
    )

    packet = _packet(root, question="external package integration", max_constraints=20, max_tokens=4000)

    graph_constraints = [c for c in packet.constraints if any(ref.get("kind") == "code_graph" for ref in c.source_refs)]
    if graph_constraints:
        text = "\n".join(c.instruction.lower() for c in graph_constraints)
        assert all(c.confidence == "low" or "unresolved" in c.instruction.lower() or "search hint" in c.instruction.lower() for c in graph_constraints)
        assert "definitely depends on" not in text
        assert "calls" not in text


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


def test_budget_drops_low_priority_constraints_first(tmp_path: Path):
    packet = _packet(_workspace(tmp_path), changed_files=["lib/foo/user.g.dart"], max_constraints=2, max_tokens=220)
    assert packet.constraints
    assert any(c.type == "generated_file" and c.source == "changed_files" for c in packet.constraints)
    assert all(c.confidence in {"high", "medium"} for c in packet.constraints)


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


def test_symbol_grounding_does_not_invent_without_source_match(tmp_path: Path):
    root = _workspace(tmp_path)

    packet = _packet(root, question="Use TotallyMissingBusinessThing", max_constraints=20, max_tokens=4000)

    assert not any(candidate["term"] == "TotallyMissingBusinessThing" for candidate in packet.symbol_candidates)


def test_constraints_have_source_attribution(tmp_path: Path):
    packet = _packet(_workspace(tmp_path))
    assert packet.constraints
    assert all(c.source and c.evidence and c.confidence in {"high", "medium", "low"} for c in packet.constraints)


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
