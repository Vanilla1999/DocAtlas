from __future__ import annotations

import hashlib
import json
import os
import signal
import shlex
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from docmancer.docs.application.action_packet import (
    build_action_packet,
    validate_action_packet,
)

from .conditions import TOOL_REQUIRED_ONCE_INSTRUCTION
from .isolated_delivery import (
    DelegationEnvelope,
    HostEvidenceSnapshot,
    IsolatedDeliveryError,
    IsolatedWorkerCapabilities,
    IsolatedWorkerOutput,
    WorkerUsage,
)
from .runners.base import AgentRunOutput, AgentRunRequest, RunnerCapabilities
from .sandbox_execution import DockerCommandSandbox, persist_boundary


GITHUB_MODELS_ENDPOINT = "https://models.github.ai/inference/chat/completions"
DEFAULT_GITHUB_MODEL = "openai/gpt-4o-mini"
OPENAI_API_ENDPOINT = "https://api.openai.com/v1/chat/completions"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini-2024-07-18"
_RUNNER_VERSION = "github-models-controlled-agent-v4-required-once"
_RUNNER_PROMPT_REVISION = "github-models-controlled-agent-v4-required-once"
_WORKER_PROMPT_REVISION = "task33c-evidence-selector-v2-full-snapshot"
_PROVIDER_INPUT_TOKEN_LIMIT = 7_000
_TASK33C_MAX_RUNNER_REQUESTS = 12
_MIN_REQUEST_INTERVAL_SECONDS = 6.2
_REQUEST_RATE_LOCK = threading.Lock()
_LAST_REQUEST_AT = 0.0
_PROCESS_REQUEST_COUNT = 0
_PROCESS_REQUEST_BUDGET = 53


@dataclass(frozen=True)
class HostedProviderConfig:
    provider_id: str
    runner_id: str
    runner_version: str
    endpoint: str
    default_model: str
    usage_filename: str
    request_id_headers: tuple[str, ...]
    extra_headers: tuple[tuple[str, str], ...] = ()
    minimum_request_interval_seconds: float = 0.0


GITHUB_MODELS_PROVIDER = HostedProviderConfig(
    provider_id="github-models",
    runner_id="github-models",
    runner_version=_RUNNER_VERSION,
    endpoint=GITHUB_MODELS_ENDPOINT,
    default_model=DEFAULT_GITHUB_MODEL,
    usage_filename="github_models_usage.json",
    request_id_headers=("x-github-request-id", "apim-request-id", "x-ms-request-id"),
    extra_headers=(("X-GitHub-Api-Version", "2026-03-10"),),
    minimum_request_interval_seconds=_MIN_REQUEST_INTERVAL_SECONDS,
)
OPENAI_API_PROVIDER = HostedProviderConfig(
    provider_id="openai-api",
    runner_id="openai-api",
    runner_version="openai-api-controlled-agent-v1-bounded-context",
    endpoint=OPENAI_API_ENDPOINT,
    default_model=DEFAULT_OPENAI_MODEL,
    usage_filename="openai_api_usage.json",
    request_id_headers=("x-request-id",),
)

__all__=[n for n in globals() if not n.startswith('__')]
