from __future__ import annotations

import hashlib
import json
import os
import random
import re
import shlex
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eval.task_level.conditions import CONDITIONS, TOOL_REQUIRED_ONCE_INSTRUCTION
from eval.task_level.artifact_hygiene import diff_stats_from_patch, is_runtime_artifact, write_patch_hygiene_artifacts
from eval.task_level.context.action_checklist import build_action_checklist, save_action_checklist
from eval.task_level.context.patch_constraints import build_patch_constraint_packet, save_patch_constraint_packet
from docmancer.docs.interfaces.mcp.context_tools import bounded_retrieval_issues
from eval.task_level.evaluators.actionability import evaluate_actionability
from eval.task_level.evaluators.constraint_validation import validate_patch_against_constraints
from eval.task_level.evaluators.contract import evaluate_contract
from eval.task_level.evaluators.docatlas_utilization import evaluate_docatlas_utilization
from eval.task_level.evaluators.patch import forbidden_changed_paths
from eval.task_level.evaluators.patch_constraints import evaluate_patch_constraint_usage, load_patch_constraint_packet
from eval.task_level.evaluators.policy import audit_trajectory
from eval.task_level.evaluators.task_contract import ContractValidation, SemanticCheck, evaluate_patch_surface, evaluation_contract_registry_sha256, evaluation_contract_sha256, load_effective_task23_protocol_tasks, load_task_evaluation_contracts, run_compile_gate, validate_task_evaluation_artifacts, validate_task_evaluation_contract
from eval.task_level.evaluators.tests import CommandResult, run_command
from eval.task_level.fixtures.builder import copy_hidden_tests, materialize_fixture
from eval.task_level.isolated_delivery import (
    DelegationEnvelope,
    HostEvidenceSnapshot,
    IsolatedDeliveryError,
    IsolatedWorker,
    TASK33_QUERY_DERIVATION,
    derive_task33_retrieval_query,
    deliver_with_exploratory_worker,
    deliver_with_isolated_worker,
    missing_packet_evidence_categories,
    missing_packet_evidence_paths,
    persist_host_evidence,
)
from eval.task_level.runners.base import AgentRunRequest, AgentRunner, RunnerCapabilities
from eval.task_level.sandbox_execution import (
    configured_runtime_root,
    persist_boundary,
    verified_task33_sandbox,
)
from eval.task_level.schemas import RESULTS_ROOT, TASK_LEVEL_ROOT, RunMetrics, TaskSpec
from eval.task_level.task33_pilot import (
    TASK33C_AGENT_TURN_LIMIT,
    TASK33C_EXPLORATORY_SMOKE_CONDITIONS,
    TASK33C_PILOT_CONDITIONS,
    TASK33C_PILOT_TASK_ID,
    TASK33C_REQUIRED_EVIDENCE_CATEGORIES,
    TASK33C_REQUIRED_EVIDENCE_PATHS,
    TASK33C_REQUIRED_TARGET_PATHS,
    build_task33c_validation_evidence,
)


RUNTIME_ROOT = TASK_LEVEL_ROOT / "runtime"
INFRASTRUCTURE_FAILURE_STATUSES = frozenset({
    "runner_unavailable",
    "runner_failed",
    "condition_setup_failed",
    "timeout",
})






ALLOWED_PATCH_PREFIXES = (
    "src/",
    "tests/",
    "lib/",
    "android/",
    "example/",
    "ViScanner/",
    "ViScannerAIDL/",
    "ViScannerService/",
    "README.md",
    "ARCHITECTURE.md",
    "docs/",
    "pyproject.toml",
    "pubspec.yaml",
    "pubspec.lock",
)
DOCATLAS_CONDITIONS = {
    "docatlas_snippet_first",
    "docatlas_tool_optional",
    "docatlas_tool_recommended",
    "docatlas_context_injected",
    "docatlas_action_checklist_injected",
    "docatlas_patch_constraints_injected",
    "docatlas_patch_constraints_workflow",
    "docatlas_action_checklist_only",
    "docatlas_tool_required_once",
    "docatlas_bounded_direct",
    "docatlas_bounded_subagent",
}
CONTEXT_INJECTION_LIMIT_CHARS = 10000
AUDITED_EXTERNAL_CONTEXT_ROOT = TASK_LEVEL_ROOT / "external_context"
TASK33_EVALUATION_CONTRACTS = load_task_evaluation_contracts()
TASK23_PROTOCOL_TASKS = load_effective_task23_protocol_tasks()
BOUNDED_DIRECT_EXECUTION_POLICY = """Host execution policy:
- The cited project docs have already been reduced to the source-backed patch contract below.
- Do not reread cited project docs unless an explicit uncertainty requires it.
- Read only target implementation files needed for the edit.
- Do not guess test paths; use only checks supplied by the contract.
- Allow at most one RED validation run and one GREEN validation run.
- After GREEN, verify the diff against every contract item.
- Stop when the contract is satisfied and the supplied validation is GREEN.
"""










_SHELL_TOOL_NAMES = frozenset({"bash", "shell", "command", "command_execution"})
_SUCCESS_STATUSES = frozenset({"completed", "success", "succeeded", "ok"})
_FAILURE_STATUSES = frozenset({"failed", "failure", "error", "cancelled", "canceled", "timeout", "timed_out"})

__all__=[n for n in globals() if not n.startswith('__')]
