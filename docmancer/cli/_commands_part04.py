"""Implementation shard 4 for commands."""
from __future__ import annotations

from ._commands_shared import *  # noqa: F401,F403

from ._commands_part01 import _create_agent_or_raise_lock_error, _effective_config, _format_size, _get_agent_class, _load_config, _operational_source_card, _resolve_config_file, _source_rows

@click.command(
    "docs-impact",
    cls=DocmancerCommand,
    context_settings=HELP_CONTEXT_SETTINGS,
    short_help="Report documentation affected by a code diff.",
    epilog=format_examples(
        "doc-atlas docs-impact --base origin/main",
        "doc-atlas docs-impact --changed-file packages/api/src/auth.ts --format json",
    ),
)
@click.option("--project-path", default=".", type=click.Path(exists=True, file_okay=False, path_type=str), show_default=True)
@click.option("--base", default=None, help="Base git ref used to discover changed files.")
@click.option("--head", default="HEAD", show_default=True, help="Head git ref used with --base.")
@click.option("--changed-file", "changed_files", multiple=True, help="Changed repository path; may be repeated instead of --base.")
@click.option("--changed-symbol", "changed_symbols", multiple=True, help="Changed API symbol or config key; may be repeated for section-level hints.")
@click.option("--candidate-offset", type=click.IntRange(min=0), default=0, show_default=True, help="Section-candidate offset used to continue a bounded report.")
@click.option("--candidate-limit", type=click.IntRange(min=1, max=200), default=200, show_default=True, help="Maximum section candidates returned in this page.")
@click.option("output_format", "--format", type=click.Choice(["markdown", "json"], case_sensitive=False), default="markdown", show_default=True)
@click.option("--fail-on-missing", is_flag=True, default=False, help="Exit non-zero when a changed module has no maintained docs.")
@click.option(
    "--sync-saved-docs",
    is_flag=True,
    default=False,
    help="Incrementally index accepted doc changes from the exact --base/--head Git diff; never writes repository files.",
)
@click.option("--config", "config_path", default=None, help="Path to docmancer.yaml.")
def docs_impact_cmd(
    project_path: str,
    base: str | None,
    head: str,
    changed_files: tuple[str, ...],
    changed_symbols: tuple[str, ...],
    candidate_offset: int,
    candidate_limit: int,
    output_format: str,
    fail_on_missing: bool,
    sync_saved_docs: bool,
    config_path: str | None,
):
    """Report which maintained docs should be reviewed after a code change."""
    from docmancer.docs.impact import analyze_docs_impact, bound_docs_impact_report, changed_evidence_from_git, format_docs_impact_markdown, unaccepted_worktree_changes
    from docmancer.docs.application.project_section_index import ProjectSectionIndexReader

    if base and changed_files:
        raise click.UsageError("Use either --base/--head or --changed-file, not both.")
    if not base and not changed_files:
        raise click.UsageError("Pass --base to read git diff paths, or at least one --changed-file.")
    if sync_saved_docs and not base:
        raise click.UsageError("--sync-saved-docs requires --base/--head so accepted rename and deletion status is exact.")
    try:
        effective_config_path = _effective_config(config_path)
        config = _load_config(effective_config_path)
        resolved_config_path = _resolve_config_file(effective_config_path)
        diff_evidence = changed_evidence_from_git(project_path, base, head) if base else None
        paths = diff_evidence["paths"] if diff_evidence else list(changed_files)
        report = analyze_docs_impact(
            project_path,
            paths,
            changed_symbols=list(changed_symbols),
            diff_evidence=diff_evidence,
            section_reader=ProjectSectionIndexReader(config.index.db_path),
            candidate_offset=candidate_offset,
            candidate_limit=candidate_limit,
            continuation_context={
                "project_path": str(Path(project_path).expanduser().resolve()),
                "config_path": str(resolved_config_path),
                "fail_on_missing": fail_on_missing,
            },
        )
        if sync_saved_docs:
            from dataclasses import asdict
            from docmancer.docs.service import LibraryDocsService

            bounds = report.get("bounds") or {}
            if bounds.get("truncated") or not bounds.get("analysis_complete", False):
                raise click.ClickException(
                    "Refusing incremental sync because the documentation impact report is incomplete; narrow the diff first."
                )

            changed_docs: list[str] = []
            deleted_docs: list[str] = []
            renamed_docs: list[dict[str, str]] = []
            ambiguous_docs: list[str] = []
            for item in report.get("impacts") or []:
                status = item.get("status")
                if status in {"updated", "changed"} and item.get("path"):
                    changed_docs.append(str(item["path"]))
                elif status == "deleted" and item.get("path"):
                    deleted_docs.append(str(item["path"]))
                elif status == "renamed" and item.get("old_path") and item.get("new_path"):
                    renamed_docs.append({
                        "old_path": str(item["old_path"]),
                        "new_path": str(item["new_path"]),
                    })
                elif status == "changed_or_deleted" and item.get("path"):
                    ambiguous_docs.append(str(item["path"]))
            if ambiguous_docs:
                raise click.ClickException(
                    "Cannot sync ambiguous documentation lifecycle evidence: "
                    + ", ".join(sorted(ambiguous_docs))
                )
            affected_docs = [
                *changed_docs,
                *deleted_docs,
                *[path for item in renamed_docs for path in (item["old_path"], item["new_path"])],
            ]
            unaccepted = unaccepted_worktree_changes(project_path, head, affected_docs)
            if unaccepted:
                raise click.ClickException(
                    "Refusing to index uncommitted or rejected documentation content: "
                    + ", ".join(unaccepted)
                )
            started_at = datetime.now(timezone.utc)
            sync = asdict(LibraryDocsService(config=config).sync_project_docs(
                project_path,
                with_vectors=False,
                changed_paths=sorted(set(changed_docs)),
                deleted_paths=sorted(set(deleted_docs)),
                renamed_paths=renamed_docs,
            ))
            elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
            metrics = dict((sync.get("diagnostics") or {}).get("metrics") or {})
            metrics["latency_ms"] = elapsed_ms
            report["sync"] = {
                "status": sync.get("status"),
                "mode": "incremental",
                "message": sync.get("message"),
                "metrics": metrics,
                "tombstones": (sync.get("tombstones") or [])[:100],
                "warnings": sync.get("warnings") or [],
            }
            report = bound_docs_impact_report(report)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if output_format.lower() == "json":
        click.echo(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        click.echo(format_docs_impact_markdown(report))
    if fail_on_missing and report["summary"]["missing_docs"]:
        raise click.exceptions.Exit(2)


@click.command(
    "agent-contract",
    cls=DocmancerCommand,
    context_settings=HELP_CONTEXT_SETTINGS,
    short_help="Describe the local docs workflow for coding agents.",
    epilog=format_examples(
        "doc-atlas agent-contract --project-path .",
        "doc-atlas agent-contract --project-path ./my-project --format json",
    ),
)
@click.option("--project-path", default=".", type=click.Path(exists=True, file_okay=False, path_type=str), show_default=True)
@click.option("output_format", "--format", type=click.Choice(["markdown", "json"], case_sensitive=False), default="json", show_default=True)
def agent_contract_cmd(project_path: str, output_format: str) -> None:
    """Emit source-of-truth and tool-selection rules for a local project."""
    from docmancer.docs.agent_contract import build_agent_contract, format_agent_contract_markdown

    contract = build_agent_contract(project_path)
    if output_format.lower() == "json":
        click.echo(json.dumps(contract, ensure_ascii=False, indent=2))
    else:
        click.echo(format_agent_contract_markdown(contract))


@click.command(
    cls=DocmancerCommand,
    context_settings=HELP_CONTEXT_SETTINGS,
    short_help="Remove an indexed source.",
    epilog=format_examples(
        "doc-atlas remove --all",
        "doc-atlas remove https://docs.example.com",
        "doc-atlas remove https://docs.example.com/page",
        "doc-atlas remove ./docs/getting-started.md",
    ),
)
@click.argument("source", required=False)
@click.option("--all", "remove_all", is_flag=True, default=False, help="Remove every stored source and docset.")
@click.option("--config", "config_path", default=None, help="Path to docmancer.yaml.")
def remove_cmd(source: str | None, remove_all: bool, config_path: str | None):
    """Remove an indexed source (URL or file path) from the knowledge base."""
    config_path = _effective_config(config_path)
    config = _load_config(config_path)
    agent = _get_agent_class()(config=config)
    if remove_all:
        if source:
            click.echo("Do not pass a source when using --all.", err=True)
            sys.exit(1)
        deleted = agent.remove_all_sources()
        if deleted:
            click.echo("Removed all sources.")
        else:
            click.echo("No data found to remove.")
        return
    if not source:
        click.echo("Missing argument 'SOURCE'.", err=True)
        sys.exit(1)
    deleted, removed_kind = agent.remove_source(source)
    if deleted:
        if removed_kind == "docset":
            click.echo(f"Removed docset: {source}")
        else:
            click.echo(f"Removed source: {source}")
    else:
        click.echo(f"No data found for source: {source}", err=True)
        sys.exit(1)


def _dir_size_bytes(path: Path) -> int:
    """Best-effort recursive size for a file or directory. Permission errors
    are skipped silently so a single unreadable file does not abort the scan."""
    if not path.exists():
        return 0
    if path.is_file() or path.is_symlink():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for child in path.rglob("*"):
        try:
            if child.is_file() and not child.is_symlink():
                total += child.stat().st_size
        except OSError:
            continue
    return total


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
    "output_format", "--format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text", show_default=True,
)
def clear_index_cmd(
    scope: str,
    project_path: str | None,
    apply: bool,
    plan_digest: str | None,
    allow_incomplete: bool,
    output_format: str,
) -> None:
    """Delete derived indexes while preserving configuration and source files."""
    from docmancer.core.config_resolution import resolve_config
    from docmancer.docs.application.index_storage_cleanup import IndexStorageCleanup

    cleanup = IndexStorageCleanup()
    normalized_scope = scope.lower()
    if normalized_scope == "project-local":
        if not project_path:
            raise click.UsageError("--project-path is required for --scope project-local")
        plan = cleanup.preview(scope=normalized_scope, project_path=project_path)
    else:
        if project_path:
            raise click.UsageError("--project-path is not allowed for --scope global")
        explicit = _effective_config(None)
        if explicit:
            resolved = resolve_config(explicit_path=explicit)
        else:
            home = Path(os.environ.get("DOCMANCER_HOME") or (Path.home() / ".docmancer"))
            resolved = resolve_config(
                cwd=home / ".no-project-config",
                user_config_path=home / "docmancer.yaml",
            )
        plan = cleanup.preview(
            scope="global",
            global_config=resolved.config,
            global_config_source=resolved.source,
            global_config_path=resolved.path,
        )

    try:
        payload = cleanup.apply(
            plan,
            expected_plan_digest=plan_digest,
            allow_incomplete=allow_incomplete,
        ) if apply else cleanup.payload(plan)
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
        click.echo(f"  [{target['kind']}] {target['path']} ({state}, {target['size_bytes']} bytes)")
    for reason in payload.get("incomplete_reasons", []):
        click.echo(f"Incomplete: {reason}", err=True)
    for reason in payload.get("blocking_reasons", []):
        click.echo(f"Blocked: {reason}", err=True)
    click.echo("Applied." if apply else "Preview only; rerun with --apply to delete this scope.")


