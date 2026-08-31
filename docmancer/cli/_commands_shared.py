from __future__ import annotations

import os
import json
import logging
import shlex
import shutil
import sqlite3
import sys
import warnings
import zipfile
from datetime import datetime, timezone
from importlib.util import find_spec
from pathlib import Path

import click

from docmancer.cli.client_identity import (
    AGENTS_MD_END as _AGENTS_MD_END,
    AGENTS_MD_START as _AGENTS_MD_START,
    PRIMARY_CONFIG_NAME,
    PROJECT_INSTALL_STATE as _PROJECT_INSTALL_STATE,
    SKILL_FILE_OWNER as _SKILL_FILE_OWNER,
    SKILL_ID,
    current_managed_block as _current_managed_block,
    ensure_user_home as _ensure_user_home,
    is_proven_docatlas_text as _is_proven_docatlas_text,
    primary_user_config_path as _primary_user_config_path,
    project_config_path as _project_config_path,
    resolved_user_home as _resolved_user_home,
)
from docmancer.cli.help import DocmancerCommand, DocmancerGroup, HELP_CONTEXT_SETTINGS, format_examples
from docmancer.cli.ui import BANNER_COLOR, BANNER_LINES, color_enabled, display_path, style


INSTALL_TARGETS = [
    "claude-code",
    "claude-desktop",
    "cline",
    "cursor",
    "codex",
    "codex-app",
    "codex-desktop",
    "gemini",
    "github-copilot",
    "opencode",
]

SETUP_PROFILES = ["cli-docs", "agent", "mcp-docs", "api-packs"]
RETRIEVAL_PROFILES = ["local-hybrid", "lexical-now", "cloud"]
DOCTOR_SEVERITIES = ["BLOCKER", "DEGRADED", "WARN", "INFO"]
DOCTOR_CHECK_GROUPS = ["config", "storage", "sqlite", "qdrant", "embeddings", "vectors", "sources", "extraction", "agent", "mcp-docs", "cloud"]


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

__all__=[n for n in globals() if not n.startswith('__')]
