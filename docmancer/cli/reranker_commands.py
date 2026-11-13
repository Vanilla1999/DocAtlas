"""`doc-atlas reranker` group: prepare and check the pinned Qwen evidence model."""
from __future__ import annotations

import json
from pathlib import Path

import click

from ..docs.application import reranker_setup


@click.group(name="reranker", help="Prepare and check the pinned Qwen evidence model (experimental).")
def reranker_group() -> None:
    """Prepare the pinned Qwen/Qwen3-Reranker-0.6B assets or verify readiness."""


@reranker_group.command("prepare")
@click.argument("out", type=click.Path(path_type=Path))
@click.option("--json", "json_output", is_flag=True, default=False, help="Emit the provenance manifest as JSON.")
def prepare_cmd(out: Path, json_output: bool) -> None:
    """Download the pinned model revision into OUT and verify every hash.

    OUT must not exist or must be an empty directory (absolute path).
    No CUDA is required at preparation time.
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
    """Verify assets, runtime compatibility and enabling environment.

    MODEL_PATH defaults to $DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH.
    Exits non-zero when the pinned contract is not satisfied.
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
        click.echo("runtime:")
        for key, row in diff.items():
            state = "ok" if row["matches"] else "MISMATCH"
            click.echo(f"  {key:<12} [{state}] expected={row['expected']} actual={row['actual']}")
        if report["runtime"].get("gpu") is not None:
            click.echo(f"  gpu          {report['runtime']['gpu']}")
        if report["runtime"].get("error"):
            click.echo(f"  error: {report['runtime']['error']}")
        if not report["ready"]:
            click.echo("Pinned hardware: CUDA capability 12.0 (Blackwell, RTX 50xx), torch 2.10.0+cu128.")
            click.echo("Install GPU torch into the tool environment, e.g.:")
            click.echo("  uv tool install --with torch==2.10.0+cu128 --index-url https://download.pytorch.org/whl/cu128 --with transformers==4.57.1 --with tokenizers==0.22.2 --with safetensors==0.8.0 doc-atlas")
    raise SystemExit(0 if report["ready"] else 1)
