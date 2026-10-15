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

