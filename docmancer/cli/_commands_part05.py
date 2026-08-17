"""Implementation shard 5 for commands."""
from __future__ import annotations

from ._commands_shared import *  # noqa: F401,F403

from ._commands_part01 import _agent_installed_targets, _apply_setup_retrieval_profile, _build_skill_content, _build_user_bootstrap_config, _effective_config, _effective_retrieval_mode, _emit_brand_header, _emit_install_summary, _emit_next_step, _emit_status_line, _ensure_user_config, _get_agent_class, _get_codex_skill_path, _get_config_class, _get_copilot_user_instructions_path, _get_shared_agent_skill_path, _get_template_content, _get_user_config_path, _install_or_append_agents_md, _install_skill_file, _resolve_install_config_path, _resolve_skill_command, _style, _write_config_yaml
from ._commands_part02 import _create_claude_desktop_zip, _install_project_bootstrap, _install_vscode_copilot_settings, _managed_instruction_paths, _other_agent_uses_project_bootstrap, _project_bootstrap_dest, _project_install_agents, _project_state_agent, _record_project_install, _register_mcp_for_agent, _remove_managed_instruction_block, _unregister_mcp_for_agent, _write_project_install_agents

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

__all__=['install_cmd', '_detect_setup_targets', '_ensure_config_and_db', '_ensure_project_config', '_emit_setup_readiness_summary', 'setup_cmd']
