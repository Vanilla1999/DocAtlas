"""Implementation shard 5 for execution."""
from __future__ import annotations

from ._execution_shared import *  # noqa: F401,F403

from ._execution_part01 import build_tool_policy, capture_patch, fresh_run_environment
from ._execution_part03 import prepare_docatlas

def run_docatlas_tool_visibility_canary(runner: AgentRunner, model: str, timeout_seconds: int, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="docatlas-tool-canary-"))
    try:
        (workspace / "README.md").write_text("# Canary Repo\n\nThis repository is used to verify documentation-context tool visibility.\n", encoding="utf-8")
        subprocess.run(["git", "init"], cwd=workspace, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        subprocess.run(["git", "config", "user.email", "benchmark@example.invalid"], cwd=workspace, check=False)
        subprocess.run(["git", "config", "user.name", "Task Benchmark"], cwd=workspace, check=False)
        subprocess.run(["git", "add", "."], cwd=workspace, check=False)
        subprocess.run(["git", "commit", "-m", "canary base"], cwd=workspace, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        policy_path, mcp_config = build_tool_policy("docatlas_tool_optional", output_dir)
        env = fresh_run_environment(output_dir)
        prepare_docatlas(TaskSpec(
            task_id="docatlas_tool_visibility_canary",
            task_type="curated",
            suite="differentiation",
            repo="fixture://docatlas_tool_visibility_canary",
            base_commit="fixture-base",
            issue_text="Ask the available DocAtlas/documentation-context MCP get_docs_context tool what documentation context is available for this repository. Do not edit files.",
            language="text",
            ecosystem="python",
            dependencies=(),
            setup_command="",
            test_command="true",
        ), workspace, output_dir, env)
        request = AgentRunRequest(
            task_id="docatlas_tool_visibility_canary",
            condition_id="docatlas_tool_visibility_canary",
            workspace=workspace,
            prompt="Ask the available DocAtlas/documentation-context MCP get_docs_context tool what documentation context is available for this repository. Do not edit files.",
            model=model,
            timeout_seconds=timeout_seconds,
            max_turns=8,
            environment=env,
            mcp_config_path=mcp_config,
            tool_policy_path=policy_path,
            output_dir=output_dir,
        )
        runner_output = runner.run(request)
        patch_path, _, _, changed = capture_patch(workspace, output_dir)
        audit = audit_trajectory("docatlas_tool_optional", Path(runner_output.trajectory_path) if runner_output.trajectory_path else None, output_dir / "policy_audit.json")
        response_saved = False
        if runner_output.trajectory_path and Path(runner_output.trajectory_path).exists():
            trajectory_text = Path(runner_output.trajectory_path).read_text(encoding="utf-8")
            response_saved = "get_docs_context" in trajectory_text or "docmancer-docs" in trajectory_text
            (output_dir / "docatlas_tool_response_excerpt.txt").write_text(trajectory_text[:8000], encoding="utf-8")
        get_docs_context_seen = False
        if runner_output.trajectory_path and Path(runner_output.trajectory_path).exists():
            get_docs_context_seen = "get_docs_context" in Path(runner_output.trajectory_path).read_text(encoding="utf-8")
        verified = audit.docatlas_calls > 0 and get_docs_context_seen and response_saved and not patch_path.read_text(encoding="utf-8").strip()
        payload = {
            "docatlas_tool_visibility_verified": verified,
            "status": "passed" if verified else "failed",
            "docatlas_calls": audit.docatlas_calls,
            "agent_docatlas_calls": audit.docatlas_calls,
            "tool_name_seen": audit.docatlas_tool_name_seen,
            "get_docs_context_seen": get_docs_context_seen,
            "response_saved": response_saved,
            "trajectory_path": runner_output.trajectory_path,
            "no_code_edits": not patch_path.read_text(encoding="utf-8").strip() and not changed,
            "failure_reason": None if verified else "DocAtlas tool call not observed, response not saved, or files were edited",
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }
        (output_dir / "docatlas_tool_visibility_canary.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return payload
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def runner_verification_payload(capabilities: RunnerCapabilities) -> dict[str, Any]:
    return {
        "runner": capabilities.runner_id,
        "version": capabilities.version,
        "causal_patch_runner_verified": capabilities.verified and capabilities.structured_trajectory and capabilities.patch_capture and capabilities.tool_isolation and capabilities.mcp_isolation and capabilities.independent_process,
        "efficiency_metrics_verified": capabilities.token_usage,
        "hard_turn_limit_verified": capabilities.hard_turn_limit,
        "trajectory_format": "stream-json normalized to trajectory.normalized.json" if capabilities.structured_trajectory else "unverified",
        "tool_isolation": "strict MCP config plus allowed/disallowed tools plus trajectory audit" if capabilities.tool_isolation else "unverified",
        "network_enforcement": "policy_and_trajectory_audit",
        "notes": capabilities.verification_notes,
    }

__all__=['run_docatlas_tool_visibility_canary', 'runner_verification_payload']
