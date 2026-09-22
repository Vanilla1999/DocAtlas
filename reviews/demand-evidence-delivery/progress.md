# Доставка свидетельств v2: старт отдельного PR

## Текущий статус

Это R0 / RED-checkpoint, а не реализация R1–R6 и не новый product gain.

Владелец попросил слить предыдущую работу в main и продолжить в новой ветке через PR. Слияние НЕ выполнено: свежий CI предыдущего PR #195 завершился failure. Часть логов/указанных в них путей не удалось независимо перепроверить через connector, поэтому причины не исправлялись наугад и проверки не обходились.

PR #196 восстановлен из полного T06 checkpoint: достижимый commit `674a4796c8a49dad305a1a22f11711fa07b5574a`, runtime tree `196d3e7b20a386ea0cf353616fdbca2190082cfc`. Это настоящий потомок удалённого `dab280325729bad7dc4cbf9c1fe1c58397816c58`, не публикация синтетической истории bundle. Старые большие архивные документы не объявляются побайтно опубликованными.

Новая ветка: `fix/evidence-delivery-v2-20260922`. Временно основана на `feat/demand-evidence-sets`, поскольку main ещё не содержит T06. Новый PR должен оставаться draft. После устранения merge blockers сначала интегрировать предыдущую работу, затем перебазировать/перенацелить этот PR на main без force-push и без потери изменений.

## Что добавлено

- Обычный `tests/docs/test_evidence_set_delivery_acceptance.py`: исходные вопросы, настоящий handler, полный естественный pool и неизменённый старый assessor.
- Test-only `_delivery_acceptance_helpers.py`: wire constraints и проверка достаточности.
- Только новая запись и hash трёх базовых node IDs в существующем `diagnostic_labels.evidence_sets.json`. Conftest и исходные green controls не отключены.
- `baseline.json` с версиями, наблюдениями и границами проверки.

Production, corpus, gold, old scorer, lock, workflows и default model в этом новом increment не меняются.

## Свежие проверки этого increment

| Команда | Наблюдение |
|---|---|
| `python -m pytest tests/docs/test_evidence_set_delivery_acceptance.py -q --tb=short` | 5 failed, 3 passed; 5.33 s |
| `python -m pytest tests/docs/test_evidence_set_*.py -q --tb=short` | 5 failed, 180 passed; 10.25 s |
| `python -m pytest -q --tb=short` | 3 skipped, 6 collection errors; missing w3lib; 10.67 s |

Пять RED: MkDocs05, Pydantic03, FastAPI06, HTTPX03, uv04. Все падения нового набора — отсутствие требуемого факта в конечной выдаче, не ImportError и не collection mismatch.

Три GREEN: сохранение известной части Pydantic07/Ruff07 и запрет подменять явно отсутствующий класс другим классом. Все прежние 177 Evidence Sets checks в общем запуске остаются зелёными.

Полный pytest остановился при collection в `tests/docs/test_curated_sources.py`, `tests/test_auto_detection.py`, `tests/test_filtering.py`, `tests/test_kotlin_partial_crawl.py`, `tests/test_preindex_coverage.py`, `tests/test_web_fetcher.py`. Это открытый environment gate, не успешная полная проверка. `uv sync --frozen --extra dev` в исходной сверке не завершился из-за DNS/доступа к сети; зависимости не подменялись mocks.

Секунды выше — длительность проверок, не сравнительный benchmark производительности. Full external80 и независимый transfer в этом increment не запускались.

## Исполнение приложенного TDD-плана

Это краткий ledger, а не замена полного пользовательского `DocAtlas_delivery_TDD_v2_RU(1).md`; SHA256 оригинала записан в baseline.

1. **R0:** завершить canonical/merge/full-environment gates. Уже перенесены стартовые RED и проверены source/runtime identities; весь R0 ещё не закрыт.
2. **R1:** включить source-safe context eligibility в общий pool до semantic culling. MkDocs05 должен стать sufficient на обычном полном pool с distractor; непустая старая цитата не блокирует лучшую. Не заменять результат первым fallback. Сохранить Pydantic07/Ruff07 и negative guards.
3. **R2:** сохранить полный перечень Pydantic03 от query window до final rows, учитывать actual DTO cost целого verified bundle и completeness categories/count. Один Field не равен полному списку.
4. **R3:** согласовать subject origin, область CORS и explicit identity; focus-only не путать с applicability. Настоящие only-when/only-for constraints сохраняются.
5. **R4:** реальные wrapped Markdown lists HTTPX и source-bound механизм+причина uv, включая bounded retrieval недостающего продолжения.
6. **R5:** opt-in multilingual experiment только при доказанной residual retrieval loss; не менять default и не маскировать downstream rejection embeddings.
7. **R6:** неизменённый old scorer/full80, source/budget/crop/condition controls, mutation tests, full suite и latency в одном окружении. Не засчитывать sidecar corrections как product gain.

Ближайший результат: MkDocs05 и полный Pydantic03 GREEN, сохранены прежние 36/48 normal и 7/8 known-part partial. Эти архивные числа — целевые retention obligations, не заново измеренный full80 этого PR.

Не повторять T00–T06. Не поднимать глобальные lexical/top-k/query/hydration budgets. Не добавлять case/library allowlists, eval imports в runtime, скрытый перевод или LLM. Каждый snippet — точный непрерывный original-source range; несоседние spans — отдельные rows либо оплаченный реальный диапазон. Final DTO <=800 tokens, <=3 source rows; answer_supported/answer_available/edit_ready=False. Source/exact/condition guards и pure no-I/O boundary обязательны.
