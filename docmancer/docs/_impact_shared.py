from __future__ import annotations

import ast
import json
import os
import re
import shlex
import subprocess
import threading
from collections import defaultdict
from pathlib import Path
from typing import Any

from docmancer.docs.project import DOC_DIRECTORIES, DOC_FILE_EXTENSIONS, ROOT_DOC_FILES, ProjectMetadataReader
from docmancer.docs.application.project_section_index import ProjectSectionIndexReader
from docmancer.docs.section_metadata import SECTION_PARSE_REASON_CODES, extract_section_metadata_result


_MODULE_ROOTS = {"packages", "apps", "services", "modules", "libs", "crates", "plugins", "components"}
_LIB_MODULE_ROOTS = {"modules", "features"}
_DEPENDENCY_FILES = {
    "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "pubspec.yaml", "pubspec.lock", "Cargo.toml", "Cargo.lock",
    "pyproject.toml", "poetry.lock", "uv.lock", "requirements.txt",
}
_MAX_CHANGED_FILES = 500
_MAX_SECTION_CANDIDATES = 200
_MAX_SECTION_CANDIDATES_EVALUATED = 2000
_MAX_DOCS_ANALYZED = 500
_MAX_FALLBACK_DOCS = 5
_MAX_OUTPUT_BYTES = 32 * 1024
_MAX_PATCH_BYTES = 2 * 1024 * 1024
_MAX_GIT_STATUS_BYTES = 4 * 1024 * 1024
_MAX_GIT_STDERR_BYTES = 64 * 1024
_MAX_GIT_PATHSPEC_BYTES = 256 * 1024
_GIT_DEADLINE_SECONDS = 15.0
_MAX_SYMBOLS = 256
_MAX_SYMBOL_EVIDENCE = 1000
_MAX_DOC_BYTES = 16 * 1024 * 1024
_SYMBOL_PATTERNS = {
    ".py": re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)"),
    ".js": re.compile(r"^\s*(?:export\s+)?(?:async\s+)?(?:function|class)\s+([A-Za-z_$][A-Za-z0-9_$]*)|^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)"),
    ".jsx": re.compile(r"^\s*(?:export\s+)?(?:async\s+)?(?:function|class)\s+([A-Za-z_$][A-Za-z0-9_$]*)|^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)"),
    ".ts": re.compile(r"^\s*(?:export\s+)?(?:declare\s+)?(?:async\s+)?(?:function|class|interface|type|enum)\s+([A-Za-z_$][A-Za-z0-9_$]*)|^(?:export\s+)?(?:declare\s+)?(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)"),
    ".tsx": re.compile(r"^\s*(?:export\s+)?(?:declare\s+)?(?:async\s+)?(?:function|class|interface|type|enum)\s+([A-Za-z_$][A-Za-z0-9_$]*)|^(?:export\s+)?(?:declare\s+)?(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)"),
    ".dart": re.compile(r"^\s*(?:abstract\s+)?(?:class|enum|mixin|extension|typedef)\s+([A-Za-z_][A-Za-z0-9_]*)|^\s*(?!(?:return|await|throw|yield|if|for|while|switch|new)\b)(?:[A-Za-z_][A-Za-z0-9_<>,?\[\] ]+\s+)+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
}

__all__=[n for n in globals() if not n.startswith('__')]
