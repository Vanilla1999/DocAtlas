# Выполнение плана #211

**Latest checkpoint: [CONTINUE_HERE_RU.md](CONTINUE_HERE_RU.md).**
Current HEAD `9a7299e2`, dictionary-exit implementation в незакоммиченном primary
diff; 146 новых tests passed, real stdio smoke PASS. Quality gate red, full exit
NOT DONE. [Owner change / journal](DICTIONARY_EXIT_EXECUTION_RU.md).
Ниже исторический CI/diagnostic отчёт: опубликованные SHA и прежние entry gates
не являются current local implementation status. P1 уже owner-approved/frozen;
replacement больше не prerequisite удаления словарей.

## Исторические исследования до dictionary-exit implementation

Дата: 2026-10-06. Опубликованный product head: `8d2381d8`.
Pebble prefit patch опубликован. Разрешения merge нет.
Последнее исследование по запросу владельца:
[удаление retrieval-словаря](RETRIEVAL_DICTIONARY_REVIEW_RU.md).
Общий план RU/EN и критерии завершения:
[DICTIONARY_EXIT_PLAN_RU.md](DICTIONARY_EXIT_PLAN_RU.md);
[реестр D01–D38](DICTIONARY_INVENTORY_RU.md). P0 archival ACTIVE,
[P1 DONE: owner-approved contract/freeze/resource limits](P1_STATUS_RU.md),
[P2 ACTIVE: isolated development prototype](P2_STATUS_RU.md), P3–P7 NOT STARTED;
реализация нового pipeline и test-contract migrations ещё не выполнены.
Продолжение P0: [caller map и baseline manifest](P0_READ_PATH_AUDIT_RU.md),
[статус этапов](DICTIONARY_STAGE_STATUS_RU.md).
Подготовлены [P1 acceptance и migration ledger](P1_ACCEPTANCE_DRAFT_RU.md),
64-case bilingual draft; [P0→P1 entry gate](P0_TO_P1_GATE_RU.md) пока NOT READY.
Итог parallel audit: [P0_PARALLEL_RESULT_RU.md](P0_PARALLEL_RESULT_RU.md).
Classification и named consumer maps завершены в pinned grouped scope;
P0 не закрыт формально из-за baseline execution-provenance linkage.
Работу по согласованию P1 можно продолжать; approval/freeze ещё нет.
Полное отключение aliases теряет recall; локальное удаление trust trigger тоже
теряет настоящие trust quotes. Ни одно не принято как готовое исправление.

Свежие checks `8d2381d8`: required-ci/core/advanced-contract/P1 stack/adversarial
FAIL, required-release PASS. Ниже сохранены исторические проверки `755b33cd`;
результаты опубликованного prefit — в [PREFIT_PATCH_RU.md](PREFIT_PATCH_RU.md).

## 1. Подтверждённый CI

Источник: `gh pr checks 211` и failed logs runs `37439569333`, `37439569262`.

- Core Python 3.11 / 3.12 / 3.13: одинаковые 17 failures, 5282 passed,
  10 skipped, 622 deselected.
- Advanced: job падает на `Run Legacy live compatibility report and lineage floor`:
  `original query coverage below frozen floor: 10 < 12`.
- Adversarial: FAILURE; подробная причина на этом этапе заново не установлена.
- Required CI: FAILURE; required release: PASS.
- P1 stack core, advanced-security и exact: FAILURE. Их самостоятельные логи
  ещё нужно сопоставить с основным CI, не считать автоматически новой причиной.

### Рoster 17 core failures

Все пути ниже относительно корня; группа — предварительная классификация assertion,
не установленная root cause. Base/head comparison пока не выполнено.

| Файл / тест | Количество | Дальнейшая проверка |
|---|---:|---|
| `tests/docs/test_component_coverage.py`: visible component novelty `[projection_clip]` | 1 | Цитата/coverage после crop; не заменять потерянный witness чужим |
| `tests/docs/test_context_projection_boundaries.py`: frozen request flow | 1 | Доставка module witnesses |
| `tests/docs/test_direct_docatlas_questions_15.py`: all required facts | 1 | Установить конкретный потерянный README fact |
| `tests/docs/test_generic_context_workflows.py`: health, first session, selection | 3 | Проверить реальные публичные цитаты; полноту отличать от доступности |
| `tests/docs/test_project_answer_contract_v3.py`: frozen V2 config | 1 | Hash/contract migration, не объясняется качеством поисковика |
| `tests/docs/test_question_plan_v4.py`: compound mandatory facets | 1 | Query-plan contract |
| `tests/docs/test_request_flow_lineage.py`: four-fact fail-safe | 1 | Source lineage и публичное покрытие |
| `tests/docs/test_review_boundary_semantics.py`: четыре `[...-256-...]` | 4 | Budget/DTO: `KeyError: sources`; не повышать лимит молча |
| `tests/evidence_quality_v2/test_readme_neutral_context.py`: safe context; duplicate lookup | 2 | Полезный Pebble контекст теряется; проверено ниже |
| `tests/test_docs_service_part02.py`: generic hint attribution | 1 | Hint versus anchor public representation |
| `tests/test_docs_service_part03.py`: non-project docs same terms | 1 | Project ownership/scope — integrity, не полнота ответа |

