# Ревью восстановления native-контекста после позднего отказа

Дата: 2026-10-12. Проверяющий: агент `eval40_corpus`. Функциональное изменение
написал координатор `root`; проверяющий ранее участвовал в добавлении
диагностики. Независимая от автора проверка здесь относится к функциональному
replacement и его consumers, а не ко всему logging diff.

## Вердикт и статус

**Блокирующих дефектов в просмотренном функциональном diff не обнаружено.**
Этот статический вывод был передан координатору до запуска `attempt-02`.
После этого координатор выполнил прежний ограниченный интеграционный сценарий:
**`attempt-02-native-restore` — 1 PASS**, исходный полный witness доставлен
при trace off и trace on. Результаты исполнения приведены отдельно ниже.
Проверяющий самостоятельно прочитал сохранённые JSON, трассы, stdout и JUnit;
новых product/model/index/test runs для этого отчёта не выполнял.

Доказано исправление одного воспроизводимого сбоя доставки уже найденного
исходного текста. Не доказаны общая релевантность выдачи, исправление
отрицательных вопросов, превосходство над Grounded или новое качество на 40
вопросах. Это известная регрессия V40-V04, а не новый holdout.

Основания: [протокол](PROTOCOL_RU.md),
[execution attempt-02](attempt-02-native-restore/execution.json),
[JUnit](attempt-02-native-restore/junit.xml),
[stdout](attempt-02-native-restore/pytest.stdout.log).

## 1. Что именно сломалось в baseline

Прочитаны полная трасса `attempt-01-logging-baseline` и независимая проверка
исходных символов в конечных snippets. В трассе 24 события, без усечения,
ошибок наблюдения или потерянных строк. Координаты ниже — позиции символов
в исходном тексте с исключённой правой границей; это не номера UTF-8 байтов.

| Граница | Наблюдение |
|---|---|
| `core.output` | Полный нужный текст `[3278,3428)` присутствует. Reference envelope `[3278,3430)` включает дополнительные внешние пробелы. |
| `joint.output` | Тот же фрагмент сохранён в видимом диапазоне `[3278,3430)`. |
| `query_block.output` | Под прежним evidence ID появляется расширенный диапазон `[3096,3430)`, пересекающий границу разделов. Исходные обязательные символы ещё присутствуют. |
| `recheck.attempt`, original seed 0 | Проверка исходного seed доходит до `structural_derivation`; причина отказа — `unverified_structural_derivation`. |
| `recheck.output` | Расширенная строка удаляется целиком. Здесь впервые отсутствуют все 150 обязательных исходных символов. |
| `budget.input` → `budget.output` | Состав уже одинаков. Budget trials не выполнялись, поэтому бюджет не является причиной этого удаления. |

Начальные отказы `missing_current_native_discovery` относятся к новому
расширенному диапазону. Их нельзя описывать как потерю current receipt
первоначального найденного seed: попытка с этим seed проходит дальше и
останавливается именно на проверке структурного преобразования.

Одновременно WebSocket parent `[8660,10810)` проходит существующую проверку
происхождения через свой native seed. Это дополнительный фрагмент,
**допустимый по происхождению, но не отвечающий на данный вопрос о поведении
`server.strictPort` при занятом порте**. Его смысловая полезность не доказана.
Упоминание `strictPort` внутри WebSocket-инструкций не заменяет исходное
правило строк 70–74; oracle его и не засчитывает. Новая recovery-строка
`[462,1318)` проверки не проходит.

Статическое чтение подтверждает несовпадение контрактов producer и guard:
`query_block_bridge.bridge_options` может собрать исходный диапазон через
границу разделов, тогда как `_checked_context_derivation` для такого
`containing_span` требует допустимую структурную связь. Источник текста
подлинный, но предложенное расширение не проходит поздний контракт.

Основания:
[baseline trace](attempt-01-logging-baseline/artifacts/V40-V04-budget/trace-on/trace.jsonl),
[baseline witness coverage](attempt-01-logging-baseline/artifacts/V40-V04-budget/witness-coverage.json),
[query_block_bridge.py](../../../../docmancer/docs/application/query_block_bridge.py),
[literal_context_admission.py](../../../../docmancer/docs/domain/literal_context_admission.py).

## 2. Что проверено в функциональном изменении

Состояние с одним логированием восстановлено в памяти из `HEAD` и
[logging-only.patch](logging-only.patch), затем сопоставлено с рабочими файлами.
Статическая проверка не исполняла production helpers. SHA-256 logging patch:

`9cfbe551dd53adb5c25189114ee7749e5ae09baa0af50bb3fb8b6d3f7269080c`.

Функциональная дельта находится в
[`experimental_context_finalization.py`](../../../../docmancer/docs/application/experimental_context_finalization.py):
добавлен `_restore_checked_native_context`, сохранены receipts принятых
поздних строк, восстановление подключено после отказов, а бюджетные trials
явно вызывают `recheck_experimental_context(..., restore_native=False)`.
В [`projection_decision_trace.py`](../../../../docmancer/docs/application/projection_decision_trace.py)
добавлена публикация счётчиков `experimental_native_restore` через существующий
whitelist. Остальные изученные consumers: `_snapshot_entry`, `_rebuild`,
`validate_model_visible_projection`, финальный MCP budget и continuation binding.

