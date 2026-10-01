# 01 — P0: recovery для неиндексированного чистого проекта

**Результат:** публичный `get_docs_context` предлагает подготовку найденной документации, а не generic code search.

**Опора:** D1 в [анализе](../audit/ANALYSIS_RU.md), [исходная выдача](../audit/raw/lifecycle/clean-fixture-query.json), `audit/probe_clean_preflight.py`. Общие правила — в [README](../README.md).

## TDD

1. **Red:** новый Git-fixture с committed README и config, чистым worktree, без индекса. Через публичный context path воспроизвести `docs_status: project_docs_found_not_indexed`, но recovery: `no_candidates → code_search`.
2. Добавить regression test: context сохраняет reason `project_docs_found_not_indexed` и typed action `prepare_docs(action="sync_project_docs")` с корректным project path и требуемыми аргументами. Original question/scope не меняются.
3. Добавить controls: dirty, no-Git и indeterminate state остаются confirmation-gated; no-docs, stale, invalid catalog, module-not-found и edit request не получают ошибочную clean-sync ветку. Смена HEAD/worktree/preflight digest до mutation блокирует устаревшее разрешение.
4. **Green:** локализовать потерю lifecycle reason между project service и публичной recovery projection; исправить только эту передачу. Не запускать безусловный sync и не обходить preflight.
5. **Проверка:** regression + controls и installed-MCP smoke на новом fixture. После разрешённого sync запрос получает текущую цитату из README; чистота Git и digest проверяются до mutation.

**Где начать:** `tests/test_clean_git_auto_sync.py`, `tests/test_docs_service.py`, `docmancer/docs/application/_project_docs_service_part03.py`; точный публичный участок найти тестом, не по старым номерам строк.

**Не менять:** поиск, scorer, budgets, пороги, остальные recovery branches без выявленного регресса.

**Готово:** до — неверный code-search action; после — корректный sync action, controls зелёные, installed stdio подтверждает исправление. Затем остановиться.
