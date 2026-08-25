from __future__ import annotations

import json
import fnmatch
import hashlib
import re
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from docmancer.docs.domain.code_graph import build_code_graph_context_items, build_project_code_graph
from docmancer.docs.domain.normative_language import (
    has_normative_language,
    is_python_declaration,
    python_declaration_line_indexes,
)
from docmancer.docs.domain.source_map import build_project_repo_map, build_project_source_evidence
from docmancer.docs.models import DependencyObservation, PatchConstraint, PatchConstraintPacket

DEFAULT_MAX_CONSTRAINTS = 12
DEFAULT_MAX_TOKENS = 1200
LOCKFILES = {
    "pubspec.lock",
    "poetry.lock",
    "uv.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "Cargo.lock",
    "go.sum",
}
MANIFESTS = {"pubspec.yaml", "pyproject.toml", "requirements.txt", "package.json", "Cargo.toml", "go.mod"}
DEPENDENCY_FILES = LOCKFILES | MANIFESTS
GENERATED_PATTERNS = (
    "*.g.dart",
    "*.freezed.dart",
    "*.pb.go",
    "*.pb.dart",
    "*.generated.*",
    "GeneratedPluginRegistrant.*",
    "generated/",
    "dist/",
)
GENERATED_ARTIFACT_SOURCE_PATTERNS = (
    "eval/task_level/results/**",
    ".docatlas/**",
    ".docmancer/**",
)
PATCH_REVIEW_DIR_NAMES = {"patch-review", "patch_review"}
PATCH_REVIEW_ARTIFACT_NAMES = {
    "review_summary.md",
    "constraints.md",
    "constraints.json",
    "validation.json",
    "changed_files.json",
    "patch.diff",
    "patch.raw.diff",
    "git_status.txt",
    "git_status.raw.txt",
    "changed_files.raw.json",
    "patch_hygiene.json",
    "untracked_files.json",
    "ignored_runtime_artifacts.json",
    "review_notes.md",
    "checks.txt",
}
DOGFOOD_TASK_ARTIFACT_NAMES = {"task.md", "review_notes.md"}
GENERIC_CALL_SYMBOLS = {
    "read", "watch", "of", "push", "pop", "map", "where", "firstWhere",
    "maybeWhen", "when", "setState",
}
ASSET_TASK_TERMS = {
    "asset", "assets", "icon", "image", "logo", "svg", "png", "jpg",
    "resource", "generated asset", "иконка", "изображение", "логотип",
    "ресурс", "ассет", "картинка",
}
ASSET_REGISTRY_FILENAMES = {"assets.dart", "asset.dart", "assets.gen.dart", "assets.g.dart"}
PHRASE_ALIASES = {
    "закрыть меню": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "закрывать меню": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "закрытие меню": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "закрыть шторку": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "закрывать шторку": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "закрытие шторки": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "закрыть панель": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "закрывать панель": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "скрыть меню": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "скрывать меню": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "скрыть шторку": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "скрывать шторку": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "close menu": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "closing menu": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "close drawer": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "closing drawer": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "hide menu": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "hide drawer": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "dismiss menu": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "dismiss drawer": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "быстрая информация": ("openInfo", "info", "information"),
    "scan doc": ("goToScanDocInit", "scanDoc", "scan", "document"),
    "сканирование документов": ("goToScanDocInit", "scanDoc", "scan", "document"),
}
SYMBOL_SOURCE_SUFFIXES = (".py", ".dart", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".kt", ".java", ".md", ".txt")
ARCHITECTURE_DOC_RE = re.compile(
    r"(^|/)(architecture\.md|architecture/|adr/|adrs/|contributing\.md|readme[^/]*\.(md|txt)|adr[^/]*\.md)$",
    re.I,
)
KEYWORD_RE = re.compile(
    r"\b(must(?:\s+not)?|should(?:\s+not)?|belongs to|owned by|owns|source[- ]of[- ]truth|canonical|single source|do not duplicate|do not bypass|do not hardcode|layer|service layer|domain layer|application layer|presentation layer|provider delegates|repository owns|adapter owns)\b",
    re.I,
)
NON_ACTIONABLE_CONSTRAINT_HEADING_RE = re.compile(
    r"^(rules?|constraints?|requirements?|notes?|guidelines?)\s+"
    r"(that\s+)?(must|should|may|must\s+not|should\s+not)?\s*"
    r"(not\s+)?(be\s+)?(violated|followed|checked)?\s*:?\s*$",
    re.I,
)
TREE_GLYPH_RE = re.compile(r"[│├└┬┴┼─]{2,}|^[│├└┬┴┼─]")
OWNER_SUFFIX_RE = re.compile(
    r"(Service|Repository|Controller|Notifier|Bloc|Cubit|Provider|Adapter|Manager|Gate|"
    r"UseCase|Store|Module|Screen|Route|Router|Policy|Gateway|Client|Api|API|"
    r"Dao|DAO|DataSource|HttpServer|Server)$"
)
EXCLUDED_SOURCE_PARTS = {
    "eval",
    "fixtures",
    "results",
    "runtime",
    "workspaces",
    "hidden_tests",
    "oracles",
    ".cache",
    ".dart_tool",
    ".pytest_cache",
    ".uv",
    "uv-cache",
    "archive-v0",
    "materialized",
    "node_modules",
    "build",
    ".venv",
    "venv",
    ".git",
    "__pycache__",
}

__all__ = [name for name in globals() if not name.startswith('__')]
