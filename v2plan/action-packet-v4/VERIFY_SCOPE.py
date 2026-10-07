"""Check changed-path ownership and unchanged protected tracked source offline."""
import ast
from pathlib import Path
import subprocess

BASE = "b89fa3cc16534445501bab14e0d63e099e9f61f6"
SOURCE_FILES = {
    "docmancer/docs/application/action_packet.py",
    *{f"docmancer/docs/application/_action_packet_{part}.py" for part in (
        "shared", "part01", "part02", "part03", "part04",
    )},
    "docmancer/docs/application/evidence_models.py",
    "docmancer/docs/application/evidence_requirements.py",
    "docmancer/docs/application/evidence_candidates.py",
    *{f"docmancer/docs/domain/_answer_units_{part}.py" for part in (
        "shared", "part01", "part02",
    )},
    "docmancer/docs/application/evidence_selection.py",
    *{f"docmancer/docs/application/_evidence_selection_{part}.py" for part in (
        "shared", "part01", "part02", "part03",
    )},
    "docmancer/docs/application/model_visible_projection.py",
    "docmancer/docs/interfaces/mcp/context_tools.py",
    "docmancer/docs/interfaces/mcp/output_contract.py",
    "docmancer/mcp/_docs_server_part01.py",
    "docmancer/mcp/_docs_server_schema.py",
    "docmancer/mcp/_docs_server_tool_data.py",
    "eval/evidence_selection_quality.py",
    "eval/answer_quality_runner.py",
    "eval/answer_quality_gate.py",
    *{f"eval/task_level/{part}.py" for part in (
        "_github_models_shared", "_github_models_part01", "task33_validation",
        "task33_codex_exploratory", "runners/codex", "_execution_part03",
        "_isolated_delivery_shared", "_isolated_delivery_part02",
        "_execution_part01", "_execution_part02", "_execution_part04",
        "_one_call_agent_loop_core", "_github_models_part02", "task33_pilot",
        "evaluators/actionability", "evaluators/docatlas_utilization", "evaluators/policy",
        "report", "_execution_shared",
    )},
}
NEW_TESTS = {
    f"tests/test_action_packet_v4_{owner}.py" for owner in (
        "contract", "selection", "public", "integrated", "eval",
    )
}
NEW_SHARDS = {
    f"tests/diagnostic_labels.action_packet_v4_{owner}.json" for owner in (
        "a", "b", "c", "integrated", "eval",
    )
}


def git(*args):
    return subprocess.check_output(["git", *args]).decode()


def verify():
    changed = set(git("diff", "--name-only", BASE).splitlines())
    changed.update(git("ls-files", "--others", "--exclude-standard").splitlines())
    unexpected = sorted(
        path for path in changed
        if path not in SOURCE_FILES | NEW_TESTS | NEW_SHARDS
        and not path.startswith("v2plan/action-packet-v4/")
    )
    assert not unexpected, unexpected
    # Old tests, conftest, gold, NEXT work and historical reports are outside
    # the write allowlist, so any such changed tracked path fails above.
    baseline_paths = set(git("ls-tree", "-r", "--name-only", BASE).splitlines())
    preserved = baseline_paths - changed
    count = 0
    for path in sorted(SOURCE_FILES | NEW_TESTS):
        source = Path(path)
        if source.exists():
            ast.parse(source.read_text(encoding="utf-8"), filename=path)
            count += 1
    subprocess.run(["git", "diff", "--check", BASE], check=True)
    print(f"ownership PASS: {len(changed)} changed paths")
    print(f"protected tracked preservation PASS: {len(preserved)} unchanged baseline paths")
    print(f"syntax PASS: {count} source/new-test modules")
    print("diff whitespace PASS")
    print("Primary user branch/artifacts require separate read-only git-status check.")


if __name__ == "__main__":
    verify()
