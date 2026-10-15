# PR211: необязательные downstream diagnostics не расширяют observer contract

## Причина и actual evidence

PR head: `321f36577577cb90a0422cee0de0b525b9cd658e` (107).
В [main run 38014539455](https://github.com/Vanilla1999/DocAtlas/actions/runs/38014539455)
[JUnit reader 114103727373](https://github.com/Vanilla1999/DocAtlas/actions/runs/38014539455/job/114103727373)
сообщает:

| Existing module | PASS | FAIL | Первая причина |
| --- | ---: | ---: | --- |
| `tests/test_project_context_quality_v2_protocol.py` | 48 | 2 | `AttributeError: 'types.SimpleNamespace' object has no attribute 'service'` |
| `tests/test_release_gate.py` | 14 | 38 | Та же ошибка в общем observer setup |

Оба focused V2 traces показывают точную строку 429:
`facade = app.service` в runner blob
`3d04068a9bb4a7d2c34148db74194c3d4b4ffb53`.
Release reader публикует первую причину модуля, а не все 38 полных traces;
все 38 выбранных cases используют общий `self_host_payload_runner`.

Reader checkout — GitHub PR merge commit
`217d21017008240cf252e6b99e5c6e810a858a2a`; в log указано слияние PR head выше
с `d2ed5c4c73dc3b7d56276fc37591cba8a4ae123c`. Это не PR-head checkout.
На каждой Python lane 3.11/3.12/3.13: 6024 PASS / 1693 FAIL / 0 ERROR / 10 SKIP,
`integrity_issues=[]`; console omitted rows = 0.
Предпочтительный 3.13 XML SHA256:
`1ac2185fc2322e032258344ad84d86b63867da738ff3401d57e2c92dcf2513c5`.

## Действующий контракт и точное исправление

Основной observer принимает объект с фактическим `get_docs_context`, напрямую
или через `unified_context`. Дополнительные project/member return observations
не требуют присутствия внутренних facade attributes у каждого такого объекта.

В исходном V2 test, blob
`58acdb941a2e1cff282ee3310a769bffeb73eeb1`, строки 284–332,
объект `app = SimpleNamespace(get_docs_context=lambda: raw)` намеренно минимален.
Два исходных случая independently проверяют own/foreign component binding,
тождественный raw return, неизменный public payload, один retrieval и один
validation, а также удаление callback после вызова.

Release fixture, blob `3b57d3033d46bdb21d74e6407e0d2aab250158a3`,
строки 17–129, имеет тот же минимальный app. Она дополнительно требует restoration
методов и ставит явный trap против повторного facade query.
Parametrized roster 480–508 содержит исходные 38 проверок, включая source identity,
changed snapshot, abstention, source keys, payload shape, coverage и full-output cost.

Изменены только четыре bounded места runner:

1. Импорт stdlib `nullcontext`.
2. Получение optional diagnostic facade/member targets через `getattr(..., None)`.
3. Локальная wrapper factory: захватывает уже полученный bound method, вызывает
   его ровно один раз, записывает наблюдение после return и возвращает тот же объект.
4. Установка downstream patches только для существующих callable methods.
   При отсутствии capability применяется `nullcontext`, без создания fake method,
   stage record, source, result или дополнительного запроса.

Обязательные unified capture, selection, validation и component coverage observers,
единственный public dispatch, observer counts, exact snapshot binding и снятие
patches/callback в исходном try/finally сохраняются. Полноценный service продолжает
наблюдаться на всех реально достигнутых стадиях. Исключения настоящего read не
заменяются diagnostic result. Serializer bodies и ограничения console transport
не меняются.

## Граница изменений и проверка

| Путь | Mode | Base blob | Proposed blob |
| --- | --- | --- | --- |
| `scripts/run_project_docs_self_host_gate.py` | `100644` | `3d04068a9bb4a7d2c34148db74194c3d4b4ffb53` | `5e57ccfe5a403cb1d6aa282e0258baa4d34723a2` |

Этот note — второй путь, новый `v2plan/pr211-execution/OPTIONAL_DELIVERY_OBSERVER_CAPABILITIES_RU.md`,
mode `100644`. Production, оба test modules, fixtures, gold, thresholds, CI reader
и critical mutation runner не изменены. Новых ordinary test functions нет.

Runner 987 строк; roundtrip точный. Inverse четырёх изменений восстанавливает
исходный runner побайтно:

- Base SHA256: `5dbb59a06aa301af9be85c6fa0c1137147f4259cef6df1f3944522faabc83988`.
- Proposed SHA256: `de95e4d399cff7d8f69ce7ae0bc791569ca741c5e34cda8784b9122c5dd5f037`.

Локальные runtime/import/AST execution, pytest и установка dependencies не выполнялись.
Static peer/root review и следующий реальный совместный CI обязательны до заявления
об устранении 40 failures. Проверяются восстановление исходных 2 + 38 controls и
сохранение двух existing real-service delivery-veto cases с полным service.

Отдельное наблюдение из того же actual reader: Legacy acceptance module уже 5 PASS
на каждой Python lane, включая
`test_legacy_compatibility_floor_keeps_original_threshold_and_hard_safety`.
Это подтверждает здоровый compact oracle control; успешность live Legacy quality
report или floor 12/15 из этого не следует.
