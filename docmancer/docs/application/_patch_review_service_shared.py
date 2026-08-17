from __future__ import annotations

import json
import re
import subprocess
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eval.task_level.artifact_hygiene import apply_patch_hygiene, is_runtime_artifact, parse_status_paths

from docmancer.docs.service import LibraryDocsService

LOW_VALUE_SYMBOLS = {
    "package", "import", "export", "part", "TODO", "FIXME", "tr", "l10n",
    "localization", "onHide", "onShow", "onTap", "onPressed",
    "barrierDismissible", "context", "build", "Widget", "State",
    "StatelessWidget", "StatefulWidget", "Text", "title", "VoidCallback",
    "onRequest",
}
DOGFOOD_MEMO_REASONS = {"dogfood_result_memo", "dogfood_task_artifact"}
MAX_PR_COMMENT_CHARS = 60_000
MAX_PR_COMMENT_FIELD_CHARS = 2_000
PATCH_REVIEW_SCHEMA_VERSIONS = {
    "review_summary_manifest.json": 1,
    "review_summary_quality.json": 2,
    "review_summary_actions.json": 1,
    "review_summary_pr_comment.json": 2,
    "review_summary_trace.json": 1,
    "review_summary_bot_bundle.json": 3,
    "constraint_coverage.json": 1,
}
TASK_TOKEN_STOPWORDS = {
    "add", "and", "before", "change", "check", "current", "diff", "file",
    "for", "from", "into", "keep", "make", "must", "path", "patch", "pr",
    "review", "task", "test", "the", "this", "with", "without",
}

__all__ = [name for name in globals() if not name.startswith('__')]
