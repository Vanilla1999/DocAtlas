# Docmancer Roadmap

This folder contains the current active roadmap for making Docmancer a practical Context7 replacement for repo-aware coding-agent work.

The product thesis:

> Docmancer is not docs search. Docmancer is repo-grounded context resolution for agents.

Short version:

> Context7 gives docs. Docmancer resolves trusted context.

## Recommended reading order

1. [`20_context7_replacement_strategy.md`](20_context7_replacement_strategy.md) - overview and product strategy.
2. [`21_trusted_context_contract.md`](21_trusted_context_contract.md) - Trust Contract schema and selected/rejected source semantics.
3. [`22_get_project_context_mvp.md`](22_get_project_context_mvp.md) - first shippable `get_project_context` / `docmancer context` slice.
4. [`23_source_resolution_and_rejection.md`](23_source_resolution_and_rejection.md) - official source discovery, confidence, and rejection reasons.
5. [`24_exact_version_and_project_context_benchmarks.md`](24_exact_version_and_project_context_benchmarks.md) - benchmarks that prove the wedge against Context7.
6. [`25_snippet_and_explain_context.md`](25_snippet_and_explain_context.md) - snippet-first output and `--explain` UX.
7. [`26_platform_hardening_after_wedge.md`](26_platform_hardening_after_wedge.md) - install, backup, security, and other later platform work.

## First implementation focus

Do not start with P2P sync, GUI, cloud backup, or a broad local clone of Context7.

Start with:

1. `get_project_context(project_path, question)` response schema.
2. Trust Contract with trusted and rejected/risky sources.
3. Minimal orchestrator that combines project docs plus one exact dependency docs source.
4. `docmancer context ... --explain` output.
5. A benchmark where Context7-only is weaker because it uses latest docs or ignores a local project rule.
