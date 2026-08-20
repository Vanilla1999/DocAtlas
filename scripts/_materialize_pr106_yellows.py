#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: anchor count={count}, expected 1")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def call(
    question: str,
    *,
    scope: str | None = None,
    mode: str = "project",
    module: str | None = None,
    module_path: str | None = None,
    packet: int = 800,
    status: str = "ok",
    required: list[str] | None = None,
    forbidden: list[str] | None = None,
    **extra: object,
) -> dict[str, object]:
    row: dict[str, object] = {
        "question": question,
        "mode": mode,
        "packet_tokens": packet,
        "max_projection_tokens": packet,
        "target_expected_status": status,
        "forbidden_sources": forbidden or [],
    }
    if scope is not None:
        row["scope"] = scope
    if module is not None:
        row["module"] = module
    if module_path is not None:
        row["module_path"] = module_path
    if required:
        row["target_required_sources"] = required
    row.update(extra)
    return row


def case(
    case_id: str,
    klass: str,
    fixture: str,
    working_path: str,
    calls: list[dict[str, object]],
    *,
    max_calls: int | None = None,
    trajectory: int = 1600,
    setup_files: list[dict[str, str]] | None = None,
    mutation: dict[str, str] | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "id": case_id,
        "class": klass,
        "fixture": fixture,
        "working_path": working_path,
        "max_get_docs_context_calls": max_calls if max_calls is not None else len(calls),
        "max_trajectory_tokens": trajectory,
        "calls": calls,
    }
    if setup_files:
        row["setup_files"] = setup_files
    if mutation:
        row["mutation_before_calls"] = mutation
    return row


def sync_recovery_call(question: str, module_path: str, *, forbidden: list[str]) -> dict[str, object]:
    return call(
        question,
        scope="module",
        module_path=module_path,
        packet=300,
        status="insufficient_evidence",
        forbidden=forbidden,
        target_next_action_tool="prepare_docs",
        target_next_action_arguments={
            "action": "sync_project_docs",
            "project_path": "$PROJECT_PATH",
            "with_vectors": False,
        },
        target_requires_confirmation=True,
        target_auto_execute=False,
        target_edit_ready=False,
        target_confirmation_reason="project_docs_preflight",
    )


def setup_auth_files() -> list[dict[str, str]]:
    return [
        {"path": "apps/auth/README.md", "content": "# Auth app\n\nAppAuthBoundary is the client authentication application boundary.\n"},
        {"path": "apps/auth/src/app.py", "content": "class AppAuthBoundary:\n    pass\n"},
        {"path": "lib/modules/auth/README.md", "content": "# Auth library module\n\nModuleAuthBoundary is the reusable authentication module boundary.\n"},
        {"path": "lib/modules/auth/src/module.py", "content": "class ModuleAuthBoundary:\n    pass\n"},
        {"path": "lib/features/auth/docs/flow.md", "content": "# Auth feature\n\nFeatureAuthBoundary is the feature-local authentication flow boundary.\n"},
        {"path": "lib/features/auth/src/feature.py", "content": "class FeatureAuthBoundary:\n    pass\n"},
    ]


