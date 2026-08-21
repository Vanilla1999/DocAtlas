from __future__ import annotations

from pathlib import Path

import pytest

from docmancer.core.config_resolution import resolve_config
from docmancer.core.product_identity import (
    PRODUCT_ID,
    StateOwnershipError,
    ensure_owned_home,
    inspect_state,
    resolve_home,
)
from docmancer.core.state_migration import (
    HomeMigrationError,
    apply_home_migration,
    plan_home_migration,
)


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
    user = user_home / "docatlas.yaml"
    explicit = tmp_path / "explicit.yaml"
    project.mkdir()
    cwd.mkdir()
    _write_config(user, mode="lexical", db_path="user.db")
    _write_config(cwd / "docatlas.yaml", mode="sparse", db_path="cwd.db")
    _write_config(project / "docatlas.yaml", mode="dense", db_path="project.db")
    _write_config(explicit, mode="hybrid", db_path="explicit.db")
    monkeypatch.setenv("DOCATLAS_HOME", str(user_home))
    monkeypatch.delenv("DOCMANCER_HOME", raising=False)

    assert resolve_home().path == user_home.resolve()
    assert resolve_config(
        explicit_path=explicit, project_path=project, cwd=cwd
    ).source == "explicit"
    project_result = resolve_config(project_path=project, cwd=cwd)
    assert project_result.source == "project_local"
    assert project_result.legacy_compatibility is False
    assert project_result.config.retrieval.default_mode == "dense"
    (project / "docatlas.yaml").unlink()
    assert resolve_config(project_path=project, cwd=cwd).source == "cwd"
    (cwd / "docatlas.yaml").unlink()
    user_result = resolve_config(project_path=project, cwd=cwd)
    assert user_result.source == "user"
    assert user_result.path == user.resolve()
    user.unlink()
    defaults = resolve_config(project_path=project, cwd=cwd)
    assert defaults.source == "defaults"
    assert Path(defaults.config.index.db_path).parent == user_home.resolve()
    assert Path(defaults.config.embeddings.cache).parent == user_home.resolve()

    # The old file name remains a compatibility input, but the new name wins
    # whenever both exist and legacy use is explicit in diagnostics.
    _write_config(project / "docmancer.yaml", mode="dense", db_path="legacy.db")
    _write_config(project / "docatlas.yaml", mode="hybrid", db_path="primary.db")
    primary = resolve_config(project_path=project, cwd=cwd)
    assert primary.path == (project / "docatlas.yaml").resolve()
    assert primary.legacy_compatibility is False
    (project / "docatlas.yaml").unlink()
    with pytest.warns(DeprecationWarning, match="docmancer.yaml"):
        legacy = resolve_config(project_path=project, cwd=cwd)
    assert legacy.path == (project / "docmancer.yaml").resolve()
    assert legacy.legacy_compatibility is True


def test_config_identity_includes_retrieval_settings_not_only_db_path(tmp_path):
    first = tmp_path / "first.yaml"
    second = tmp_path / "second.yaml"
    shared_db = str(tmp_path / "shared.db")
    _write_config(first, mode="lexical", db_path=shared_db)
    _write_config(second, mode="hybrid", db_path=shared_db)

    assert resolve_config(explicit_path=first).identity != resolve_config(explicit_path=second).identity

    # A strongly identified legacy DocAtlas home can be copied into the new
    # namespace without deleting or rewriting the source. Config paths are
    # rebound and repeated application is idempotent.
    source = tmp_path / ".docmancer"
    target = tmp_path / ".docatlas"
    (source / "mcp").mkdir(parents=True)
    (source / "mcp" / "manifest.json").write_text("{}", encoding="utf-8")
    (source / "docmancer.yaml").write_text(
        "index:\n  db_path: ~/.docmancer/docmancer.db\n",
        encoding="utf-8",
    )
    (source / "docmancer.db").write_bytes(b"legacy-db")
    assert inspect_state(source).classification == "legacy_docatlas"
    plan = plan_home_migration(source, target)
    assert plan.can_apply is True
    assert plan.source_classification == "legacy_docatlas"
    assert {entry.target_relative for entry in plan.entries} >= {
        "docatlas.yaml",
        "docmancer.db",
        "mcp/manifest.json",
    }
    applied = apply_home_migration(plan)
    assert applied.status == "applied"
    assert source.exists()
    assert (source / "docmancer.yaml").exists()
    assert not (target / "docmancer.yaml").exists()
    assert str(target.resolve() / "docmancer.db") in (target / "docatlas.yaml").read_text(encoding="utf-8")
    owner = inspect_state(target)
    assert owner.classification == "owned_docatlas"
    assert owner.owner and owner.owner["product_id"] == PRODUCT_ID
    assert apply_home_migration(plan).status == "already_applied"


def test_explicit_config_must_be_a_file(tmp_path):
    with pytest.raises(ValueError, match="explicit config path is not a file"):
        resolve_config(explicit_path=tmp_path)

    # Config-only legacy state is intentionally ambiguous because the active
    # upstream docmancer product uses the same historical file name/schema.
    ambiguous = tmp_path / "ambiguous"
    ambiguous.mkdir()
    (ambiguous / "docmancer.yaml").write_text("index: {}\n", encoding="utf-8")
    assert inspect_state(ambiguous).classification == "ambiguous"
    ambiguous_plan = plan_home_migration(ambiguous, tmp_path / "ambiguous-target")
    assert ambiguous_plan.can_apply is False
    assert ambiguous_plan.reason == "source_not_proven_docatlas"
    with pytest.raises(StateOwnershipError, match="refusing to write unowned state root"):
        ensure_owned_home(ambiguous)

    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "memory.db").write_bytes(b"foreign-memory")
    (foreign / "tree").mkdir()
    assert inspect_state(foreign).classification == "foreign"
    foreign_plan = plan_home_migration(foreign, tmp_path / "foreign-target")
    assert foreign_plan.can_apply is False
    assert foreign_plan.reason == "source_not_proven_docatlas"
    with pytest.raises(StateOwnershipError, match="refusing to write unowned state root"):
        ensure_owned_home(foreign)

    # A legacy-looking marker reached through a symlink is not ownership proof.
    external = tmp_path / "external"
    external.mkdir()
    (external / "manifest.json").write_text("{}", encoding="utf-8")
    symlinked = tmp_path / "symlinked"
    symlinked.mkdir()
    try:
        (symlinked / "mcp").symlink_to(external, target_is_directory=True)
    except OSError:
        pass
    else:
        inspection = inspect_state(symlinked)
        assert inspection.classification == "ambiguous"
        assert "symlink" in " ".join(inspection.reasons)
        with pytest.raises(StateOwnershipError, match="refusing to write unowned state root"):
            ensure_owned_home(symlinked, allow_legacy_claim=True)

    legacy = tmp_path / "bounded"
    (legacy / "mcp").mkdir(parents=True)
    (legacy / "mcp" / "manifest.json").write_text("{}", encoding="utf-8")
    (legacy / "one").write_text("1", encoding="utf-8")
    with pytest.raises(HomeMigrationError, match="file limit"):
        plan_home_migration(legacy, tmp_path / "bounded-target", max_files=1)
