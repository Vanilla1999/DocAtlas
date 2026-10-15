# Исполнение: API исправлены, интеграции и установленный SDK проверены

База304b56e1, ветка experiment/heuristic-removal-20261013. Commit/push не выполнялись.

## Изменения

- SQLiteStore.query ограничивает SDK delivery целыми окнами по limit и stored
  display-token budget. Внутренний acquire_candidates сохраняет отдельные ceilings.
  Dispatcher, его lexical fallback и hybrid lexical lane используют acquisition,
  не ранние SDK caps.
- Agent передаёт final budget formatter. Formatter сохраняет source whitespace,
  считает весь rendered string с attribution/escaping/separators, исключает целиком
  не помещающиеся окна и продолжает в исходном порядке.
- Lexical explicit/config expansion выполняется и входит в config hash.
  SDK принимает expand. Neighbor windows принадлежат тому же source/generation,
  проходят request filters и не объявляются дополнительными BM25 hits.
- Adjacent читает immediate children в source; existing page mode читает neighbors
  в parent плюс bounded code/table same-atom siblings, не весь файл/PDF page.

Файлы: client.py, agent.py, context.py, core/_sqlite_store_part03.py,
core/_sqlite_store_part04.py, retrieval/_dispatch_part01.py, retrieval/lexical.py.
Контракт: docs/sdk-delivery-budgets.md. Явное ужесточение: вместо body-only estimate
и oversized-first exception применяется rendered estimate, допустима пустая строка.
SDK body budget — stored estimates (UTF8/4), formatted budget — character/4,
НЕ provider/o200k guarantee. Внешний prompt не включён.

## Проверки

Первый запуск:6 PASS за30.88s: новый public SDK scenario, существующий public lifecycle/partial/
trace/read-only и4 prepared retrieval сценария. Артефакты api-fixes.xml,
SDK_DELIVERY_AFTER.json. Diagnostic node hash обновлён.
После defensive bound:2 PASS за0.97s (SDK и scope/version/foreign isolation).
После уточнения delivery metrics и zero/expanded formatted checks:4 PASS за1.53s
(SDK, exact library version, patch-plan, mixed provenance), final-delivery.xml.
Это10 различных интеграционных сценариев в трёх целевых запусках, не12 уникальных.
SDK_FINAL.json содержит нынешние12 public retrieval calls и1 prepare. Повторы SDK
обусловлены новыми product/harness критериями; остальные наборы не повторялись.

До: исходный SDK_BUDGET_REPRO.json и SDK_EXPANSION_BEFORE.json. После:
limit1 возвращает1 вместо3 окон, body estimate<=100, rendered estimate<=100;
wide delivery сохраняет все3 Observatory документа; dispatcher при limit1/budget100
сохраняет3 native candidates. Photograph none не доставляет соседнее вводное
условие checklist, adjacent/page доставляют. Exact source spans/hashes/scope/
generation и read-only logical DB/files проверены без mocks.

Первоначальная exploratory expansion проба выбрала факт уже внутри native window:
она НЕ доказывала expansion. Затем ДО product changes выбрано вводное условие
из неизменённого corpus; после правки критерий не менялся. Exploratory JSON и
manifest с удалёнными temporary paths удалены только ради освобождения диска.
Исходный аудит и действительный before/after сохранены.

Команда: /tmp/opencode/docatlas-heuristic-removal-runtime/bin/python -m pytest
tests/test_heuristic_removal_public_integration.py::test_public_sdk_delivery_caps_and_explicit_lexical_expansion
tests/test_heuristic_removal_public_integration.py::test_public_removal_lifecycle_partial_source_integrity_trace_and_read_only
tests/test_prepared_retrieval_integration.py -q --junitxml=<audit>/api-fixes.xml.
Использован существующий TIKTOKEN_CACHE_DIR из heuristic-removal/tokenizer-cache.

