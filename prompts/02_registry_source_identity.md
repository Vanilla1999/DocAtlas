# Prompt 02 — Registry / Source Identity Model

Ты — architect для local documentation registry, versioned docs и MCP tooling.

## Контекст

Docmancer хранит library docs entries и предоставляет MCP docs server. У docs entries могут быть разные источники:

- generic web docs;
- GitBook;
- Mintlify;
- GitHub;
- local files;
- Dartdoc API pages;
- pub.dev package documentation;
- Flutter API docs;
- project-aware dependencies из lockfiles.

Ранее была выявлена проблема: `get_library_docs` может вернуть `needs_docs_url`, хотя web docs target уже зарегистрирован и проиндексирован. Это говорит о том, что source identity / registry model должны быть более понятными и machine-readable для агента.

## Задача

Спроектируй registry/source identity model для Docmancer docs registry, чтобы resolve/query/inspect/versioning работали предсказуемо.

## Поля, которые нужно учесть

В registry могут быть такие данные:

- `library`
- `canonical_id`
- `ecosystem`
- `version`
- `source_type`
- `docs_url`
- `docs_url_template`
- `seed_urls`
- `allowed_domains`
- `path_prefixes`
- `doc_format`
- `docs_snapshot_exact`
- `last_refreshed_at`
- `stale/fresh status`
- `warnings`
- `project_path`
- `version_source`, например `explicit`, `pubspec.lock`, `.fvmrc`, `package-lock.json`, etc.
- `resolved_version`
- `requested_version`

## Что нужно выдать

Дай структурированный design doc:

1. **Core concepts**
   - Что такое library.
   - Что такое source.
   - Что такое canonical id.
   - Что такое versioned docs entry.
   - Чем отличается docs source от indexed docset.

2. **Proposed data model**
   - Таблица/структура полей.
   - Required vs optional fields.
   - Derived fields.
   - Индексы/constraints, если уместно.

3. **Canonical id rules**
   - Как строить canonical id для unversioned docs.
   - Как строить `library@version`.
   - Что делать с `latest`, `stable`, `main`.
   - Как обрабатывать ecosystem namespaces.
   - Как избегать collisions.

4. **Version resolution rules**
   - Explicit version.
   - Project metadata version.
   - `latest` fallback.
   - Ambiguous version.
   - Exact vs non-exact snapshot.

5. **Web source resolution rules**
   - Как работать с `docs_url`.
   - Когда `docs_url` required.
   - Когда можно использовать stored `docs_url`.
   - Как обрабатывать `seed_urls`, `allowed_domains`, `path_prefixes`.

6. **docs_url_template rules**
   - `{library}` / `{version}` rendering.
   - Ecosystem-specific transformations.
   - Validation.
   - Failure modes.

7. **Project-aware metadata**
   - Как представлять source of version.
   - Как хранить confidence.
   - Как показывать агенту, что version inferred.

8. **MCP response examples**
   - Resolved known library.
   - Unknown library.
   - Ambiguous library.
   - Version inferred from project.
   - Non-exact snapshot warning.

9. **Validation rules**
   - URL validation.
   - Domain/path validation.
   - Version validation.
   - Canonical id validation.

10. **Migration plan**
    - Как перейти от текущей registry model.
    - Какие поля можно backfill-ить.
    - Какие entries требуют user action.

11. **Backward compatibility risks**
    - Что может сломаться.
    - Как смягчить.

12. **Acceptance criteria and tests**
    - Unit tests.
    - MCP integration tests.
    - Migration tests.

## Ограничения

- Не делай модель избыточно enterprise-heavy.
- Приоритет: predictability для LLM-agent и простота implementation.
- Ответ должен помогать устранить `needs_docs_url` ambiguity.

## Формат ответа

Используй таблицы, JSON examples и список implementation steps. В конце дай `Must / Should / Could`.