| Проверяемое свойство | Статический вывод |
|---|---|
| Сохранённый native не является разрешением | Каждый сохранённый core candidate заново проходит `recheck_source_valid_candidate` с исходным вопросом, ожидаемым project identity и lifecycle. |
| Отказ расширения не превращается в допуск | Для восстановления пробуются собственные `native` и `contained_span`. Отвергнутая derived-строка не используется как доказательство. Структурные guards не ослаблены. |
| Сохраняются текущие проверки источника | Вызван тот же путь current discovery, canonical source/member, request constraints и точного raw visible window. Старый receipt не копируется как действующее разрешение. |
| Принятые поздние строки не перезаписываются | Сначала сохранены все `kept` rows. Native alternatives только дополняют их после свежей проверки. Это сохраняет прошедшие source/lineage check фрагменты, не объявляя их семантически полезными. |
| Дедуп опирается на проверенный текст | Сравниваются полное равенство `reference.source` и интервалы из `receipt.body_window`, а не одинаковые слова, evidence ID или reference envelope. |
| Коллизия evidence ID не меняет binding принятой строки | Если ID уже занят другим оставленным диапазоном, fallback получает детерминированный ID, связанный с identity и диапазоном, затем свежий `_snapshot_entry(candidate, row)`. |
| Attribution и assignment proof не переносятся вслепую | `_rebuild` повторно проверяет видимый текст, ограничивает attribution прежним публичным credit ceiling и очищает assignments. |
| Старые continuations не приклеиваются к новой строке | У восстановленной строки удаляется `source_uri`; `_rebuild` очищает `read_next` и сохраняет bindings только итоговых строк. Последующая выдача continuation остаётся отдельной действующей процедурой. |
| Внутри budget trial не возникает обратного восстановления | `restore_native=False` предотвращает ситуацию, когда trial сохраняет число строк, но заменяет их, а budgetcaller продолжает использовать первоначальный option. Терминальный cap сохранён. |
| Диагностика не управляет восстановлением | Вычисление результата не зависит от trace switch. Product exception наблюдается с `error_type` и затем выбрасывается дальше; ошибки безопасного diagnostic collector обрабатываются прежним fail-open механизмом. |

Новый путь работает только внутри уже существующего экспериментального
`source_valid` режима. Новый env switch не добавлен, обычный default не
переключён. В replacement нет case ID, названия Vite, слов `strictPort`,
координат oracle, числовых условий из вопросов, модели или нового retrieval.

## 3. Отдельный результат исполнения attempt-02

Координатор запустил прежний тест
`test_selected_native_context_survives_public_delivery_with_trace_parity`.
Сохранённый [execution.json](attempt-02-native-restore/execution.json)
фиксирует exit 0, отсутствие automatic retries и неизменность runtime inputs
в ходе попытки. JUnit содержит один тест без failures/errors/skips.

Это один публичный in-process MCP сценарий с настоящими компонентами
подготовки, retrieval, selection, validation и storage: 1 prepare,
2 `get_docs_context` (trace off/on), 0 source continuation calls,
0 answer generator calls и 0 model forwards. Модельные модули `torch`,
`transformers`, `safetensors` отсутствовали и до, и после сценария.
Уровень проверки не объявляется installed stdio, внешним MCP-клиентом или
production smoke.

### Конечный результат и сохранение защит

| Показатель | Logging baseline | Native restore |
|---|---:|---:|
| Исходный полный witness `[3278,3428)` | Отсутствует в обоих ответах | Полностью присутствует в обоих ответах |
| Недостающие обязательные символы | 150 | 0 |
| Итоговые source rows | 1 | 2 |
| Полный сериализованный JSON, UTF-8 bytes | 3374 | 3980 |
| UTF-8/4 proxy | 844 | 995 |
| Named codec `o200k_base` | 916 | 1125 |
| Применяемый полный budget cost | 916 / 12000 | 1125 / 12000 |
| Budget trial attempts | 0 | 0 |
| События trace on / пропуски | 24 / 0 | 28 / 0 |
| Изменения таблиц SQLite и файлов проекта после запросов | Нет | Нет |

В `attempt-02` полные wire hashes trace off/on совпадают:
`9dcc7f432b975aea4d9404d4ac7df79acbfa455dc826259e9fc724ef76e422e5`.
Стабильный публичный DTO, pool/universe/selection receipts, допустимость
исходных snippets, их координаты, scope/version/project identity и
неизменность состояния прошли предусмотренные тестом проверки. Независимый
пересчёт проекционного `content_sha256` этим сценарием не заявляется:
проверены его форма и паритет, а raw hashes исходных документов проверяются
отдельно от проекционного fingerprint.

Новая трасса показывает две свежие native-проверки: `checked=2`, `restored=1`,
`already_covered=1`, `rejected=0`. Исходный фрагмент `strictPort` принят как
`native`, возвращён под исходным ID `ev-c66b14aafe987977` и доходит до финального
пакета. WebSocket native не добавляется второй раз: его проверенный диапазон
уже содержится в прошедшем source/lineage check parent. Отвергнутые derived
и recovery ranges не были объявлены допустимыми через fallback.

