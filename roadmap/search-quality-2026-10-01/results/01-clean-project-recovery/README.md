# Шаг 01: результат TDD

**Ветка:** `experiment/retrieval-ablation-continuation`, по запросу пользователя без перехода на `main`.
**Первый коммит:** `5cd7515c` — аудит и TDD-план. Runtime-правка, тесты, ревью и результаты включены в отдельный коммит; push/merge не выполнялись.

## Исправлено

- `get_project_docs` сохраняет точную проверенную clean-Git action, включая `plan_digest`.
- Unified context передаёт `project_docs_found_not_indexed` как operational reason только для чистого неиндексированного project lane без evidence/confirmation.
- Публичная projection больше не заменяет эту action на generic code search из-за `source_search_required`.
- Сам `get_docs_context` не выполняет sync и не выдаёт answer/edit permission. Мутация по возвращённой action повторно проверяет HEAD, worktree и preflight.

Production diff ограничен тремя файлами:

1. `docmancer/docs/application/_project_docs_service_part03.py`.
2. `docmancer/docs/application/_unified_context_service_part01.py`.
3. `docmancer/docs/interfaces/mcp/context_tools.py`.

Тесты: `tests/test_clean_project_context_recovery.py` и его hash-bound diagnostic label shard. Поиск, scorer, caps, бюджеты, defaults, зависимости и lockfile не менялись.

## До / после

| Проверка | До | После |
|---|---|---|
| Новые 29 regression/control cases на одинаковых финальных fixtures | 20 failed, 9 passed | **29 passed** |
| Installed wheel, настоящий MCP stdio | `no_candidates → code_search` | `project_docs_found_not_indexed → prepare_docs` с точным digest |
| Dirty worktree после получения action | Action не доставлялась | `precondition_failed`, indexed=0 |
| Sync и повтор исходного вопроса | Недоступны по recommended action | success → текущая verbatim README citation |

Baseline — production из `5cd7515c`; новые тесты запускались с этим неизменённым кодом, затем с working-tree правкой. Python 3.12, зависимости из frozen lockfile. Для installed smoke использован wheel в локальной `.venv`, не editable package и не глобально установленный MCP. Проверена byte parity всех **383** production Python-файлов; между wheels отличаются только три файла выше.

- [Baseline tests и три старых failures](baseline-comparison.log).
- [29 зелёных regression cases](regression.log).
- [Расширенный прогон](focused.log): **292 passed, 3 failed**. Все три failures воспроизводятся и на baseline: generic retrieval-hint attribution, отсев `docs/note-*`, frozen request-flow witness. Общий suite не объявляется зелёным; их поиск здесь не исправлялся.
- Финальное lifecycle сравнение: [before-explicit-fixture](before-explicit-fixture/result.json) → [after](after/result.json). Рядом сохранены официальные wires и runtime hashes.
- [Runner](run_installed_smoke.py) одноразовый: `--phase before|after --executable <installed doc-atlas> --checkout <repo> --output <new directory>`. Before проверяет wheel против pinned `--baseline-commit` (по умолчанию `5cd7515c`), after — против working tree. Использовать только новый output; fixtures создаются в `/tmp/opencode`, существующие индексы не очищаются.
- [Ревью перед коммитом](REVIEW_RU.md): исправлена привязка before-runner к перемещающемуся HEAD; production diff после ревью не расширялся.

## Ограничения и остановка

1. **No-Git пункт исходного плана полностью не закрыт:** legacy inspection разрешает explicit sync без Git (`requires_confirmation=false`), public sync без `plan_digest` не является clean-Git recovery. Новая ветка не даёт такому проекту clean witness; потеря Git после получения guarded action блокирует mutation. Изменение legacy confirmation policy требует отдельного решения; старые tests не ослаблялись и эта policy не переписывалась.
2. Первый fixture из старого аудита после sync показывал отдельную retrieval-потерю, хотя lower service находил README. Он сохранён в [before](before/result.json). Финальный lifecycle fixture явно формулирует how-to sentence; его bytes одинаковы в before-explicit-fixture/after. Это не исправление recall и не доказательство качества поиска на произвольных вопросах.
3. Проверены dirty/indeterminate state, no-Git isolation от clean ветки, смена HEAD/digest/preflight, no-docs, invalid catalog, module-not-found, stale/ready и отсутствие edit permission. Существующая stale recovery отдельно не переписывалась.
4. Step 02 (clear/rebuild), поиск и следующие задания не начаты. Полный test suite и независимый end-to-end benchmark не запускались.

Исходные 885 manifest entries в `audit/` совпадают с сохранёнными SHA256 и в working tree, и в Git blobs первого коммита.
