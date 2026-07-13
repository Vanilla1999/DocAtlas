from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


ConditionId = Literal[
    "repo_only",
    "repo_only_strict_offline",
    "repo_only_web_audited",
    "repo_plus_audited_external_context",
    "context7",
    "docatlas_evidence_first",
    "docatlas_snippet_first",
    "docatlas_tool_optional",
    "docatlas_tool_recommended",
    "docatlas_context_injected",
    "docatlas_action_checklist_injected",
    "docatlas_patch_constraints_injected",
    "docatlas_patch_constraints_workflow",
    "docatlas_action_checklist_only",
    "docatlas_tool_required_once",
    "docatlas_zero_setup",
]


@dataclass(frozen=True)
class DependencySpec:
    name: str
    version: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "DependencySpec":
        return cls(name=str(data["name"]), version=str(data["version"]))


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    task_type: Literal["real", "curated"]
    suite: Literal["comparable", "differentiation"]
    repo: str
    base_commit: str
    issue_text: str
    language: str
    ecosystem: str
    dependencies: tuple[DependencySpec, ...]
    setup_command: str
    test_command: str
    fail_to_pass_tests: tuple[str, ...] = ()
    pass_to_pass_tests: tuple[str, ...] = ()
    expected_docs_domains: tuple[str, ...] = ()
    expected_symbols: tuple[str, ...] = ()
    expected_project_docs: tuple[str, ...] = ()
    gold_patch_path: str = "private/oracle only"
    gold_context: str = "private/evaluator only"
    max_minutes: int = 20
    max_turns: int = 40
    max_input_tokens: int = 120_000
    max_output_tokens: int = 30_000
    source_project: str | None = None
    role: str = "candidate"
    differentiating: bool = True
    selection_status: str = "not_screened"
    selection_reason: str = ""
    docatlas_relevance: tuple[str, ...] = ()

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "TaskSpec":
        return cls(
            task_id=str(data["task_id"]),
            task_type=data["task_type"],
            suite=data["suite"],
            repo=str(data["repo"]),
            base_commit=str(data["base_commit"]),
            issue_text=str(data["issue_text"]),
            language=str(data["language"]),
            ecosystem=str(data["ecosystem"]),
            dependencies=tuple(DependencySpec.from_json(x) for x in data.get("dependencies", [])),
            setup_command=str(data.get("setup_command", "")),
            test_command=str(data["test_command"]),
            fail_to_pass_tests=tuple(data.get("fail_to_pass_tests", [])),
            pass_to_pass_tests=tuple(data.get("pass_to_pass_tests", [])),
            expected_docs_domains=tuple(data.get("expected_docs_domains", [])),
            expected_symbols=tuple(data.get("expected_symbols", [])),
            expected_project_docs=tuple(data.get("expected_project_docs", [])),
            gold_patch_path=str(data.get("gold_patch_path", "private/oracle only")),
            gold_context=str(data.get("gold_context", "private/evaluator only")),
            max_minutes=int(data.get("max_minutes", 20)),
            max_turns=int(data.get("max_turns", 40)),
            max_input_tokens=int(data.get("max_input_tokens", 120_000)),
            max_output_tokens=int(data.get("max_output_tokens", 30_000)),
            source_project=data.get("source_project"),
            role=str(data.get("role", "candidate")),
            differentiating=bool(data.get("differentiating", True)),
            selection_status=str(data.get("selection_status", "not_screened")),
            selection_reason=str(data.get("selection_reason", "")),
            docatlas_relevance=tuple(data.get("docatlas_relevance", [])),
        )


@dataclass(frozen=True)
class ToolPolicy:
    allow_docatlas: bool = False
    allow_context7: bool = False
    allow_web: bool = False
    docatlas_response_style: Literal["evidence-first", "snippet-first"] | None = None
    preindex: bool = False
    inject_docatlas_context: bool = False
    inject_action_checklist: bool = False
    inject_patch_constraints: bool = False
    inject_external_context: bool = False
    recommend_docatlas_before_edit: bool = False
    require_docatlas_call_before_edit: bool = False
    max_constraint_packet_tokens: int = 1200
    max_constraints: int = 12
    max_sources: int = 8


@dataclass(frozen=True)
class Condition:
    condition_id: ConditionId
    label: str
    tool_policy: ToolPolicy


@dataclass
class RunMetrics:
    wall_time_seconds: float | None = None
    time_to_first_edit: float | None = None
    time_to_first_test: float | None = None
    time_to_first_useful_context: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cached_input_tokens: int | None = None
    uncached_input_tokens: int | None = None
    reasoning_tokens: int | None = None
    agent_turns: int | None = None
    shell_calls: int = 0
    file_reads: int = 0
    file_searches: int = 0
    edit_calls: int = 0
    test_runs: int = 0
    docs_tool_calls: int = 0
    docs_setup_calls: int = 0
    network_calls: int = 0
    patch_files_changed: int = 0
    patch_lines_added: int = 0
    patch_lines_removed: int = 0
    api_hallucinations: int = 0
    wrong_version_api_uses: int = 0
    source_contamination: int = 0
    context_chunks_returned: int = 0
    context_chunks_opened: int = 0
    context_chunks_used_in_patch: int = 0
    context_precision: float | None = None
    context_recall: float | None = None
    injected_context_tokens: int | None = None
    checklist_tokens: int | None = None
    retrieved_context_tokens: int | None = None
    constraint_packet_tokens: int | None = None
    raw_doc_context_tokens: int | None = None


@dataclass
class RunResult:
    run_id: str
    task_id: str
    condition_id: str
    repeat: int
    status: str
    resolved: bool = False
    tests_passed: bool = False
    compile_success: bool = False
    patch_path: str | None = None
    trajectory_path: str | None = None
    metrics: RunMetrics = field(default_factory=RunMetrics)
    notes: list[str] = field(default_factory=list)


ROOT = Path(__file__).resolve().parents[2]
TASK_LEVEL_ROOT = ROOT / "eval" / "task_level"
TASKS_PATH = TASK_LEVEL_ROOT / "tasks.jsonl"
RESULTS_ROOT = TASK_LEVEL_ROOT / "results"
VALIDATION_ROOT = TASK_LEVEL_ROOT / "validation"