Итоговый пакет продолжает явно иметь `answer_supported=false`,
`answer_available=false`, `edit_ready=false`, `answer_policy=cite_only`,
`facet_coverage=unverified`. Его `query_coverage=full` относится к retrieval
attribution; это не независимая оценка смысловой полноты ответа модели.

Основания:
[operations](attempt-02-native-restore/artifacts/V40-V04-budget/operations.json),
[witness coverage](attempt-02-native-restore/artifacts/V40-V04-budget/witness-coverage.json),
[trace-off metadata](attempt-02-native-restore/artifacts/V40-V04-budget/trace-off/metadata.json),
[trace-on metadata](attempt-02-native-restore/artifacts/V40-V04-budget/trace-on/metadata.json),
[полный публичный DTO](attempt-02-native-restore/artifacts/V40-V04-budget/trace-on/public-payload.json),
[trace](attempt-02-native-restore/artifacts/V40-V04-budget/trace-on/trace.jsonl).

## 4. Почему это не изменение oracle ради PASS

В обеих попытках совпадают SHA-256 теста, frozen manifest и сохранённого
`inputs.json`. Источники, исходный вопрос и полный witness не заменены после
получения baseline FAIL.

| Файл, одинаковый в обеих попытках | SHA-256 |
|---|---|
| `tests/test_native_context_preservation_integration.py` | `b01db2f7b3851a6899a3a190c77b21a4cd265a5980b4f403f8e4db8ee02928ea` |
| `FROZEN_INPUTS.json` | `c4b367fd4889ffe069e190ed00527fab3d5ed82e7ffafb8a887abfc915f0d971` |
| `artifacts/V40-V04-budget/inputs.json` | `2f78f2e13baa4a6e44f4459af9619bd518ea195dfa0c598dd145c0f7771bd9cb` |

Просмотренные finalization и trace файлы совпадают по SHA с
[runtime-inputs attempt-02](attempt-02-native-restore/runtime-inputs.json):
`29764a693cdeed8a81cf26800bc38b2f2c94b005418a25339b87668fc4742bc5` и
`4f0c671355ee28cd3c149b3f30d274627f6a77ebd54a326703027e32a45d60f6`
соответственно.

Исправление выбрано после наблюдения конкретного FAIL, поэтому этот пример
является регрессионным. Общность обеспечивается правилом сохранения и свежей
проверки исходных вариантов, а не независимостью этого примера от разработки.
Одного PASS недостаточно, чтобы объявить устранёнными остальные потери V40.

## 5. Остаточные ограничения

- **Смысловой шум остался.** В конечном ответе вместе со 150 символами нужного
  правила присутствуют 2150 символов раздела WebSocket. Этот дополнительный
  фрагмент прошёл проверку происхождения, но не отвечает на текущий вопрос
  о занятом порте. Его сохранение не является доказанным улучшением
  релевантности. Полный пакет стал больше; экономия context budget не заявляется.
- **Producer и guard всё ещё расходятся.** Producer продолжает предлагать
  расширение через границу разделов, которое поздний guard отвергает.
  Восстановление делает этот отказ безопасным для уже проверенного native
  контекста, но не устраняет лишнюю сборку и повторную проверку. Объединённый
  структурный контракт остаётся отдельной задачей.
- **Область исправления ограничена late rejection.** Восстанавливаются только
  сохранённые core alternatives после фактического отказа поздней строки.
  Потери до core, отсутствие найденного кандидата или удаление без такого
  отказа этим механизмом не доказаны исправленными.
- **Дедуп не решает компактность всего набора.** Сейчас достаточно покрытия
  native одной принятой строкой. Если его покрывает только объединение
  нескольких строк, возможна дополнительная копия текста; полный terminal cap
  остаётся последним ограничением размера.
- **Не все ветви были исполнены этим тестом.** В `attempt-02` не понадобились
  новый ID при коллизии, fallback `contained_span` и budget trial. Эти ветви
  получили статический review; отдельное runtime-доказательство их поведения
  данным PASS не получено. Изменение доступа между проверками и исключение
  diagnostic sink также этим неизменным сценарием не моделировались.
- **Измерения задержки не являются benchmark.** Одна пара trace off/on и
  отсутствие model forwards не доказывают ускорение. Время запросов включает
  разный прогрев; новые native checks и trace-on overhead требуют отдельного
  учёта, если принимается решение о производительности.
- **Нет нового доказательства semantic sufficiency и отрицательного
  контракта.** Никакой answer generator не вызывался. Source-valid extra
  fragments и нарушения empty-source на прежних отрицательных сценариях
  нельзя считать исправленными по этому положительному примеру. Прежние
  критерии и результаты V40 не переименованы.

Проверяющий изменил только этот отчёт. Исходники продукта, вопросы, corpus,
oracle, frozen test и сохранённые runtime-артефакты при его подготовке не
менялись; дополнительных запусков не было.
