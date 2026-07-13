from __future__ import annotations

import os
import json
import logging
import shlex
import shutil
import sqlite3
import sys
import warnings
import zipfile
from datetime import datetime, timezone
from importlib.util import find_spec
from pathlib import Path

import click

from docmancer.cli.help import DocmancerCommand, DocmancerGroup, HELP_CONTEXT_SETTINGS, format_examples
from docmancer.cli.ui import BANNER_COLOR, BANNER_LINES, color_enabled, display_path, style


def _effective_config(config_path: str | None) -> str | None:
    """Merge subcommand --config with group-level --config."""
    if config_path is not None:
        return config_path
    ctx = click.get_current_context(silent=True)
    if ctx and ctx.parent and ctx.parent.obj:
        return ctx.parent.obj.get("config_path")
    return None

INSTALL_TARGETS = [
    "claude-code",
    "claude-desktop",
    "cline",
    "cursor",
    "codex",
    "codex-app",
    "codex-desktop",
    "gemini",
    "github-copilot",
    "opencode",
]


def _get_agent_class():
    from docmancer.agent import DocmancerAgent

    return DocmancerAgent


def _get_config_class():
    from docmancer.core.config import DocmancerConfig

    return DocmancerConfig


def _get_user_config_dir() -> Path:
    return Path.home() / ".docmancer"


def _get_user_config_path() -> Path:
    return _get_user_config_dir() / "docmancer.yaml"


def _get_codex_skill_path() -> Path:
    return Path.home() / ".codex" / "skills" / "docmancer" / "SKILL.md"


def _get_shared_agent_skill_path() -> Path:
    return Path.home() / ".agents" / "skills" / "docmancer" / "SKILL.md"


def _get_gemini_skill_path() -> Path:
    return Path.home() / ".gemini" / "skills" / "docmancer" / "SKILL.md"


def _get_cline_skill_path() -> Path:
    return Path.home() / ".cline" / "skills" / "docmancer" / "SKILL.md"


def _get_copilot_user_instructions_path() -> Path:
    return Path.home() / ".copilot" / "copilot-instructions.md"


def _build_user_bootstrap_config():
    DocmancerConfig = _get_config_class()
    config = DocmancerConfig()
    config.index.db_path = str((_get_user_config_dir() / "docmancer.db").resolve())
    config.index.extracted_dir = str((_get_user_config_dir() / "extracted").resolve())
    return config


def _ensure_user_config() -> Path:
    import yaml as _yaml

    config_path = _get_user_config_path()
    if config_path.exists():
        return config_path

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config = _build_user_bootstrap_config()
    with open(config_path, "w") as f:
        _yaml.dump(config.model_dump(), f, default_flow_style=False, sort_keys=False)
    return config_path


def _load_config(config_path: str | None):
    DocmancerConfig = _get_config_class()
    if config_path:
        return DocmancerConfig.from_yaml(config_path)
    default_yaml = Path("docmancer.yaml")
    if default_yaml.exists():
        return DocmancerConfig.from_yaml(default_yaml)
    return DocmancerConfig.from_yaml(_ensure_user_config())


def _resolve_config_file(config_path: str | None) -> Path:
    if config_path:
        return Path(config_path).resolve()
    if Path("docmancer.yaml").exists():
        return Path("docmancer.yaml").resolve()
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


SETUP_PROFILES = ["cli-docs", "agent", "mcp-docs", "api-packs"]
RETRIEVAL_PROFILES = ["local-hybrid", "lexical-now", "cloud"]
DOCTOR_SEVERITIES = ["BLOCKER", "DEGRADED", "WARN", "INFO"]
DOCTOR_CHECK_GROUPS = ["config", "storage", "sqlite", "qdrant", "embeddings", "vectors", "sources", "extraction", "agent", "mcp-docs", "cloud"]


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
        return Path(".claude") / "skills" / "docmancer" / "SKILL.md" if project else home / ".claude" / "skills" / "docmancer" / "SKILL.md"
    if normalized == "cursor":
        return home / ".cursor" / "skills" / "docmancer" / "SKILL.md"
    if normalized == "cline":
        return Path(".cline") / "skills" / "docmancer" / "SKILL.md" if project else _get_cline_skill_path()
    if normalized in {"codex", "codex-app", "codex-desktop"}:
        return _get_codex_skill_path()
    if normalized == "gemini":
        return Path(".gemini") / "skills" / "docmancer" / "SKILL.md" if project else _get_gemini_skill_path()
    if normalized == "github-copilot":
        return Path(".github") / "copilot-instructions.md" if project else _get_copilot_user_instructions_path()
    if normalized == "opencode":
        return home / ".config" / "opencode" / "skills" / "docmancer" / "SKILL.md"
    if normalized == "claude-desktop":
        return _get_user_config_dir() / "exports" / "claude-desktop" / "docmancer.zip"
    return home / ".docmancer" / normalized


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
    elif Path("docmancer.yaml").exists():
        effective_config = Path("docmancer.yaml").resolve()
    else:
        effective_config = _get_user_config_path()
    issues: list[dict] = []
    checks: list[dict] = []

    def add_check(group: str, status: str, message: str) -> None:
        checks.append({"group": group, "status": status, "message": message})

    if effective_config.exists():
        add_check("config", "ok", f"Config exists at {effective_config}")
    else:
        add_check("config", "failed", f"Config missing at {effective_config}")
        issues.append(_doctor_issue("CONFIG_MISSING", "config", "BLOCKER", "Docmancer has no config to load paths and retrieval defaults.", "doc-atlas setup --yes", "docmancer.yaml exists and doctor can read it.", auto_fix=True))

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
            issues.append(_doctor_issue(f"LOADER_{label.upper().replace(' ', '_')}_MISSING", "extraction", "WARN", f"{label} documents may not extract correctly.", f"pip install docmancer", f"{label} loader is available."))

    retrieval_mode = _effective_retrieval_mode(None, config)
    if retrieval_mode != "lexical":
        if find_spec("fastembed") is None:
            issues.append(_doctor_issue("FASTEMBED_MISSING", "embeddings", "DEGRADED", "Dense/sparse retrieval cannot embed queries locally.", "pip install docmancer", "doctor shows embeddings provider available."))
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
        from docmancer.embeddings import get_embeddings_provider
        from docmancer.retrieval.dispatch import HybridRetrievalError, RetrievalDispatcher
        from docmancer.runtime.qdrant_manager import ensure_running
        from docmancer.stores.base import get_vector_store
    except ImportError:
        chunks = agent.query(query, limit=limit, budget=budget, expand=expand)
        return chunks, {}, {}, "lexical", {"lexical": len(chunks)}

    vs_config = config.vector_store
    if vs_config.provider == "qdrant" and not vs_config.url:
        resolution = ensure_running()
        if resolution.fallback or not resolution.url:
            vs_config = vs_config.model_copy(update={"provider": "sqlite-vec"})
        else:
            vs_config = vs_config.model_copy(update={"url": resolution.url})

    try:
        vector_store = get_vector_store(vs_config, embeddings_dim=config.embeddings.dimensions)
        provider = get_embeddings_provider(config.embeddings)
    except Exception as exc:
        failures = {"vector": f"{type(exc).__name__}: {exc}"}
        if allow_degraded:
            chunks = agent.query(query, limit=limit, budget=budget, expand=expand)
            return chunks, {}, failures, "lexical", {"lexical": len(chunks)}
        raise HybridRetrievalError(failures) from exc

    collection = agent._vector_collection_name()
    dispatcher = RetrievalDispatcher(
        store=agent.store,
        config=config,
        vector_store=vector_store,
        provider=provider,
        collection=collection,
    )
    result = dispatcher.run(
        query,
        mode=mode,
        limit=limit,
        budget=budget,
        expand=expand,
        allow_degraded=allow_degraded,
    )
    return result.chunks, result.contributions, result.failures, result.mode_used, result.candidate_counts


