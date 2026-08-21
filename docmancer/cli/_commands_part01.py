"""Implementation shard 1 for commands."""
from __future__ import annotations

from ._commands_shared import *  # noqa: F401,F403

def _effective_config(config_path: str | None) -> str | None:
    """Merge subcommand --config with group-level --config."""
    if config_path is not None:
        return config_path
    ctx = click.get_current_context(silent=True)
    if ctx and ctx.parent and ctx.parent.obj:
        return ctx.parent.obj.get("config_path")
    return None


def _get_agent_class():
    from docmancer.agent import DocmancerAgent

    return DocmancerAgent


def _get_config_class():
    from docmancer.core.config import DocmancerConfig

    return DocmancerConfig


def _get_user_config_dir() -> Path:
    return _resolved_user_home(home_dir=Path.home())


def _get_user_config_path() -> Path:
    return _primary_user_config_path(home_dir=Path.home())


def _get_codex_skill_path() -> Path:
    return Path.home() / ".codex" / "skills" / SKILL_ID / "SKILL.md"


def _get_shared_agent_skill_path() -> Path:
    return Path.home() / ".agents" / "skills" / SKILL_ID / "SKILL.md"


def _get_gemini_skill_path() -> Path:
    return Path.home() / ".gemini" / "skills" / SKILL_ID / "SKILL.md"


def _get_cline_skill_path() -> Path:
    return Path.home() / ".cline" / "skills" / SKILL_ID / "SKILL.md"


def _get_copilot_user_instructions_path() -> Path:
    return Path.home() / ".copilot" / "copilot-instructions.md"


def _build_user_bootstrap_config():
    DocmancerConfig = _get_config_class()
    config = DocmancerConfig()
    config.index.db_path = str((_get_user_config_dir() / "docatlas.db").resolve())
    config.index.extracted_dir = str((_get_user_config_dir() / "extracted").resolve())
    return config


def _ensure_user_config() -> Path:
    import yaml as _yaml

    config_path = _get_user_config_path()
    if config_path.exists():
        return config_path
    legacy_path = _legacy_user_config_path(home_dir=Path.home())
    if legacy_path.exists():
        warnings.warn(
            f"Legacy DocAtlas config {legacy_path} is deprecated; rename it to {config_path.name!r}.",
            DeprecationWarning,
            stacklevel=2,
        )
        return legacy_path

    owned_home = _ensure_user_home(home_dir=Path.home())
    config_path = owned_home / PRIMARY_CONFIG_NAME
    config = _build_user_bootstrap_config()
    with open(config_path, "w", encoding="utf-8") as handle:
        _yaml.dump(config.model_dump(), handle, default_flow_style=False, sort_keys=False)
    return config_path


def _load_config(config_path: str | None):
    DocmancerConfig = _get_config_class()
    if config_path:
        return DocmancerConfig.from_yaml(config_path)
    for name in (PRIMARY_CONFIG_NAME, LEGACY_CONFIG_NAME):
        candidate = Path(name)
        if candidate.exists():
            if name == LEGACY_CONFIG_NAME:
                warnings.warn(
                    f"Legacy DocAtlas config name {LEGACY_CONFIG_NAME!r} is deprecated; use {PRIMARY_CONFIG_NAME!r}.",
                    DeprecationWarning,
                    stacklevel=2,
                )
            return DocmancerConfig.from_yaml(candidate)
    return DocmancerConfig.from_yaml(_ensure_user_config())


def _resolve_config_file(config_path: str | None) -> Path:
    if config_path:
        return Path(config_path).resolve()
    for name in (PRIMARY_CONFIG_NAME, LEGACY_CONFIG_NAME):
        candidate = Path(name)
        if candidate.exists():
            return candidate.resolve()
    return _ensure_user_config().resolve()


def _describe_index(config) -> str:
    return f"SQLite FTS5 at {display_path(config.index.db_path)}"


def _effective_retrieval_mode(mode: str | None, config) -> str:
    if mode:
        return mode.lower()
    configured = getattr(getattr(config, "retrieval", None), "default_mode", None)
    if isinstance(configured, str) and configured:
        return configured.lower()
    return "lexical"


