"""Offline ownership, protected-history, D1 and syntax checks for delivery."""
from __future__ import annotations

import ast
from pathlib import Path
import subprocess

BASE = "2d060bf06904cc84a98b7de39f86529a94ea7c39"
ALLOWED = {
    "tests/docs/test_docs_context_read_next.py",  # Reviewed confirmed fixture lifecycle only.
    "tests/docs/test_context_capture_integrity.py",
    "tests/task_level/test_task33_validation.py",  # Unused test-stub keyword removal only.
    "tests/docs/test_context_projection_boundaries.py",  # Reviewed consent-scope regressions.
    "tests/diagnostic_labels.projection_boundaries.json",
    "eval/evidence_quality_v2/runtime.py",
    "tests/test_evidence_quality_v2_fixture_runtime.py",
    "tests/diagnostic_labels.evidence_quality_v2_fixture_runtime.json",
    "eval/agent_developer_v1/installed_mcp_benchmark.py",
    "tests/test_installed_mcp_bootstrap_contract.py",
    "tests/diagnostic_labels.installed_mcp_bootstrap_contract.json",
    "tests/test_dictionary_exit_local_entry_closure.py",
    "docmancer/docs/interfaces/mcp/error_contract.py",
    ".github/workflows/ci.yml",  # Explicit Linux/macOS supported-platform matrices only.
    ".github/workflows/p1-stack-exact-validation.yml",
    ".github/workflows/mcp-platform-proof.yml",
    "scripts/docs_mcp_platform_proof.sh",
    "scripts/test-install.sh",  # Reviewed nested-config/JSONC installer checks.
    "tests/test_nl_dictionary_removal_consumer_contract.py",
    "tests/test_dictionary_exit_selector_visibility.py",
    "tests/diagnostic_labels.dictionary_exit_selector_visibility.json",
    "README.md",  # Coordinator: reviewed auto-install command documentation.
    # Coordinator records for the explicitly approved storage continuation.
    "v2plan/mcp-storage/AUTHORIZATION.md",
    "v2plan/mcp-storage/PROGRESS_RU.md",
    "v2plan/mcp-storage/FRESH_PLAN_RU.md",
    # Reviewed experimental spike only; no production persistence integration.
    "experiments/mcp_storage_native/README.md",
    "experiments/mcp_storage_native/sqlite_fd_vfs.c",
    "experiments/mcp_storage_native/worker.py",
    "experiments/mcp_storage_native/include/sqlite3.h",
    "experiments/mcp_storage_native/include/sqlite3ext.h",
    "tests/test_mcp_storage_native_spike.py",
    "tests/mcp_storage_native_spike_checks.py",
    "tests/diagnostic_labels.mcp_storage_native_spike.json",
    # Independently reviewed found-window retention and real service forwarding.
    "docmancer/docs/application/_unified_context_service_part01.py",
    "docmancer/docs/application/_project_context_service_part01.py",
    "docmancer/docs/application/_project_docs_service_part03.py",
    "docmancer/docs/domain/project_doc_ranking.py",
    "docmancer/docs/service.py",
    "tests/test_action_packet_v4_found_window_retention.py",
    "tests/diagnostic_labels.action_packet_v4_found_window_retention.json",
    "tests/test_action_packet_v4_public.py",
    # Reviewed trusted-local storage profile and cold initialization lifecycle.
    "docmancer/core/member_storage_policy.py",
    "docmancer/core/config_resolution.py",
    "tests/test_mcp_trusted_storage_lifecycle.py",
    "tests/diagnostic_labels.mcp_trusted_storage_lifecycle.json",
    "tests/docs/test_host_scope_planning_contract.py",  # Active wording migration.
    "tests/docs/test_host_scope_contract.py",  # Reviewed explicit-preparation fixtures.
    # Independently reviewed actual-version wire preservation / nullable schema.
    "docmancer/docs/application/_action_packet_shared.py",
    "docmancer/docs/application/_action_packet_part03.py",
    "docmancer/docs/application/_action_packet_part04.py",
    "docmancer/mcp/_docs_server_shared.py",
    "tests/test_action_packet_v4_wire_version.py",
    "tests/diagnostic_labels.action_packet_v4_wire_version.json",
    # Independently reviewed library lineage preservation / duplicate rejection.
    "docmancer/docs/application/_library_docs_service_part03.py",
    "docmancer/docs/application/_unified_context_service_part02.py",
    # Reviewed finite active NL/proof expectation migration; runtime unchanged.
    "tests/docs/test_query_planning_scope_regressions.py",
    "tests/diagnostic_labels.query_planning.json",
    "tests/docs/test_quantified_attribute_scope_isolation.py",
    "tests/diagnostic_labels.quantified_attribute_scope_isolation.json",
    "docmancer/docs/application/_project_docs_service_part01.py",
    "docmancer/docs/application/_project_docs_service_part02.py",
    "docmancer/docs/application/project_docs_member_transaction.py",
    "docmancer/docs/interfaces/mcp/prefetch_tools.py",
    "docmancer/core/_sqlite_store_part01.py",
    "tests/test_mcp_delivery_member_transaction.py",
    "tests/diagnostic_labels.mcp_delivery_member_transaction.json",
    "docmancer/docs/interfaces/mcp/context_tools.py",
    "docmancer/docs/interfaces/grounded_mcp_session.py",
    "docmancer/docs/interfaces/host_context.py",
    "docmancer/mcp/agent_workflow_contract.py",
    "docmancer/mcp/_docs_server_resources.py",
    "docmancer/mcp/_docs_server_tool_data.py",
    "docmancer/mcp/_docs_server_schema.py",
    "docmancer/templates/agent_contract.md",
    "docmancer/docs/application/model_visible_projection.py",
    "docmancer/docs/application/_model_visible_patch_projection.py",
    "docmancer/docs/application/_model_visible_docs_support.py",
    "tests/test_action_packet_v4_delivery_consumers.py",
    "tests/test_action_packet_v4_workflow_surface.py",
    "tests/test_action_packet_v4_projection_split.py",
    "tests/diagnostic_labels.action_packet_v4_delivery_b.json",
    "tests/docs/test_mcp_docs_tools_registration.py",
    "scripts/docs_mcp_stdio_smoke.py",
    "docmancer/mcp/agent_config.py",
    "scripts/install.sh",
    "tests/test_mcp_agent_config.py",
    "tests/test_opencode_environment_validation.py",
    "tests/test_docs_mcp_stdio_delivery.py",
    "tests/test_opencode_v2_installer.py",
    "tests/diagnostic_labels.mcp_delivery_c.json",
    "docmancer/_agent_parser_loading.py",
    "docmancer/mcp/_docs_server_part01.py",
    "tests/test_mcp_delivery_dispatch_boundary.py",
    "tests/diagnostic_labels.mcp_delivery_dispatch.json",
    "docmancer/agent.py",
    "docmancer/cli/_commands_part04.py",
    "docmancer/docs/agent_contract.py",
    "tests/docs/test_content_trust.py",
    "tests/test_dictionary_exit_read_packet_residuals.py",
    "tests/test_cli.py",
    "tests/test_release_gate.py",
    "tests/test_dictionary_exit_inert_security.py",
    "tests/test_dictionary_exit_admission_literals.py",
    "tests/test_dictionary_exit_inert_sdk_closure.py",
    "tests/test_dictionary_exit_public_request.py",
    "tests/test_nl_dictionary_removal_packet_contract.py",
    "tests/diagnostic_labels.json",
    ".github/workflows/ci.yml",
    ".github/workflows/p1-stack-exact-validation.yml",
}


