from __future__ import annotations

from pathlib import Path


benchmark_path = Path("eval/agent_developer_v1/installed_mcp_benchmark.py")
text = benchmark_path.read_text(encoding="utf-8")

old_env = '''        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env.pop("DOCMANCER_HOME", None)
        env.update(
            {
                "HOME": str(user_home),
                "USERPROFILE": str(user_home),
                "DOCATLAS_HOME": str(home),
                "DOCMANCER_OFFLINE": "1",
                "NO_PROXY": "*",
            }
        )
'''
new_env = '''        env = {
            key: value
            for key in (
                "PATH",
                "SYSTEMROOT",
                "WINDIR",
                "TMPDIR",
                "TEMP",
                "TMP",
                "LANG",
                "LC_ALL",
                "PYTHONUTF8",
            )
            if (value := os.environ.get(key))
        }
        env.update(
            {
                "HOME": str(user_home),
                "USERPROFILE": str(user_home),
                "DOCATLAS_HOME": str(home),
                "DOCMANCER_OFFLINE": "1",
                "NO_PROXY": "*",
            }
        )
'''
assert text.count(old_env) == 1, text.count(old_env)
text = text.replace(old_env, new_env, 1)

old_reason = '"reason": str(action["reason"]),'
new_reason = '''"reason_sha256": hashlib.sha256(
                                    str(action["reason"]).encode("utf-8")
                                ).hexdigest(),'''
assert text.count(old_reason) == 1, text.count(old_reason)
text = text.replace(old_reason, new_reason, 1)

marker = "\n\ndef _aggregate(\n"
helper = '''

def _evaluator_failure_stages(score: dict[str, Any]) -> set[str]:
    # Empty trajectories already carry model-format/adapter attribution. Do not
    # convert the scorer's necessarily-false scope flag into a retrieval claim.
    if int(score.get("context_call_count") or 0) == 0:
        return set()
    errors = [str(value).lower() for value in score.get("errors") or ()]
    stages: set[str] = set()
    if (
        score.get("scope_contract_ok") is False
        or any(
            token in error
            for error in errors
            for token in (
                "source",
                "scope",
                "module candidate",
                "module_path",
            )
        )
    ):
        stages.add("retrieval")
    if (
        int(score.get("false_supported") or 0) > 0
        or any(
            token in error
            for error in errors
            for token in (
                "supported result",
                "support",
                "expected status",
                "answer_available",
            )
        )
    ):
        stages.add("support")
    if (
        score.get("recovery_contract_ok") is False
        or any(
            token in error
            for error in errors
            for token in (
                "recovery",
                "docs_status",
                "next action",
                "recommended action",
            )
        )
    ):
        stages.add("recovery")
    return stages


def _aggregate(
'''
assert text.count(marker) == 1, text.count(marker)
text = text.replace(marker, helper, 1)

score_line = "            score = redact(score, project)"
score_replacement = (
    "            failure_stages.extend(_evaluator_failure_stages(score))\n"
    "            score = redact(score, project)"
)
assert text.count(score_line) == 1, text.count(score_line)
text = text.replace(score_line, score_replacement, 1)
benchmark_path.write_text(text, encoding="utf-8")

self_test_path = Path("scripts/installed_mcp_contract_self_test.py")
self_test = self_test_path.read_text(encoding="utf-8")
assert self_test.count("import copy\n") == 1
self_test = self_test.replace(
    "import copy\n",
    "import copy\nfrom pathlib import Path\n",
    1,
)
main_marker = "\n\ndef main() -> int:\n"
insertion = '''

def test_server_environment_finish_and_stage_logic_are_hardened() -> None:
    source = Path(
        "eval/agent_developer_v1/installed_mcp_benchmark.py"
    ).read_text(encoding="utf-8")
    assert "env = dict(os.environ)" not in source
    assert '"OPENAI_API_KEY"' not in source
    assert '"GH_TOKEN"' not in source
    assert '"reason": str(action["reason"])' not in source
    assert '"reason_sha256": hashlib.sha256(' in source
    assert "_evaluator_failure_stages(score)" in source


def main() -> int:
'''
assert self_test.count(main_marker) == 1, self_test.count(main_marker)
self_test = self_test.replace(main_marker, insertion, 1)
tuple_marker = '''        test_unknown_origin_and_failure_stage_fail_closed,
    )
'''
tuple_replacement = '''        test_unknown_origin_and_failure_stage_fail_closed,
        test_server_environment_finish_and_stage_logic_are_hardened,
    )
'''
assert self_test.count(tuple_marker) == 1, self_test.count(tuple_marker)
self_test = self_test.replace(tuple_marker, tuple_replacement, 1)
self_test_path.write_text(self_test, encoding="utf-8")