def update_cases() -> None:
    path = ROOT / "eval/agent_developer_v2/cases.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload["cases"]
    by_id = {row["id"]: row for row in rows}
    policy = by_id["project_policy_tiny_budget"]
    policy["max_trajectory_tokens"] = 1400
    policy["calls"][0]["packet_tokens"] = 1400
    policy["calls"][0]["max_projection_tokens"] = 1400

    new_ids = {
        "wrong_module_orders_rejects_payment",
        "wrong_module_payments_rejects_orders",
        "project_scope_rejects_module_detail",
        "module_name_orders_supported",
        "module_name_payments_supported",
        "stale_orders_module_recovery",
        "stale_payments_module_recovery",
        "dependency_only_prefetch_recovery",
        "module_plus_dependency_bounded",
        "traversal_module_path_rejected",
        "absolute_module_path_rejected",
        "prefix_collision_module_path_rejected",
        "case_collision_module_path_rejected",
        "long_missing_module_path_bounded",
        "long_exact_module_path_supported",
        "many_auth_ambiguity_bounded_recovery",
        "many_auth_exact_feature_collision",
        "many_auth_exact_service_collision",
    }
    rows[:] = [row for row in rows if row.get("id") not in new_ids]

    explicit = "explicit_manifest_monorepo"
    orders_working = "packages/orders/src/submission.py"
    rows.extend([
        case(
            "wrong_module_orders_rejects_payment", "scope_isolation", explicit, orders_working,
            [call("What is PaymentOutbox?", scope="module", module_path="packages/orders", packet=300,
                  status="insufficient_evidence", forbidden=["packages/payments/README.md", "ARCHITECTURE.md"],
                  target_edit_ready=False)], trajectory=300,
        ),
        case(
            "wrong_module_payments_rejects_orders", "scope_isolation", explicit, "packages/payments/src/outbox.py",
            [call("What is OrdersDraftStore?", scope="module", module_path="packages/payments", packet=300,
                  status="insufficient_evidence", forbidden=["packages/orders/README.md", "ARCHITECTURE.md"],
                  target_edit_ready=False)], trajectory=300,
        ),
        case(
            "project_scope_rejects_module_detail", "scope_isolation", explicit, orders_working,
            [call("What is OrdersDraftStore?", scope="project", packet=300,
                  status="insufficient_evidence", forbidden=["packages/orders/README.md", "packages/payments/README.md"],
                  target_edit_ready=False)], trajectory=300,
        ),
        case(
            "module_name_orders_supported", "module_name_resolution", explicit, orders_working,
            [call("What is OrdersDraftStore?", scope="module", module="orders", packet=900,
                  required=["packages/orders/README.md"], forbidden=["packages/payments/README.md", "ARCHITECTURE.md"])],
            trajectory=900,
        ),
        case(
            "module_name_payments_supported", "module_name_resolution", explicit, "packages/payments/src/outbox.py",
            [call("What is PaymentOutbox?", scope="module", module="payments", packet=900,
                  required=["packages/payments/README.md"], forbidden=["packages/orders/README.md", "ARCHITECTURE.md"])],
            trajectory=900,
        ),
        case(
            "stale_orders_module_recovery", "stale_recovery", explicit, orders_working,
            [sync_recovery_call("What is OrdersDraftStore?", "packages/orders", forbidden=["packages/payments/README.md"])],
            trajectory=300,
            mutation={"path": "packages/orders/README.md", "append": "\nPostIndexOrdersFact is added after indexing.\n"},
        ),
        case(
            "stale_payments_module_recovery", "stale_recovery", explicit, "packages/payments/src/outbox.py",
            [sync_recovery_call("What is PaymentOutbox?", "packages/payments", forbidden=["packages/orders/README.md"])],
            trajectory=300,
            mutation={"path": "packages/payments/README.md", "append": "\nPostIndexPaymentsFact is added after indexing.\n"},
        ),
        case(
            "dependency_only_prefetch_recovery", "dependency_recovery", explicit, orders_working,
            [call("What is tenacity.Retrying?", mode="dependency", packet=300, status="insufficient_evidence",
                  forbidden=["packages/orders/README.md", "packages/payments/README.md"],
                  target_next_action_tool="prepare_docs",
                  target_next_action_arguments={"action": "prefetch_project_dependency_docs", "project_path": "$PROJECT_PATH"},
                  target_requires_confirmation=True, target_auto_execute=False, target_edit_ready=False,
                  target_confirmation_reason="network_fetch")], trajectory=300,
        ),
        case(
            "module_plus_dependency_bounded", "dependency_multi_scope", explicit, orders_working,
            [
                call("What is OrdersDraftStore?", scope="module", module_path="packages/orders", packet=800,
                     required=["packages/orders/README.md"], forbidden=["packages/payments/README.md"]),
                call("What is tenacity.Retrying?", mode="dependency", packet=300, status="insufficient_evidence",
                     forbidden=["packages/payments/README.md"], target_next_action_tool="prepare_docs",
                     target_next_action_arguments={"action": "prefetch_project_dependency_docs", "project_path": "$PROJECT_PATH"},
                     target_requires_confirmation=True, target_auto_execute=False, target_edit_ready=False,
                     target_confirmation_reason="network_fetch"),
            ], max_calls=2, trajectory=1100,
        ),
        case(
            "traversal_module_path_rejected", "path_security", explicit, orders_working,
            [call("What is PaymentOutbox?", scope="module", module_path="packages/orders/../payments", packet=300,
                  status="insufficient_evidence", forbidden=["packages/payments/README.md"],
                  target_operational_reason_code="module_not_found", target_edit_ready=False)], trajectory=300,
        ),
        case(
            "absolute_module_path_rejected", "path_security", explicit, orders_working,
            [call("What is OrdersDraftStore?", scope="module", module_path="/packages/orders", packet=300,
                  status="insufficient_evidence", forbidden=["packages/orders/README.md"],
                  target_operational_reason_code="module_not_found", target_edit_ready=False)], trajectory=300,
        ),
        case(
            "prefix_collision_module_path_rejected", "path_collision", explicit, orders_working,
            [call("What is OrdersDraftStore?", scope="module", module_path="packages/order", packet=300,
                  status="insufficient_evidence", forbidden=["packages/orders/README.md"],
                  target_operational_reason_code="module_not_found", target_edit_ready=False)], trajectory=300,
        ),
        case(
            "case_collision_module_path_rejected", "path_collision", explicit, orders_working,
            [call("What is OrdersDraftStore?", scope="module", module_path="packages/Orders", packet=300,
                  status="insufficient_evidence", forbidden=["packages/orders/README.md"],
                  target_operational_reason_code="module_not_found", target_edit_ready=False)], trajectory=300,
        ),
    ])

    long_name = "module_" + ("very_long_safe_segment_" * 5) + "end"
    long_module = f"packages/{long_name}"
    rows.append(case(
        "long_missing_module_path_bounded", "path_security", explicit, orders_working,
        [call("What is OrdersDraftStore?", scope="module", module_path=long_module + "_missing", packet=256,
              status="insufficient_evidence", forbidden=["packages/orders/README.md"],
              target_operational_reason_code="module_not_found", target_edit_ready=False)], trajectory=256,
    ))
    long_setup = [
        {"path": f"{long_module}/README.md", "content": "# Long module\n\nLongPathBoundary is the exact long-path module boundary.\n"},
        {"path": f"{long_module}/src/worker.py", "content": "class LongPathBoundary:\n    pass\n"},
    ]
    rows.append(case(
        "long_exact_module_path_supported", "long_path", "ambiguous_modules_monorepo", f"{long_module}/src/worker.py",
        [call("What is LongPathBoundary?", scope="module", module_path=long_module, packet=1000,
              required=[f"{long_module}/README.md"], forbidden=["packages/auth/README.md", "services/auth/README.md"])],
        trajectory=1000, setup_files=long_setup,
    ))

    auth_setup = setup_auth_files()
    ambiguity_call = call(
        "What is AppAuthBoundary?", scope="module", module="auth", packet=256,
        status="insufficient_evidence",
        forbidden=["apps/auth/README.md", "lib/features/auth/docs/flow.md", "lib/modules/auth/README.md",
                   "packages/auth/README.md", "services/auth/README.md"],
        target_next_action_tool="docs_status",
        target_next_action_arguments={"action": "project", "details": True, "project_path": "$PROJECT_PATH"},
        target_requires_confirmation=False, target_auto_execute=False, target_edit_ready=False,
        target_operational_reason_code="module_ambiguous",
        target_module_candidates=["apps/auth", "lib/features/auth", "lib/modules/auth", "packages/auth", "services/auth"],
        recovery={
            "max_status_projection_tokens": 900,
            "expected_module_paths": ["apps/auth", "lib/features/auth", "lib/modules/auth", "packages/auth", "services/auth"],
            "retry": call("What is AppAuthBoundary?", scope="module", module_path="apps/auth", packet=800,
                          required=["apps/auth/README.md"],
                          forbidden=["lib/features/auth/docs/flow.md", "lib/modules/auth/README.md", "packages/auth/README.md", "services/auth/README.md"]),
        },
    )
    rows.append(case(
        "many_auth_ambiguity_bounded_recovery", "many_ambiguity", "ambiguous_modules_monorepo", "packages/auth/src/auth.py",
        [ambiguity_call], max_calls=2, trajectory=1950, setup_files=auth_setup,
    ))
    rows.append(case(
        "many_auth_exact_feature_collision", "many_ambiguity_exact", "ambiguous_modules_monorepo", "lib/features/auth/src/feature.py",
        [call("What is FeatureAuthBoundary?", scope="module", module_path="lib/features/auth", packet=900,
              required=["lib/features/auth/docs/flow.md"],
              forbidden=["apps/auth/README.md", "lib/modules/auth/README.md", "packages/auth/README.md", "services/auth/README.md"])],
        trajectory=900, setup_files=auth_setup,
    ))
    rows.append(case(
        "many_auth_exact_service_collision", "many_ambiguity_exact", "ambiguous_modules_monorepo", "services/auth/src/auth.py",
        [call("What is ServiceAuthBoundary?", scope="module", module_path="services/auth", packet=900,
              required=["services/auth/README.md"], forbidden=["packages/auth/README.md"])],
        trajectory=900,
    ))

    if len(rows) != 27:
        raise RuntimeError(f"expected 27 v2 cases, got {len(rows)}")
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def update_gate() -> None:
    path = ROOT / "scripts/run_agent_developer_adversarial_gate.py"
    anchor = '''def _case_scope(call: dict[str, Any]) -> dict[str, str]:\n    return base._scope_signature(call)\n\n\ndef _run_adversarial_case(case: dict[str, Any]) -> dict[str, Any]:\n'''
    replacement = '''def _case_scope(call: dict[str, Any]) -> dict[str, str]:\n    return base._scope_signature(call)\n\n\ndef _safe_setup_path(project: Path, raw_path: Any) -> Path | None:\n    return base._safe_fixture_path(project, raw_path)\n\n\ndef _apply_setup_files(project: Path, rows: Any) -> None:\n    if rows in (None, []):\n        return\n    if not isinstance(rows, list) or len(rows) > 24:\n        raise ValueError("setup_files must contain at most 24 files")\n    seen: set[Path] = set()\n    for index, row in enumerate(rows):\n        if not isinstance(row, dict) or set(row) != {"path", "content"}:\n            raise ValueError(f"setup_files[{index}] must contain exactly path and content")\n        target = _safe_setup_path(project, row.get("path"))\n        content = row.get("content")\n        if target is None:\n            raise ValueError(f"setup_files[{index}] path is unsafe")\n        if target in seen:\n            raise ValueError(f"setup_files[{index}] duplicates a prior path")\n        if not isinstance(content, str) or len(content.encode("utf-8")) > 4096:\n            raise ValueError(f"setup_files[{index}] content exceeds the 4096-byte bound")\n        seen.add(target)\n        target.parent.mkdir(parents=True, exist_ok=True)\n        target.write_text(content, encoding="utf-8")\n\n\ndef _run_adversarial_case(case: dict[str, Any]) -> dict[str, Any]:\n'''
    replace_once(path, anchor, replacement)

    old = '''    fixture = base.PROJECTS_ROOT / str(case["fixture"])\n    working = base._safe_fixture_path(fixture, case.get("working_path"))\n    errors: list[str] = []\n    events: list[dict[str, Any]] = []\n    trajectory_tokens = 0\n    context_calls = 0\n    previous_home = os.environ.get("DOCMANCER_HOME")\n\n    if working is None or not working.is_file():\n        return {\n            "case_id": case_id,\n            "passed": False,\n            "trajectory_tokens": 0,\n            "errors": ["working_path is missing or unsafe"],\n            "events": [],\n        }\n\n    try:\n'''
    new = '''    fixture = base.PROJECTS_ROOT / str(case["fixture"])\n    errors: list[str] = []\n    events: list[dict[str, Any]] = []\n    trajectory_tokens = 0\n    context_calls = 0\n    previous_home = os.environ.get("DOCMANCER_HOME")\n\n    if not fixture.is_dir():\n        return {\n            "case_id": case_id,\n            "passed": False,\n            "trajectory_tokens": 0,\n            "errors": ["fixture is missing"],\n            "events": [],\n        }\n\n    try:\n'''
    replace_once(path, old, new)

    old = '''            project = tmp / "project"\n            shutil.copytree(fixture, project)\n            os.environ["DOCMANCER_HOME"] = str(tmp / "home")\n            service = base._service(tmp)\n'''
    new = '''            project = tmp / "project"\n            shutil.copytree(fixture, project)\n            _apply_setup_files(project, case.get("setup_files"))\n            working = _safe_setup_path(project, case.get("working_path"))\n            if working is None or not working.is_file():\n                return {\n                    "case_id": case_id,\n                    "passed": False,\n                    "trajectory_tokens": 0,\n                    "errors": ["working_path is missing or unsafe"],\n                    "events": [],\n                }\n            os.environ["DOCMANCER_HOME"] = str(tmp / "home")\n            service = base._service(tmp)\n'''
    replace_once(path, old, new)

    old = '''        if planned_calls > max_calls:\n            raise ValueError(f"{case_id}: planned calls exceed call budget")\n    return payload\n'''
    new = '''        if planned_calls > max_calls:\n            raise ValueError(f"{case_id}: planned calls exceed call budget")\n        setup_files = case.get("setup_files")\n        if setup_files is not None:\n            if not isinstance(setup_files, list) or len(setup_files) > 24:\n                raise ValueError(f"{case_id}: invalid setup_files bound")\n            seen_setup_paths: set[str] = set()\n            for index, row in enumerate(setup_files):\n                if not isinstance(row, dict) or set(row) != {"path", "content"}:\n                    raise ValueError(f"{case_id}: invalid setup_files[{index}]")\n                raw_path = str(row.get("path") or "").replace("\\\\", "/")\n                parts = Path(raw_path).parts\n                if (\n                    not raw_path or raw_path.startswith("/") or ".." in parts\n                    or (parts and str(parts[0]).endswith(":"))\n                    or raw_path in seen_setup_paths\n                ):\n                    raise ValueError(f"{case_id}: unsafe setup_files[{index}] path")\n                content = row.get("content")\n                if not isinstance(content, str) or len(content.encode("utf-8")) > 4096:\n                    raise ValueError(f"{case_id}: invalid setup_files[{index}] content")\n                seen_setup_paths.add(raw_path)\n    return payload\n'''
    replace_once(path, old, new)

    old = '''    assert not _edit_safe({"status": "insufficient_evidence", "edit_ready": True})\n'''
    new = '''    assert not _edit_safe({"status": "insufficient_evidence", "edit_ready": True})\n    with TemporaryDirectory(prefix="docatlas-v2-setup-selftest-") as raw_tmp:\n        root = Path(raw_tmp)\n        assert _safe_setup_path(root, "packages/auth/README.md") is not None\n        assert _safe_setup_path(root, "../outside.md") is None\n        assert _safe_setup_path(root, "/absolute.md") is None\n'''
    replace_once(path, old, new)


