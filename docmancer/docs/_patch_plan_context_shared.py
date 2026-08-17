from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterator, Sequence

from docmancer.docs.dart_package_config import resolve_dart_package_roots
from docmancer.docs.domain.code_graph import build_project_code_graph, code_graph_diagnostics


PATCH_PLAN_CONTEXT_SCHEMA_VERSION = "patch-plan-context-1"
PATCH_PLAN_CONTEXT_TOOL = "get_patch_plan_context"
_PATCH_PLAN_NOT_IMPLEMENTED_WARNING = "Patch planning source analysis is not implemented yet."
_PATCH_PLAN_LIMITED_WARNING = "Patch planning source discovery is lightweight; dependency analysis is Dart/Flutter package_config only."
_SOURCE_SUFFIXES = {".dart", ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".swift", ".go", ".rs"}
_DART_SOURCE_SUFFIXES = {".dart"}
_SKIPPED_PATH_PARTS = {".dart_tool", ".git", ".gradle", ".idea", ".pub-cache", "fake_pub_cache", "build", "cache", "generated"}
_DEP_SKIPPED_PATH_PARTS = {".dart_tool", ".git", ".gradle", ".idea", "build", "cache", "generated"}
_SKIPPED_SUFFIXES = (".g.dart", ".freezed.dart", ".gr.dart")
_SYMBOL_DEF_RE = re.compile(r"\b(?:class|mixin|enum|extension|typedef|void|Widget|Future<[^>]+>|[A-Z][A-Za-z0-9_<>?]*)\s+([A-Za-z_][A-Za-z0-9_]*)\b")
_IMPORT_EXPORT_RE = re.compile(r"^\s*(?:import|export)\s+['\"]([^'\"]+)['\"]", re.MULTILINE)
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_\.]*")

__all__=[n for n in globals() if not n.startswith('__')]
