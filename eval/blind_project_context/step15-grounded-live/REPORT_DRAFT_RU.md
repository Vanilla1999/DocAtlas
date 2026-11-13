# Step15: Grounded D против historical A/B/C — черновик

**Четыре реальные Terra Low сессии завершены. Semantic review ожидается.**
Этот результат заменяет первоначальный статус блокировки, но не изменяет старые
receipts. `BLOCKER_RU.md` и `status.json` описывают только первую подготовку.

## Измерение

- Установленный Grounded `@arabold/docs-mcp-server@3.2.1`, настоящий stdio MCP.
  `serverInfo.version` сообщает `0.1.0`; обе версии зафиксированы отдельно.
- Изолированный store:
  `/home/viadmin/.local/share/docatlas-eval/step15/work/attempt-02/grounded-store`.
  Ровно одна library `meridian-step15-e62fa9e3`, версия `1.0.0`, 6 страниц,
  9 chunks. Чужие библиотеки не переносились, не удалялись и не индексировались.
- Реальные scrape шести pinned raw URL на commit
  `e62fa9e357bd22731cddabe930532a4a2faecc18`: maxPages=1, maxDepth=0,
  exact include-pattern, redirects=false. Без private/oracle/report.
- **Lexical mode:** штатная конфигурация embedding model осталась
  `text-embedding-3-small`, но credentials не добавлялись и embeddings в индексе
  отсутствуют. Это не сравнение с настроенным платным vector search Grounded.
  Retrieval, chunking, query processing, limit=5 и assembly — штатные Grounded;
  нет question→document mapping, hand-crafted synonyms или mock retrieval.
- `openai/gpt-6.1-terra#low`, существующая OpenCode авторизация. Каждый реальный
  provider request подтверждает wire model `gpt-6.1-terra`, effort `low`.
  Четыре свежих Location и session ID, исходные вопросы неизменны, max12steps,
  timeout900. No warming/compaction; deterministic title; model retries=0.
- Общие concise/source-to-draft абзацы взяты дословно из A. Их наличие проверено
  в первом реальном provider request всех четырёх сессий. Добавлена только
  механика Grounded: library/version, search/fetch и общая allowlist 6 URLs.
- Модели доступны только `grounded_search_docs` и `grounded_fetch_url`.
  Execute-before guard требует exact library/version; fetch — exact raw URL и
  followRedirects=false. Нет файловых инструментов, DocAtlas или произвольного
  web fetch. Preflight results модель не видела. Skills catalog очищен тем же
  старым observer, что в A/B/C.

## Предварительные суммы за четыре задачи

| Arm | Provider requests | Input | Cached input | Uncached input | Output | Время, s |
|---|---:|---:|---:|---:|---:|---:|
| A historical | 13 | 26 342 | 12 544 | 13 798 | 1 245 | 66.15 |
| B historical host-v1 | 9 | 18 604 | 7 424 | 11 180 | 1 150 | unknown |
| C historical files | 14 | 22 896 | 9 856 | 13 040 | 1 727 | 49.83 |
| D Grounded lexical | 10 | 17 294 | 6 144 | 11 150 | 1 434 | 47.64 |

D относительно B: input меньше на 1 310 (~7.0%), но uncached input практически
одинаков (меньше всего на 30), output больше на 284. Это не вывод о денежной
стоимости и не доказательство лучшего качества. Денежная стоимость не установлена.

| D case | Requests | search_docs | Input | Uncached | Output | Seconds |
|---|---:|---:|---:|---:|---:|---:|
| V-M1 | 3 | 2 | 5 171 | 3 763 | 643 | 17.88 |
| V-M2 | 2 | 1 | 3 493 | 2 341 | 227 | 8.58 |
| V-M3 | 2 | 1 | 3 487 | 2 335 | 322 | 10.25 |
| V-M4 | 3 | 2 | 5 143 | 2 711 | 242 | 10.93 |

Всего D: 6 реальных `search_docs`; модельных `fetch_url` — 0. По одному первому
поиску V-M1 и V-M4 вернуло no-results; последующие запросы сформировала сама Terra.
В preparation отдельно выполнены 6 `fetch_url` и 1 `list_libraries`: они не входят
в model-session metrics и не подмешивались в контекст модели.

### Границы сопоставимости