После первого PASS добавлено ограничение neighbors семью окнами: LIMIT8 мог дать8
neighbors, если anchor не оказался среди первых8 same-atom rows. Последующие
интеграции и installed SDK проверяют обычное расширение с этой правкой;
специальный table>8children edge пока НЕ исполнен.
Delivery docmancer_tokens/raw_tokens/savings/runway теперь описывают выбранные
SDK окна, не всю acquisition пачку; acquisition ledger сохраняется отдельно.
Также проверены zero caps и расширенный formatted context в budget600.

## Временный блокер и installed проверка

Wheel собран и установлен в отдельный venv. Installed SDK PASS НЕ получен:
unsafe TMPDIR до prepare; missing yaml после prepare до SDK; ошибочный Path вместо
str в harness после prepare до retrieval. Environment/harness исправлены.
Следующая попытка остановилась на OSError ENOSPC при записи fixture. Диск блокировал
даже отчёт. Для освобождения удалены только собственные новые wheel/venv и
exploratory артефакты; чужие данные и shared directory permissions не изменены.

Позже место снова стало доступно (df:5.8GiB свободно). Пересобран wheel,
восстановлен отдельный installed venv. Первые7 SDK calls прошли. Новый reusable
runner сначала ошибочно resolve-ил symlink Python до системного executable:
import docmancer failed ДО retrieval. Harness исправлен на absolute без resolve;
этот FAIL сохранён в installed-sdk-final/stderr.log, не объявлен product failure.

**Финальный installed SDK PASS:** installed-sdk-verified/RESULT.json —10 calls,
0 model calls,0.0577s retrieval, exact source/hash/span/scope/generation,
zero caps, expanded formatted budget600 и неизменность DB/files. Подготовка
source-tree public MCP, чтение — настоящий installed SDK с Python -I. Это
НЕ installed preparation/stdio, реальный клиент или production smoke.

Воспроизведение (после build/install wheel и подключения существующих dependencies):

```sh
TIKTOKEN_CACHE_DIR="$PWD/reports/docatlas-grounded-20261013/heuristic-removal/tokenizer-cache" /tmp/opencode/docatlas-heuristic-removal-runtime/bin/python -m eval.heuristic_removal.sdk_delivery --installed-python /tmp/opencode/docatlas-sdk-delivery-installed-20261013/bin/python --output <новый_каталог>
```

Runner создаёт fresh temporary fixture, public prepare, затем installed
eval/heuristic_removal/installed_sdk_delivery.py внутри fixture lifetime.
Manifest в сохранённых результатах имеет уже удалённые temporary paths — не
готовый живой index. Источник ожиданий сохранён в fixture.json.
FINAL_FREEZE.json подтверждает source/wheel/installed equality изменённых product
файлов, hashes, syntax и git diff --check PASS.
Installed stdio/CLI не повторялись; полный старый suite, real vector/backend и
answer-quality comparative НЕ запускались. Модели/сервисы/downloads не запускались.

## Потери фактов текущей копии

Ожидания из authored Observatory documents и существующего CHECKLIST_DOCUMENTS;
доказательства SDK_FINAL.json, FACT_FLOW.json (27 строк, офлайн без дополнительных
product calls) и независимые integration assertions.
SDK не имеет отдельного semantic admission/selection этапа.

| Вопрос / факт | Корпус | Acquisition | Admission | Selection | Final | Первая потеря |
| --- | --- | --- | --- | --- | --- | --- |
| Observatory: packing/issue facts |Да|Да|Не отдельный SDK этап|Wide: да|Весь packing.md|Нет|
| Observatory: upright/broken seal facts |Да|Да|Не отдельный SDK этап|Wide: да|Весь transport.md|Нет|
| Observatory: dry/locked/damaged lens facts |Да|Да|Не отдельный SDK этап|Wide: да|Весь storage.md|Нет|
| Observatory limit1: два остальных документа |Да|Да,3 candidates|Не отдельный SDK этап|Только1 window|Не все факты|Delivery count cap|
| Photograph: вводное условие, none |Да|Нет в native hit|Не отдельный SDK этап|Нет|Нет|Выбранное none, не дефект|
| Photograph: вводное условие, adjacent/page |Да|Да, expanded window|Не отдельный SDK этап|Да|Да|Устранено в сценарии|

