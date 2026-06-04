# Prompt 01 — Agent-proof MCP Docs UX

Ты — principal product engineer / architect для devtools, local-first RAG и AI coding agents.

## Контекст

У нас есть продукт **Docmancer**: local-first docs-RAG для coding agents.

Docmancer умеет:

- индексировать локальные документы и web docs;
- хранить library docs registry;
- искать по docs через CLI и MCP docs server;
- возвращать compact context packs с source attribution;
- работать с versioned docs;
- поддерживать project-aware Flutter/Dart docs;
- использовать hybrid retrieval: SQLite FTS5 + dense vectors + sparse vectors;
- предоставлять MCP docs tools вроде `resolve_library_id`, `get_library_docs`, `list_library_docs`, `inspect_library_docs`, `prefetch_library_docs`, `refresh_library_docs`.

## Конкретная проблема из живого использования

Мы проиндексировали web docs target:

- `library`: `flutter-adaptive-responsive`
- `docs_url`: `https://docs.flutter.dev/ui/adaptive-responsive`
- pages indexed: 90

При вызове `get_library_docs` только с `library` и `topic` tool вернул warning `needs_docs_url`.

Агент ошибочно интерпретировал это как failure и ушел в direct WebFetch, хотя docs уже были локально indexed.

Желаемое поведение: если docs source уже зарегистрирован в Docmancer registry, агент или сам MCP tool должен получить `docs_url` / source metadata из registry и продолжить через Docmancer, **не уходя в WebFetch**.

## Задача

Спроектируй **agent-proof UX и technical behavior** для MCP docs server, чтобы LLM-agent не ошибался в таких сценариях.

Фокус: не общий roadmap, а конкретный дизайн, который можно превратить в задачи и PR.

## Что нужно выдать

Дай структурированный ответ с разделами:

1. **Target behavior / happy path**
   - Как должен работать flow `resolve -> inspect/query -> answer`.
   - Какой минимальный набор MCP calls должен делать агент.
   - Как должен выглядеть успешный ответ.

2. **Behavior for already registered web docs**
   - Должен ли `get_library_docs` автоматически использовать stored `docs_url`?
   - Нужно ли предварительно вызывать `resolve_library_id`?
   - Как tool должен вести себя, если `docs_url` есть в registry, но caller его не передал?

3. **Behavior for unknown library**
   - Когда warning `needs_docs_url` допустим.
   - Как должен выглядеть machine-readable remediation.
   - Что должен делать агент дальше.

4. **Behavior for ambiguous library/version**
   - Что делать, если есть несколько versions или несколько matching entries.
   - Как возвращать candidates.
   - Как не заставлять агента гадать.

5. **MCP response schemas / warnings**
   - Предложи machine-readable response structure.
   - Какие поля должны быть обязательными.
   - Какие warnings нужны: `needs_docs_url`, `ambiguous_library`, `stale_docs`, `using_latest`, `not_exact_snapshot`, etc.
   - Как warnings должны отличаться от fatal errors.

6. **Tool behavior design**
   - `resolve_library_id`
   - `get_library_docs`
   - `inspect_library_docs`
   - `list_library_docs`
   - `refresh_library_docs`
   - `prefetch_library_docs`

7. **Fallback policy**
   - Когда direct WebFetch допустим.
   - Когда direct WebFetch должен быть запрещен или discouraged.
   - Как сформулировать agent guidance: “never WebFetch registered docs before Docmancer retry”.

8. **Migration and backward compatibility**
   - Что может сломаться у существующих clients.
   - Как сохранить compatibility.
   - Нужны ли deprecation warnings.

9. **Acceptance criteria**
   - Конкретные критерии приемки.
   - Например: registered web docs query succeeds without manually supplied `docs_url`.
   - Average MCP calls to useful answer.
   - No direct WebFetch in happy path.

10. **Regression test scenarios**
    - Для registered web docs.
    - Для unknown library.
    - Для ambiguous versions.
    - Для stale docs.
    - Для missing docs_url.
    - Для project_path resolution.

11. **Implementation plan**
    - Пошагово.
    - Какие modules likely affected.
    - Какие data/model/API changes нужны.
    - Какие tests написать первыми.

12. **LLM-agent edge cases**
    - Где агент может неверно интерпретировать response.
    - Как сделать responses максимально self-correcting.

## Ограничения

- Не предлагай direct WebFetch как основной fallback, если docs source уже зарегистрирован.
- Не давай только общие советы.
- Не расширяй scope на весь продукт.
- Ответ должен быть пригоден для превращения в engineering epic.

## Формат ответа

Используй таблицы, bullet points и примеры JSON responses. В конце дай краткий список `Must / Should / Could`.
