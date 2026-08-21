"""Implementation shard 2 for commands."""
from __future__ import annotations

from ._commands_shared import *  # noqa: F401,F403

from ._commands_part01 import _build_skill_content, _configure_ingest_logging, _effective_config, _emit_index_summary, _emit_status_line, _get_agent_class, _get_codex_skill_path, _get_config_class, _get_copilot_user_instructions_path, _get_shared_agent_skill_path, _get_template_content, _get_user_config_dir, _install_or_append_agents_md, _load_config, _split_front_matter

def _create_claude_desktop_zip(config_path: str | Path | None) -> Path:
    content = _build_skill_content("claude_desktop_skill.md", config_path)
    export_dir = _get_user_config_dir() / "exports" / "claude-desktop"
    export_dir.mkdir(parents=True, exist_ok=True)
    zip_path = export_dir / "docatlas.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("docatlas/Skill.md", content)
    return zip_path


def _project_state_agent(agent: str) -> str:
    normalized = agent.lower()
    return "codex" if normalized in {"codex-app", "codex-desktop"} else normalized


def _project_bootstrap_dest(agent: str) -> Path | None:
    """Return the project instruction file supported by an agent.

    AGENTS.md is deliberately used for compatible coding agents: it keeps one
    compact, reviewable contract in the repository instead of duplicating a
    generated dependency or documentation inventory per agent.
    """
    normalized = agent.lower()
    if normalized == "claude-code":
        return Path("CLAUDE.md")
    if normalized in {"codex", "codex-app", "codex-desktop", "cursor", "opencode", "cline", "gemini", "github-copilot"}:
        return Path("AGENTS.md")
    return None


def _project_install_agents() -> set[str]:
    state_path = (
        _PROJECT_INSTALL_STATE
        if _PROJECT_INSTALL_STATE.exists()
        else _LEGACY_PROJECT_INSTALL_STATE
        if _LEGACY_PROJECT_INSTALL_STATE.exists()
        else None
    )
    if state_path is None:
        try:
            from docmancer.mcp.agent_config import known_agents, target_has_current_server_entry

            return {
                target.name
                for target in known_agents(project=True)
                if _project_bootstrap_dest(target.name) is not None
                and target_has_current_server_entry(target)
            }
        except (OSError, ValueError):
            return {
                "claude-code", "codex", "cursor", "opencode",
                "cline", "gemini", "github-copilot",
            }
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        agents = payload.get("agents", [])
        return {str(agent) for agent in agents if str(agent) in INSTALL_TARGETS}
    except (json.JSONDecodeError, OSError, AttributeError):
        return set()


def _write_project_install_agents(agents: set[str]) -> None:
    if not agents and not _LEGACY_PROJECT_INSTALL_STATE.exists():
        if _PROJECT_INSTALL_STATE.exists():
            _PROJECT_INSTALL_STATE.unlink()
        return
    _PROJECT_INSTALL_STATE.parent.mkdir(parents=True, exist_ok=True)
    _PROJECT_INSTALL_STATE.write_text(
        json.dumps({"agents": sorted(agents)}, indent=2) + "\n", encoding="utf-8"
    )


def _record_project_install(agent: str) -> None:
    agents = _project_install_agents()
    agents.add(_project_state_agent(agent))
    _write_project_install_agents(agents)


def _other_agent_uses_project_bootstrap(agent: str, dest: Path) -> bool:
    current = _project_state_agent(agent)
    return any(
        other != current and _project_bootstrap_dest(other) == dest
        for other in _project_install_agents()
    )


def _install_project_bootstrap(agent: str) -> Path | None:
    dest = _project_bootstrap_dest(agent)
    if dest is None:
        return None
    _install_or_append_agents_md(dest, _get_template_content("project_bootstrap.md"))
    return dest


def _remove_project_bootstrap(agent: str) -> bool:
    if agent.lower() == "github-copilot":
        copilot_removed = _remove_managed_instruction_block(Path(".github") / "copilot-instructions.md")
        agents_removed = _remove_managed_instruction_block(Path("AGENTS.md"))
        return copilot_removed or agents_removed
    dest = _project_bootstrap_dest(agent)
    return _remove_managed_instruction_block(dest) if dest else False