def _format_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    if num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / 1024 / 1024:.1f} MB"
    return f"{num_bytes / 1024 / 1024 / 1024:.1f} GB"


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
        ("txt", find_spec("charset_normalizer") is not None, "reinstall docmancer; charset-normalizer ships in core"),
        ("pdf", find_spec("pypdf") is not None, "reinstall docmancer; pypdf ships in core"),
        ("pdf fallback", find_spec("pdfplumber") is not None, "reinstall docmancer; pdfplumber ships in core"),
        ("docx", find_spec("docx") is not None, "reinstall docmancer; python-docx ships in core"),
        ("rtf", find_spec("striprtf") is not None, "reinstall docmancer; striprtf ships in core"),
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


# ---------------------------------------------------------------------------
# Skill install helpers
# ---------------------------------------------------------------------------

def _get_template_content(template_name: str) -> str:
    from importlib.resources import files
    templates = files("docmancer.templates")
    content = templates.joinpath(template_name).read_text(encoding="utf-8")
    if "{{CANONICAL_AGENT_CONTRACT}}" in content:
        canonical = templates.joinpath("agent_contract.md").read_text(encoding="utf-8").strip()
        content = content.replace("{{CANONICAL_AGENT_CONTRACT}}", canonical)
    return content


def _resolve_docmancer_executable() -> str:
    resolved = shutil.which("docmancer")
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
        default_yaml = Path("docmancer.yaml")
        if default_yaml.exists():
            return default_yaml.resolve()
        return None
    return _ensure_user_config().resolve()


def _build_skill_content(template_name: str, config_path: str | Path | None) -> str:
    content = _get_template_content(template_name)
    return content.replace("{{DOCS_KIT_CMD}}", _resolve_skill_command(config_path))


def _install_skill_file(content: str, dest: Path) -> None:
    front_matter, body = _split_front_matter(content)
    marker_block = f"{_AGENTS_MD_START}\n{body.strip()}\n{_AGENTS_MD_END}\n"
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(front_matter + _SKILL_FILE_OWNER + "\n" + marker_block, encoding="utf-8")
        return

    existing = dest.read_text(encoding="utf-8")
    # Migrate the invalid legacy layout that put a marker before YAML.
    if existing.startswith(_AGENTS_MD_START):
        end_idx = existing.find(_AGENTS_MD_END)
        if end_idx != -1:
            managed = existing[len(_AGENTS_MD_START):end_idx].strip()
            old_front_matter, _ = _split_front_matter(managed)
            if old_front_matter:
                suffix = existing[end_idx + len(_AGENTS_MD_END):]
                dest.write_text(front_matter + _SKILL_FILE_OWNER + "\n" + marker_block + suffix, encoding="utf-8")
                return

    existing_front_matter, _ = _split_front_matter(existing)
    if _SKILL_FILE_OWNER in existing and existing_front_matter:
        start_idx = existing.find(_AGENTS_MD_START)
        end_idx = existing.find(_AGENTS_MD_END)
        if start_idx == -1 or end_idx == -1 or start_idx > end_idx:
            raise click.ClickException(
                f"Could not update {display_path(dest)} because its DocAtlas markers are incomplete or out of order."
            )
        suffix = existing[end_idx + len(_AGENTS_MD_END):]
        dest.write_text(front_matter + _SKILL_FILE_OWNER + "\n" + marker_block + suffix, encoding="utf-8")
        return
    if front_matter and not existing_front_matter:
        # Do not prepend metadata to a user-authored non-skill file.
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


def _create_claude_desktop_zip(config_path: str | Path | None) -> Path:
    content = _build_skill_content("claude_desktop_skill.md", config_path)
    export_dir = _get_user_config_dir() / "exports" / "claude-desktop"
    export_dir.mkdir(parents=True, exist_ok=True)
    zip_path = export_dir / "docmancer.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("docmancer/Skill.md", content)
    return zip_path


_AGENTS_MD_START = "<!-- docmancer:start -->"
_AGENTS_MD_END = "<!-- docmancer:end -->"
_SKILL_FILE_OWNER = "<!-- docmancer:managed-skill-file -->"
_PROJECT_INSTALL_STATE = Path(".docmancer") / "agent-installs.json"


def _project_state_agent(agent: str) -> str:
    normalized = agent.lower()
    return "codex" if normalized in {"codex-app", "codex-desktop"} else normalized


def _install_or_append_agents_md(dest: Path, content_body: str) -> None:
    marker_block = f"{_AGENTS_MD_START}\n{content_body.strip()}\n{_AGENTS_MD_END}"
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        existing = dest.read_text(encoding="utf-8")
        start_idx = existing.find(_AGENTS_MD_START)
        end_idx = existing.find(_AGENTS_MD_END)
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            # Replace existing block
            new_content = (
                existing[:start_idx]
                + marker_block
                + existing[end_idx + len(_AGENTS_MD_END):]
            )
            dest.write_text(new_content, encoding="utf-8")
        elif start_idx == -1 and end_idx == -1:
            # Append to file
            separator = "\n\n" if existing and not existing.endswith("\n\n") else ""
            dest.write_text(
                existing + separator + marker_block + "\n",
                encoding="utf-8",
            )
        else:
            raise click.ClickException(
                f"Could not update {display_path(dest)} because its DocAtlas markers are incomplete or out of order."
            )
    else:
        dest.write_text(marker_block + "\n", encoding="utf-8")


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
    if not _PROJECT_INSTALL_STATE.exists():
        try:
            from docmancer.mcp.agent_config import known_agents, target_has_current_server_entry

            return {
                target.name
                for target in known_agents(project=True)
                if _project_bootstrap_dest(target.name) is not None
                and target_has_current_server_entry(target)
            }
        except (OSError, ValueError):
            # A malformed legacy MCP config makes ownership unknowable. Prefer
            # retaining shared guidance over deleting another agent's contract.
            return {
                "claude-code", "codex", "cursor", "opencode",
                "cline", "gemini", "github-copilot",
            }
    try:
        payload = json.loads(_PROJECT_INSTALL_STATE.read_text(encoding="utf-8"))
        agents = payload.get("agents", [])
        return {str(agent) for agent in agents if str(agent) in INSTALL_TARGETS}
    except (json.JSONDecodeError, OSError, AttributeError):
        return set()


