# Шаг 04 — catalog authority и lifecycle

Baseline HEAD: `11ee5dbe`; при выполнении шага 04 незакоммиченные изменения шага 03 оставлены на месте, fixture использует страницы после шага 03. Результат включён в общий коммит шагов 03–04 по запросу пользователя; без push/merge. [Саморевью](../03-public-docs-contract/REVIEW_RU.md).

## До → правка → после

Подтверждён конкретный current/history конфликт из класса D6: ADR 0003 объявляет project-answer v1–v4 evaluators retired, но catalog entry `eval/project_answer_surface_v1/README.md` оставался `source_of_truth / active`, а страница называла frozen parser surface обязательным product contract. ADR 0002 уже корректно `historical / superseded` и не менялся.

- [Red](red.log): 2 assertion failures, 1 history-routing control passed. Предварительные ошибки настройки diagnostic label и имени поля candidate исправлены до этого сохранённого regression run.
- `docatlas.project-docs.yaml`: только v1 entry переведён в существующие `historical / superseded`, уточнена description; role/scope/impact сохранены.
- `eval/project_answer_surface_v1/README.md`: добавлена lifecycle-пометка и ссылки на ADR 0003/current project-context protocol. Frozen cases, команды и историческое содержание не удалены.
- `tests/test_corpus_authority_catalog.py` и diagnostic label: canonical active sources, retired ADR/protocol, supporting plans/analysis, module scope и существующий history/lifecycle routing.
- [Green](green.log): **36 passed** — новые tests, project-docs catalog и task19 closure (validation, safe roots, module/project scopes, lifecycle и isolation controls).

## Installed MCP stdio

[Runner](run_installed_smoke.py), [provenance](installed/provenance.json), [sync](installed/sync.json), [current](installed/current.json), [history](installed/history.json), [evidence IDs + роли](installed/evidence-roles.json).

Пять настоящих документов скопированы без изменения байтов в новый committed Git fixture; catalog entries взяты из текущего каталога. Installed runtime import — site-packages, все Python runtime bytes сверены с checkout; version/HEAD/corpus hashes сохранены. Один MCP stdio процесс: sync → current → history.

- Current: ADR 0003 и MCP contract, только `source_of_truth / active`; retired v1 не доставлен.
- Explicit historical evaluation: две цитаты v1 с evidence IDs, `historical / superseded`; snippet bytes проверены против fixture sources.
- Роли в sidecar сопоставлены с fixture catalog по фактически возвращённым paths, а не объявлены дополнительными public wire fields.

## Ограничения

Это исправление одного подтверждённого catalog drift, не полная ревизия всех ADR/plans и не recall benchmark. Supporting plans остаются supporting; active roadmap не объявлен устаревшим. Новые статусы, authority/routing механизмы, search/ranking/qualification, budgets, defaults, scorer, зависимости и runtime не менялись. Audit не перезаписывался и не добавлялся как operational source of truth. Full suite и независимый quality gate не заявляются. Шаг 05 не начат; после этого шага остановка.

Повторный installed smoke после ревью сохранён в новом [review-installed](review-installed/provenance.json) output; [evidence roles](review-installed/evidence-roles.json) и wire packets не подменяют предыдущий прогон. Проверены final corpus parity и неизменность installed runtime. Объединённые тесты обоих шагов — [81 passed](../03-public-docs-contract/review-tests.log).