def _managed_instruction_paths(agent: str, *, project: bool) -> list[Path]:
    def include_legacy(paths: list[Path]) -> list[Path]:
        expanded: list[Path] = []
        for path in paths:
            expanded.append(path)
            legacy = _legacy_skill_path(path)
            if legacy is not None:
                expanded.append(legacy)
        return list(dict.fromkeys(expanded))

    if project:
        normalized = agent.lower()
        if normalized == "github-copilot":
            return [Path(".github") / "copilot-instructions.md", Path("AGENTS.md")]
        bootstrap = _project_bootstrap_dest(agent)
        skill_paths = {
            "claude-code": Path(".claude") / "skills" / SKILL_ID / "SKILL.md",
            "cursor": Path(".cursor") / "skills" / SKILL_ID / "SKILL.md",
            "cline": Path(".cline") / "skills" / SKILL_ID / "SKILL.md",
            "gemini": Path(".gemini") / "skills" / SKILL_ID / "SKILL.md",
        }
        paths = [path for path in (skill_paths.get(normalized), bootstrap) if path is not None]
        return include_legacy(paths)
    home = Path.home()
    normalized = agent.lower()
    paths = {
        "claude-code": [home / ".claude" / "skills" / SKILL_ID / "SKILL.md"],
        "cursor": [home / ".cursor" / "skills" / SKILL_ID / "SKILL.md", home / ".cursor" / "AGENTS.md"],
        "codex": [_get_codex_skill_path(), _get_shared_agent_skill_path()],
        "codex-app": [_get_codex_skill_path(), _get_shared_agent_skill_path()],
        "codex-desktop": [_get_codex_skill_path(), _get_shared_agent_skill_path()],
        "cline": [home / ".cline" / "skills" / SKILL_ID / "SKILL.md"],
        "gemini": [home / ".gemini" / "skills" / SKILL_ID / "SKILL.md"],
        "github-copilot": [_get_copilot_user_instructions_path()],
        "opencode": [home / ".config" / "opencode" / "skills" / SKILL_ID / "SKILL.md"],
    }
    return include_legacy(paths.get(normalized, []))


def _remove_managed_instruction_block(dest: Path) -> bool:
    if not dest.exists():
        return False
    existing = dest.read_text(encoding="utf-8")
    try:
        block = _current_managed_block(existing)
        marker_end = _AGENTS_MD_END
        if block is None:
            block = _legacy_managed_block(existing)
            marker_end = _LEGACY_AGENTS_MD_END
    except ValueError as exc:
        raise click.ClickException(f"Could not uninstall from {display_path(dest)} because {exc}.") from exc
    if block is None:
        return False
    start_idx, end_idx = block
    remaining = existing[:start_idx] + existing[end_idx + len(marker_end):]
    updated = remaining.strip()
    front_matter, body = _split_front_matter(remaining.lstrip())
    owned_skill_file = _SKILL_FILE_OWNER in remaining or _LEGACY_SKILL_FILE_OWNER in remaining
    cleaned_body = body.replace(_SKILL_FILE_OWNER, "").replace(_LEGACY_SKILL_FILE_OWNER, "")
    if owned_skill_file and front_matter and not cleaned_body.strip():
        dest.unlink()
    elif updated:
        dest.write_text(updated + "\n", encoding="utf-8")
    else:
        dest.unlink()
    return True


def _register_mcp_for_agent(agent_name: str, *, project: bool) -> None:
    """Register `doc-atlas mcp docs-serve` into a known agent's MCP config (best-effort)."""
    try:
        from docmancer.cli.mcp_commands import register_docmancer_mcp_in_agent
    except Exception:
        return
    msg = register_docmancer_mcp_in_agent(agent_name, project=project)
    if msg:
        _emit_status_line(msg, indent=0)


def _unregister_mcp_for_agent(agent_name: str, *, project: bool) -> bool:
    """Remove only DocAtlas' MCP entry from a supported client config."""
    try:
        from docmancer.mcp.agent_config import find_agent, unregister_server

        target = find_agent(agent_name, project=project)
        return unregister_server(target) if target else False
    except Exception as exc:
        raise click.ClickException(
            f"Could not unregister MCP server for {agent_name}: {exc}"
        ) from exc