def git(*args):
    return subprocess.check_output(["git", *args], text=True)


def verify():
    root = Path(git("rev-parse", "--show-toplevel").strip())
    changed = set(git("diff", "--name-only", BASE).splitlines())
    changed.update(git("ls-files", "--others", "--exclude-standard").splitlines())
    unexpected = sorted(p for p in changed if p not in ALLOWED
                        and not p.startswith("v2plan/mcp-delivery/"))
    assert not unexpected, unexpected
    # Catalog bytes, historical reports/gold/thresholds, NEXT work and old v4
    # acceptance records cannot change under this scope.
    assert git("diff", BASE, "--", "docatlas.project-docs.yaml") == ""
    import yaml
    catalog = yaml.safe_load((root / "docatlas.project-docs.yaml").read_text())
    assert len(catalog["documents"]) == 10
    assert catalog["code_files"] == []
    assert not catalog.get("roots")
    count = 0
    for path in sorted(changed):
        source = root / path
        if source.suffix == ".py" and source.is_file():
            ast.parse(source.read_text(encoding="utf-8"), filename=path)
            count += 1
    subprocess.run(["git", "diff", "--check", BASE], check=True)
    print(f"delivery ownership PASS: {len(changed)} changed paths")
    print(f"syntax PASS: {count} modules; whitespace PASS")
    print("D1 catalog bytes unchanged; exact 10 documents, code_files=(): PASS")
    print("Runtime installed/index parity requires separate checks; not proved here.")


if __name__ == "__main__":
    verify()