MCP optics final facts проверены existing assertions; отдельные промежуточные
admission/selection для каждого факта UNKNOWN. Не выводить их задним числом из PASS.
Исторические V40-E02/Q loss и A gains T03/P06/T07/V06, negative losses
B08/P07/T08/V07/V08 относятся к старому code/config, не к текущей копии.
NEW20 просмотрен; тогда S/ALL comparative не завершён.

## Матрица оснований и unknown

Подробные первичные ссылки/методические sections: исходный RESULT_RU.md и
../heuristic-removal/METHOD_CONFORMANCE.md. Они не переписаны ради PASS.

| Этап / основание | Реализация / отклонение | Доказательство / unknown |
| --- | --- | --- |
| Access/scope/version/freshness: engineering contract |Receipts, identities, hashes/spans|Existing public lifecycle/scope; не все случаи|
| Extraction: сохранность фактов |Snapshot/display windows|Markdown/RST; полнота HTML/PDF/DOCX unknown|
| Chunking: Anthropic implementation considerations |Heading/path prefix,160/512 estimates, overlap0; не LLM contextualizer|Spans; оптимальность unknown|
| Prepared parents: immutable parser reuse |Generation/parser-bound, не RAPTOR|Existing parity/freshness; latency unknown|
| Query/acquisition: BEIR §4 BM25 |FTS5 вместо Lucene, OR/equal fields/fixed ceilings|Baseline; параметры не paper optima|
| Dense/sparse: BEIR retrieval families |Выбранные backend/model|Historical smoke; current relevance unknown|
| Fusion: Cormack2009 RRF |RRF/weighted, коррелированные BM25 lanes|Формула; веса/gains unknown|
| Admission: Sufficient Context §3 |Source-valid/relevance unassessed|Provenance не sufficiency|
| Selection/dedupe: SetR §3 |Native order/exact dedupe, не trained joint selector|Полнота unknown|
| Expansion: source reading contract |Explicit coordinates/native-first|Checklist contrast; table/filter edges unknown|
| Packing: resource contract |Whole windows/rendered attribution|SDK cap; provider/full prompt unknown|
| Sufficiency/answer: Sufficient Context, Lost in the Middle §2–3 |False authority; нет generator experiment|Answer quality unknown|

Не требовать paper для каждого engineering cap; не выдавать локальные параметры
за научный optimum или baseline за точное воспроизведение Anthropic/SetR/RAPTOR.

## Минимальные следующие проверки и сравнительный план

1. Installed SDK gate закрыт. При отдельной проверке protocol delivery повторить
   stdio prepare/context/version/resource и CLI; прежний PASS не переносить.
2. Один публичный corpus: table/code page bounds, cross-parent adjacent,
   metadata/source/generation restrictions. Проверить последнюю defensive правку.
3. Zero/expanded format уже проверены. Расширить SDK integration XML/plain/oversized
   cases с independent estimates и проверкой source equality.
4. Для unknown MCP stages: отключаемая trace без изменения output/rights/sources/
   числа calls; отсутствие log entry не доказательство потери факта.
5. По одному original document каждого extractor формата с independent facts.
6. Отдельный quality comparison: freeze code/config/parser/tokenizer/corpus/oracle,
   6 открытых calibration questions, lexical/hybrid12 calls, <=2 prepares,
   wall ceiling180s, одинаковый final packet budget с overhead. Stop при
   source/version/state violation/ресурсном потолке. Hybrid требует отдельного
   разрешения model/backend runtime. Не запускался.
7. Затем отдельно chunking/selector comparison, новый непросмотренный holdout
   и одинаковый answering model/prompt. Provider usage отдельно от estimates.

Итог: API fixes,10 различных source-tree integration PASS и installed SDK10 calls
PASS. Улучшение retrieval/answer quality и correctness всей цепочки НЕ доказаны.