def _install_vscode_copilot_settings(dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    settings: dict[str, object] = {}
    if dest.exists() and dest.read_text(encoding="utf-8").strip():
        try:
            settings = json.loads(dest.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise click.ClickException(f"Could not update {display_path(dest)} because it is not valid JSON: {exc}") from exc
        if not isinstance(settings, dict):
            raise click.ClickException(f"Could not update {display_path(dest)} because it must contain a JSON object.")
    settings.setdefault("github.copilot.chat.codeGeneration.useInstructionFiles", True)
    dest.write_text(json.dumps(settings, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return settings["github.copilot.chat.codeGeneration.useInstructionFiles"] is True


@click.command(
    cls=DocmancerCommand,
    context_settings={**HELP_CONTEXT_SETTINGS, "allow_extra_args": True},
    short_help="Create a project-local config file.",
    epilog=format_examples(
        "doc-atlas init",
        "doc-atlas init --dir ./sandbox",
    ),
)
@click.option("--dir", "directory", default=None, help="Target directory for the config file.")
def init_cmd(directory: str | None):
    """Initialize a DocAtlas project with the primary config identity."""
    import yaml as _yaml

    dir_path = Path(directory or ".")
    dir_path.mkdir(parents=True, exist_ok=True)
    config_path = dir_path / PRIMARY_CONFIG_NAME
    legacy_path = dir_path / LEGACY_CONFIG_NAME
    if config_path.exists():
        click.echo(f"Config already exists at {display_path(config_path)}")
        return
    if legacy_path.exists():
        click.echo(
            f"Legacy config already exists at {display_path(legacy_path)}; "
            f"refusing to create parallel {PRIMARY_CONFIG_NAME}. Rename it explicitly after review."
        )
        return
    DocmancerConfig = _get_config_class()
    config = DocmancerConfig()
    config.index.db_path = ".docatlas/docatlas.db"
    config.index.extracted_dir = ".docatlas/extracted"
    data = config.model_dump()
    with open(config_path, "w", encoding="utf-8") as handle:
        _yaml.dump(data, handle, default_flow_style=False, sort_keys=False)
    click.echo(f"Created config at {display_path(config_path)}")
    click.echo("Local SQLite FTS5 index configured at .docatlas/docatlas.db")


@click.command(
    cls=DocmancerCommand,
    context_settings=HELP_CONTEXT_SETTINGS,
    short_help="Add URL docs to the local SQLite index.",
    epilog=format_examples(
        "doc-atlas add https://docs.example.com",
        "doc-atlas add https://github.com/owner/repo",
        "doc-atlas add https://docs.example.com --max-pages 200",
    ),
)
@click.argument("path")
@click.option("--recreate", is_flag=True, help="Recreate the collection first.")
@click.option("--provider", default="auto", show_default=True,
              type=click.Choice(["auto", "gitbook", "mintlify", "web", "github", "crawl4ai"], case_sensitive=False),
              help="Docs platform. auto tries llms.txt then sitemap.xml. web uses generic pipeline.")
@click.option("--config", "config_path", default=None, help="Path to DocAtlas YAML config.")
@click.option("--max-pages", default=500, show_default=True, type=int,
              help="Maximum pages to fetch (web provider).")
@click.option("--strategy", default=None, type=str,
              help="Force a discovery strategy (e.g. llms-full.txt, sitemap.xml, nav-crawl).")
@click.option("--browser", is_flag=True, default=False,
              help="Enable Playwright browser fallback for JS-heavy sites.")
@click.option("--fetch-workers", default=None, type=int,
              help="Number of concurrent page fetch workers for the web provider.")
def add_cmd(
    path: str,
    recreate: bool,
    provider: str,
    config_path: str | None,
    max_pages: int,
    strategy: str | None,
    browser: bool,
    fetch_workers: int | None,
):
    """Add documents from a documentation URL or GitHub repository."""
    config_path = _effective_config(config_path)
    _configure_ingest_logging()

    config = _load_config(config_path)
    if fetch_workers is not None:
        config.web_fetch.workers = fetch_workers
    agent = _get_agent_class()(config=config)

    try:
        if path.startswith("http://") or path.startswith("https://"):
            click.echo(f"Adding docs from {path}...")
            total = agent.add(
                path,
                recreate=recreate,
                provider=provider if provider != "auto" else None,
                max_pages=max_pages,
                strategy=strategy,
                browser=browser,
            )
        else:
            warnings.warn(
                "doc-atlas add for local files is deprecated. Use doc-atlas ingest <path>. "
                "The compatibility path is retained through 1.x and scheduled for removal in 2.0.0.",
                DeprecationWarning,
                stacklevel=2,
            )
            click.echo(
                "Warning: local paths now belong to `doc-atlas ingest`. "
                "`doc-atlas add ./path` remains compatible through 1.x and is scheduled for removal in 2.0.0.",
                err=True,
            )
            total = agent.add(path, recreate=recreate)
        _emit_index_summary(total, agent)
        if getattr(agent, "last_ingest_skips", None):
            report_path = getattr(agent, "last_ingest_report_path", None)
            click.echo(f"Skipped {len(agent.last_ingest_skips)} file(s). Report: {display_path(report_path)}")
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@click.command(
    cls=DocmancerCommand,
    context_settings=HELP_CONTEXT_SETTINGS,
    short_help="Refresh all or specific indexed docs sources.",
    epilog=format_examples(
        "doc-atlas update",
        "doc-atlas update https://docs.example.com",
        "doc-atlas update ./docs",
    ),
)
@click.argument("source", required=False, default=None)
@click.option("--config", "config_path", default=None, help="Path to DocAtlas YAML config.")
@click.option("--max-pages", default=500, show_default=True, type=int,
              help="Maximum pages to fetch (web sources).")
@click.option("--browser", is_flag=True, default=False,
              help="Enable Playwright browser fallback for JS-heavy sites.")
def update_cmd(
    source: str | None,
    config_path: str | None,
    max_pages: int,
    browser: bool,
):
    """Re-fetch and re-index existing docs sources.

    With no arguments, refreshes every source in the index. Pass a specific
    source URL or path to update only that source.
    """
    config_path = _effective_config(config_path)
    _configure_ingest_logging()

    config = _load_config(config_path)
    agent = _get_agent_class()(config=config)

    sources = agent.list_sources_with_dates()
    if not sources:
        click.echo("No indexed sources to update. Run 'doc-atlas add <url-or-path>' first.")
        return

    if source:
        matching = [s for s in sources if s["source"] == source]
        if not matching:
            # Try matching against grouped docset roots
            grouped = agent.list_grouped_sources_with_dates()
            matching_root = [g for g in grouped if g["source"] == source]
            if matching_root:
                # Re-add the entire docset root
                matching = [s for s in sources if True]  # will be filtered below
                # Get all individual sources under this docset root
                all_sources = agent.list_sources_with_dates()
                matching = []
                with agent.store._connect() as conn:
                    rows = conn.execute(
                        "SELECT source FROM sources WHERE docset_root = ?", (source,)
                    ).fetchall()
                    matching = [{"source": row["source"]} for row in rows]
            if not matching:
                click.echo(f"Source not found in index: {source}")
                click.echo("Run 'doc-atlas list' to see indexed sources.")
                sys.exit(1)
        targets = matching
    else:
        # Deduplicate by docset root so we re-add at the docset level
        grouped = agent.list_grouped_sources_with_dates()
        targets = grouped

    updated = 0
    failed = 0
    for entry in targets:
        src = entry["source"]
        try:
            if src.startswith(("http://", "https://")):
                click.echo(f"Updating {src}...")
                agent.remove_source(src)
                total = agent.add(src, recreate=False, max_pages=max_pages, browser=browser)
            else:
                if not Path(src).exists():
                    click.echo(f"Skipping {src} (path not found on disk)")
                    failed += 1
                    continue
                click.echo(f"Updating {src}...")
                total = agent.add(src, recreate=False)
            click.echo(f"  {total} sections indexed")
            updated += 1
        except Exception as e:
            click.echo(f"  Error updating {src}: {e}", err=True)
            failed += 1

    click.echo()
    click.echo(f"Updated {updated} source(s)." + (f" {failed} failed." if failed else ""))


@click.command(
    cls=DocmancerCommand,
    context_settings=HELP_CONTEXT_SETTINGS,
    short_help="Index local files into the SQLite index.",
    epilog=format_examples(
        "doc-atlas ingest ./docs",
        "doc-atlas ingest ./README.md",
        "doc-atlas ingest ./docs --format md --format pdf",
        "doc-atlas ingest ./docs --include 'guides/**' --exclude '**/draft*'",
    ),
)
@click.argument("path")
@click.option("--recreate", is_flag=True, help="Recreate the collection first.")
@click.option("--include", "include_patterns", multiple=True, help="Glob pattern to include, relative to the ingest root.")
@click.option("--exclude", "exclude_patterns", multiple=True, help="Glob pattern to exclude, relative to the ingest root.")
@click.option(
    "--format",
    "formats",
    multiple=True,
    type=click.Choice(["md", "markdown", "txt", "pdf", "docx", "rtf", "html", "htm"], case_sensitive=False),
    help="Restrict ingest to one or more file formats.",
)
@click.option("--recursive/--no-recursive", default=True, show_default=True, help="Recurse through directories.")
@click.option("--skip-known", is_flag=True, help="Skip files whose content hash is already indexed.")
@click.option("--no-vectors", is_flag=True, help="Index FTS5 only; skip embedding/vector upsert.")
@click.option("--config", "config_path", default=None, help="Path to DocAtlas YAML config.")
def ingest_cmd(
    path: str,
    recreate: bool,
    include_patterns: tuple[str, ...],
    exclude_patterns: tuple[str, ...],
    formats: tuple[str, ...],
    recursive: bool,
    skip_known: bool,
    no_vectors: bool,
    config_path: str | None,
):
    """Index local files or directories."""
    if path.startswith(("http://", "https://")):
        raise click.ClickException("Use `doc-atlas add` for URLs.")

    config_path = _effective_config(config_path)
    _configure_ingest_logging()
    config = _load_config(config_path)
    agent = _get_agent_class()(config=config)

    if recreate and not no_vectors:
        _drop_vector_collection(config, agent)

    try:
        total = agent.ingest(
            path,
            recreate=recreate,
            include=include_patterns,
            exclude=exclude_patterns,
            formats=formats,
            recursive=recursive,
            skip_known=skip_known,
            with_vectors=not no_vectors,
        )
        _emit_index_summary(total, agent)
        if getattr(agent, "last_ingest_skips", None):
            report_path = getattr(agent, "last_ingest_report_path", None)
            click.echo(f"Skipped {len(agent.last_ingest_skips)} file(s). Report: {display_path(report_path)}")
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _drop_vector_collection(config, agent) -> None:
    """Best-effort: remove the Qdrant collection + persisted meta so the
    next ingest rebuilds at the current embedder dimension.

    Silent on missing-collection / Qdrant-down: callers use this defensively
    before re-ingest, and a missing collection is success, not failure.
    """
    try:
        from docmancer.core import index_meta
        from docmancer.runtime.qdrant_manager import ensure_running
        from docmancer.stores.base import get_vector_store
    except ImportError:
        return

    collection = agent._vector_collection_name()
    vs_config = config.vector_store
    if vs_config.provider == "qdrant" and not vs_config.url:
        resolution = ensure_running()
        if not resolution.url:
            index_meta.drop(collection)
            return
        vs_config = vs_config.model_copy(update={"url": resolution.url})

    try:
        store = get_vector_store(vs_config, embeddings_dim=config.embeddings.dimensions)
        store.delete_collection(collection)
    except Exception as exc:
        logger = logging.getLogger(__name__)
        logger.debug("could not drop vector collection %r: %s", collection, exc)
    index_meta.drop(collection)


@click.command(
    cls=DocmancerCommand,
    context_settings=HELP_CONTEXT_SETTINGS,
    short_help="Download docs to Markdown files.",
    epilog=format_examples(
        "doc-atlas fetch https://docs.example.com",
        "doc-atlas fetch https://docs.example.com --output ./downloaded-docs",
    ),
)
@click.argument("url")
@click.option(
    "--output",
    "output_dir",
    default="docmancer-docs",
    show_default=True,
    help="Output directory for downloaded .md files.",
)
def fetch_cmd(url: str, output_dir: str):
    """Download docs from a GitBook URL to local .md files."""
    from urllib.parse import urlparse
    from docmancer.connectors.fetchers.factory import build_fetcher

    fetcher = build_fetcher(url, provider="gitbook")
    click.echo(f"Fetching docs from {url}...")
    try:
        documents = fetcher.fetch(url)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    for doc in documents:
        parsed = urlparse(doc.source)
        slug = parsed.path.strip("/").replace("/", "_") or "index"
        filename = f"{slug}.md"
        file_path = out_path / filename
        file_path.write_text(doc.content, encoding="utf-8")
        click.echo(f"  Saved {display_path(file_path)}")

    click.echo(f"Downloaded {len(documents)} document(s) to {output_dir}/")


@click.command(
    cls=DocmancerCommand,
    context_settings=HELP_CONTEXT_SETTINGS,
    short_help="Stream-ingest a USPTO trademark XML / ZIP bulk file.",
    epilog=format_examples(
        "doc-atlas ingest-uspto apc18840407-20240102-xx.xml",
        "doc-atlas ingest-uspto bulk-trademarks-2024.zip --include-dead",
        "doc-atlas ingest-uspto daily.xml.gz --no-vectors --batch-size 5000",
    ),
)
@click.argument("path", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option("--recreate", is_flag=True, help="Clear the index before ingesting.")
@click.option("--include-dead", is_flag=True, help="Index dead/abandoned marks too (default: live only).")
@click.option("--no-vectors", is_flag=True, help="Skip embedding/vector upsert; index FTS5 only.")
@click.option("--batch-size", default=1000, type=int, show_default=True, help="Commit batch size for streaming ingest.")
@click.option("--limit", default=None, type=int, help="Stop after N records (smoke testing).")
@click.option("--config", "config_path", default=None, help="Path to DocAtlas YAML config.")
def ingest_uspto_cmd(
    path: str,
    recreate: bool,
    include_dead: bool,
    no_vectors: bool,
    batch_size: int,
    limit: int | None,
    config_path: str | None,
):
    """Stream USPTO trademark case-files into the local index.

    Accepts an `.xml`, `.xml.gz`, or `.zip` archive containing the USPTO bulk
    trademark XML. Each `<case-file>` becomes one Section in SQLite (no
    heading splitting). Memory stays flat thanks to streaming iterparse and
    batched SQLite commits.
    """
    from docmancer.connectors.fetchers.uspto_tm import (
        ParseStats,
        iter_uspto_documents,
    )

    config_path = _effective_config(config_path)
    _configure_ingest_logging()
    config = _load_config(config_path)
    agent = _get_agent_class()(config=config)

    stats = ParseStats()

    def _records():
        count = 0
        for doc in iter_uspto_documents(path, live_only=not include_dead, stats=stats):
            yield doc
            count += 1
            if limit is not None and count >= limit:
                break

    def _progress(sources: int, sections: int) -> None:
        click.echo(
            f"  ... {sources} record(s) ingested ({stats.parsed} parsed, "
            f"{stats.skipped_dead} skipped dead, {stats.failed} failed)"
        )

    try:
        total = agent.ingest_records(
            _records(),
            recreate=recreate,
            batch_size=batch_size,
            with_vectors=not no_vectors,
            progress_callback=_progress,
        )
    except Exception as exc:
        click.echo(f"USPTO ingest failed: {type(exc).__name__}: {exc}", err=True)
        sys.exit(1)

    click.echo()
    click.echo(f"Parsed:        {stats.parsed}")
    click.echo(f"Emitted:       {stats.emitted}")
    click.echo(f"Skipped dead:  {stats.skipped_dead}")
    click.echo(f"Failed:        {stats.failed}")
    if stats.failures_by_reason:
        click.echo("Failure reasons:")
        for reason, count in sorted(stats.failures_by_reason.items()):
            click.echo(f"  {reason}: {count}")
    click.echo(f"Sections indexed: {total}")

__all__=['_create_claude_desktop_zip', '_project_state_agent', '_project_bootstrap_dest', '_project_install_agents', '_write_project_install_agents', '_record_project_install', '_other_agent_uses_project_bootstrap', '_install_project_bootstrap', '_remove_project_bootstrap', '_managed_instruction_paths', '_remove_managed_instruction_block', '_register_mcp_for_agent', '_unregister_mcp_for_agent', '_install_vscode_copilot_settings', 'init_cmd', 'add_cmd', 'update_cmd', 'ingest_cmd', '_drop_vector_collection', 'fetch_cmd', 'ingest_uspto_cmd']