@click.command(
    cls=DocmancerCommand,
    context_settings=HELP_CONTEXT_SETTINGS,
    short_help="Remove all docmancer state from this machine.",
    epilog=format_examples(
        "doc-atlas clear",
        "doc-atlas clear --yes",
        "doc-atlas clear --dry-run",
        "doc-atlas clear --keep-config",
        "doc-atlas clear --keep-models",
    ),
)
@click.option("--yes", "-y", "assume_yes", is_flag=True, help="Skip the confirmation prompt.")
@click.option("--dry-run", is_flag=True, help="Print what would be deleted without removing anything.")
@click.option("--keep-config", is_flag=True, help="Preserve ~/.docmancer/docmancer.yaml.")
@click.option(
    "--keep-models",
    is_flag=True,
    help="Skip the FastEmbed / Qdrant-hosted HuggingFace model caches.",
)
def clear_cmd(assume_yes: bool, dry_run: bool, keep_config: bool, keep_models: bool) -> None:
    """Remove every docmancer-related directory from this machine.

    Removes (by default):

    \b
    - ~/.docmancer/ (config, SQLite FTS5 index, extracted docs, embeddings cache,
      managed Qdrant storage, MCP packs)
    - ~/.cache/fastembed/ (FastEmbed ONNX model cache)
    - ~/.cache/huggingface/hub/models--Qdrant--* (Qdrant-published models that
      docmancer pulled via the qdrant_client embedding helper)

    The managed Qdrant process is stopped first if it is running. Other tools'
    HuggingFace caches (non-Qdrant publishers) are left untouched.
    """
    home = Path.home()

    docmancer_home = home / ".docmancer"
    targets: list[Path] = []

    if docmancer_home.exists():
        if keep_config:
            for child in sorted(docmancer_home.iterdir()):
                if child.name == "docmancer.yaml":
                    continue
                targets.append(child)
        else:
            targets.append(docmancer_home)

    if not keep_models:
        fastembed_cache = home / ".cache" / "fastembed"
        if fastembed_cache.exists():
            targets.append(fastembed_cache)
        hf_hub = home / ".cache" / "huggingface" / "hub"
        if hf_hub.exists():
            for child in sorted(hf_hub.iterdir()):
                if child.name.startswith("models--Qdrant--"):
                    targets.append(child)

    if not targets:
        click.echo("Nothing to remove. Docmancer state is already clear.")
        return

    sizes = {t: _dir_size_bytes(t) for t in targets}
    total = sum(sizes.values())

    click.echo("Will remove:")
    for t in targets:
        click.echo(f"  {_format_size(sizes[t]):>10}  {t}")
    click.echo(f"  {'-' * 10}")
    click.echo(f"  {_format_size(total):>10}  total")

    if dry_run:
        click.echo("\nDry run; no changes made.")
        return

    if not assume_yes:
        click.confirm("\nRemove all of this?", abort=True)

    # Stop the managed Qdrant before deleting its storage so the binary
    # is not still writing into ~/.docmancer/qdrant as we remove it.
    try:
        from docmancer.runtime.qdrant_manager import QdrantManager

        mgr = QdrantManager()
        if mgr.stop():
            click.echo("Stopped managed qdrant.")
    except Exception as exc:  # noqa: BLE001
        click.echo(f"Warning: could not stop managed qdrant: {exc}", err=True)

    removed = 0
    failed: list[tuple[Path, str]] = []
    for t in targets:
        try:
            if t.is_dir() and not t.is_symlink():
                shutil.rmtree(t)
            else:
                t.unlink()
            removed += sizes[t]
        except OSError as exc:
            failed.append((t, str(exc)))

    click.echo(f"Removed {_format_size(removed)} of docmancer state.")
    if failed:
        click.echo("Some paths could not be removed:", err=True)
        for path, msg in failed:
            click.echo(f"  {path}: {msg}", err=True)
        sys.exit(1)


