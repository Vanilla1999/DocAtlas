# Terminal transport integrity — TRANSPORT_VALIDATED

Ветка: next07-feasibility-audit. База: 3f82cae4c31de69e4c4df920a1d211e2f37bb6e2.
Code fix: 4b37ba3a6fc1b5314f25f7ea26a55e5ea3341581.
Авторский review до исполнения: 2d5ad6f77a8c26b3c636c57a42999f2f96278eff.
Исполненная revision: 5f878b206b18ca8e5bc97624744fe78e00124680.
Никакой внешний независимый аудит не заявляется.

## Что исправлено и что не менялось

compact_mcp_payload теперь считает docs_context/docs_answer/patch_context
неделимыми projections. Сохраняет ВСЕ поля исходного DTO либо выдаёт новый
transport_size_limit без прежних sources/hash/proof/edit claims. Это один
consumer для call_docs_tool_payload и последующего _mcp_tool_result.
После валидации нельзя отдельно сокращать даже metadata: estimates и snapshot
связаны со всем согласованным пакетом. Generic administrative compaction сохранён.

max_transport_bytes — внутреннее поле caller-owned ReadDeliveryLimits.
Custom/default policy сохраняет32000 bytes; COMPACT_READ_LIMITS явно задаёт None.
Явный положительный integer max_bytes приоритетнее unlimited policy. Поля источника
и payload не выбирают policy. При утрате caller context повторная упаковка
явно отказывает большому пакету, а не портит цитаты. Проверено и для обоих SDK
представлений, и для asyncio.to_thread. Реальная live stdio/network session
этими SDK roundtrip tests не заявляется.

Runtime diff: только read_delivery_limits.py и output_contract.py.
В прежнем test_next07_compact_delivery.py изменён shape internal dataclass и
проверка её нового поля —2 строки; semantic expectations прежние.
Parser/owner materialization, read_decision, first_fit, guards, retrieval/ranking,
корпус/labels, assessor/audit, scope wiring и production activation не менялись.
Пороги не повышались, новые LLM/regex relevance-фильтры/fallback не добавлялись.

## Запуски и ревью

Первый native run37235135829 / ee293888 остановлен до тестов: смешали v2plan
с tests/docs в одном pytest, product diagnostic manifest не знает research modules.
Лог: `no tests ran in 1.83s`. Это technical invalid, не algorithm failure.
Сохранён REVIEW_AMENDMENT_RU.md. Исправлен только workflow: два pytest-процесса,
manifest/conftest/expectations/code не изменены. Review hashes сохранились.

Настоящий успешный run:
https://github.com/Vanilla1999/DocAtlas/actions/runs/37235320731
Artifact ID11315507040, name next07-transport-integrity-5f878b206b18ca8e5bc97624744fe78e00124680.
SHA-256 ZIP: 9ddda9b2e2f72b3cd153af755891b84dc31e09716a9e6d587f137b85e1f7703d.

212 PASS research/native regression +13 PASS existing product output contracts.
Из новых checks: finite failure/no inherited credit, explicit cap priority,
source-policy spoofing, preserved CRLF/Unicode/tail restriction, real >32KB owner
через actual handler и SDK, serialization с text_fallback False/True.

LeaseClient native:
- P1:17 seconds +LeaseExpired, owner/expiration,608 tokens/3 sources;
- P2:29 seconds +WaitExpired, owner/expiration,618/3;
- P3:default17 seconds без выдуманной exception,442/2.
Target validator/audit чистые. Это не единственный тест отмены caps:
дополнительный native >32KB test тоже прошёл.

80/80 N/C пар выполнены и оценены. Ни у N, ни у C нет source audit errors.
После handler каждый из160 packets дополнительно прошёл настоящий mcp.types SDK
в двух формах:320 сериализаций; payload equality и повторный source audit чистые.
Frozen inputs неизменны. Локальный29-PASS subset не прибавляется к212 повторно.

## Результаты качества, отдельно от transport

| Метрика | Предыдущая owner revision | Сейчас |
|---|---:|---:|
| Fresh retained vs N |46|48|
| Нераспознанная поддержка относительно N |3|1|
| Fresh gained vs N |6|6|
| Historical49, source-valid retained |40|48|
| Historical49 definite lost |0|0|
| Historical49 UNKNOWN |9|1|
| C cases с source audit errors |17|0|

Все52 прежних recognized C IDs сохранились, добавились ruff-06 и uv-05.
Текущий C имеет54 supported IDs по existing assessor. Review queues сохранены;
это не обещание отсутствия любых ненайденных противоречий.

Проверка attribution между двумя runs: множества выбранных C source spans/text
до transport совпадают во всех80 случаях. N assessor statuses тоже совпадают.
Final C source sets равны selected sets во всех80 случаях. Это поддерживает
конкретный вывод: два восстановленных IDs и17 исправленных packets получены
без изменения поиска/read selection, за счёт устранения транспортного обрезания.

Остаток fastapi-02: вопрос «Может ли task function для BackgroundTasks быть
обычной def, а не async def?». Supporting input row background-tasks.md
[1095,1610] получает missing_visible_exact_or_subject ДО transport. Итог C
needs_review: это UNKNOWN, не доказанная потеря/ложный ответ. Guard не ослаблялся.

Фактический объём C: median3386.5 admission tokens, max15294; max56937 UTF-8 bytes,
max19 source rows. В17 cases размер больше32000 bytes. Краткость не решена
магическим сжатием: transport теперь честно сохраняет selected материалы.

## Что закрыто и что не разрешено

TRANSPORT_VALIDATED в проверенной области: подготовленный packet не меняется
после validator, finite failure корректен, обе терминальные функции охвачены.
Не переписывать transport ради N10 или оставшегося semantic/exact guard.
Существующие source constraints не ослаблены и качество не объявлено безошибочным.

N10: NOT_RUN_UNCHANGED. Обсуждение отдельно в N10_DISCUSSION_RU.md, без правки кода.
Общий candidate verdict и исторические REJECTED не переименовываются.
Full product suite, historical partial ledger, downstream-reader evaluation и
rollout здесь NOT_RUN/NOT_AUTHORIZED.48/49 — не49/49.

В raw artifact сохранены tests/legacy logs+JUnit, target captures,160 corpus
captures с final snapshots, assessor/review queues, terminal-sdk.json,
protocol/postflight hashes/pip-freeze/summary.json. Отдельный result.json рядом
с этим отчётом содержит проверенные агрегаты и фактические ID.