def _write_project_install_agents(agents: set[str]) -> None:
    if not agents:
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
    if project:
        normalized = agent.lower()
        if normalized == "github-copilot":
            return [Path(".github") / "copilot-instructions.md", Path("AGENTS.md")]
        bootstrap = _project_bootstrap_dest(agent)
        skill_paths = {
            "claude-code": Path(".claude") / "skills" / "docmancer" / "SKILL.md",
            "cursor": Path(".cursor") / "skills" / "docmancer" / "SKILL.md",
            "cline": Path(".cline") / "skills" / "docmancer" / "SKILL.md",
            "gemini": Path(".gemini") / "skills" / "docmancer" / "SKILL.md",
        }
        paths = [path for path in (skill_paths.get(normalized), bootstrap) if path is not None]
        return list(dict.fromkeys(paths))
    home = Path.home()
    normalized = agent.lower()
    paths = {
        "claude-code": [home / ".claude" / "skills" / "docmancer" / "SKILL.md"],
        "cursor": [home / ".cursor" / "skills" / "docmancer" / "SKILL.md", home / ".cursor" / "AGENTS.md"],
        "codex": [_get_codex_skill_path(), _get_shared_agent_skill_path()],
        "codex-app": [_get_codex_skill_path(), _get_shared_agent_skill_path()],
        "codex-desktop": [_get_codex_skill_path(), _get_shared_agent_skill_path()],
        "cline": [home / ".cline" / "skills" / "docmancer" / "SKILL.md"],
        "gemini": [home / ".gemini" / "skills" / "docmancer" / "SKILL.md"],
        "github-copilot": [_get_copilot_user_instructions_path()],
        "opencode": [home / ".config" / "opencode" / "skills" / "docmancer" / "SKILL.md"],
    }
    return paths.get(normalized, [])


def _remove_managed_instruction_block(dest: Path) -> bool:
    if not dest.exists():
        return False
    existing = dest.read_text(encoding="utf-8")
    start_idx = existing.find(_AGENTS_MD_START)
    end_idx = existing.find(_AGENTS_MD_END)
    if start_idx == -1 and end_idx == -1:
        return False
    if start_idx == -1 or end_idx == -1 or start_idx > end_idx:
        raise click.ClickException(
            f"Could not uninstall from {display_path(dest)} because its DocAtlas markers are incomplete or out of order."
        )
    remaining = existing[:start_idx] + existing[end_idx + len(_AGENTS_MD_END):]
    updated = remaining.strip()
    front_matter, body = _split_front_matter(remaining.lstrip())
    owned_skill_file = _SKILL_FILE_OWNER in remaining
    if owned_skill_file and front_matter and not body.replace(_SKILL_FILE_OWNER, "").strip():
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


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

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
    """Initialize a docmancer project with a config file."""
    import yaml as _yaml

    dir_path = Path(directory or ".")
    dir_path.mkdir(parents=True, exist_ok=True)
    config_path = dir_path / "docmancer.yaml"
    if config_path.exists():
        click.echo(f"Config already exists at {display_path(config_path)}")
        return
    DocmancerConfig = _get_config_class()
    config = DocmancerConfig()
    config.index.db_path = ".docmancer/docmancer.db"
    config.index.extracted_dir = ".docmancer/extracted"
    data = config.model_dump()
    with open(config_path, "w") as f:
        _yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    click.echo(f"Created config at {display_path(config_path)}")
    click.echo("Local SQLite FTS5 index configured at .docmancer/docmancer.db")


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
@click.option("--config", "config_path", default=None, help="Path to docmancer.yaml.")
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
@click.option("--config", "config_path", default=None, help="Path to docmancer.yaml.")
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
@click.option("--config", "config_path", default=None, help="Path to docmancer.yaml.")
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
@click.option("--config", "config_path", default=None, help="Path to docmancer.yaml.")
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


@click.command(
    cls=DocmancerCommand,
    context_settings=HELP_CONTEXT_SETTINGS,
    short_help="Show collection stats.",
    epilog=format_examples(
        "doc-atlas inspect",
        "doc-atlas inspect pytest --vectors",
        "doc-atlas inspect pytest --json",
        "doc-atlas inspect --config ./docmancer.yaml",
    ),
)
@click.argument("source", required=False)
@click.option("--failed", "show_failed", is_flag=True, default=False, help="Show failure-focused details for the source.")
@click.option("--vectors", "show_vectors", is_flag=True, default=False, help="Show retrieval/vector state for the source.")
@click.option("--extraction", "show_extraction", is_flag=True, default=False, help="Show extraction/content state for the source.")
@click.option("--json", "json_output", is_flag=True, default=False, help="Emit source card as JSON.")
@click.option("--config", "config_path", default=None, help="Path to docmancer.yaml.")
def inspect_cmd(source: str | None, show_failed: bool, show_vectors: bool, show_extraction: bool, json_output: bool, config_path: str | None):
    """Show collection stats or a source operational card."""
    config_path = _effective_config(config_path)
    config = _load_config(config_path)
    agent = _create_agent_or_raise_lock_error(config)

    if source:
        cards = [_operational_source_card(row) for row in _source_rows(config, grouped=False)]
        matches = [card for card in cards if source in card["source"]]
        if not matches:
            raise click.ClickException(f"No indexed source matches {source!r}.")
        card = matches[0]
        if json_output:
            click.echo(json.dumps(card, ensure_ascii=False, indent=2))
            return
        click.echo(f"Source: {card['source']}")
        click.echo(f"Type: {card['type']}")
        click.echo(f"Status: {card['status']}")
        click.echo(f"Freshness: {card['freshness']}")
        click.echo(f"Content: {card['content']}")
        click.echo(f"Vectors: {card['vectors']}")
        click.echo(f"Failures: {card['failures']}")
        details = card["details"]
        if show_extraction or not (show_failed or show_vectors):
            click.echo("Extraction:")
            click.echo(f"  empty sections: {details['empty_sections']}")
            click.echo(f"  sparse sections: {details['sparse_sections']}")
        if show_vectors or not (show_failed or show_extraction):
            click.echo("Retrieval/vector state:")
            click.echo(f"  vectors: {card['vectors']}")
        if show_failed:
            click.echo("Failures:")
            click.echo(f"  vector failures: {card['failures']}")
        click.echo(f"Fix command: {card['next_action']}")
        return

    stats = agent.collection_stats()
    if json_output:
        click.echo(json.dumps(stats, ensure_ascii=False, indent=2))
        return
    click.echo(f"Index: {display_path(config.index.db_path)}")
    click.echo(f"Exists: {stats.get('collection_exists', False)}")
    click.echo(f"Sources: {stats.get('sources_count', 0)}")
    sources_by_format = stats.get("sources_by_format") or {}
    if sources_by_format:
        click.echo("Sources by format:")
        for format_name, count in sorted(sources_by_format.items()):
            click.echo(f"  {format_name}: {count}")
    click.echo(f"Sections: {stats.get('sections_count', 0)}")
    sections_by_format = stats.get("sections_by_format") or {}
    if sections_by_format:
        click.echo("Sections by format:")
        for format_name, count in sorted(sections_by_format.items()):
            click.echo(f"  {format_name}: {count}")
    click.echo(f"Extracted: {display_path(stats.get('extracted_dir', ''))}")


