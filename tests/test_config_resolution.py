from __future__ import annotations

from pathlib import Path

import pytest

from docmancer.core.config_resolution import resolve_config


def _write_config(path: Path, *, mode: str, db_path: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"index:\n  db_path: {db_path}\nretrieval:\n  default_mode: {mode}\n",
        encoding="utf-8",
    )


def test_config_resolution_precedence_is_explicit_project_cwd_user_defaults(tmp_path):
    project = tmp_path / "project"
    cwd = tmp_path / "cwd"
    user = tmp_path / "home" / "docmancer.yaml"
    explicit = tmp_path / "explicit.yaml"
    project.mkdir()
    cwd.mkdir()
    _write_config(user, mode="lexical", db_path="user.db")
    _write_config(cwd / "docmancer.yaml", mode="sparse", db_path="cwd.db")
    _write_config(project / "docmancer.yaml", mode="dense", db_path="project.db")
    _write_config(explicit, mode="hybrid", db_path="explicit.db")

    assert resolve_config(
        explicit_path=explicit, project_path=project, cwd=cwd, user_config_path=user
    ).source == "explicit"
    project_result = resolve_config(project_path=project, cwd=cwd, user_config_path=user)
    assert project_result.source == "project_local"
    assert project_result.config.retrieval.default_mode == "dense"
    (project / "docmancer.yaml").unlink()
    assert resolve_config(project_path=project, cwd=cwd, user_config_path=user).source == "cwd"
    (cwd / "docmancer.yaml").unlink()
    assert resolve_config(project_path=project, cwd=cwd, user_config_path=user).source == "user"
    user.unlink()
    assert resolve_config(project_path=project, cwd=cwd, user_config_path=user).source == "defaults"


def test_config_identity_includes_retrieval_settings_not_only_db_path(tmp_path):
    first = tmp_path / "first.yaml"
    second = tmp_path / "second.yaml"
    shared_db = str(tmp_path / "shared.db")
    _write_config(first, mode="lexical", db_path=shared_db)
    _write_config(second, mode="hybrid", db_path=shared_db)

    assert resolve_config(explicit_path=first).identity != resolve_config(explicit_path=second).identity


def test_explicit_config_must_be_a_file(tmp_path):
    with pytest.raises(ValueError, match="explicit config path is not a file"):
        resolve_config(explicit_path=tmp_path)
