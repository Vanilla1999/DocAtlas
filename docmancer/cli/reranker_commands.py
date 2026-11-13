"""`doc-atlas reranker` group: prepare and check the pinned Qwen evidence model."""
from __future__ import annotations

import json
from pathlib import Path

import click

from .._version import __version__
from ..docs.application import reranker_setup


_GPU_INSTALL_EXAMPLE = (
    "uv tool install --force --with torch==2.10.0+cu128 "
    "--index pytorch=https://download.pytorch.org/whl/cu128 "
    "--default-index https://pypi.org/simple "
    "--with transformers==4.57.1 --with tokenizers==0.22.2 "
    f"--with safetensors==0.8.0 doc-atlas=={__version__}"
)


@click.group(name="reranker", help="Prepare and check the pinned Qwen evidence model (experimental).")
def reranker_group() -> None:
    """Prepare the pinned Qwen/Qwen3-Reranker-0.6B assets or verify readiness."""


@reranker_group.command("prepare")
@click.argument("out", type=click.Path(path_type=Path))
@click.option("--json", "json_output", is_flag=True, default=False, help="Emit the provenance manifest as JSON.")
def prepare_cmd(out: Path, json_output: bool) -> None:
    """Download the pinned model revision into OUT and verify every hash.

    OUT must be an absolute, absent or empty directory, not a symlink.
    Downloads are verified in private staging before publication; failures
    clean only that staging directory. No CUDA is required at preparation time.
    """
    try:
        manifest = reranker_setup.prepare_assets(out)
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(str(exc)) from exc
    if json_output:
        click.echo(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2))
        return
    for name, row in manifest["files"].items():
        click.echo(f"  verified {name} ({row['bytes']} bytes)")
    click.echo(f"Prepared pinned {manifest['model']} @ {manifest['revision'][:12]} at {out}")
    click.echo("Point DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH at this directory, then run: doc-atlas reranker check")


@reranker_group.command("check")
@click.argument("model_path", type=click.Path(path_type=Path), required=False)
@click.option("--json", "json_output", is_flag=True, default=False, help="Emit the readiness report as JSON.")
def check_cmd(model_path: Path | None, json_output: bool) -> None:
    """Preflight assets, runtime compatibility and this process's configuration.

    MODEL_PATH defaults to $DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH.
    Exits non-zero for an incompatible preflight, including conflicting flags.
    Does not load the model, run inference or inspect another client's config.
    """
    report = reranker_setup.check_ready(str(model_path) if model_path else None)
    if json_output:
        click.echo(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        assets, diff = report["assets"], report["runtime_diff"]
        click.echo(f"model: {report['model_id']} @ {report['revision'][:12]}")
        state = "ok" if assets["ok"] else "failed"
        click.echo(f"assets [{state}]: {assets['path'] or '(path not set)'}")
        if not assets["ok"]:
            click.echo(f"  error: {assets['error']}")
        configured = report["configured_assets"]
        if configured is not None and configured != assets:
            state = "ok" if configured["ok"] else "failed"
            click.echo(f"configured assets [{state}]: {configured['path'] or '(path not set)'}")
            if not configured["ok"]:
                click.echo(f"  error: {configured['error']}")
        click.echo("runtime:")
        for key, row in diff.items():
            state = "ok" if row["matches"] else "MISMATCH"
            click.echo(f"  {key:<12} [{state}] expected={row['expected']} actual={row['actual']}")
        if report["runtime"].get("gpu") is not None:
            click.echo(f"  gpu          {report['runtime']['gpu']}")
        if report["runtime"].get("error"):
            click.echo(f"  error: {report['runtime']['error']}")
        state = "ok" if report["profile_valid"] else "invalid"
        click.echo(f"profile [{state}]: Qwen {'enabled' if report['enabled'] else 'disabled'}")
        click.echo(f"  configured native budget: {report['profile']['native_budget']}")
        click.echo("environment: current process only; use the same variables as the MCP server")
        for name, value in report["environment"].items():
            if value is not None:
                click.echo(f"  {name}={value}")
        click.echo("model load / inference / future request binding: NOT CHECKED")
        for issue in report["issues"]:
            click.echo(f"[{issue['code']}] {issue['message']}")
            click.echo(f"  next: {issue['action']}")
        if any(issue["component"] == "runtime_dependencies" for issue in report["issues"]):
            click.echo("Pinned dependency example for a published release (recent uv required):")
            click.echo("  " + _GPU_INSTALL_EXAMPLE)
            click.echo("For an unpublished/source build, replace doc-atlas==VERSION with that candidate's wheel path.")
            click.echo("This preserves PyPI, does not enable Qwen, and cannot fix unsupported hardware or model files.")
        if report["ready"]:
            click.echo("Preflight passed; perform a real MCP read to validate model loading and scoring.")
        else:
            click.echo("Preflight blocked; resolve the reported issues and restart the configured MCP server.")
    raise SystemExit(0 if report["ready"] else 1)
