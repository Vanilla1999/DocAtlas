# 08 — Next Wedge: Project-Aware Project Docs Runtime

Это entrypoint для нового roadmap-направления после первичного roadmap Docmancer.

Подробности разнесены по отдельным файлам, чтобы из них было проще делать issues, PR sequence и implementation tasks.

## Strategic thesis

> **Context7 gives agents public library docs. Docmancer should give agents the docs this project actually uses.**

Docmancer не должен в ближайшем цикле становиться hosted Context7 clone. Его лучший wedge — local-first project-aware workflow:

1. project-owned docs из repo files;
2. private/local docs как отдельный source class;
3. exact dependency docs из lockfiles/project metadata;
4. source/version exactness;
5. compact context packs with attribution;
6. agent-discoverable onboarding, чтобы пользователь получил эти плюсы даже если думает “Docmancer — это аналог Context7”.

## Почему roadmap разбит на файлы

Главная product risk: возможности можно реализовать, но агент продолжит использовать Docmancer как обычный `get_library_docs` / Context7-style lookup.

Поэтому roadmap теперь разделён на слои:

- product framing;
- agent-discoverable onboarding;
- MCP/CLI surface;
- implementation PR sequence;
- demos/evals/metrics.

## Reading order

1. [`08_project_docs/00_product_framing.md`](08_project_docs/00_product_framing.md) — positioning, anti-goals, official docs as files.
2. [`08_project_docs/01_agent_discoverable_onboarding.md`](08_project_docs/01_agent_discoverable_onboarding.md) — ключевая доработка: агент сам предлагает inspect/ingest/prefetch workflow.
3. [`08_project_docs/02_mcp_cli_surface.md`](08_project_docs/02_mcp_cli_surface.md) — proposed MCP/CLI tools и response contracts.
4. [`08_project_docs/03_pr_sequence.md`](08_project_docs/03_pr_sequence.md) — разбивка на PR, включая discovery-first UX.
5. [`08_project_docs/04_demos_evals_metrics.md`](08_project_docs/04_demos_evals_metrics.md) — 60/90-day follow-up, demos, evals, metrics.
6. [`08_project_docs/05_open_questions.md`](08_project_docs/05_open_questions.md) — decisions, которые надо закрыть перед/во время реализации.

## Main 30-day milestone

**Milestone: First-class Project Docs MCP Workflow.**

Target user story:

```json
get_project_docs({
  "project_path": ".",
  "topic": "architecture constraints for the docs MCP runtime"
})
```

Docmancer должен:

1. обнаружить project-owned docs candidates;
2. показать, что уже indexed, что stale, что missing;
3. вернуть actionable next actions для агента;
4. проиндексировать official project docs по явному вызову;
5. query-ить только релевантные project docs с project filters;
6. возвращать source class и атрибуцию файлов;
7. не писать official docs в hidden DB;
8. быть понятным агенту через tool descriptions, README quickstart и fallback messages.

## Decision rule

If a proposed task helps Docmancer become “Context7 but hosted/public”, defer it.

If it helps Docmancer answer from **this project’s docs and this project’s exact dependencies** with better source/version trust than Context7, prioritize it.
