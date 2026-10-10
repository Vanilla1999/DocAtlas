# PR #211: явная подготовка четырёх real-index fixture scenarios

Статус: подготовлено для независимого review и обычного PR CI.
Production и общий fixture runtime не меняются.

## Наблюдавшееся падение

На0855 общий [JUnit reader114047940486](https://github.com/Vanilla1999/DocAtlas/actions/runs/37996655986/job/114047940486)
показал PermissionError в первом generic workflow и единственном frame end-to-end test:
старый service.sync_project_docs не имеет явного mutation grant.
Catalog membership само по себе не разрешает запись, deduplication или deletion.

В frame test это блокирует весь исходный список вопросов до первого public read.
В generic module меняется только первый test с тремя существующими параметрами.
Остальные38failures этого модуля не объявляются исправленными; первая причина
не классифицирует их автоматически.

## Миграция setup

Оба теста используют существующие isolated_service и index_project из
eval/evidence_quality_v2/runtime.py, base blob153107026c725d9ee4ad10d1e4849a6956264300.
Этот путь уже выполняет настоящий public prepare_docs с явным confirm,
точным host-selected storage_path, generation, catalog SHA и document/hash roster.

Индексируется только прежний конечный явный docs-only catalog.
После preparation сверяется весь expected/indexed path roster и отсутствие
неожиданных/неподготовленных источников.
Первоначальные документы, roles/authorities, вопросы и lookup_queries сохраняются.
Все прежние source/fact/answer/edit/unknown-tail assertions также сохраняются.

Frame module: старый общий helper _service оставлен побайтно неизменным для прочих callers.
Единственный текущий test переводится на жизненный цикл isolated_service.
Generic module: аналогично меняется только test_generic_workflow_facts_survive_real_index;
остаток модуля, все decorators и параметры остаются прежними.

Новых test definitions/expanded cases нет. Это четыре setup migrations, не test reduction.
В обоих тестах после подготовки всё ещё исполняется настоящий get_docs_context.
Нет новых provider calls, моделей, downloads, пользовательских индексов или общей конфигурации.
Источники и state относятся только к временной fixture существующего harness.

## Что требуется от CI

Setup должен дойти до неизменённых вопросов и fact assertions.
Если далее выявится отсутствие факта/qualification, это отдельный сохраняющийся FAIL,
а не разрешение подставить actual пустой result в ожидание.
Read-only startup boundary отдельно проверяется recovery gate; эта миграция её не
переносит и не объявляет исправленной.

Локальные imports/pytest/AST/runtime не выполнялись.
Нужен independent static review, затем обычный core на опубликованном SHA.

| Файл | Base blob | Proposed blob | Mode |
| --- | --- | --- | --- |
| tests/docs/test_question_frame_paraphrase_e2e.py | ef4fc66a967783ceae1ec444fbf7a6a35ff99b67 | 179ae9e486628e86a34c8d665f08e562d2580de4 | 100644 |
| tests/docs/test_generic_context_workflows.py | 9bf2fb1243fdfc114c79a5513a092d015fcecea1 | 91d85c23e67e31d4b0e774f596824e0b5a464d92 | 100644 |
