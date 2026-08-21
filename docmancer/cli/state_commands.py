"""State-identity-aware implementations of existing CLI maintenance commands.

This module intentionally overrides only existing command surfaces.  It keeps
P0.3B1 focused on removing direct legacy-home discovery from stateful CLI
consumers without adding a new public command or changing the Python package
namespace.
"""
from __future__ import annotations

import json

import click

from docmancer.cli.help import DocmancerCommand, HELP_CONTEXT_SETTINGS, format_examples
from docmancer.core.config_resolution import resolve_config
from docmancer.core.product_identity import resolve_home
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
    resolver.  It never probes ``~/.docmancer`` implicitly.  An explicitly set
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


__all__ = ["clear_index_cmd"]
