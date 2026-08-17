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
# Skill install helpers
# ---------------------------------------------------------------------------

















_AGENTS_MD_START = "<!-- docmancer:start -->"
_AGENTS_MD_END = "<!-- docmancer:end -->"
_SKILL_FILE_OWNER = "<!-- docmancer:managed-skill-file -->"
_PROJECT_INSTALL_STATE = Path(".docmancer") / "agent-installs.json"






























# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

__all__=[n for n in globals() if not n.startswith('__')]
