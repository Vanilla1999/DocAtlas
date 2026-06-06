# 08.00 — Product Framing

## Почему нужен новый roadmap

Предыдущий roadmap был сфокусирован на превращении Docmancer из мощного, но местами непредсказуемого docs-RAG/MCP инструмента в более agent-proof продукт:

- убрать `needs_docs_url` trap;
- стабилизировать registry/source identity;
- разделить Docs и Packs в narrative;
- начать project-aware dependency docs;
- добавить eval/observability/doctor.

Судя по текущему состоянию README, тестов и product brief, значительная часть этих работ уже реализована или начата. Поэтому следующий roadmap не должен повторять старые пункты как будто проект стартует с нуля.

Новый фокус: **найти wedge, где Docmancer становится лучше Context7 не за счёт hosted public catalog, а за счёт local/project-aware преимуществ.**

## Strategic thesis

> **Context7 gives agents public library docs. Docmancer should give agents the docs this project actually uses.**

Это означает единый agent workflow для:

1. project-owned docs из repo files;
2. private/local docs;
3. exact dependency docs из lockfiles/project metadata;
4. source/version exactness;
5. compact context packs with attribution.

## Anti-goals

Не строить в ближайшем цикле:

- hosted query plane;
- Context7 clone с глобальным public catalog как главным продуктом;
- dashboard/TUI раньше agent-proof CLI/MCP flow;
- SSO/SOC2/enterprise admin;
- broad npm/Python universal discovery до стабилизации project-aware workflow;
- hidden CMS для архитектуры проекта;
- DB-only official project docs без reviewable files;
- Packs hero narrative.

## Product principle: official docs are files

Docmancer должен поддерживать документацию самого проекта, но не заменять её скрытыми записями в SQLite.

Правильная модель:

```text
README.md / docs/*.md / wiki/*.md / Architecture.md / ADR
  -> Docmancer ingest/index
  -> get_project_docs/query
  -> compact grounded context для агента
```

Официальная архитектура, ADR, security model, API contracts и onboarding должны оставаться файлами в repo, потому что это даёт:

- git diff;
- review;
- blame/history;
- rollback;
- portability;
- visibility для людей.

Docmancer-only memory допустима для другого класса данных:

- session summaries;
- investigation notes;
- private user notes;
- temporary hypotheses;
- local-only agent scratchpad.

Но такой контент должен явно маркироваться как `local_memory`, а не смешиваться с official project docs.

## Why this is better than chasing Context7 coverage

Context7 выигрывает в instant public docs lookup. Docmancerу невыгодно догонять его как hosted catalog.

Docmancer структурно сильнее там, где Context7 слабее:

- приватные docs не уходят в облако;
- project architecture и roadmap доступны агенту локально;
- exact dependency versions можно брать из lockfiles;
- sources inspectable на диске;
- можно объединить project docs + dependency docs в одном grounded answer;
- offline/local-first trust model.

Главный narrative:

```text
Context7 knows public libraries.
Docmancer knows your project and the docs your project actually uses.
```
