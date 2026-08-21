from __future__ import annotations

from pathlib import Path

from docmancer.core.product_identity import (
    DEFAULT_HOME_NAME,
    LEGACY_CONFIG_NAME,
    PRIMARY_CONFIG_NAME,
    ensure_owned_home,
    resolve_home,
)

SKILL_ID = "docatlas"
LEGACY_SKILL_ID = "docmancer"

AGENTS_MD_START = "<!-- docatlas:start -->"
AGENTS_MD_END = "<!-- docatlas:end -->"
LEGACY_AGENTS_MD_START = "<!-- docmancer:start -->"
LEGACY_AGENTS_MD_END = "<!-- docmancer:end -->"
SKILL_FILE_OWNER = "<!-- docatlas:managed-skill-file -->"
LEGACY_SKILL_FILE_OWNER = "<!-- docmancer:managed-skill-file -->"

PROJECT_INSTALL_STATE = Path(".docatlas") / "agent-installs.json"
LEGACY_PROJECT_INSTALL_STATE = Path(".docmancer") / "agent-installs.json"

_DOCS_TOOL_SIGNATURE = ("get_docs_context", "prepare_docs", "docs_status")


def resolved_user_home(*, home_dir: str | Path | None = None) -> Path:
    """Resolve the user-level DocAtlas root without implicit ~/.docmancer fallback."""

    return resolve_home(home_dir=home_dir).path


def ensure_user_home(*, home_dir: str | Path | None = None) -> Path:
    """Establish ownership before creating new user-level DocAtlas state."""

    return ensure_owned_home(resolved_user_home(home_dir=home_dir))


def primary_user_config_path(*, home_dir: str | Path | None = None) -> Path:
    return resolved_user_home(home_dir=home_dir) / PRIMARY_CONFIG_NAME


def legacy_user_config_path(*, home_dir: str | Path | None = None) -> Path:
    return resolved_user_home(home_dir=home_dir) / LEGACY_CONFIG_NAME


def project_config_path(root: str | Path = ".") -> Path:
    return Path(root) / PRIMARY_CONFIG_NAME


def legacy_project_config_path(root: str | Path = ".") -> Path:
    return Path(root) / LEGACY_CONFIG_NAME


def legacy_skill_path(primary: Path) -> Path | None:
    """Return the old skills/docmancer path for a primary skills/docatlas path."""

    parts = list(primary.parts)
    try:
        index = len(parts) - 1 - parts[::-1].index(SKILL_ID)
    except ValueError:
        return None
    parts[index] = LEGACY_SKILL_ID
    return Path(*parts)


def is_proven_docatlas_text(text: str) -> bool:
    """Require a DocAtlas-specific executable/tool signature before legacy mutation."""

    return "doc-atlas" in text or all(tool in text for tool in _DOCS_TOOL_SIGNATURE)


def legacy_managed_block(text: str) -> tuple[int, int] | None:
    start = text.find(LEGACY_AGENTS_MD_START)
    end = text.find(LEGACY_AGENTS_MD_END)
    if start == -1 and end == -1:
        return None
    if start == -1 or end == -1 or start > end:
        if is_proven_docatlas_text(text):
            raise ValueError("legacy DocAtlas markers are incomplete or out of order")
        return None
    block_end = end + len(LEGACY_AGENTS_MD_END)
    if not is_proven_docatlas_text(text[start:block_end]):
        return None
    return start, end


def current_managed_block(text: str) -> tuple[int, int] | None:
    start = text.find(AGENTS_MD_START)
    end = text.find(AGENTS_MD_END)
    if start == -1 and end == -1:
        return None
    if start == -1 or end == -1 or start > end:
        raise ValueError("DocAtlas markers are incomplete or out of order")
    return start, end


def legacy_skill_is_fully_managed(text: str) -> bool:
    """Allow path migration only when the entire legacy file is demonstrably ours."""

    block = legacy_managed_block(text)
    if block is None or LEGACY_SKILL_FILE_OWNER not in text:
        return False
    start, end = block
    suffix = text[end + len(LEGACY_AGENTS_MD_END):]
    if suffix.strip():
        return False
    prefix = text[:start].replace(LEGACY_SKILL_FILE_OWNER, "")
    # Front matter is allowed before the managed block; arbitrary prose is not.
    if prefix.startswith("---\n"):
        boundary = prefix.find("\n---\n", 4)
        if boundary == -1:
            return False
        prefix = prefix[boundary + len("\n---\n"):]
    return not prefix.strip()


def migrate_legacy_skill_file(primary: Path) -> bool:
    """Move an old fully-managed DocAtlas skill to skills/docatlas.

    Ambiguous/foreign `skills/docmancer` content is left untouched. A proven
    DocAtlas skill with user-authored suffix/prefix fails closed instead of
    moving user content or creating two active DocAtlas skills.
    """

    if primary.exists():
        return False
    legacy = legacy_skill_path(primary)
    if legacy is None or not legacy.is_file():
        return False
    text = legacy.read_text(encoding="utf-8")
    if not is_proven_docatlas_text(text):
        return False
    if not legacy_skill_is_fully_managed(text):
        raise ValueError(
            f"legacy DocAtlas skill at {legacy} contains unowned/user content; "
            "refusing automatic path migration"
        )
    primary.parent.mkdir(parents=True, exist_ok=True)
    legacy.replace(primary)
    try:
        legacy.parent.rmdir()
    except OSError:
        pass
    return True


__all__ = [
    "AGENTS_MD_END",
    "AGENTS_MD_START",
    "DEFAULT_HOME_NAME",
    "LEGACY_AGENTS_MD_END",
    "LEGACY_AGENTS_MD_START",
    "LEGACY_CONFIG_NAME",
    "LEGACY_PROJECT_INSTALL_STATE",
    "LEGACY_SKILL_FILE_OWNER",
    "LEGACY_SKILL_ID",
    "PRIMARY_CONFIG_NAME",
    "PROJECT_INSTALL_STATE",
    "SKILL_FILE_OWNER",
    "SKILL_ID",
    "current_managed_block",
    "ensure_user_home",
    "is_proven_docatlas_text",
    "legacy_managed_block",
    "legacy_project_config_path",
    "legacy_skill_is_fully_managed",
    "legacy_skill_path",
    "legacy_user_config_path",
    "migrate_legacy_skill_file",
    "primary_user_config_path",
    "project_config_path",
    "resolved_user_home",
]