@click.command(
    cls=DocmancerCommand,
    context_settings=HELP_CONTEXT_SETTINGS,
    short_help="Diagnose docs-context readiness.",
    epilog=format_examples(
        "doc-atlas doctor",
        "doc-atlas doctor --profile agent",
        "doc-atlas doctor --json",
        "doc-atlas doctor --list-checks",
        "doc-atlas doctor --check sources",
        "doc-atlas doctor --config ./docmancer.yaml",
    ),
)
@click.option("--config", "config_path", default=None, help="Path to docmancer.yaml.")
@click.option("--profile", type=click.Choice(SETUP_PROFILES, case_sensitive=False), default="cli-docs", show_default=True, help="Goal/path to diagnose.")
@click.option("--json", "json_output", is_flag=True, default=False, help="Emit structured doctor report as JSON.")
@click.option("--list-checks", is_flag=True, default=False, help="List available doctor check groups and exit.")
@click.option("--check", "checks", multiple=True, type=click.Choice(DOCTOR_CHECK_GROUPS, case_sensitive=False), help="Only show one check group. Can be repeated.")
def doctor_cmd(config_path: str | None, profile: str, json_output: bool, list_checks: bool, checks: tuple[str, ...]):
    """Diagnose what blocks documentation context for a selected path."""
    if list_checks:
        for group in DOCTOR_CHECK_GROUPS:
            click.echo(group)
        return
    config_path = _effective_config(config_path)
    config = _load_config(config_path)
    report = _collect_doctor_report(config, config_path, profile=profile.lower())
    if checks:
        selected = {check.lower() for check in checks}
        report["checks"] = [check for check in report["checks"] if check["group"] in selected]
        report["issues"] = [issue for issue in report["issues"] if issue["group"] in selected]
    if json_output:
        click.echo(json.dumps(report, ensure_ascii=False, indent=2))
        return
    _emit_doctor_report(report)



