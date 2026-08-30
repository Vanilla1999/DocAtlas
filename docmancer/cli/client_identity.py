from __future__ import annotations

from pathlib import Path

from docmancer.core.product_identity import (
    DEFAULT_HOME_NAME,
    PRIMARY_CONFIG_NAME,
    ensure_owned_home,
    resolve_home,
)

SKILL_ID = "docatlas"

AGENTS_MD_START = "<!-- docatlas:start -->"
AGENTS_MD_END = "<!-- docatlas:end -->"
SKILL_FILE_OWNER = "<!-- docatlas:managed-skill-file -->"

PROJECT_INSTALL_STATE = Path(".docatlas") / "agent-installs.json"

_DOCS_TOOL_SIGNATURE = ("get_docs_context", "prepare_docs", "docs_status")


def resolved_user_home(*, home_dir: str | Path | None = None) -> Path:
    """Resolve the user-level DocAtlas root."""

    return resolve_home(home_dir=home_dir).path


def ensure_user_home(*, home_dir: str | Path | None = None) -> Path:
    """Establish ownership before creating new user-level DocAtlas state."""

    resolution = resolve_home(home_dir=home_dir)
    return ensure_owned_home(resolution.path)


def primary_user_config_path(*, home_dir: str | Path | None = None) -> Path:
    return resolved_user_home(home_dir=home_dir) / PRIMARY_CONFIG_NAME


def project_config_path(root: str | Path = ".") -> Path:
    return Path(root) / PRIMARY_CONFIG_NAME


def is_proven_docatlas_text(text: str) -> bool:
    """Require a DocAtlas-specific executable/tool signature before legacy mutation."""

    return "doc-atlas" in text or all(tool in text for tool in _DOCS_TOOL_SIGNATURE)


def current_managed_block(text: str) -> tuple[int, int] | None:
    start = text.find(AGENTS_MD_START)
    end = text.find(AGENTS_MD_END)
    if start == -1 and end == -1:
        return None
    if start == -1 or end == -1 or start > end:
        raise ValueError("DocAtlas markers are incomplete or out of order")
    return start, end


__all__ = [
    "AGENTS_MD_END",
    "AGENTS_MD_START",
    "DEFAULT_HOME_NAME",
    "PRIMARY_CONFIG_NAME",
    "PROJECT_INSTALL_STATE",
    "SKILL_FILE_OWNER",
    "SKILL_ID",
    "current_managed_block",
    "ensure_user_home",
    "is_proven_docatlas_text",
    "primary_user_config_path",
    "project_config_path",
    "resolved_user_home",
]