def _write_config_yaml(config, config_file: Path) -> None:
    import yaml as _yaml

    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(_yaml.safe_dump(config.model_dump(), sort_keys=False), encoding="utf-8")


def _apply_setup_retrieval_profile(config, retrieval_profile: str, *, offline: bool = False, vectors: str | None = None):
    profile = retrieval_profile.lower()
    vectors = (vectors or "auto").lower()
    if offline or vectors == "off" or profile == "lexical-now":
        config.retrieval.default_mode = "lexical"
    elif profile == "local-hybrid":
        config.retrieval.default_mode = "hybrid"
        config.vector_store.provider = "qdrant"
        config.embeddings.provider = "fastembed"
    elif profile == "cloud":
        config.retrieval.default_mode = "hybrid"
    return config


def _agent_install_path(target: str, *, project: bool = False) -> Path:
    home = Path.home()
    normalized = target.lower()
    if normalized == "claude-code":
        return Path(".claude") / "skills" / SKILL_ID / "SKILL.md" if project else home / ".claude" / "skills" / SKILL_ID / "SKILL.md"
    if normalized == "cursor":
        return Path(".cursor") / "skills" / SKILL_ID / "SKILL.md" if project else home / ".cursor" / "skills" / SKILL_ID / "SKILL.md"
    if normalized == "cline":
        return Path(".cline") / "skills" / SKILL_ID / "SKILL.md" if project else _get_cline_skill_path()
    if normalized in {"codex", "codex-app", "codex-desktop"}:
        return _get_codex_skill_path()
    if normalized == "gemini":
        return Path(".gemini") / "skills" / SKILL_ID / "SKILL.md" if project else _get_gemini_skill_path()
    if normalized == "github-copilot":
        return Path(".github") / "copilot-instructions.md" if project else _get_copilot_user_instructions_path()
    if normalized == "opencode":
        return home / ".config" / "opencode" / "skills" / SKILL_ID / "SKILL.md"
    if normalized == "claude-desktop":
        return _get_user_config_dir() / "exports" / "claude-desktop" / "docatlas.zip"
    return _get_user_config_dir() / normalized