@click.command(
    cls=DocmancerCommand,
    context_settings={**HELP_CONTEXT_SETTINGS, "allow_extra_args": True},
    short_help="Search indexed docs.",
    epilog=format_examples(
        'doc-atlas query "How do I authenticate?"',
        'doc-atlas query "getting started" --limit 3',
        'doc-atlas query "season 5 end date" --expand',
        'doc-atlas query "season 5 end date" --expand page',
        'doc-atlas query "auth" --format json',
    ),
)
@click.argument("text")
@click.option("--config", "config_path", default=None, help="Path to docmancer.yaml.")
@click.option("--limit", default=None, type=int, help="Maximum sections to return.")
@click.option("--budget", default=None, type=int, help="Maximum estimated output tokens.")
@click.option(
    "--expand",
    flag_value="adjacent",
    default=None,
    help="Include adjacent sections around matches. Add 'page' after the flag for the full page.",
)
@click.option("output_format", "--format", type=click.Choice(["markdown", "json"], case_sensitive=False), default="markdown", show_default=True)
@click.option(
    "--mode",
    type=click.Choice(["lexical", "dense", "sparse", "hybrid"], case_sensitive=False),
    default=None,
    help="Retrieval mode. Default reads from retrieval.default_mode in config.",
)
@click.option("--explain", is_flag=True, help="Show per-source rank contributions for each result.")
@click.option(
    "--explain-json",
    type=click.Path(dir_okay=False, writable=True, path_type=str),
    default=None,
    help="Write a structured retrieval/packing explain trace JSON artifact.",
)
@click.option(
    "--allow-degraded",
    is_flag=True,
    default=False,
    help="In non-lexical modes, fall back to remaining signals if a retriever fails instead of erroring.",
)
@click.pass_context
def query_cmd(
    ctx: click.Context,
    text: str,
    config_path: str | None,
    limit: int | None,
    budget: int | None,
    expand: str | None,
    output_format: str,
    mode: str | None,
    explain: bool,
    explain_json: str | None,
    allow_degraded: bool,
):
    """Return a compact docs context pack from the local SQLite index."""
    import json as _json
    from docmancer.retrieval.dispatch import HybridRetrievalError

    if expand and ctx.args:
        if ctx.args == ["page"]:
            expand = "page"
        elif ctx.args == ["adjacent"]:
            expand = "adjacent"
        else:
            raise click.ClickException("Unexpected argument after --expand. Use '--expand' or '--expand page'.")
    config_path = _effective_config(config_path)
    config = _load_config(config_path)
    agent = _get_agent_class()(config=config)
    effective_mode = _effective_retrieval_mode(mode, config)
    contributions: dict = {}
    failures: dict[str, str] = {}
    candidate_counts: dict[str, int] = {}
    mode_used = effective_mode
    from docmancer.eval.trace import build_explain_trace, elapsed_ms, started_timer, validate_explain_trace

    trace_start = started_timer()
    if effective_mode == "lexical":
        chunks = agent.query(text, limit=limit, budget=budget, expand=expand)
        contributions = {c.metadata.get("section_id"): {"lexical": idx + 1} for idx, c in enumerate(chunks) if (c.metadata or {}).get("section_id") is not None}
        candidate_counts = {"lexical": len(chunks)}
        mode_used = "lexical"
    else:
        try:
            chunks, contributions, failures, mode_used, candidate_counts = _run_dispatch_query(
                agent=agent,
                config=config,
                query=text,
                mode=effective_mode,
                limit=limit,
                budget=budget,
                expand=expand,
                allow_degraded=allow_degraded,
            )
        except HybridRetrievalError as exc:
            click.echo(f"Error: {exc}", err=True)
            sys.exit(2)

    if not chunks:
        click.echo("No results found.")
        sys.exit(1)

    trace_latency_ms = elapsed_ms(trace_start)
    if explain_json:
        trace = build_explain_trace(
            query=text,
            selected_mode=mode_used,
            chunks=chunks,
            limit=limit,
            budget=budget or config.query.default_budget,
            expand=expand,
            contributions=contributions,
            candidate_counts=candidate_counts,
            failures=failures,
            latency_ms=trace_latency_ms,
        )
        validate_explain_trace(trace)
        Path(explain_json).write_text(_json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")

    meta = chunks[0].metadata or {}
    savings = meta.get("savings_percent", 0)
    runway = meta.get("runway_multiplier", 1)
    docmancer_tokens = meta.get("docmancer_tokens", 0)
    raw_tokens = meta.get("raw_tokens", 0)

    if output_format == "json":
        click.echo(
            _json.dumps(
                {
                    "query": text,
                    "budget": budget or config.query.default_budget,
                    "docmancer_tokens": docmancer_tokens,
                    "raw_tokens": raw_tokens,
                    "savings_percent": savings,
                    "runway_multiplier": runway,
                    "degraded": bool(failures),
                    "failures": failures,
                    "mode_used": mode_used,
                    "results": [chunk.model_dump() for chunk in chunks],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    click.echo(
        f"Context pack: ~{docmancer_tokens} tokens vs ~{raw_tokens} raw docs tokens "
        f"({savings}% less docs overhead, {runway}x agentic runway)"
    )
    if failures:
        for source, failure in failures.items():
            click.echo(f"Warning: {source} retriever degraded: {failure}", err=True)
    click.echo("---")

    for i, chunk in enumerate(chunks, start=1):
        body = chunk.text
        click.echo(f"[{i}] score={chunk.score:.2f}  source={chunk.source}")
        meta = chunk.metadata or {}
        if meta.get("title"):
            click.echo(f"    section: {meta['title']}")
        click.echo(f"    tokens: ~{meta.get('token_estimate', 0)}")
        if explain:
            sid = meta.get("section_id")
            contrib = contributions.get(sid) if sid is not None else None
            if contrib:
                parts = ", ".join(f"{src}#{rank}" for src, rank in sorted(contrib.items()))
                click.echo(f"    explain: {parts}")
            elif effective_mode == "lexical":
                click.echo("    explain: lexical#1")
            elif failures:
                failure_parts = "; ".join(f"{src}: {msg}" for src, msg in sorted(failures.items()))
                click.echo(f"    explain: degraded retrieval ({failure_parts})")
        click.echo(body)
        click.echo("---")


def _format_context_explain(result) -> str:
    contract = result.trust_contract or {}

    def contract_sources(lane: str) -> list[dict]:
        sources = contract.get("sources")
        if isinstance(sources, dict) and isinstance(sources.get(lane), list):
            return sources[lane]
        legacy_key = f"{lane}_sources"
        value = contract.get(lane) or contract.get(legacy_key)
        return value if isinstance(value, list) else []

    def label(source: dict) -> str:
        return str(source.get("path") or source.get("library") or source.get("source") or source.get("url") or source.get("canonical_id") or "unknown")

    def reason(source: dict) -> str:
        return str(source.get("why_selected") or source.get("reason") or source.get("reason_code") or source.get("message") or "not specified")

    lines = [f"Trusted context for: {result.question}", "", "Used:"]
    selected = contract_sources("selected")
    if selected:
        for source in selected:
            lines.append(f"  [{source.get('source_class', 'source')}] {label(source)}")
            lines.append(f"    why: {reason(source)}")
            if source.get("freshness"):
                lines.append(f"    freshness: {source['freshness']}")
            if source.get("docs_exactness"):
                lines.append(f"    docs_exactness: {source['docs_exactness']}")
            if source.get("version_source"):
                lines.append(f"    version_source: {source['version_source']}")
    else:
        lines.append("  none")
    lines.extend(["", "Rejected / risky:"])
    rejected_or_risky = [*contract_sources("rejected"), *contract_sources("risky")]
    if rejected_or_risky:
        for source in rejected_or_risky:
            lines.append(f"  [{source.get('source_class', 'source')}] {label(source)}")
            lines.append(f"    reason: {reason(source)}")
    else:
        lines.append("  none")
    lines.extend(["", "Warnings:"])
    warnings = contract.get("warnings") or []
    if warnings:
        for warning in warnings:
            lines.append(f"  - {warning.get('message') if isinstance(warning, dict) else warning}")
    else:
        lines.append("  none")
    lines.extend(["", "Next actions:"])
    next_actions = contract.get("next_actions") or result.next_actions or []
    if next_actions:
        for action in next_actions:
            if isinstance(action, dict):
                tool = action.get("tool") or "action"
                why = action.get("reason") or action.get("message") or "not specified"
                lines.append(f"  - {tool}: {why}")
            else:
                lines.append(f"  - {action}")
    else:
        lines.append("  none")
    return "\n".join(lines)


@click.command(
    cls=DocmancerCommand,
    context_settings=HELP_CONTEXT_SETTINGS,
    epilog=format_examples(
        'doc-atlas patch-review --project-path . --task "Review current patch"',
        'doc-atlas patch-review --project-path . --task "Add menu action" --base-ref main --strict',
    ),
)
@click.option("--project-path", required=True, type=click.Path(file_okay=False, path_type=Path), help="Local project repository path to review.")
@click.option("--task", required=True, help="Task or PR intent to compile constraints for.")
@click.option("--base-ref", default="HEAD", show_default=True, help="Git ref used for changed_files and patch.diff.")
@click.option("--output-dir", default=None, type=click.Path(file_okay=False, path_type=Path), help="Artifact output directory. Defaults to .docatlas/patch-review/<timestamp> inside the project.")
@click.option("--changed-file", "changed_files", multiple=True, help="Explicit changed file. Repeatable; defaults to git diff --name-only.")
@click.option("--strict", is_flag=True, help="Mark unknown validation results as manual-review warnings.")
@click.option("--max-constraints", default=12, show_default=True, type=int, help="Maximum constraints to keep in the packet.")
@click.option("--max-tokens", default=1200, show_default=True, type=int, help="Approximate token budget for constraints.")
@click.option("--summary-max-items", default=5, show_default=True, type=click.IntRange(1, 20), help="Maximum actionable checklist items in review_summary.md.")
@click.option("--summary-mode", default="standard", show_default=True, type=click.Choice(["compact", "standard", "verbose"], case_sensitive=False), help="review_summary.md verbosity.")
@click.option("output_format", "--format", type=click.Choice(["text", "json"], case_sensitive=False), default="text", show_default=True)
def patch_review_cmd(
    project_path: Path,
    task: str,
    base_ref: str,
    output_dir: Path | None,
    changed_files: tuple[str, ...],
    strict: bool,
    max_constraints: int,
    max_tokens: int,
    summary_max_items: int,
    summary_mode: str,
    output_format: str,
):
    """Generate read-only patch constraints, validation, diff, and review artifacts."""
    from docmancer.docs.application.patch_review_service import PatchReviewService

    result = PatchReviewService().run(
        project_path=str(project_path),
        task=task,
        base_ref=base_ref,
        output_dir=str(output_dir) if output_dir else None,
        changed_files=list(changed_files) or None,
        strict=strict,
        max_constraints=max_constraints,
        max_tokens=max_tokens,
        summary_max_items=summary_max_items,
        summary_mode=summary_mode,
    )
    if output_format.lower() == "json":
        click.echo(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return
    validation = result["validation"]
    click.echo(f"patch review artifacts: {result['output_dir']}")
    click.echo(f"changed files: {len(result['changed_files'])}")
    click.echo(f"constraints: {len(result['constraints'].get('constraints', []))}")
    click.echo(f"validation: satisfied={validation.get('satisfied', 0)} violated={validation.get('violated', 0)} unknown={validation.get('unknown', 0)}")


@click.command(
    cls=DocmancerCommand,
    context_settings=HELP_CONTEXT_SETTINGS,
    short_help="Return repo-grounded context with a Trust Contract.",
    epilog=format_examples(
        'doc-atlas context . "How should I test go_router changes?"',
        'doc-atlas context . "How should I test go_router changes?" --library go_router --format json',
        'doc-atlas context . "Architecture rules" --explain',
    ),
)
@click.argument("project_path", type=click.Path(exists=True, file_okay=False, path_type=str))
@click.argument("question")
@click.option("--config", "config_path", default=None, help="Path to docmancer.yaml.")
@click.option("--tokens", default=None, type=int, help="Maximum estimated output tokens.")
@click.option("--limit", default=None, type=int, help="Maximum sections to return.")
@click.option("--expand", default=None, type=click.Choice(["adjacent", "page"], case_sensitive=False), help="Expand adjacent sections or full page context.")
@click.option("--library", default=None, help="Dependency library to include in the context pack.")
@click.option("--libraries", multiple=True, help="Additional dependency libraries. The MVP uses the first value when --library is omitted.")
@click.option("--ecosystem", default=None, help="Dependency ecosystem, for example pub or rust.")
@click.option("--version", default=None, help="Dependency docs version.")
@click.option("--mode", default="auto", type=click.Choice(["auto", "project-only", "deps-only", "public-docs"], case_sensitive=False), show_default=True)
@click.option("output_format", "--format", type=click.Choice(["text", "json"], case_sensitive=False), default="text", show_default=True)
@click.option("--explain", is_flag=True, help="Print selected, rejected, and risky source decisions.")
def context_cmd(
    project_path: str,
    question: str,
    config_path: str | None,
    tokens: int | None,
    limit: int | None,
    expand: str | None,
    library: str | None,
    libraries: tuple[str, ...],
    ecosystem: str | None,
    version: str | None,
    mode: str,
    output_format: str,
    explain: bool,
):
    """Return project docs plus optional dependency docs in one context pack."""
    from dataclasses import asdict
    from docmancer.docs.service import LibraryDocsService

    config = _load_config(_effective_config(config_path))
    result = LibraryDocsService(config=config).get_project_context(
        project_path,
        question,
        tokens=tokens,
        limit=limit,
        expand=expand,
        library=library,
        libraries=list(libraries) or None,
        ecosystem=ecosystem,
        version=version,
        mode=mode,
    )
    payload = asdict(result)
    if output_format == "json":
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    click.echo(f"Project context: {result.status}")
    sources = result.trust_contract.get("sources") if isinstance(result.trust_contract, dict) else {}
    if not isinstance(sources, dict):
        sources = {}
    selected_sources = sources.get("selected") or result.trust_contract.get("selected_sources", [])
    rejected_sources = sources.get("rejected") or result.trust_contract.get("rejected_sources", [])
    risky_sources = sources.get("risky") or result.trust_contract.get("risky_sources", [])
    click.echo(f"Trust Contract: {len(selected_sources)} selected, {len(rejected_sources)} rejected, {len(risky_sources)} risky")
    if result.project_docs and result.project_docs.results:
        click.echo("--- project docs ---")
        for item in result.project_docs.results:
            click.echo(f"[{item.path or item.source}] {item.title or ''}".rstrip())
            click.echo(item.content)
    if result.dependency_docs and result.dependency_docs.results:
        click.echo("--- dependency docs ---")
        for item in result.dependency_docs.results:
            click.echo(f"[{item.source}] {item.title or ''}".rstrip())
            click.echo(item.content)
    if explain:
        click.echo("--- explain ---")
        click.echo(_format_context_explain(result))
    if result.next_actions:
        click.echo("--- next actions ---")
        click.echo(json.dumps(result.next_actions, ensure_ascii=False, indent=2))


@click.command(
    cls=DocmancerCommand,
    context_settings=HELP_CONTEXT_SETTINGS,
    short_help="Run retrieval quality evals.",
    epilog=format_examples(
        "doc-atlas eval golden.yaml",
        "doc-atlas eval golden.json --format json",
        "doc-atlas eval golden.yaml --source-health",
    ),
)
@click.argument("dataset", type=click.Path(exists=True, dir_okay=False, path_type=str))
@click.option("--config", "config_path", default=None, help="Path to docmancer.yaml.")
@click.option("--mode", type=click.Choice(["lexical", "dense", "sparse", "hybrid"], case_sensitive=False), default="lexical", show_default=True)
@click.option("--limit", default=10, type=int, show_default=True, help="Maximum sections per eval query.")
@click.option("--budget", default=10_000, type=int, show_default=True, help="Maximum estimated output tokens per eval query.")
@click.option("output_format", "--format", type=click.Choice(["text", "json"], case_sensitive=False), default="text", show_default=True)
@click.option("--source-health", is_flag=True, default=False, help="Include a basic source/index health report.")
@click.option("--allow-degraded/--strict", default=True, show_default=True, help="Allow degraded non-lexical retrieval during evals.")
def eval_cmd(
    dataset: str,
    config_path: str | None,
    mode: str,
    limit: int,
    budget: int,
    output_format: str,
    source_health: bool,
    allow_degraded: bool,
):
    """Evaluate retrieval quality against a golden dataset."""
    from docmancer.eval.health import source_health_report
    from docmancer.eval.runner import format_eval_report, run_retrieval_eval

    config_path = _effective_config(config_path)
    config = _load_config(config_path)
    agent = _get_agent_class()(config=config)
    report = run_retrieval_eval(
        dataset_path=dataset,
        agent=agent,
        config=config,
        mode=mode,
        limit=limit,
        budget=budget,
        allow_degraded=allow_degraded,
    )
    if source_health:
        report["source_health"] = source_health_report(agent)
    if output_format == "json":
        click.echo(json.dumps(report, ensure_ascii=False, indent=2))
        return
    click.echo(format_eval_report(report))
    if source_health:
        health = report["source_health"]
        click.echo("---")
        click.echo(
            f"Source health: sources={health['sources_count']} sections={health['sections_count']} "
            f"empty={health['empty_sections']} sparse={health['sparse_sections']} duplicates={health['duplicate_content_hashes']}"
        )


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


def _format_size(n: int) -> str:
    f = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if f < 1024:
            return f"{f:.1f} {unit}"
        f /= 1024
    return f"{f:.1f} TB"


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


@click.command(
    cls=DocmancerCommand,
    context_settings=HELP_CONTEXT_SETTINGS,
    short_help="Install docmancer skills into an AI agent.",
    epilog=format_examples(
        "doc-atlas install claude-code",
        "doc-atlas install codex",
        "doc-atlas install claude-code --project",
        "doc-atlas install cursor",
        "doc-atlas install claude-desktop",
        "doc-atlas install gemini",
        "doc-atlas install github-copilot --project",
        "doc-atlas install opencode",
        "doc-atlas install cline",
    ),
)
@click.argument("agent", type=click.Choice(INSTALL_TARGETS, case_sensitive=False))
@click.option("--project", is_flag=True, default=False,
              help="Install in project-level settings when the agent supports them.")
@click.option("--uninstall", "uninstall", is_flag=True, default=False,
              help="Remove only DocAtlas-managed project guidance for this agent.")
@click.option("--config", "config_path", default=None, help="Path to docmancer.yaml.")
def install_cmd(agent: str, project: bool, uninstall: bool, config_path: str | None):
    """Install docmancer skill files into an AI agent.

    Installs the canonical three-tool Docs MCP workflow and registers the local
    `doc-atlas mcp docs-serve` entry in the agent's MCP config.

    AGENT must be one of: claude-code, claude-desktop, cline, cursor, codex,
    codex-app, codex-desktop, gemini, github-copilot, opencode
    """
    config_path = _effective_config(config_path)
    normalized = agent.lower()
    if uninstall:
        removed = False
        for path in _managed_instruction_paths(normalized, project=project):
            if project and path == _project_bootstrap_dest(normalized) and _other_agent_uses_project_bootstrap(normalized, path):
                continue
            removed = _remove_managed_instruction_block(path) or removed
        if project:
            agents = _project_install_agents()
            agents.discard(_project_state_agent(normalized))
            _write_project_install_agents(agents)
        unregistered = _unregister_mcp_for_agent(normalized, project=project)
        click.echo("Removed DocAtlas-managed project guidance." if removed else "No DocAtlas-managed project guidance found.")
        click.echo("Removed DocAtlas MCP registration." if unregistered else "No DocAtlas MCP registration found.")
        return
    _register_mcp_for_agent(normalized, project=project)
    if not project:
        click.echo(f"Project guidance: run `doc-atlas install {agent} --project` inside the repository.")
    home = Path.home()
    user_config_exists_before = _get_user_config_path().exists()
    effective_config_path = _resolve_install_config_path(config_path, project)
    created_user_config = (
        not project
        and config_path is None
        and not user_config_exists_before
        and effective_config_path == _get_user_config_path().resolve()
    )

    if normalized == "claude-desktop":
        zip_path = _create_claude_desktop_zip(effective_config_path)
        _emit_install_summary(
            "Package skill for Claude Desktop.",
            [("Created docmancer skill package at", zip_path)],
            created_user_config,
            effective_config_path,
            f"Upload {display_path(zip_path)} in Claude Desktop > Customize > Skills.",
            extra_lines=[
                "1. Open Claude Desktop",
                "2. Go to Customize > Skills",
                '3. Click "+" and select "Upload a skill"',
                f"4. Upload: {display_path(zip_path)}",
            ],
        )
        return

    if normalized == "claude-code":
        if project:
            dest = Path(".claude") / "skills" / "docmancer" / "SKILL.md"
        else:
            dest = home / ".claude" / "skills" / "docmancer" / "SKILL.md"
        content = _build_skill_content("claude_code_skill.md", effective_config_path)
        _install_skill_file(content, dest)
        bootstrap_dest = _install_project_bootstrap(normalized) if project else None
        if project:
            _record_project_install(normalized)
        installed = [("Installed docmancer skill at", dest)]
        if bootstrap_dest:
            installed.append(("Updated project instructions at", bootstrap_dest))
        _emit_install_summary(
            "Install skill for Claude Code.",
            installed,
            created_user_config,
            effective_config_path,
            "Claude Code can use docmancer immediately. No restart needed.",
            extra_lines=["Claude Code will automatically use docmancer commands."],
        )
        return

    if normalized in {"codex", "codex-app", "codex-desktop"}:
        if project:
            bootstrap_dest = _install_project_bootstrap(normalized)
            _record_project_install(normalized)
            installed = [("Updated project instructions at", bootstrap_dest)]
        else:
            dest = _get_codex_skill_path()
            shared_dest = _get_shared_agent_skill_path()
            content = _build_skill_content("skill.md", effective_config_path)
            _install_skill_file(content, dest)
            _install_skill_file(content, shared_dest)
            installed = [
                ("Installed docmancer skill at", dest),
                ("Also installed shared compatibility skill at", shared_dest),
            ]
        _emit_install_summary(
            "Install skill for Codex.",
            installed,
            created_user_config,
            effective_config_path,
            "Start a new Codex session and ask a documentation question to verify get_docs_context routing.",
            extra_lines=["Codex will automatically use the DocAtlas Docs MCP workflow."],
        )
        return

    if normalized == "cursor":
        dest = (
            Path(".cursor") / "skills" / "docmancer" / "SKILL.md"
            if project
            else home / ".cursor" / "skills" / "docmancer" / "SKILL.md"
        )
        content = _build_skill_content("skill.md", effective_config_path)
        _install_skill_file(content, dest)

        # Also write AGENTS.md fallback while Cursor's skill discovery matures
        if project:
            agents_md = _install_project_bootstrap(normalized)
            _record_project_install(normalized)
        else:
            agents_md = home / ".cursor" / "AGENTS.md"
            agents_body = _get_template_content("cursor_agents_md.md").replace(
                "{{DOCS_KIT_CMD}}", _resolve_skill_command(effective_config_path)
            )
            _install_or_append_agents_md(agents_md, agents_body)
        _emit_install_summary(
            "Install skill for Cursor.",
            [
                ("Installed docmancer skill at", dest),
                ("Updated fallback at", agents_md),
            ],
            created_user_config,
            effective_config_path,
            "Restart Cursor for changes to take effect.",
        )
        return

    if normalized == "cline":
        if project:
            dest = Path(".cline") / "skills" / "docmancer" / "SKILL.md"
        else:
            dest = home / ".cline" / "skills" / "docmancer" / "SKILL.md"
        content = _build_skill_content("skill.md", effective_config_path)
        _install_skill_file(content, dest)
        bootstrap_dest = _install_project_bootstrap(normalized) if project else None
        if project:
            _record_project_install(normalized)
        installed = [("Installed docmancer skill at", dest)]
        if bootstrap_dest:
            installed.append(("Updated project instructions at", bootstrap_dest))
        _emit_install_summary(
            "Install skill for Cline.",
            installed,
            created_user_config,
            effective_config_path,
            "Enable Skills in Cline (Settings → Features) if you have not already. Restart VS Code if Cline does not pick up the skill.",
            extra_lines=[
                "Cline discovers skills from ~/.cline/skills/ or .cline/skills/ in the workspace.",
            ],
        )
        return

    if normalized == "github-copilot":
        if project:
            copilot_dest = Path(".github") / "copilot-instructions.md"
            agents_dest = Path("AGENTS.md")
            settings_dest = Path(".vscode") / "settings.json"
            mcp_dest = Path(".vscode") / "mcp.json"
            bootstrap = _get_template_content("project_bootstrap.md")
            _install_or_append_agents_md(copilot_dest, bootstrap)
            _install_or_append_agents_md(agents_dest, bootstrap)
            instructions_enabled = _install_vscode_copilot_settings(settings_dest)
            _record_project_install(normalized)
            _emit_install_summary(
                "Install instructions for GitHub Copilot.",
                [
                    ("Updated Copilot repository instructions at", copilot_dest),
                    ("Updated Copilot coding-agent fallback at", agents_dest),
                    (
                        "Enabled VS Code Copilot instruction files at"
                        if instructions_enabled
                        else "Preserved disabled VS Code Copilot instruction setting at",
                        settings_dest,
                    ),
                    ("Registered Docs MCP server at", mcp_dest),
                ],
                created_user_config,
                effective_config_path,
                "Reload VS Code or start a new Copilot Chat session if the instructions are not picked up immediately.",
                extra_lines=[
                    "Copilot Chat and code review use .github/copilot-instructions.md.",
                    "Copilot coding agent can also read AGENTS.md.",
                    *([] if instructions_enabled else [
                        "WARNING: Copilot instruction files remains disabled by explicit user configuration."
                    ]),
                ],
            )
        else:
            content = _build_skill_content("copilot_instructions.md", effective_config_path)
            dest = _get_copilot_user_instructions_path()
            _install_or_append_agents_md(dest, content)
            _emit_install_summary(
                "Install user instructions for GitHub Copilot CLI.",
                [("Updated Copilot user instructions at", dest)],
                created_user_config,
                effective_config_path,
                "Start a new Copilot CLI session for the instructions to take effect.",
                extra_lines=[
                    "For Copilot in VS Code, Xcode, JetBrains, or GitHub.com, run `doc-atlas install github-copilot --project` inside each repository.",
                ],
            )
        return

    if normalized == "gemini":
        if project:
            dest = Path(".gemini") / "skills" / "docmancer" / "SKILL.md"
        else:
            dest = home / ".gemini" / "skills" / "docmancer" / "SKILL.md"
        content = _build_skill_content("skill.md", effective_config_path)
        _install_skill_file(content, dest)
        bootstrap_dest = _install_project_bootstrap(normalized) if project else None

        if project:
            _record_project_install(normalized)
        installed_paths = [("Installed docmancer skill at", dest)]
        if bootstrap_dest:
            installed_paths.append(("Updated project instructions at", bootstrap_dest))

        _emit_install_summary(
            "Install skill for Gemini CLI.",
            installed_paths,
            created_user_config,
            effective_config_path,
            "Start a new Gemini session and ask a documentation question to verify get_docs_context routing.",
            extra_lines=["Gemini CLI will automatically use the DocAtlas Docs MCP workflow."],
        )
        return

    if normalized == "opencode":
        if project:
            bootstrap_dest = _install_project_bootstrap(normalized)
            _record_project_install(normalized)
            installed_paths = [("Updated project instructions at", bootstrap_dest)]
        else:
            dest = home / ".config" / "opencode" / "skills" / "docmancer" / "SKILL.md"
            content = _build_skill_content("skill.md", effective_config_path)
            _install_skill_file(content, dest)
            installed_paths = [("Installed docmancer skill at", dest)]

        _emit_install_summary(
            "Install skill for OpenCode.",
            installed_paths,
            created_user_config,
            effective_config_path,
            "Start a new OpenCode session and ask a documentation question to verify get_docs_context routing.",
            extra_lines=["OpenCode will automatically use the DocAtlas Docs MCP workflow."],
        )
        return


def _detect_setup_targets() -> list[str]:
    home = Path.home()
    targets: list[str] = []
    checks = [
        ("claude-code", home / ".claude"),
        ("cursor", home / ".cursor"),
        ("codex", home / ".codex"),
        ("cline", home / ".cline"),
        ("gemini", home / ".gemini"),
        ("opencode", home / ".config" / "opencode"),
    ]
    for target, path in checks:
        if path.exists():
            targets.append(target)
    # Claude Desktop has no stable skill directory to inspect, so include it
    # when its macOS support directory exists.
    if (home / "Library" / "Application Support" / "Claude").exists():
        targets.append("claude-desktop")
    vscode_ext_dir = home / ".vscode" / "extensions"
    vscode_app_dir = home / "Library" / "Application Support" / "Code"
    if (
        _get_copilot_user_instructions_path().parent.exists()
        or vscode_app_dir.exists()
        or (vscode_ext_dir.exists() and any(vscode_ext_dir.glob("github.copilot*")))
    ):
        targets.append("github-copilot")
    return targets


def _ensure_config_and_db(config_path: str | None) -> Path:
    config_file = Path(config_path).resolve() if config_path else _ensure_user_config().resolve()
    config = _get_config_class().from_yaml(config_file)
    agent = _get_agent_class()(config=config)
    agent.collection_stats()
    return config_file


def _ensure_project_config() -> Path:
    config_file = Path("docmancer.yaml").resolve()
    if not config_file.exists():
        config = _build_user_bootstrap_config()
        config.index.db_path = str((Path.cwd() / ".docmancer" / "docmancer.db").resolve())
        config.index.extracted_dir = str((Path.cwd() / ".docmancer" / "extracted").resolve())
        _write_config_yaml(config, config_file)
    config = _get_config_class().from_yaml(config_file)
    agent = _get_agent_class()(config=config)
    agent.collection_stats()
    return config_file


def _emit_setup_readiness_summary(config, *, selected_agents: list[str], profile: str) -> None:
    try:
        agent = _get_agent_class()(config=config)
        stats = agent.collection_stats()
    except Exception:  # noqa: BLE001
        stats = {"sources_count": 0, "sections_count": 0}
    sources = int(stats.get("sources_count", 0) or 0)
    mode = _effective_retrieval_mode(None, config)
    installed_agents = selected_agents or _agent_installed_targets()
    click.echo()
    click.echo(_style("Ready now", fg="white", bold=True))
    click.echo(f"  CLI query ............. {'yes' if sources else 'after ingest'}")
    click.echo(f"  Local hybrid .......... {'ready' if mode == 'hybrid' else 'off'}")
    click.echo(f"  Coding agent .......... {'installed' if installed_agents else 'not installed'}")
    click.echo(f"  MCP docs server ....... {'run doc-atlas mcp docs-serve' if profile == 'mcp-docs' else 'not configured'}")
    click.echo()
    click.echo(_style("Next best command", fg="white", bold=True))
    if sources:
        click.echo('  doc-atlas query "How do I authenticate?"')
    elif profile == "mcp-docs":
        click.echo("  doc-atlas mcp docs-serve")
    else:
        click.echo("  doc-atlas ingest ./docs")


@click.command(
    cls=DocmancerCommand,
    context_settings=HELP_CONTEXT_SETTINGS,
    short_help="Set up docmancer for local agent docs retrieval.",
    epilog=format_examples(
        "doc-atlas setup",
        "doc-atlas setup --yes",
        "doc-atlas setup --profile agent --agent claude-code --yes",
        "doc-atlas setup --offline --vectors off --yes",
        "doc-atlas setup --project-local --yes",
        "doc-atlas setup --all",
        "doc-atlas setup --agent codex --agent claude-desktop",
        "doc-atlas setup --agent github-copilot",
    ),
)
@click.option("--all", "install_all", is_flag=True, default=False, help="Install every supported agent integration non-interactively.")
@click.option("--agent", "agents", multiple=True, type=click.Choice(INSTALL_TARGETS, case_sensitive=False), help="Agent integration to install. Can be repeated.")
@click.option("--profile", type=click.Choice(SETUP_PROFILES, case_sensitive=False), default="cli-docs", show_default=True, help="Goal/path to set up.")
@click.option("--retrieval-profile", type=click.Choice(RETRIEVAL_PROFILES, case_sensitive=False), default="lexical-now", show_default=True, help="Retrieval readiness profile.")
@click.option("--yes", "assume_yes", is_flag=True, default=False, help="Non-interactive defaults; never prompt.")
@click.option("--offline", is_flag=True, default=False, help="Avoid network/model setup and prefer lexical retrieval.")
@click.option("--vectors", type=click.Choice(["auto", "on", "off"], case_sensitive=False), default="auto", show_default=True, help="Vector setup policy.")
@click.option("--project-local", is_flag=True, default=False, help="Create/use ./docmancer.yaml and project-local state.")
@click.option("--config", "config_path", default=None, help="Path to docmancer.yaml.")
def setup_cmd(
    install_all: bool,
    agents: tuple[str, ...],
    profile: str,
    retrieval_profile: str,
    assume_yes: bool,
    offline: bool,
    vectors: str,
    project_local: bool,
    config_path: str | None,
):
    """Create the local index and optionally connect agents/MCP.

    Goal-first profiles focus on outcomes: CLI querying, coding-agent context,
    MCP docs serving, or future API packs. `lexical-now` gives first success
    without model downloads; `local-hybrid` prepares higher-quality retrieval.
    """
    config_path = _effective_config(config_path)
    config_file = _ensure_project_config() if project_local and config_path is None else _ensure_config_and_db(config_path)
    _emit_brand_header("doc-atlas setup", "Choose an outcome, then get first docs context fast.")
    _emit_status_line(f"Config: {display_path(config_file)}")
    config = _get_config_class().from_yaml(config_file)
    config = _apply_setup_retrieval_profile(config, retrieval_profile, offline=offline, vectors=vectors)
    _write_config_yaml(config, config_file)
    _emit_status_line(f"SQLite index: {display_path(config.index.db_path)}")
    _emit_status_line(f"Profile: {profile.lower()}")
    _emit_status_line(f"Retrieval profile: {retrieval_profile.lower()} (mode={config.retrieval.default_mode})")

    selected = [agent.lower() for agent in agents]
    if install_all:
        selected = list(INSTALL_TARGETS)
    elif profile.lower() == "agent" and not selected:
        detected = _detect_setup_targets()
        selected = detected or ([] if assume_yes else ["codex"])
    elif not selected:
        detected = _detect_setup_targets()
        if detected:
            selected = detected
        elif not assume_yes and click.confirm("No agent installs detected. Install Codex skill?", default=True):
            selected = ["codex"]

    if not selected:
        _emit_setup_readiness_summary(config, selected_agents=[], profile=profile.lower())
        return

    for target in dict.fromkeys(selected):
        ctx = click.get_current_context()
        ctx.invoke(install_cmd, agent=target, project=(target == "github-copilot"), config_path=str(config_file))

    _emit_setup_readiness_summary(config, selected_agents=list(dict.fromkeys(selected)), profile=profile.lower())

    _emit_next_step("Run `doc-atlas add <url-or-path>`, then `doc-atlas query \"your question\"`.")