def update_status_projection() -> None:
    path = ROOT / "docmancer/docs/interfaces/mcp/prefetch_tools.py"
    old = '''    module_count = len(modules)\n    compact: dict[str, Any] = {\n'''
    new = '''    module_count = len(modules)\n    raw_diagnostics = project.get("diagnostics")\n    diagnostics = raw_diagnostics if isinstance(raw_diagnostics, dict) else {}\n    raw_active_index = diagnostics.get("active_index")\n    active_index = raw_active_index if isinstance(raw_active_index, dict) else {}\n    active_db_path = active_index.get("db_path")\n    compact: dict[str, Any] = {\n'''
    replace_once(path, old, new)
    old = '''        "project_docs": {\n            "module_count": module_count,\n            "modules": visible_modules,\n            "modules_omitted": max(0, module_count - len(visible_modules)) if details else module_count,\n        },\n        "warnings": list(project.get("warnings") or [])[:_DOCS_STATUS_WARNING_LIMIT],\n'''
    new = '''        "project_docs": {\n            "module_count": module_count,\n            "modules": visible_modules,\n            "modules_omitted": max(0, module_count - len(visible_modules)) if details else module_count,\n        },\n        "diagnostics": (\n            {"active_index": {"db_path": active_db_path}}\n            if active_db_path not in (None, "") else {}\n        ),\n        "warnings": list(project.get("warnings") or [])[:_DOCS_STATUS_WARNING_LIMIT],\n'''
    replace_once(path, old, new)