def _source_rows(config, *, grouped: bool = True) -> list[dict]:
    db_path = Path(config.index.db_path)
    if not db_path.exists():
        return []
    group_expr = "COALESCE(NULLIF(s.docset_root, ''), s.source)" if grouped else "s.source"
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT
                    {group_expr} AS source,
                    MAX(s.ingested_at) AS ingested_at,
                    COALESCE(NULLIF(json_extract(s.metadata_json, '$.format'), ''), sec.format, 'unknown') AS type,
                    COUNT(sec.id) AS sections,
                    SUM(CASE WHEN LENGTH(TRIM(COALESCE(sec.text, ''))) = 0 THEN 1 ELSE 0 END) AS empty_sections,
                    SUM(CASE WHEN LENGTH(TRIM(COALESCE(sec.text, ''))) < 80 THEN 1 ELSE 0 END) AS sparse_sections,
                    SUM(CASE WHEN up.status IS NOT NULL AND up.status != 'ok' THEN 1 ELSE 0 END) AS vector_failures,
                    SUM(CASE WHEN up.chunk_id IS NOT NULL THEN 1 ELSE 0 END) AS vector_rows
                FROM sources s
                LEFT JOIN sections sec ON sec.source_id = s.id
                LEFT JOIN embedding_upserts up ON up.chunk_id = sec.id
                GROUP BY {group_expr}
                ORDER BY MAX(s.ingested_at) DESC, {group_expr}
                """
            ).fetchall()
    except sqlite3.Error:
        return []
    return [dict(row) for row in rows]


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _freshness_label(ingested_at: str | None) -> tuple[str, bool]:
    parsed = _parse_dt(ingested_at)
    if parsed is None:
        return "unknown", False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    days = max(0, (datetime.now(timezone.utc) - parsed).days)
    if days == 0:
        return "today", False
    return f"stale {days}d", days >= 30


def _operational_source_card(row: dict) -> dict:
    sections = int(row.get("sections") or 0)
    empty = int(row.get("empty_sections") or 0)
    sparse = int(row.get("sparse_sections") or 0)
    failures = int(row.get("vector_failures") or 0)
    vector_rows = int(row.get("vector_rows") or 0)
    freshness, stale = _freshness_label(row.get("ingested_at"))
    vectors = "none"
    if vector_rows and vector_rows == sections:
        vectors = "ok"
    elif vector_rows:
        vectors = "drift"
    status = "ready"
    next_action = f"doc-atlas query \"question about {row.get('source', 'docs')}\""
    if failures:
        status = "failed"
        next_action = f"doc-atlas update {row.get('source', '')}".strip()
    elif stale or vectors == "drift" or empty or sparse:
        status = "degraded"
        next_action = f"doc-atlas update {row.get('source', '')}".strip()
    elif sections == 0:
        status = "failed"
        next_action = f"doc-atlas remove {row.get('source', '')}".strip()
    return {
        "source": row.get("source") or "unknown",
        "type": row.get("type") or "unknown",
        "status": status,
        "freshness": freshness,
        "content": f"{sections} sections",
        "vectors": vectors,
        "failures": failures,
        "next_action": next_action,
        "details": {"sections": sections, "empty_sections": empty, "sparse_sections": sparse, "ingested_at": row.get("ingested_at")},
    }


def _agent_installed_targets() -> list[str]:
    installed: list[str] = []
    for target in INSTALL_TARGETS:
        if _agent_install_path(target, project=(target == "github-copilot")).exists() or _agent_install_path(target).exists():
            installed.append(target)
    return installed


def _doctor_issue(code: str, group: str, severity: str, impact: str, fix_command: str, expected_result: str, *, restart_required: bool = False, auto_fix: bool = False) -> dict:
    return {
        "code": code,
        "group": group,
        "severity": severity,
        "impact": impact,
        "fix_command": fix_command,
        "expected_result": expected_result,
        "restart_required": restart_required,
        "auto_fix": auto_fix,
    }


def _collect_doctor_report(config, config_path: str | None, *, profile: str = "cli-docs") -> dict:
    if config_path:
        effective_config = Path(config_path).resolve()
    elif Path(PRIMARY_CONFIG_NAME).exists():
        effective_config = Path(PRIMARY_CONFIG_NAME).resolve()
    elif Path(LEGACY_CONFIG_NAME).exists():
        effective_config = Path(LEGACY_CONFIG_NAME).resolve()
    else:
        primary_user = _get_user_config_path()
        legacy_user = _legacy_user_config_path(home_dir=Path.home())
        effective_config = primary_user if primary_user.exists() or not legacy_user.exists() else legacy_user
    issues: list[dict] = []
    checks: list[dict] = []

    def add_check(group: str, status: str, message: str) -> None:
        checks.append({"group": group, "status": status, "message": message})

    if effective_config.exists():
        add_check("config", "ok", f"Config exists at {effective_config}")
    else:
        add_check("config", "failed", f"Config missing at {effective_config}")
        issues.append(_doctor_issue("CONFIG_MISSING", "config", "BLOCKER", "DocAtlas has no config to load paths and retrieval defaults.", "doc-atlas setup --yes", "docatlas.yaml exists and doctor can read it.", auto_fix=True))

    db_path = Path(config.index.db_path)
    add_check("storage", "ok" if db_path.parent.exists() else "failed", f"Index path: {db_path}")
    try:
        import sqlite3 as _sqlite3
        with _sqlite3.connect(db_path) as conn:
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts5_doctor_check USING fts5(value)")
            conn.execute("DROP TABLE IF EXISTS fts5_doctor_check")
        add_check("sqlite", "ok", "SQLite FTS5 is available")
    except Exception as exc:  # noqa: BLE001
        add_check("sqlite", "failed", str(exc))
        issues.append(_doctor_issue("SQLITE_FTS5_MISSING", "sqlite", "BLOCKER", "Lexical search cannot work without SQLite FTS5.", "Use a Python build with SQLite FTS5, then rerun doc-atlas setup --yes", "doctor shows SQLite FTS5 available."))

    stats = {"sources_count": 0, "sections_count": 0, "extracted_dir": str(getattr(config.index, "extracted_dir", ""))}
    try:
        agent = _get_agent_class()(config=config)
        stats = agent.collection_stats()
        sources = int(stats.get("sources_count", 0) or 0)
        sections = int(stats.get("sections_count", 0) or 0)
        add_check("sources", "ok" if sources else "empty", f"{sources} source(s), {sections} section(s)")
        if sources == 0:
            issues.append(_doctor_issue("NO_SOURCES", "sources", "BLOCKER" if profile == "cli-docs" else "DEGRADED", "Queries have no documentation context to return.", "doc-atlas ingest ./docs", "doc-atlas list shows at least one ready source."))
    except Exception as exc:  # noqa: BLE001
        add_check("storage", "failed", str(exc))
        issues.append(_doctor_issue("INDEX_OPEN_FAILED", "storage", "BLOCKER", "The local index cannot be opened.", "doc-atlas setup --yes", "doctor can read collection stats."))

    for label, available, hint in _loader_availability():
        add_check("extraction", "ok" if available else "missing", f"{label}: {'available' if available else hint}")
        if not available:
            issues.append(_doctor_issue(f"LOADER_{label.upper().replace(' ', '_')}_MISSING", "extraction", "WARN", f"{label} documents may not extract correctly.", f"pip install doc-atlas", f"{label} loader is available."))

    retrieval_mode = _effective_retrieval_mode(None, config)
    if retrieval_mode != "lexical":
        if find_spec("fastembed") is None:
            issues.append(_doctor_issue("FASTEMBED_MISSING", "embeddings", "DEGRADED", "Dense/sparse retrieval cannot embed queries locally.", "pip install doc-atlas", "doctor shows embeddings provider available."))
        add_check("embeddings", "ok" if find_spec("fastembed") else "missing", f"provider={config.embeddings.provider} model={config.embeddings.model}")
        try:
            from docmancer.runtime.qdrant_manager import QdrantManager

            qdrant_status = QdrantManager().status()
            add_check("qdrant", "ok" if qdrant_status.get("alive") else "missing", "qdrant running" if qdrant_status.get("alive") else "qdrant not running")
            if not qdrant_status.get("alive"):
                issues.append(_doctor_issue("QDRANT_NOT_RUNNING", "qdrant", "DEGRADED", "Hybrid/vector retrieval falls back or fails depending on --allow-degraded.", "doc-atlas qdrant up", "doctor shows qdrant running.", auto_fix=True))
        except Exception as exc:  # noqa: BLE001
            add_check("qdrant", "failed", str(exc))

    installed_agents = _agent_installed_targets()
    add_check("agent", "ok" if installed_agents else "missing", f"installed: {', '.join(installed_agents) if installed_agents else 'none'}")
    if profile == "agent" and not installed_agents:
        issues.append(_doctor_issue("AGENT_NOT_INSTALLED", "agent", "BLOCKER", "The selected agent path cannot see Docmancer instructions.", "doc-atlas install codex", "doctor shows at least one installed agent integration.", restart_required=True, auto_fix=True))

    severity_rank = {name: i for i, name in enumerate(DOCTOR_SEVERITIES)}
    worst = min((severity_rank.get(issue["severity"], 99) for issue in issues), default=severity_rank["INFO"])
    return {
        "profile": profile,
        "config_path": str(effective_config),
        "index": str(db_path),
        "retrieval_mode": retrieval_mode,
        "stats": stats,
        "checks": checks,
        "issues": issues,
        "status": DOCTOR_SEVERITIES[worst] if issues else "OK",
    }


def _emit_doctor_report(report: dict) -> None:
    _emit_brand_header("doc-atlas doctor", "What prevents docs context in the selected path?")
    click.echo(_style("  Selected path", fg="white", bold=True))
    _emit_status_line(f"profile: {report['profile']}")
    _emit_status_line(f"retrieval: {report['retrieval_mode']}")
    _emit_status_line(f"Config: {display_path(report['config_path'])}")
    _emit_status_line(f"Index: SQLite FTS5 at {display_path(report['index'])}")
    stats = report.get("stats") or {}
    _emit_status_line(f"Sources indexed: {stats.get('sources_count', 0)}")
    _emit_status_line(f"Sections indexed: {stats.get('sections_count', 0)}")
    _emit_status_line(f"Inspectable extracts: {display_path(stats.get('extracted_dir', ''))}")

    grouped: dict[str, list[dict]] = {}
    for check in report["checks"]:
        grouped.setdefault(check["group"], []).append(check)
    for group in DOCTOR_CHECK_GROUPS:
        checks = grouped.get(group)
        if not checks:
            continue
        click.echo()
        display_group = "Local loaders" if group == "extraction" else group
        click.echo(_style(f"  {display_group}", fg="white", bold=True))
        for check in checks:
            state = "ok" if check["status"] == "ok" else "warn" if check["status"] in {"empty", "missing"} else "error"
            _emit_status_line(check["message"], state=state, indent=4)

    if report["issues"]:
        click.echo()
        click.echo(_style("  Issues", fg="white", bold=True))
        for issue in report["issues"]:
            click.echo(f"    [{issue['severity']}] {issue['code']} ({issue['group']})")
            click.echo(f"      Impact: {issue['impact']}")
            click.echo(f"      Fix command: {issue['fix_command']}")
            click.echo(f"      Expected result: {issue['expected_result']}")
            click.echo(f"      Restart required: {'yes' if issue['restart_required'] else 'no'}")
            click.echo(f"      Auto-fix: {'yes' if issue['auto_fix'] else 'no'}")
    else:
        click.echo()
        _emit_status_line("No blockers for selected path.")


def _run_dispatch_query(
    *,
    agent,
    config,
    query: str,
    mode: str,
    limit: int | None,
    budget: int | None,
    expand: str | None,
    allow_degraded: bool = False,
):
    """Build a RetrievalDispatcher and return chunks plus trace metadata.

    Falls back to lexical-only if the embeddings provider or vector store
    cannot be *constructed*. Runtime retrieval failures (dimension mismatch,
    Qdrant down) propagate to the caller in non-lexical modes unless the caller
    sets ``allow_degraded=True``.
    """
    try:
        from docmancer.retrieval.runtime import dispatcher_for_agent

        dispatcher = dispatcher_for_agent(agent, mode=mode)
    except Exception as exc:
        failures = {"vector": f"{type(exc).__name__}: {exc}"}
        if allow_degraded:
            chunks = agent.query(query, limit=limit, budget=budget, expand=expand)
            return chunks, {}, failures, "lexical", {"lexical": len(chunks)}
        raise HybridRetrievalError(failures) from exc

    result = dispatcher.run(
        query,
        mode=mode,
        limit=limit,
        budget=budget,
        expand=expand,
        allow_degraded=allow_degraded,
    )
    return result.chunks, result.contributions, result.failures, result.mode_used, result.candidate_counts


def _path_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


def _emit_index_summary(total: int, agent) -> None:
    click.echo(f"Total: {total} sections indexed")
    try:
        stats = agent.collection_stats()
    except Exception:
        return

    db_path_value = stats.get("db_path") if isinstance(stats, dict) else None
    extracted_dir_value = stats.get("extracted_dir") if isinstance(stats, dict) else None

    db_path = Path(db_path_value) if db_path_value else None
    extracted_dir = Path(extracted_dir_value) if extracted_dir_value else None
    db_size = _path_size(db_path) if db_path else 0
    extracted_size = _path_size(extracted_dir) if extracted_dir else 0
    total_size = db_size + extracted_size

    if total_size:
        click.echo(f"Storage: {_format_size(total_size)} on disk")
    if db_path:
        suffix = f" ({_format_size(db_size)})" if db_size else ""
        click.echo(f"Index: {display_path(db_path)}{suffix}")
    if extracted_dir:
        suffix = f" ({_format_size(extracted_size)})" if extracted_size else ""
        click.echo(f"Extracted docs: {display_path(extracted_dir)}{suffix}")


def _create_agent_or_raise_lock_error(config):
    try:
        return _get_agent_class()(config=config)
    except RuntimeError:
        raise


def _color_enabled() -> bool:
    return color_enabled()


def _style(text: str, **styles: str | bool) -> str:
    return style(text, **styles)


def _emit_brand_header(command: str, subtitle: str) -> None:
    click.echo()
    for line in BANNER_LINES:
        click.echo(_style(line, fg=BANNER_COLOR, bold=True))
    click.echo(_style(f"  {command}", fg="white", bold=True) + _style(f"  {subtitle}", fg="bright_black"))
    click.echo()


def _emit_status_line(message: str, state: str = "ok", indent: int = 2) -> None:
    palette = {
        "ok": ("[OK]", "bright_green"),
        "info": ("[--]", "bright_cyan"),
        "warn": ("[--]", "yellow"),
        "error": ("[!!]", "red"),
    }
    label, color = palette[state]
    click.echo(" " * indent + _style(label, fg=color, bold=True) + f" {message}")


def _emit_next_step(text: str) -> None:
    click.echo()
    click.echo(_style("  Next:", fg="bright_green", bold=True) + f" {text}")


def _loader_availability() -> list[tuple[str, bool, str]]:
    checks = [
        ("txt", find_spec("charset_normalizer") is not None, "reinstall doc-atlas; charset-normalizer ships in core"),
        ("pdf", find_spec("pypdf") is not None, "reinstall doc-atlas; pypdf ships in core"),
        ("pdf fallback", find_spec("pdfplumber") is not None, "reinstall doc-atlas; pdfplumber ships in core"),
        ("docx", find_spec("docx") is not None, "reinstall doc-atlas; python-docx ships in core"),
        ("rtf", find_spec("striprtf") is not None, "reinstall doc-atlas; striprtf ships in core"),
        ("html", True, "built in"),
        ("markdown", True, "built in"),
    ]
    return checks


class _IngestLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        lower = message.lower()

        if lower.startswith("http request:"):
            return _style("[http] ", fg="bright_black") + message
        if "auto-detected platform" in lower or lower.startswith("detected platform:"):
            return _style("[site] ", fg="bright_cyan", bold=True) + message
        if lower.startswith("fetched ") and "starting ingest" in lower:
            return _style("[fetch] ", fg="bright_green", bold=True) + message
        if lower.startswith("chunking ") or lower.startswith("built "):
            return _style("[chunk] ", fg="yellow", bold=True) + message
        if lower.startswith("embedding ") or lower.startswith("vectors:"):
            return _style("[embed] ", fg="bright_cyan", bold=True) + message
        if lower.startswith("indexing "):
            return _style("[index] ", fg="magenta", bold=True) + message
        if lower.startswith("stored ") or lower.startswith("persisting batch "):
            return _style("[store] ", fg="bright_blue", bold=True) + message
        if lower.startswith("stored source ") or lower.startswith("processed "):
            return _style("[done] ", fg="bright_green", bold=True) + message
        if "large local write detected" in lower or "this step can take a while" in lower:
            return _style("[hint] ", fg="bright_yellow", bold=True) + message
        return message


def _configure_ingest_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(_IngestLogFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    for noisy_logger in ("httpx", "httpcore", "qdrant_client"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


def _emit_install_summary(
    heading: str,
    installed_paths: list[tuple[str, Path]],
    created_user_config: bool,
    effective_config_path: Path | None,
    next_step: str,
    extra_lines: list[str] | None = None,
) -> None:
    _emit_brand_header("doc-atlas install", heading)
    for label, path in installed_paths:
        _emit_status_line(f"{label}: {display_path(path)}")
    if created_user_config:
        _emit_status_line(f"Created user config at {display_path(_get_user_config_path())}")
    elif effective_config_path is not None:
        _emit_status_line(f"Skill uses config {display_path(effective_config_path)}")
    for line in extra_lines or []:
        _emit_status_line(line, state="info")
    _emit_next_step(next_step)


def _get_template_content(template_name: str) -> str:
    from importlib.resources import files
    templates = files("docmancer.templates")
    content = templates.joinpath(template_name).read_text(encoding="utf-8")
    if "{{CANONICAL_AGENT_CONTRACT}}" in content:
        canonical = templates.joinpath("agent_contract.md").read_text(encoding="utf-8").strip()
        content = content.replace("{{CANONICAL_AGENT_CONTRACT}}", canonical)
    return content


def _resolve_docmancer_executable() -> str:
    resolved = shutil.which("doc-atlas") or shutil.which("docmancer")
    if resolved:
        return str(Path(resolved).resolve())
    return f"{sys.executable} -m docmancer"


def _resolve_skill_command(config_path: str | Path | None) -> str:
    parts = [_resolve_docmancer_executable()]
    if config_path is not None:
        parts.extend(["--config", str(Path(config_path).resolve())])
    return " ".join(shlex.quote(part) for part in parts)


def _resolve_install_config_path(config_path: str | None, project: bool) -> Path | None:
    if config_path:
        return Path(config_path).resolve()
    if project:
        for name in (PRIMARY_CONFIG_NAME, LEGACY_CONFIG_NAME):
            candidate = Path(name)
            if candidate.exists():
                return candidate.resolve()
        return None
    return _ensure_user_config().resolve()


def _build_skill_content(template_name: str, config_path: str | Path | None) -> str:
    content = _get_template_content(template_name)
    return content.replace("{{DOCS_KIT_CMD}}", _resolve_skill_command(config_path))


def _install_skill_file(content: str, dest: Path) -> None:
    try:
        _migrate_legacy_skill_file(dest)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    front_matter, body = _split_front_matter(content)
    marker_block = f"{_AGENTS_MD_START}\n{body.strip()}\n{_AGENTS_MD_END}\n"
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(front_matter + _SKILL_FILE_OWNER + "\n" + marker_block, encoding="utf-8")
        return

    existing = dest.read_text(encoding="utf-8")
    for start_marker, end_marker in (
        (_AGENTS_MD_START, _AGENTS_MD_END),
        (_LEGACY_AGENTS_MD_START, _LEGACY_AGENTS_MD_END),
    ):
        if existing.startswith(start_marker):
            end_idx = existing.find(end_marker)
            if end_idx != -1:
                managed = existing[len(start_marker):end_idx].strip()
                old_front_matter, _ = _split_front_matter(managed)
                if old_front_matter and _is_proven_docatlas_text(managed):
                    suffix = existing[end_idx + len(end_marker):]
                    dest.write_text(front_matter + _SKILL_FILE_OWNER + "\n" + marker_block + suffix, encoding="utf-8")
                    return

    try:
        legacy = _legacy_managed_block(existing)
    except ValueError as exc:
        raise click.ClickException(f"Could not update {display_path(dest)} because {exc}.") from exc
    if legacy is not None:
        start_idx, end_idx = legacy
        legacy_managed = existing[
            start_idx + len(_LEGACY_AGENTS_MD_START):end_idx
        ].strip()
        old_front_matter, _ = _split_front_matter(legacy_managed)
        legacy_prefix = (
            existing[:start_idx]
            .replace(_LEGACY_SKILL_FILE_OWNER, "")
            .replace(_SKILL_FILE_OWNER, "")
            .strip()
        )
        if old_front_matter and not legacy_prefix and _is_proven_docatlas_text(legacy_managed):
            suffix = existing[end_idx + len(_LEGACY_AGENTS_MD_END):]
            dest.write_text(
                front_matter + _SKILL_FILE_OWNER + "\n" + marker_block + suffix,
                encoding="utf-8",
            )
            return
        existing = (
            existing[:start_idx]
            + marker_block.rstrip("\n")
            + existing[end_idx + len(_LEGACY_AGENTS_MD_END):]
        )
        existing = existing.replace(_LEGACY_SKILL_FILE_OWNER, _SKILL_FILE_OWNER, 1)
        dest.write_text(existing, encoding="utf-8")

    existing_front_matter, _ = _split_front_matter(existing)
    if _SKILL_FILE_OWNER in existing and existing_front_matter:
        try:
            block = _current_managed_block(existing)
        except ValueError as exc:
            raise click.ClickException(f"Could not update {display_path(dest)} because {exc}.") from exc
        if block is None:
            raise click.ClickException(f"Could not update {display_path(dest)} because its DocAtlas markers are missing.")
        start_idx, end_idx = block
        suffix = existing[end_idx + len(_AGENTS_MD_END):]
        dest.write_text(front_matter + _SKILL_FILE_OWNER + "\n" + marker_block + suffix, encoding="utf-8")
        return
    if front_matter and not existing_front_matter:
        _install_or_append_agents_md(dest, content)
        return
    _install_or_append_agents_md(dest, body if existing_front_matter else content)


def _split_front_matter(content: str) -> tuple[str, str]:
    """Return YAML front matter (including delimiters) and the remaining body."""
    if not content.startswith("---\n"):
        return "", content
    end = content.find("\n---\n", 4)
    if end == -1:
        return "", content
    boundary = end + len("\n---\n")
    return content[:boundary], content[boundary:]


def _install_or_append_agents_md(dest: Path, content_body: str) -> None:
    marker_block = f"{_AGENTS_MD_START}\n{content_body.strip()}\n{_AGENTS_MD_END}"
    dest.parent.mkdir(parents=True, exist_ok=True)

    if not dest.exists():
        dest.write_text(marker_block + "\n", encoding="utf-8")
        return

    existing = dest.read_text(encoding="utf-8")
    try:
        current = _current_managed_block(existing)
        legacy = None if current is not None else _legacy_managed_block(existing)
    except ValueError as exc:
        raise click.ClickException(f"Could not update {display_path(dest)} because {exc}.") from exc
    if current is not None:
        start_idx, end_idx = current
        new_content = existing[:start_idx] + marker_block + existing[end_idx + len(_AGENTS_MD_END):]
        dest.write_text(new_content, encoding="utf-8")
    elif legacy is not None:
        start_idx, end_idx = legacy
        new_content = existing[:start_idx] + marker_block + existing[end_idx + len(_LEGACY_AGENTS_MD_END):]
        new_content = new_content.replace(_LEGACY_SKILL_FILE_OWNER, _SKILL_FILE_OWNER, 1)
        dest.write_text(new_content, encoding="utf-8")
    else:
        separator = "\n\n" if existing and not existing.endswith("\n\n") else ""
        dest.write_text(existing + separator + marker_block + "\n", encoding="utf-8")


def _format_size(n: int) -> str:
    f = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if f < 1024:
            return f"{f:.1f} {unit}"
        f /= 1024
    return f"{f:.1f} TB"

__all__=['_effective_config', '_get_agent_class', '_get_config_class', '_get_user_config_dir', '_get_user_config_path', '_get_codex_skill_path', '_get_shared_agent_skill_path', '_get_gemini_skill_path', '_get_cline_skill_path', '_get_copilot_user_instructions_path', '_build_user_bootstrap_config', '_ensure_user_config', '_load_config', '_resolve_config_file', '_describe_index', '_effective_retrieval_mode', '_write_config_yaml', '_apply_setup_retrieval_profile', '_agent_install_path', '_source_rows', '_parse_dt', '_freshness_label', '_operational_source_card', '_agent_installed_targets', '_doctor_issue', '_collect_doctor_report', '_emit_doctor_report', '_run_dispatch_query', '_path_size', '_emit_index_summary', '_create_agent_or_raise_lock_error', '_color_enabled', '_style', '_emit_brand_header', '_emit_status_line', '_emit_next_step', '_loader_availability', '_IngestLogFormatter', '_configure_ingest_logging', '_emit_install_summary', '_get_template_content', '_resolve_docmancer_executable', '_resolve_skill_command', '_resolve_install_config_path', '_build_skill_content', '_install_skill_file', '_split_front_matter', '_install_or_append_agents_md', '_format_size']
