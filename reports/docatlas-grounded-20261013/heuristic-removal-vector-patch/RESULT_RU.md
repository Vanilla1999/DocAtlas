# Продолжение: vector/degraded retrieval и advanced patch context

База изменений: `b9ef424d`, ветка `experiment/heuristic-removal-20261013`.
Этот этап не завершает удаление эвристик из всех подсистем.

## Изменения

- Dispatcher больше не применяет квоту по источнику и structural-overflow
  добор по совпадению parent. Порядок native/fused retrieval сохраняется под
  общим ограничением количества. Acquisition reserve не зависит от старой
  настройки `max_sections_per_source`.
- Удалено автоматическое включение hierarchical retrieval по размеру корпуса.
  Явно включённый двухэтапный метод пока сохранён.
- В patch selection удалены coverage-first/completeness ordering и отбор по
  marginal utility/lexical novelty. Сохраняются acquisition order, точная
  дедупликация, проверки допустимости источников и отдельные проверки coverage.
- Request-bound source receipts теперь доступны для явно выбранного
  `context_format=patch_context`. Это исправило пустой advanced patch packet
  для исходного optics-вопроса: ранее исключение patch-format из receipt scope
  приводило к `retrieval_status:not_found` и `no_admitted_evidence`.
- Публичный advanced patch packet остаётся read-only: четыре исходных окна,
  `result=data`, `completeness=partial`, `edit_ready=false`,
  `missing=[visible_content_assignment_required]`. Источник не стал доказательством
  разрешения на изменение или полного ответа.

## Проверки и границы доказательства

`vector-patch-final.log/xml`: **8 passed in 4.54s**:

```
tests/test_heuristic_removal_public_integration.py
tests/test_prepared_retrieval_integration.py
```

После добавления записи patch evidence и включения patch trace повторён только
изменённый lifecycle сценарий: `vector-patch-trace.log/xml`, PASS.
Unit не запускались и не добавлялись. `git diff --check` — PASS.

Новый vector-сценарий использует production ingest, настоящий SQLite,
sqlite-vec и dispatcher runtime. Только внешний embedding HTTP заменён
фиксированным ответом через транспорт настоящего OpenAIProvider. Модель и
векторный сервис не загружались и не запускались. В изолированный Python runtime
добавлен OpenAI SDK 2.54.0; lockfile проекта не менялся.

Два HTTP-ответа обслужили batch из четырёх индексируемых окон и один запрос.
Проверены три независимых факта одного документа (73 mm, 19 seconds, 41 nights),
буквальная принадлежность окон исходнику, исключение `secret.md`/HIDDEN_97,
сохранность SQLite состояния и отсутствие document-count autorouting.
Старая квота настроена в 1, но все три окна доставляются.
Фиксированные embeddings не доказывают качество semantic relevance.

**Полноценный hybrid не прошёл в этом окружении:** действующий readiness
контракт требует `sparse_model`, которой у OpenAI dense-индекса нет.
Сценарий явно проверяет этот отказ, затем разрешённый
`hybrid/lexical_fallback_degraded`. Он не объявляется проверкой fusion или sparse.
Проверка полноценного hybrid остаётся открытой, её исходный FAIL сохранён.
Readiness/parity/access проверки ради PASS не ослаблялись.

Advanced patch проверяется через публичный MCP с явно включённым
`DOCATLAS_MCP_ADVANCED_TOOLS=1`. Использованы прежние optics-вопрос и исходники;
проверены все исходные факты, текст, SHA-256, char spans, untrusted-data маркировка,
отсутствие edit authority и общий read-only инвариант lifecycle-сценария.
Это source-tree integration, не installed stdio и не production smoke.

## Разбор неуспешных запусков

- `vector-patch01`: default MCP schema отклонила advanced формат; исправлена
  конфигурация harness. Hybrid отказал из-за отсутствия sparse_model;
  дальнейший прогон разделяет dense, явный отказ и degraded fallback.
- `vector-patch02`: patch v4 не имеет поля answer_supported; matcher перенесён
  на реальный контракт v4. Отсутствие sources оставлено ошибкой.
- `vector-patch03/04`: расширена диагностика реального пустого patch packet;
  зафиксирован failure с `no_admitted_evidence`. Исправлен receipt scope продукта.
- `vector-patch05`: источники появились, но прежний docs-context integrity
  helper ожидал другой формат полей. Добавлены независимые v4 проверки
  path/text/hash/span и неизменённых optics-фактов.
- `vector-patch-final`: все восемь сценариев прошли.
- `vector-patch-trace`: проверена включённая трасса patch, сохранён итоговый
  packet в XML properties. Логи не заменяют проверки конечных фактов.

`LOG_ANALYSIS.json` содержит извлечённые runtime/patch результаты, request-end
events и SHA-256 сохранённых логов/XML. Повторные запуски были связаны с
исправлениями либо недостаточной диагностикой конкретного FAIL.

## Точный остаток для продолжения

1. `_dispatch_part01.py`: явно включённый `_run_hierarchical` с document-score
   aggregation и top-documents; `_rank_candidate_lists` с configurable
   weighted RRF. Отличать стандартный выбранный метод от локальной эвристики.
2. `_dispatch_part01.py` / `_dispatch_part02.py`: ограниченные candidate pools,
   vector scoring reserve, explicit adjacent/page expansion. Это не удалённые
   квоты источников; определить согласованный ресурсный/методный контракт.
3. Полноценный hybrid+sparse и fusion: нужен изолированный настоящий sparse
   backend/provider; текущий результат этого не доказывает. Readiness требует
   sparse_model, хотя `_fan_out` условно добавляет sparse — несогласованность
   нуждается в отдельном решении контракта, не в обходе проверки.
4. `_evidence_selection_part01.py`: `_query_identifier_conflict` всё ещё может
   отклонять patch candidate по строковому identifier prefix. Coverage/witness
   assignment остаётся отдельным путём; его нельзя подменять source admission.
5. `docs/_patch_plan_context_part02.py`: graph hint score boosts, threshold seeds,
   top-files и graph-neighbor expansion. В этом этапе не изменялись.
6. SDK/CLI/mixed-context последствия обязательного live receipt, installed
   wheel/stdio и старые unit-импорты удалённых modules из прошлого этапа остаются
   непроверенными. Прежний library trace gap upstream diagnostics не устранён.

Изменения этого этапа не коммитились и не пушились.