def update_mutations() -> None:
    path = ROOT / "scripts/run_agent_developer_adversarial_mutation_gate.py"
    old = '''    Mutant(\n        "project_module_ambiguity_guard",\n        "docmancer/docs/application/_project_docs_service_part01.py",\n        "        if len(paths) > 1:\\n            return None, {",\n        "        if False and len(paths) > 1:  # mutation: silently select ambiguous module\\n            return None, {",\n        FULL_GATE,\n    ),\n)\n'''
    new = '''    Mutant(\n        "project_module_ambiguity_guard",\n        "docmancer/docs/application/_project_docs_service_part01.py",\n        "        if len(paths) > 1:\\n            return None, {",\n        "        if False and len(paths) > 1:  # mutation: silently select ambiguous module\\n            return None, {",\n        FULL_GATE,\n    ),\n    Mutant(\n        "project_status_module_projection_guard",\n        "docmancer/docs/interfaces/mcp/prefetch_tools.py",\n        "_DOCS_STATUS_MODULE_LIMIT = 8",\n        "_DOCS_STATUS_MODULE_LIMIT = 0  # mutation: hide module recovery inventory",\n        FULL_GATE,\n    ),\n    Mutant(\n        "module_recovery_reason_projection_guard",\n        "docmancer/docs/interfaces/mcp/context_tools.py",\n        "_MODULE_RECOVERY_REASON_CODES = frozenset({\\n    \\\"module_ambiguous\\\", \\\"module_not_found\\\", \\\"no_module_docs\\\",\\n})",\n        "_MODULE_RECOVERY_REASON_CODES = frozenset({\\n    \\\"module_not_found\\\", \\\"no_module_docs\\\",\\n})  # mutation: hide ambiguous-module recovery metadata",\n        FULL_GATE,\n    ),\n)\n'''
    replace_once(path, old, new)