## 2. Первая адресная проверка: Pebble

Команда локального воспроизведения:

```bash
uv sync --frozen --python 3.12 --extra dev
DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest -q tests/evidence_quality_v2/test_readme_neutral_context.py
```

Результат: **2 failed, 13 passed**. В обоих failures вопрос:
`What kind of interfaces does Pebble create, and how is it intended to compose them?`
Retrieval действительно содержит `command line interfaces\nin a composable way`,
но публичный `context_available=False`, reason quality — `source_unavailable`.
Test уже требует только partial retrieval с false answer/edit flags, а не доказанного
ответа. Поэтому пожелание владельца не делает этот assertion устаревшим автоматически.

Дополнительный live capture через тот же `capture()` показывает, что в
`trace.stages.projector_inputs[0].context_pack` уже **0 источников**, хотя в
`retrieved_candidates` нужная цитата есть. Query plan сохраняет original и hints
`interfaces`/части вопроса; обе части находятся в `unresolved_parts`, component
contract пуст. Следовательно, для этой потери сначала исследовать отбор **до**
public projector; изменение только его late fallback не доказано достаточным.
Полный локальный capture: `/tmp/opencode/pr211-pebble-current-capture.json`;
это временная диагностика, не committed переносимый архив.

Первоначальный offline запуск с Python 3.13 не смог создать полное окружение:
wheel onnxruntime отсутствовал в локальном cache. Это ошибка setup, не product FAIL.
Повтор на Python 3.12 с frozen lockfile выполнен успешно; lockfile не менялся.

## 3. Grounded на том же исходном тексте Pebble

Использован точный `TEXT` из указанного test-файла (придуманная fixture, не
публикация проектных документов). Отдельная одностраничная библиотека:
`pr211-comparison-pebble-20261006@0.0.1`.
Job `65e1e98a-41be-47f7-92ae-ad03d13ceaf4`: completed,
2026-10-06 09:08:35–09:08:36 UTC.
Scrape: `maxPages=1`, `maxDepth=0`, `scope=subpages`.
Transport: `https://httpbingo.org/base64/` + percent-encoded Base64 исходного UTF-8
`TEXT` с завершающим newline, как в предыдущем Grounded report.

`search_docs` в обоих случаях: указанная library/version, `limit=3`.

| Точный query | Фактический результат | Сравнение |
|---|---|---|
| `What kind of interfaces does Pebble create, and how is it intended to compose them?` | `Result 1` с полным TEXT, включая нужную цитату | Потеря полезной цитаты наблюдается только у DocAtlas, не у Grounded |
| `Как Pebble отправляет сообщения через квантовый канал?` | `Result 1` с тем же полным TEXT; про квантовый канал ничего нет | Нерелевантный search hit у Grounded; наш локальный negative control проходит и контекст отвергает |

Нет выводов о ложном ответе host LLM или answer authority Grounded. Один документ
не измеряет ranking quality и частоту дефекта. Здесь нельзя поставить общую метку
«проблема у обоих» ни потере полезной цитаты, ни quantum negative control.

## 4. Следующие действия

1. На Pebble проследить query plan → qualification → hint fallback → final packet,
   установить конкретную причину отбрасывания. Проверить тот же кейс на main.
2. Попробовать минимальную коррекцию retrieval-only admission с положительными и
   negative controls; не делать topic-name совпадение достаточным доказательством.
3. Если correction теряет safety/полезные факты — сохранить неудачную попытку,
   не переносить её в продукт; решение о deferred limitation записать отдельно.
4. Продолжить остальные группы реестра, затем full CI/review по merge plan.

Обновление после выполнения следующей итерации: применён кандидат prefit fallback,
добавлены отдельные behavioral tests и их hash-bound diagnostic shard. Существующие
tests, gold, budgets и workflows не изменены. Core: 15 FAIL вместо 17;
advanced pytest: 622 PASS; legacy: 11 < 12; adversarial: 27/28.
Есть прогресс, полного выполнения merge plan нет. Код и документы публикуются
по разрешению владельца; кандидат ещё требует независимого review и итогового CI.
