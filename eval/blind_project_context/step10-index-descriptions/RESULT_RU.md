# Итог bounded development: прироста покрытия нет

Статус: implementation/integration выполнены; единственный frozen A/B завершён.
Parent final review выполнен: `PARENT_REVIEW_RU.md`; отрицательный результат
подтверждён по diff и raw packets. Historical Qwen validation FAIL сохранён.

## Результат публичного acquisition API

| Вопрос | Факты baseline → descriptions | Returned candidates | Source UTF8 bytes | Raw JSON packet bytes |
|---|---:|---:|---:|---:|
| V-M1 | 0/8 → 0/8 | 0 → 0 | 0 → 0 | 364 → 364 |
| V-M2 | 5/6 → 5/6 | 20 → 20 | 3870 → 3870 | 157405 → 176930 |
| V-M3 | 5/5 → 5/5 | 17 → 18 | 3334 → 3506 | 134117 → 159270 |
| V-M4, no-answer | 0 required; оба пустые | 0 → 0 | 0 → 0 | 364 → 364 |
| Итого | **10/19 → 10/19** | **37 → 38** | **7204 → 7376** | **292250 → 336928** |

Все21 descriptions добавлены, без skip в Meridian. В V-M3 появился дополнительный
`overview.md[0:172]`; обязательных фактов это не добавило. В обоих V-M2 отсутствует
`Weather decisions govern execution, not ownership of reservations.`
V-M1 остаётся пустым при исходном русском вопросе и English lexical corpus;
перевода и rewriting не было. Пустой V-M4 не доказывает semantic no-answer:
языковая граница может давать тот же результат независимо от содержания вопроса.
Полнота не достигнута; экономия не доказана, объём returned acquisition вырос.

Обязательные source/span/hash/scope/version проверки прошли на всех returned
chunks. Для пустых packets это vacuous check, не доказательство качества поиска.
Description metadata реально видна Python-клиенту в непустом enriched packet,
но literal facts считались исключительно по chunk.text соответствующего source.
Raw bytes — размер сохранённого полного JSON результата Python API, не network
wire measurement; source UTF8 bytes посчитаны отдельно. Инженерные UTF8/4 estimates
по запросам есть в results.json; provider tokens не измерялись.

Измеренная граница — **все returned acquisition candidates**, не final answer.
Аргументы limit5/budget4096 фиксированы, но dispatcher их reported_not_applied;
top5/crop не применялся. Реальные ceilings:256 candidates,131072 estimated tokens,
1048576 UTF8 bytes. Final-context reduction и internal candidate recall не заявляются.

## Реализация и история проверок

- `experimental_search_descriptions.py`: строгая source/child/hash validation,
  whole-description skip по512bytes/hard_max, matched child binding/status.
- `_sqlite_store_part02.py`: source-level artifact, append после прежнего text,
  независимо реконструируемая generation validation, точный display сохранён.
- `_sqlite_store_part03.py`: утверждённая recipe `source-description-routing-v1`:
  только appended description в существующем routing field. Body statistics,
  BM25, веса и baseline без artifact сохранены. BEFORE захвачен из dirty worktree.
- Существующий `tests/test_contextual_indexing.py` расширен одним public integration
  lifecycle. Diagnostic inventory обновлён одной node-hash строкой, labels прежние.
- Первая попытка: collection ERROR,0tests. После разрешённой registration repair:
  1PASS/1FAIL (description отсутствовала в admission). После разрешённого wiring:
  **2PASS**. Тесты/критерии между FAIL и PASS не менялись. Все исходные logs сохранены.

## Work counts / provenance

- Prepare:1 ingestion,6documents,21children;21/21 exact heading-to-child matches.
- Integration:3 попытки, суммарно4 исполнившихся tests,4 public query calls.
- A/B:1 run,2 isolated ingestions,8 public queries (4 на arm).
- Всего10 public ingestion attempts,9successful,1ожидаемый stale artifact reject.
- Runner model calls0, downloads0. Annotation — отдельная harness generation;
  её provider calls/tokens/cost неизвестны, не объявляются нулевыми.
- Checkout `.venv/bin/python` CPython3.13; не installed stdio/real client/Terra.

Основные artifacts: `freeze.r3.json`, `implementation.r3.diff`, `BEFORE/`,
`integration.r3.*`, `EXECUTION_RESULT.r3.json`, `runtime-evidence/`,
`runtime-evidence-hashes.json`. Предыдущие freezes/errors/FAIL сохранены отдельно.
Commands и executable paths находятся в `*-command.json` и runtime provenance.
Исходные SQLite/run dirs: `/tmp/opencode/step10-index-descriptions-prepare-01/`
и `/tmp/opencode/step10-index-descriptions-ab-01/`.

Scope/recipe/inputs не менялись после first A/B; повтор A/B не выполнялся.