A/B/C — historical результаты step14, D выполнен позже: **не одновременная
рандомизация**. Не контролировались прогрев provider cache и внешняя нагрузка.
Время включает session lifecycle, а не только retrieval latency.
В historical B1 сохранилась неизвестная хронология host language preflight;
в B4 внешний 120s timeout оборвал координатор, поэтому end-to-end seconds unknown.
Эти пробелы не восстановлены по догадке. Usage взят из provider responses;
отсутствующие поля остаются null, не заменяются tokenizer estimates.
Preparation, transport probes и orchestration-agent usage исключены из таблицы.

Tooling отличается: A/B имеют DocAtlas compact contract и source IDs/line spans;
D получает стандартные Grounded search chunks без DocAtlas compression и с
нормализованными URL. D prompt включает одинаковую для всех вопросов allowlist
имён/URL всех шести документов. Это scope metadata, но дополнительная видимость
имён источников относительно initial A/B также является различием tooling.
D не получает host-v1 language hint; источник языка из preflight не инжектируется.

## Hash/span и scope

`sources.json` + `source-bytes/`: все raw bytes равны frozen originals.
`attempt-02/index-inspection.json`: все indexed chunks, metadata, hashes и
построчные соответствия. Grounded удаляет пустые строки в indexed chunks,
поэтому chunk hash не равен source-file hash, и непрерывный исходный span нельзя
объявлять без оговорок. Каждая непустая строка каждого delivered result точно
найдена в соответствующем исходном документе.

`scope-source-model-audit.json` фиксирует каждый actual call, разрешённый
library/version/URL, доставленные source hashes и line mapping, wire model/effort,
видимые tools и citations URL. Snapshot индекса одинаков до и после каждой
сессии. URL в search нормализованы без `.md`; content_url/raw URL сохраняют `.md`.
`runtime-evidence.json` отдельно проверяет bytes, доставленные preflight fetch.
Это механическая проверка происхождения, **не semantic grade ответов**.

## Сохранённые исправления harness

1. **Attempt01:** CLI `--config` не применил storePath. Новый library попал в
   default store; старые материалы сохранены без изменений. После разрешённого
   recovery создан новый отдельный store через явные CLI/env параметры.
2. **Attempt02 prepare:** диагностический `config` уже создал installation.id.
   Проверено отсутствие DB/данных, сохранён файл; подготовка продолжена.
3. **Attempt02 первый клиент V-M1:** readiness=10s истёк до любого provider call.
   Отдельный реальный observer transport probe занял 23.9s. Новые Locations,
   readiness/startup=60s; 900s model budget не менялся. Ноль model requests в
   неудачном клиенте подтверждены capture/accounting. Исходные receipts сохранены.
4. **Live-02 V-M1:** ответ и все 3 provider usage records получены успешно,
   но legacy transport classifier распознавал только DocAtlas/files tool names
   и назвал Grounded retrieval `not_observed`. Это не model/provider error.
   V-M1 **не повторялся**; `finish02.py` продолжил только ещё не запущенные V-M2–4.
   Legacy receipts не переписаны. `grounded-transport-verification.json` для
   каждого case отдельно проверяет actual Grounded calls, полную capture,
   отсутствие ошибок/retries, финальный ответ и lifecycle cleanup.

## Файлы для родительского semantic review

- Основные результаты: `preliminary-results.json`.
- Четыре полных ответа: `attempt-02/live-02/D/V-M*/answer.md`.
- Raw OpenCode: `attempt-02/live-02/D/V-M*/runtime/raw.jsonl`.
- MCP raw: `attempt-02/live-02/D/V-M*/stdio-events.jsonl`.
- Provider bodies/usage: `attempt-02/live-02/D/V-M*/capture/events.jsonl`.
- Per-case metrics: `attempt-02/live-02/D/V-M*/accounting.json`.
- Общий scope/model/source audit: `scope-source-model-audit.json`.
- Эталоны: unchanged `../step14-host-language-live/tasks.json` и
  `../step14-host-language-live/review-criteria.json`; oracle не передавался модели.

Из isolated checkout для независимого анализа, без повторного запуска моделей:

```sh
cat eval/blind_project_context/step15-grounded-live/attempt-02/live-02/run-complete.json
cat eval/blind_project_context/step15-grounded-live/preliminary-results.json
cat eval/blind_project_context/step15-grounded-live/scope-source-model-audit.json
git status --short
```

`analyze.py` содержит воспроизводимые offline calculations; существующие выходы
создаются эксклюзивно, поэтому не перезапускать поверх receipts. Runner scripts
также не возобновлять: четыре model cases уже выполнены.

Основной checkout не менялся. Commit/push не выполнялись. Финальная semantic
оценка и вывод о качестве оставлены родительской сессии.
