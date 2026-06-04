# Prompt 03 — Product Positioning and Packaging

Ты — product strategist для devtools, AI coding agents и developer infrastructure.

## Контекст

Docmancer — local-first docs context system для coding agents.

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

4. **Packaging decision**
   - Один продукт с несколькими режимами?
   - Два продукта под одним брендом?
   - CLI-first или MCP-first?
   - Как разделить quickstarts.

5. **Top-3 wow use cases**
   - Конкретные сценарии, которые надо polish-ить.
   - Для каждого: target user, setup, expected “wow moment”, success metric.

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
   - Как объяснять docs-RAG vs API packs.

9. **90-day product focus**
   - 3–5 крупных outcomes.
   - Что должно стать лучше для пользователя.
   - Что должно стать лучше для агента.

10. **Risks and open questions**
    - Что нужно уточнить у команды/рынка.

## Ограничения

- Не превращай ответ в общий стартап-консалтинг.
- Не игнорируй техническую реальность: продукт уже имеет CLI, MCP docs server, API packs и local hybrid retrieval.
- Нужен actionable output для README, backlog и roadmap.

## Формат ответа

Сначала дай comparison table, затем recommendation, затем concrete 90-day plan. В конце дай `Must / Should / Could`.
