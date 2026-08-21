from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from filelock import FileLock

from docmancer.cli.__main__ import cli
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
    _migration_lock_path,
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
    explicit_result = resolve_config(
        explicit_path=explicit, project_path=project, cwd=cwd
    )
    assert explicit_result.source == "explicit"
    assert explicit_result.legacy_compatibility is False
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

    explicit_legacy = tmp_path / "explicit-legacy" / "docmancer.yaml"
    _write_config(explicit_legacy, mode="lexical", db_path="legacy-explicit.db")
    with pytest.warns(DeprecationWarning, match="docmancer.yaml"):
        explicit_legacy_result = resolve_config(explicit_path=explicit_legacy)
    assert explicit_legacy_result.source == "explicit"
    assert explicit_legacy_result.path == explicit_legacy.resolve()
    assert explicit_legacy_result.legacy_compatibility is True

    isolated_cwd = tmp_path / "isolated-cwd"
    isolated_cwd.mkdir()
    with pytest.warns(DeprecationWarning, match="docmancer.yaml"):
        user_legacy_result = resolve_config(
            cwd=isolated_cwd,
            user_config_path=explicit_legacy,
        )
    assert user_legacy_result.source == "user"
    assert user_legacy_result.legacy_compatibility is True


def test_config_identity_includes_retrieval_settings_not_only_db_path(tmp_path):
    first = tmp_path / "first.yaml"
    second = tmp_path / "second.yaml"
    shared_db = str(tmp_path / "shared.db")
    _write_config(first, mode="lexical", db_path=shared_db)
    _write_config(second, mode="hybrid", db_path=shared_db)

    assert resolve_config(explicit_path=first).identity != resolve_config(explicit_path=second).identity

    # A strongly identified legacy DocAtlas home can be copied into the new
    # namespace without deleting or rewriting the source. The public CLI is
    # preview-first and requires the exact reviewed digest before applying.
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

    runner = CliRunner()
    args = [
        "migrate-home",
        "--source",
        str(source),
        "--target",
        str(target),
    ]
    preview = runner.invoke(cli, [*args, "--format", "json"])
    assert preview.exit_code == 0, preview.output
    preview_payload = json.loads(preview.output)
    assert preview_payload["status"] == "preview"
    assert preview_payload["plan_digest"] == plan.plan_digest
    assert not target.exists()

    missing_digest = runner.invoke(cli, [*args, "--apply"])
    assert missing_digest.exit_code == 2
    assert "--plan-digest is required" in missing_digest.output
    assert not target.exists()

    wrong_digest = runner.invoke(
        cli,
        [*args, "--apply", "--plan-digest", "0" * 64],
    )
    assert wrong_digest.exit_code == 1
    assert "digest no longer matches" in wrong_digest.output
    assert not target.exists()

    applied_cli = runner.invoke(
        cli,
        [
            *args,
            "--apply",
            "--plan-digest",
            plan.plan_digest,
            "--format",
            "json",
        ],
    )
    assert applied_cli.exit_code == 0, applied_cli.output
    applied_payload = json.loads(applied_cli.output)
    assert applied_payload["status"] == "applied"
    assert applied_payload["source_preserved"] is True
    assert source.exists()
    assert (source / "docmancer.yaml").exists()
    assert not (target / "docmancer.yaml").exists()
    assert str(target.resolve() / "docmancer.db") in (target / "docatlas.yaml").read_text(encoding="utf-8")
    owner = inspect_state(target)
    assert owner.classification == "owned_docatlas"
    assert owner.owner and owner.owner["product_id"] == PRODUCT_ID

    # Default migration source may deliberately inspect the legacy env, while
    # target resolution is strictly DocAtlas-owned and never inherits it.
    env_target = tmp_path / "env-docatlas"
    env_preview = runner.invoke(
        cli,
        ["migrate-home", "--format", "json"],
        env={
            "DOCMANCER_HOME": str(source),
            "DOCATLAS_HOME": str(env_target),
        },
    )
    assert env_preview.exit_code == 0, env_preview.output
    env_payload = json.loads(env_preview.output)
    assert Path(env_payload["source"]) == source.resolve()
    assert Path(env_payload["target"]) == env_target.resolve()
    assert not env_target.exists()

    fake_home = tmp_path / "fresh-home"
    default_target_preview = runner.invoke(
        cli,
        ["migrate-home", "--format", "json"],
        env={
            "HOME": str(fake_home),
            "USERPROFILE": str(fake_home),
            "DOCMANCER_HOME": str(source),
            "DOCATLAS_HOME": "",
        },
    )
    assert default_target_preview.exit_code == 0, default_target_preview.output
    default_payload = json.loads(default_target_preview.output)
    assert Path(default_payload["source"]) == source.resolve()
    assert Path(default_payload["target"]) == (fake_home / ".docatlas").resolve()
    assert not (fake_home / ".docatlas").exists()

    repeat_plan = plan_home_migration(source, target)
    assert repeat_plan.can_apply is True
    assert repeat_plan.plan_digest == plan.plan_digest
    assert repeat_plan.target_classification == "owned_docatlas"

    migration_lock = FileLock(
        str(_migration_lock_path(Path(repeat_plan.source), Path(repeat_plan.target))),
        timeout=0,
    )
    with migration_lock:
        with pytest.raises(HomeMigrationError, match="already in progress"):
            apply_home_migration(repeat_plan)

    repeated_cli = runner.invoke(
        cli,
        [
            *args,
            "--apply",
            "--plan-digest",
            plan.plan_digest,
            "--format",
            "json",
        ],
    )
    assert repeated_cli.exit_code == 0, repeated_cli.output
    assert json.loads(repeated_cli.output)["status"] == "already_applied"

    (target / "docmancer.db").write_bytes(b"tampered")
    tampered_plan = plan_home_migration(source, target)
    assert tampered_plan.can_apply is False
    assert tampered_plan.reason == "target_not_matching_migration"
    blocked_cli = runner.invoke(cli, [*args, "--format", "json"])
    assert blocked_cli.exit_code == 1
    blocked_payload = json.loads(blocked_cli.output)
    assert blocked_payload["status"] == "blocked"
    assert blocked_payload["reason"] == "target_not_matching_migration"


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
