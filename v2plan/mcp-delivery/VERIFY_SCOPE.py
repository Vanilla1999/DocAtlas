"""Offline ownership, protected-history, D1 and syntax checks for delivery."""
from __future__ import annotations

import ast
from pathlib import Path
import subprocess

BASE = "2d060bf06904cc84a98b7de39f86529a94ea7c39"
ALLOWED = {
    # Coordinator records for the explicitly approved storage continuation.
    "v2plan/mcp-storage/AUTHORIZATION.md",
    "v2plan/mcp-storage/PROGRESS_RU.md",
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
