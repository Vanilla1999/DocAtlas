"""Implementation shard 3 for commands."""
from __future__ import annotations

from ._commands_shared import *  # noqa: F401,F403

from ._commands_part01 import _collect_doctor_report, _create_agent_or_raise_lock_error, _effective_config, _effective_retrieval_mode, _emit_doctor_report, _get_agent_class, _load_config, _operational_source_card, _run_dispatch_query, _source_rows


def _json_collection_default(value: object) -> object:
    if isinstance(value, (set, frozenset)):
        return sorted(value, key=str)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")

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

    from docmancer.core.storage_topology import StorageTopologyResolver

    effective_config_path = _effective_config(config_path)
    fallback_config = _load_config(effective_config_path)
    topology = StorageTopologyResolver(
        fallback_config=fallback_config,
        # An explicit --config is an operator decision.  In particular,
        # read-only sandboxes use it to keep runtime indexes outside the
        # mounted project checkout.  Implicit discovery continues to prefer a
        # project's own docmancer.yaml.
        prefer_fallback=effective_config_path is not None,
    ).resolve(project_path)
    result = LibraryDocsService(
        config=topology.config,
        library_index_root=topology.library_index_root,
    ).get_project_context(
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
        click.echo(json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            default=_json_collection_default,
        ))
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

__all__=['inspect_cmd', 'doctor_cmd', 'query_cmd', '_format_context_explain', 'patch_review_cmd', 'context_cmd', 'eval_cmd']
