# Docmancer Roadmap Plans

Эта папка содержит рабочие планы развития Docmancer, собранные на основе:

1. `DOCMANCER_PRODUCT_BRIEF.md` — исходная выжимка по текущему состоянию Docmancer.
2. Ответов сильной модели по prompt-ам:
   - Agent-proof MCP Docs UX;
   - Registry / Source Identity;
   - Product Positioning;
   - Project-aware Docs and Version Resolution;
   - Retrieval Quality / Eval / Observability;
   - First-run DX / Doctor / Onboarding;
   - Merged Execution Roadmap.

Фокус этих документов — не повторять ответы модели целиком, а превратить их в **практические планы**, которые можно дальше разложить на GitHub issues, milestones и PR sequence.

## Рекомендуемый порядок чтения

1. [`00_overview.md`](00_overview.md) — общая стратегия, эпики, очередность.
2. [`01_agent_proof_mcp_docs_ux.md`](01_agent_proof_mcp_docs_ux.md) — первый engineering epic: убрать `needs_docs_url` trap.
3. [`02_registry_source_identity.md`](02_registry_source_identity.md) — data model и identity rules для registry.
4. [`03_product_positioning.md`](03_product_positioning.md) — product packaging: Docs vs Packs.
5. [`04_project_aware_version_resolution.md`](04_project_aware_version_resolution.md) — project-aware dependency docs.
6. [`05_retrieval_quality_eval.md`](05_retrieval_quality_eval.md) — eval framework и observability.
7. [`06_first_run_dx_doctor.md`](06_first_run_dx_doctor.md) — first-run DX, `doctor`, onboarding.
8. [`07_pr_sequence.md`](07_pr_sequence.md) — рекомендуемый порядок PR и milestones.
9. [`08_next_wedge_project_docs.md`](08_next_wedge_project_docs.md) — entrypoint новой roadmap-гипотезы после выполнения базового roadmap.
10. [`08_project_docs/`](08_project_docs/) — разложение 08 на отдельные implementation files: framing, agent-discoverable onboarding, MCP/CLI surface, PR sequence, demos/evals/metrics, open questions.
11. [`09_riverpod_context7_benchmark_followups.md`](09_riverpod_context7_benchmark_followups.md) — выводы Riverpod Context7-vs-Docmancer benchmark и PR plan по source hygiene, exact Pub Dartdoc, diversity и eval observability.

## Обновление после первичного roadmap

После выполнения значительной части первичного roadmap следующий фокус — не строить hosted Context7 clone, а усилить то, где Docmancer может быть структурно лучше:

> **Context7 gives agents public library docs. Docmancer should give agents the docs this project actually uses.**

Практически это означает first-class workflow для project-owned docs (`README`, `docs`, `wiki`, `Architecture`, ADR) и дальнейшее соединение с exact dependency docs из project metadata/lockfiles.

Важная доработка к этому направлению: **discovery-first agent workflow**. Пользователь может думать, что Docmancer — просто аналог Context7, поэтому агент должен сам обнаружить project docs возможности через `inspect_project_docs`, tool descriptions и machine-readable next actions.

## Главный принцип roadmap

Docmancer уже имеет сильное техническое ядро. Ближайший цикл развития должен не расширять surface area, а сделать продукт предсказуемым:

- registered docs должны query-иться без ручного `docs_url`;
- registry identity должна быть machine-readable;
- agent не должен преждевременно уходить в WebFetch;
- version/source exactness должны быть явно видны;
- качество retrieval должно измеряться;
- первый запуск должен вести пользователя к первому useful answer, а не к инфраструктурным деталям.

Новый принцип следующего цикла:

- official project docs должны оставаться reviewable файлами в repo;
- Docmancer должен индексировать и обслуживать их для агента;
- dependency docs должны соответствовать версиям проекта;
- source class и version/source exactness должны быть явно видны;
- `inspect_project_docs` должен быть безопасным default entrypoint внутри repo;
- missing/stale project docs responses должны возвращать next actions, а не тупик;
- cloud/dashboard/enterprise features не должны вытеснять local-first agent workflow.
