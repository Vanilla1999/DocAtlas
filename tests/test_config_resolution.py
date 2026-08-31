from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from docmancer.cli.__main__ import cli
from docmancer.core.config_resolution import resolve_config
from docmancer.core.product_identity import StateOwnershipError, ensure_owned_home, inspect_state, resolve_home


def _write_config(path: Path, *, mode: str, db_path: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"index:\n  db_path: {db_path}\nretrieval:\n  default_mode: {mode}\n",
        encoding="utf-8",
    )


def test_config_resolution_precedence_is_explicit_project_cwd_user_defaults(tmp_path, monkeypatch):
    project = tmp_path / "project"
    cwd = tmp_path / "cwd"
    user_home = tmp_path / "home" / ".docatlas"
    project.mkdir()
    cwd.mkdir()
    _write_config(project / "docmancer.yaml", mode="dense", db_path="old.db")
    _write_config(cwd / "docatlas.yaml", mode="sparse", db_path="cwd.db")
    _write_config(user_home / "docatlas.yaml", mode="lexical", db_path="user.db")
    monkeypatch.setenv("DOCATLAS_HOME", str(user_home))

    assert resolve_home().path == user_home.resolve()
    resolved = resolve_config(project_path=project, cwd=cwd)
    assert resolved.source == "cwd"
    assert resolved.path == (cwd / "docatlas.yaml").resolve()

    (cwd / "docatlas.yaml").unlink()
    assert resolve_config(project_path=project, cwd=cwd).source == "user"

    legacy = project / "docmancer.yaml"
    assert resolve_config(explicit_path=legacy).source == "explicit"
    assert resolve_config(cwd=tmp_path, user_config_path=legacy).source == "user"


def test_config_identity_includes_retrieval_settings_not_only_db_path(tmp_path):
    first = tmp_path / "first.yaml"
    second = tmp_path / "second.yaml"
    _write_config(first, mode="lexical", db_path="shared.db")
    _write_config(second, mode="hybrid", db_path="shared.db")
    assert resolve_config(explicit_path=first).identity != resolve_config(explicit_path=second).identity

    legacy = tmp_path / ".docmancer"
    (legacy / "mcp").mkdir(parents=True)
    (legacy / "mcp" / "manifest.json").write_text("{}", encoding="utf-8")

    assert inspect_state(legacy).classification == "ambiguous"
    with pytest.raises(StateOwnershipError, match="refusing to write unowned state root"):
        ensure_owned_home(legacy)

    result = CliRunner().invoke(cli, ["migrate-home"])
    assert result.exit_code == 2
    assert "No such command" in result.output


def test_explicit_config_must_be_a_file(tmp_path):
    with pytest.raises(ValueError, match="explicit config path is not a file"):
        resolve_config(explicit_path=tmp_path)
