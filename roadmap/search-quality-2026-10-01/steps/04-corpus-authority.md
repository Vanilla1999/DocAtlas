# 04 — P1: authority и lifecycle проектных документов

**Результат:** wiki, ADR, supporting analysis, планы и roadmap имеют проверяемую роль; история не выдаётся за новый operational contract.

**Опора:** D6 и ограничения корпуса в [анализе](../audit/ANALYSIS_RU.md). Общие правила — в [README](../README.md).

## TDD

1. **Red:** выбрать конкретный конфликт current/history из аудита. Проверить его catalog entries и действующие authority/lifecycle правила; не объявлять весь roadmap или все ADR устаревшими.
2. Добавить catalog regression: canonical current страница корректно классифицирована; superseded/исторический вариант не получает current authority; supporting/planning документ не превращается в обязательное product guarantee.
3. Control: явный запрос истории остаётся доступным через предусмотренный contract routing. Валидация catalog, project/module scopes и source isolation не ослабляются.
4. **Green:** минимально исправить подтверждённые entries в `docatlas.project-docs.yaml` и lifecycle-пометки/ссылки соответствующих страниц. Использовать существующие роли и статусы.
5. **Проверка:** catalog tests + current/history запросы через installed MCP на fixture с этими документами. Сохранить evidence IDs и роли источников; файлы истории остаются на месте.

**Где начать:** `tests/docs/test_project_docs_catalog.py`, `tests/docs/test_task19_project_docs_closure.py`, `docatlas.project-docs.yaml`.

**Не менять:** ranking/qualification, scorer, budgets; не удалять исследования, планы или пользовательскую работу. Не добавлять этот архив как operational source of truth.

**Стоп:** если исправление требует нового routing/authority механизма, вынести его в отдельную задачу. Готово после исправления catalog drift, а не после искусственного сокращения corpus ради score.