@click.command(
    cls=DocmancerCommand,
    context_settings=HELP_CONTEXT_SETTINGS,
    short_help="List indexed documentation sources.",
    epilog=format_examples(
        "doc-atlas list",
        "doc-atlas list --all",
        "doc-atlas list --stale",
        "doc-atlas list --vectors=drift",
        "doc-atlas list --format json",
        "doc-atlas list --config ./docmancer.yaml",
    ),
)
@click.option("--all", "show_all", is_flag=True, default=False, help="Show every stored page/file source.")
@click.option("--stale", is_flag=True, default=False, help="Only show stale sources (30+ days old).")
@click.option("--failed", is_flag=True, default=False, help="Only show sources with failures.")
@click.option("--vectors", type=click.Choice(["ok", "none", "drift"], case_sensitive=False), default=None, help="Filter by vector state.")
@click.option("output_format", "--format", type=click.Choice(["table", "json"], case_sensitive=False), default="table", show_default=True)
@click.option("--config", "config_path", default=None, help="Path to docmancer.yaml.")
def list_cmd(show_all: bool, stale: bool, failed: bool, vectors: str | None, output_format: str, config_path: str | None):
    """List indexed sources with operational state and next actions."""
    config_path = _effective_config(config_path)
    config = _load_config(config_path)
    agent = _create_agent_or_raise_lock_error(config)
    agent.collection_stats()
    cards = [_operational_source_card(row) for row in _source_rows(config, grouped=not show_all)]
    if stale:
        cards = [card for card in cards if str(card["freshness"]).startswith("stale")]
    if failed:
        cards = [card for card in cards if card["status"] == "failed" or int(card["failures"] or 0) > 0]
    if vectors:
        cards = [card for card in cards if card["vectors"] == vectors.lower()]
    if output_format == "json":
        click.echo(json.dumps(cards, ensure_ascii=False, indent=2))
        return
    if not cards:
        click.echo("No sources indexed yet.")
        return
    click.echo(f"{'SOURCE':<28} {'TYPE':<9} {'STATUS':<9} {'FRESHNESS':<12} {'CONTENT':<14} {'VECTORS':<8} {'FAILURES':<8} NEXT ACTION")
    for card in cards:
        source = str(card["source"])
        if len(source) > 27:
            source = source[:24] + "..."
        click.echo(
            f"{source:<28} {str(card['type'])[:8]:<9} {card['status']:<9} {card['freshness']:<12} "
            f"{card['content']:<14} {card['vectors']:<8} {str(card['failures']):<8} {card['next_action']}"
        )

__all__=['docs_impact_cmd', 'agent_contract_cmd', 'remove_cmd', '_dir_size_bytes', 'clear_index_cmd', 'clear_cmd', 'list_cmd']
