"""State-identity-aware CLI maintenance commands.

State-mutating commands in this module bind user-facing operations to the
central DocAtlas ownership and reviewed-plan contracts instead of rediscovering
legacy paths ad hoc.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import click

from docmancer.cli.help import DocmancerCommand, HELP_CONTEXT_SETTINGS, format_examples
from docmancer.core.config_resolution import resolve_config
from docmancer.core.product_identity import (
    LEGACY_HOME_ENV,
    PRODUCT_HOME_ENV,
    legacy_default_home,
    resolve_home,
)
from docmancer.core.state_migration import (
    HomeMigrationError,
    apply_home_migration,
    plan_home_migration,
)
from docmancer.docs.application.index_storage_cleanup import IndexStorageCleanup


def _group_config_path() -> str | None:
    """Return the hidden group-level --config value without importing shards."""
    ctx = click.get_current_context(silent=True)
    if ctx and ctx.parent and ctx.parent.obj:
        value = ctx.parent.obj.get("config_path")
        return str(value) if value is not None else None
    return None


@click.command(
    "clear-index",
    cls=DocmancerCommand,
    context_settings=HELP_CONTEXT_SETTINGS,
    short_help="Preview or safely clear derived DocAtlas index state.",
    epilog=format_examples(
        "doc-atlas clear-index --scope project-local --project-path .",
        "doc-atlas clear-index --scope project-local --project-path . --apply",
        "doc-atlas clear-index --scope global --format json",
        "doc-atlas clear-index --scope global --apply",
    ),
)
@click.option(
    "--scope",
    type=click.Choice(["project-local", "global"], case_sensitive=False),
    required=True,
)
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, path_type=str),
    required=False,
    help="Project root for --scope project-local; forbidden for --scope global.",
)
@click.option("--apply", is_flag=True, default=False, help="Apply the displayed plan; default is preview only.")
@click.option(
    "--plan-digest",
    default=None,
    help="Require the applied plan to match a previously reviewed preview digest.",
)
@click.option(
    "--allow-incomplete",
    is_flag=True,
    default=False,
    help="Retain explicitly reported remote or unowned vector state instead of failing.",
)
@click.option(
    "output_format",
    "--format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    show_default=True,
)
def clear_index_cmd(
    scope: str,
    project_path: str | None,
    apply: bool,
    plan_digest: str | None,
    allow_incomplete: bool,
    output_format: str,
) -> None:
    """Delete derived indexes while preserving configuration and source files.

    Global resolution is intentionally anchored to the central DocAtlas home
    resolver. It never probes ``~/.docmancer`` implicitly. An explicitly set
    ``DOCMANCER_HOME`` remains a bounded 1.x compatibility input through the
    same resolver and receives the normal compatibility warning.
    """

    cleanup = IndexStorageCleanup()
    normalized_scope = scope.lower()
    if normalized_scope == "project-local":
        if not project_path:
            raise click.UsageError("--project-path is required for --scope project-local")
        plan = cleanup.preview(scope=normalized_scope, project_path=project_path)
    else:
        if project_path:
            raise click.UsageError("--project-path is not allowed for --scope global")
        explicit = _group_config_path()
        if explicit:
            resolved = resolve_config(explicit_path=explicit)
        else:
            home = resolve_home().path
            # A synthetic non-existent cwd prevents an unrelated project config
            # from shadowing the global state identity while still letting
            # resolve_config apply primary/legacy user-config precedence.
            resolved = resolve_config(cwd=home / ".global-config-resolution")
        plan = cleanup.preview(
            scope="global",
            global_config=resolved.config,
            global_config_source=resolved.source,
            global_config_path=resolved.path,
        )

    try:
        payload = (
            cleanup.apply(
                plan,
                expected_plan_digest=plan_digest,
                allow_incomplete=allow_incomplete,
            )
            if apply
            else cleanup.payload(plan)
        )
    except (RuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    if output_format == "json":
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    click.echo(f"Scope: {payload['scope']} ({payload['config_source']})")
    click.echo(f"Storage root: {payload['storage_root']}")
    click.echo(f"Plan digest: {payload['plan_digest']}")
    click.echo("Plan:")
    for target in payload.get("targets", []):
        state = "present" if target["exists"] else "missing"
        click.echo(
            f"  [{target['kind']}] {target['path']} "
            f"({state}, {target['size_bytes']} bytes)"
        )
    for reason in payload.get("incomplete_reasons", []):
        click.echo(f"Incomplete: {reason}", err=True)
    for reason in payload.get("blocking_reasons", []):
        click.echo(f"Blocked: {reason}", err=True)
    click.echo(
        "Applied."
        if apply
        else "Preview only; rerun with --apply to delete this scope."
    )


def _migration_source(source: str | None) -> Path:
    if source:
        return Path(source).expanduser()
    legacy_env = str(os.environ.get(LEGACY_HOME_ENV) or "").strip()
    if legacy_env:
        return Path(legacy_env).expanduser()
    return legacy_default_home(home_dir=Path.home())


def _migration_target(target: str | None) -> Path:
    if target:
        return Path(target).expanduser()
    primary_env = str(os.environ.get(PRODUCT_HOME_ENV) or "").strip()
    env = {PRODUCT_HOME_ENV: primary_env} if primary_env else {}
    return resolve_home(env=env, home_dir=Path.home()).path


@click.command(
    "migrate-home",
    cls=DocmancerCommand,
    context_settings=HELP_CONTEXT_SETTINGS,
    short_help="Preview or copy proven legacy DocAtlas state into the primary home.",
    epilog=format_examples(
        "doc-atlas migrate-home",
        "doc-atlas migrate-home --format json",
        "doc-atlas migrate-home --apply --plan-digest <reviewed-digest>",
        "doc-atlas migrate-home --source /old/home --target /new/home",
    ),
)
@click.option(
    "--source",
    default=None,
    type=click.Path(path_type=str),
    help="Legacy source root. Defaults to explicit DOCMANCER_HOME, otherwise ~/.docmancer.",
)
@click.option(
    "--target",
    default=None,
    type=click.Path(path_type=str),
    help="Target root. Defaults to DOCATLAS_HOME when set, otherwise ~/.docatlas.",
)
@click.option(
    "--apply",
    is_flag=True,
    default=False,
    help="Apply a previously reviewed preview plan.",
)
@click.option(
    "--plan-digest",
    default=None,
    help="Exact digest printed by the reviewed preview; required with --apply.",
)
@click.option(
    "output_format",
    "--format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    show_default=True,
)
def migrate_home_cmd(
    source: str | None,
    target: str | None,
    apply: bool,
    plan_digest: str | None,
    output_format: str,
) -> None:
    """Copy proven legacy DocAtlas state without deleting or rewriting source."""

    if apply and not plan_digest:
        raise click.UsageError(
            "--plan-digest is required with --apply; preview migrate-home first"
        )
    if plan_digest and not apply:
        raise click.UsageError("--plan-digest is only valid together with --apply")

    source_path = _migration_source(source)
    target_path = _migration_target(target)
    try:
        plan = plan_home_migration(source_path, target_path)
    except HomeMigrationError as exc:
        raise click.ClickException(str(exc)) from exc

    if not plan.can_apply:
        if output_format == "json":
            payload = plan.to_dict()
            payload["status"] = "blocked"
            click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
            raise click.exceptions.Exit(1)
        raise click.ClickException(
            f"migration cannot be applied: {plan.reason}; "
            f"source={plan.source_classification}, "
            f"target={plan.target_classification}"
        )

    if apply:
        if plan.plan_digest != plan_digest:
            raise click.ClickException(
                "reviewed migration plan digest no longer matches source/target state"
            )
        try:
            result = apply_home_migration(plan)
        except HomeMigrationError as exc:
            raise click.ClickException(str(exc)) from exc
        payload = result.to_dict()
        payload["source_preserved"] = True
        if output_format == "json":
            click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
            return
        click.echo(f"Migration status: {result.status}")
        click.echo(f"Source: {result.source}")
        click.echo(f"Target: {result.target}")
        click.echo(f"Plan digest: {result.plan_digest}")
        click.echo("Source preserved: yes")
        return

    payload = plan.to_dict()
    payload["status"] = "preview"
    if output_format == "json":
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    click.echo(f"Source: {plan.source} ({plan.source_classification})")
    click.echo(f"Target: {plan.target} ({plan.target_classification})")
    click.echo(f"Files: {plan.file_count}")
    click.echo(f"Source bytes: {plan.total_source_bytes}")
    click.echo(f"Plan digest: {plan.plan_digest}")
    click.echo("Plan:")
    for entry in plan.entries:
        click.echo(
            f"  {entry.source_relative} -> {entry.target_relative} "
            f"({entry.size_bytes} bytes, source_sha256={entry.source_sha256}, "
            f"target_sha256={entry.target_sha256})"
        )
    click.echo(
        "Preview only; source and target were not modified. "
        "Rerun with --apply --plan-digest <digest> after review."
    )


__all__ = ["clear_index_cmd", "migrate_home_cmd"]
