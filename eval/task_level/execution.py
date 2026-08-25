from __future__ import annotations

import json
from pathlib import Path

from ._execution_shared import *  # noqa: F401,F403

from ._execution_part01 import *  # noqa: F401,F403

from ._execution_part02 import *  # noqa: F401,F403

from ._execution_part03 import *  # noqa: F401,F403

from ._execution_part04 import *  # noqa: F401,F403

from ._execution_part05 import *  # noqa: F401,F403

__all__=[n for n in globals() if not n.startswith("__")]

from docmancer._internal.shard_compat import install_function_shard_bridge as _install_function_shard_bridge
_install_function_shard_bridge(
    __name__,
    [
        "eval.task_level._execution_shared",
        "eval.task_level._execution_part01",
        "eval.task_level._execution_part02",
        "eval.task_level._execution_part03",
        "eval.task_level._execution_part04",
        "eval.task_level._execution_part05",
    ],
)

from .evaluators.process_quality import evaluate_process_quality as _evaluate_process_quality

_evaluate_agent_patch_without_process_quality = evaluate_agent_patch


def evaluate_agent_patch(
    task: TaskSpec,
    workspace: Path,
    run_output_dir: Path,
    condition_id: str,
    trajectory_path: str | None,
    runner_output: Any,
    *,
    evaluation_backend: str = "docker",
) -> dict[str, Any]:
    """Evaluate the patch and attach observable, fail-closed process metrics."""

    result = _evaluate_agent_patch_without_process_quality(
        task,
        workspace,
        run_output_dir,
        condition_id,
        trajectory_path,
        runner_output,
        evaluation_backend=evaluation_backend,
    )
    process_quality = _evaluate_process_quality(
        result,
        trajectory_path=Path(trajectory_path) if trajectory_path else None,
    )
    result["process_quality"] = process_quality
    metrics = result.get("metrics")
    if isinstance(metrics, dict):
        breadth = process_quality["validation_breadth"]
        robustness = process_quality["patch_robustness"]
        search = process_quality["search_efficiency"]
        provider = process_quality["provider_efficiency"]
        metrics.update({
            "first_edit_correctness": process_quality["first_edit_correctness"],
            "first_edit_correctness_status": process_quality["first_edit_correctness_status"],
            "repair_count": process_quality["repair_count"],
            "regression_count": process_quality["regression_count"],
            "validation_test_runs_observed": breadth["test_runs_observed"],
            "validation_distinct_test_commands": breadth["distinct_test_commands"],
            "patch_robust": robustness["robust"],
            "evidence_found_per_exploration_call": search["evidence_found_per_exploration_call"],
            "correct_runs_per_100k_uncached_tokens": provider["correct_runs_per_100k_uncached_tokens"],
        })
    (run_output_dir / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return result