def update_readme() -> None:
    path = ROOT / "eval/agent_developer_v2/README.md"
    path.write_text('''# Agent Developer adversarial v2\n\nThis provider-free gate extends Agent Developer Protocol v1 without changing its frozen corpus. V1 must remain 11/11 target-green; v2 adds 27 reviewed architectural scenarios and measures every model-visible DocAtlas projection.\n\nThe v2 corpus covers bounded definition/behavior/requirements/project-policy packets, exact module-name/path resolution, bidirectional module isolation, project-vs-module leakage, cross-module evidence, multi-scope trajectories, stale project/module recovery, dependency-prefetch recovery, traversal/absolute/prefix/case/long-path safety, and five-way module-name ambiguity with a bounded `docs_status` recovery hop and exact retry.\n\nRun the deterministic gate with:\n\n```bash\npython scripts/run_agent_developer_adversarial_gate.py\n```\n\nHard invariants:\n\n- Agent Developer v1 remains target-green;\n- every `get_docs_context`, `docs_status`, and recovery projection is charged at its actual model-visible size;\n- every complete trajectory is <= 2,000 model-visible tokens;\n- requested `packet_tokens` and per-call ceilings are never exceeded;\n- exact module scope, returned recovery candidates, and path identity remain fail-closed;\n- forbidden-source contamination is zero;\n- stale or dependency-missing evidence returns typed recovery instead of edit authorization;\n- setup-only adversarial fixture files are path-bounded, byte-bounded, temporary, and never alter the frozen v1 corpus.\n\nThe companion mutation gate:\n\n```bash\npython scripts/run_agent_developer_adversarial_mutation_gate.py\n```\n\nIt kills nine v2-critical mutants covering per-call/trajectory token ceilings, contamination, scope drift, unreturned retry paths, insufficient-evidence edit readiness, production ambiguity rejection, bounded `docs_status` module inventory, and ambiguity recovery projection. The existing repository critical-mutation gate remains separate and runs first.\n''', encoding="utf-8")


def main() -> None:
    update_cases()
    update_gate()
    update_status_projection()
    update_mutations()
    update_readme()
    print("materialized PR106 yellow gates: 27 cases, bounded status compatibility, 9 v2 mutants")


if __name__ == "__main__":
    main()
