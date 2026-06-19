# Prompt 03 — Product Positioning and Packaging

Ты — product strategist для devtools, AI coding agents и developer infrastructure.

## Контекст

Docmancer — project-aware documentation runtime для coding agents.

Важно: не позиционировать Docmancer только как “local Context7”. Это полезное сравнение, но слишком узкое primary positioning. Главное отличие: Docmancer работает с документацией конкретного проекта — repo docs, module docs, exact dependency docs, local/private docs и source attribution.

Короткая формула:

```text
Context7 answers from public library docs.
Docmancer answers from the docs your project actually uses:
project docs, module docs, dependency docs, exact versions, local/private sources.
```

Текущие поверхности продукта:

1. **Docs-RAG / context packs**
   - `docmancer ingest`
   - `docmancer add`
   - `docmancer query`
   - compact context packs
   - local SQLite/Qdrant/FastEmbed
   - agent skill integrations

2. **MCP docs server / versioned library docs**
   - `resolve_library_id`
   - `get_library_docs`
   - `prefetch_library_docs`
   - project-aware Flutter/Dart docs
   - project-owned docs discovery and ingest
   - module-level docs for monorepos (`packages/*`, `apps/*`, `services/*`, etc.)
   - module-scoped queries via `module_path`

3. **MCP API tool packs**
   - `install-pack`
   - version-pinned API tools
   - Tool Search pattern
   - `docmancer_search_tools`
   - `docmancer_call_tool`
   - safety gates, auth, idempotency

Главная проблема: продукт мощный, но может восприниматься как несколько продуктов сразу. Нужно понять, как его позиционировать и упаковать.

## Задача

Определи product positioning, packaging и 90-day focus для Docmancer.

## Что нужно выдать

1. **Positioning options**
    - Local docs-RAG для coding agents.
    - Context7 alternative / local Context7.
    - Project-aware docs runtime для coding agents.
    - Agent docs runtime.
   - MCP API tools platform.
   - Другие варианты, если видишь лучше.

2. **Для каждого positioning option**
   - ICP.
   - Core value proposition.
   - Top use cases.
   - Pros.
   - Cons.
   - Risks.
   - What to emphasize.
   - What to hide/deprioritize.

3. **Recommended positioning**
   - Один выбранный вариант.
   - Почему именно он.
   - Как он соотносится с текущими возможностями.
   - Какие функции не должны быть в hero narrative.
   - Почему “local Context7” лучше использовать как comparison, а не primary positioning.

4. **Packaging decision**
   - Один продукт с несколькими режимами?
   - Два продукта под одним брендом?
   - CLI-first или MCP-first?
   - Как разделить quickstarts.

5. **Top-3 wow use cases**
   - Конкретные сценарии, которые надо polish-ить.
   - Для каждого: target user, setup, expected “wow moment”, success metric.
   - Один из use cases должен быть monorepo/module-aware: агент видит доступные modules, уточняет ambiguity, затем отвечает из конкретного `module_path`.

6. **North Star metric**
   - Основная метрика.
   - Supporting metrics.
   - Anti-metrics.

7. **What to cut / deprioritize**
   - Какие направления пока не развивать.
   - Какие возможности оставить advanced/hidden.
   - Как избежать расползания feature surface.

8. **README / landing narrative**
   - Hero statement.
   - 3 bullets value proposition.
   - 5-minute quickstart outline.
   - Как объяснять project docs vs module docs vs dependency docs vs API packs.

9. **90-day product focus**
   - 3–5 крупных outcomes.
   - Что должно стать лучше для пользователя.
   - Что должно стать лучше для агента.
   - Включи outcome: module-aware repo context должен стать production-ready для monorepo.

10. **Risks and open questions**
    - Что нужно уточнить у команды/рынка.

## Ограничения

- Не превращай ответ в общий стартап-консалтинг.
- Не игнорируй техническую реальность: продукт уже имеет CLI, MCP docs server, API packs и local hybrid retrieval.
- Нужен actionable output для README, backlog и roadmap.

## Формат ответа

Сначала дай comparison table, затем recommendation, затем concrete 90-day plan. В конце дай `Must / Should / Could`.
