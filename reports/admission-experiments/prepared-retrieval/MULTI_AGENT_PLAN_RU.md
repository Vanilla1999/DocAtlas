# План нескольких агентов: подготовленный retrieval вместо цепочки admission-эвристик

Дата: 2026-10-12. База: `80fa1078842cfdddb4b7ecfd9d6faa681744fc39`.
Статус: **план**, не запуск реализации/моделей/CI. Предыдущий V3 runtime budget
закрыт; новые исполнения требуют нового зафиксированного workload согласно checkpoint.
[Анализ и исследования](ANALYSIS_RU.md) · [root-cause](../FILTER_ROOT_CAUSE_AND_GROUNDED_RU.md).

## 1. Цель и первая поставка

Цель: доставлять нужные исходные факты без whole-question lexical/numeric
эвристик и отвечать быстро за счёт предвычисления структуры/поисковых данных.

Первая поставка состоит из двух независимо оцениваемых изменений:

1. **Admission experiment:** ограниченный source-valid контекст до прежнего
   lexical/numeric veto, с правильным прохождением всех downstream consumers.
2. **Prepared structure:** те же структурные данные и итоговые исходные spans,
   но parsing/статистики переиспользуются из versioned index вместо повторения
   на каждом запросе. Это отдельное доказательство скорости, не quality gain.

Оба изменения host-opt-in. Первый target — настоящий public project MCP путь,
SQLite+lexical. Existing FTS OR union/context prefix/parser переиспользовать.
Новая модель, project embeddings, generated summaries, semantic decomposition,
новый API и смена default не входят автоматически в эту поставку.

## 2. Решения до patch

Координатор фиксирует `CONTRACT_DECISION_RU.md` в новой execution-папке:

### D1. Три независимые оси

- `source_admissible`: текущие membership/scope/version/hash/span/owner/lifecycle,
  актуальные access/consent и same-call discovery binding.
- `request_constraints`: явный locator, hard-exact/identity, действующие
  unresolved-name ограничения. Их не снимать вместе с numeric relevance veto.
- `contribution`: полезность исходного фрагмента/набора для исходного вопроса.
  Search score и текст с цифрой не доказывают эту ось.

Названия концептуальные, не требование ввести именно такие DTO. Переиспользовать
канонические проверки, а не копировать их в более слабый validator. Удаление
одного lexical условия не должно пропускать source-policy отказ другого типа.

### D2. Рекомендуемый режим первого опыта

**Исследовательская opt-in доставка relevance-unassessed candidates**, без
переопределения default-контракта. Старый `CURRENT_CONTRACT` empty-source oracle
сохраняется, все nonempty negatives оцениваются как FAIL. Это диагностическое
измерение, а не заявление о готовности заменить фильтр в продукте.

Для default по-прежнему требуется соблюдение действующего negative-контракта.
Если понадобится публичный отдельный candidate channel или другая семантика
`sources`, это отдельное контрактное/API изменение. Отказ генератора не делает
неподходящий source packet допустимым.

### D3. Разрешённая поверхность

В первом опыте меняются только правила eligibility доставки по whole-question
overlap/numeric veto. Вопрос не переписывается. Нет имён benchmark/case IDs,
словарей единиц/тем, исключений по конкретным numbers/labels или oracle в runtime.
Существующие source/request constraints, source snapshots и false answer/edit
flags сохраняются. Не выдавать `qualified=True` ради прохождения consumers.

### D4. Ограничения работы

Зафиксировать K acquisition/seed/neighbor limits, точный размер final packet и
полного host prompt, один и тот же generator/presentation, число обращений.
Параметры выбрать только на calibration, затем freeze. Они операционные, не
правила под содержание вопроса. Исторический `k=2` Mini не переносить автоматически.

Текущий product context budget по умолчанию не ограничен; не вводить незаметно
новый глобальный cap. Общая экспериментальная упаковка должна быть одинаковой
для arms; если она меняет baseline, явно назвать baseline соответствующим образом.

## 3. Роли, ownership и интерфейсы

Ниже шесть агентов плюс координатор. При меньшем числе слотов роли выполняются
последовательно; независимый reviewer не становится автором implementation/oracle.
Фактический список файлов фиксируется до edits. Shared-файл имеет одного владельца.

| Роль | Зона работы | Передаваемый результат |
| --- | --- | --- |
| **A — контракт и admission** | `evidence_qualification.py`, `query_reference_binding.py`, `literal_context_admission.py`, `original_body_discovery.py`, `ordinary_body_context.py`; tagging boundary по согласованию | Source/request/contribution разделение; один recheckable contract, без forged metadata grants |
| **B — подготовка структуры** | `structured_chunking.py`, generation schema/write/validation в `_sqlite_store_part01/02.py`, новый generation-bound reader; существующий `contextual_indexing.py` только при необходимости | Persisted atoms/ancestry/order/dependencies/counts с hash/config revision; migration/invalidation и одинаковая структура |
| **C — query integration и сборка** | `_project_docs_service_part03.py`, `experimental_candidate_selection.py`, `project_doc_ranking.py`, `_docs_context_projection_core.py`, `docs_context_projection.py`, `joint_context_*`, `query_block_context.py`, `source_dependency_preparation.py` | Source-valid pool переживает retention/ranking/projection; bounded raw assembly; позже prepared-reader consumer |
| **D — нейронные представления/стоимость** | Сначала только research/config/cost manifest; позже отдельный opt-in context/embedding arm в согласованной зоне | Что уже доступно, hardware/model revisions, стоимость build/update/query; один обоснованный кандидат вместо model matrix |
| **E — независимые данные и оценка** | Новые fixtures/oracle/freeze и адаптация существующего публичного integration runner | Calibration + закрытый holdout, допустимые альтернативные доказательства, per-case verdicts и costs |
| **F — независимый review** | Read-only code/contracts/raw artifacts, собственный review report | Проверка границ, примеров потерь, конечных bytes/фактов и выводов; может блокировать promotion |
| **Координатор** | Ownership map, общий manifest/checkpoint, последовательность, единственный execution owner | Согласованные интерфейсы, сборка branch, учёт всех запусков, итог/решение |

### Обязательные интерфейсы

**A → C:** admission recheck связывает current question/discovery, source identity,
generation, raw span/hash, режим и сохранённые request constraints. Его сериализация
не создаёт право повторной доставки. Failed lexical qualification остаётся failed.

**B → C:** reader отдаёт source-bound структурные данные; read не пишет/не запускает
индексацию. Отсутствующий/устаревший derived artifact даёт явный miss/fallback
по контракту, не silent rebuild. Предусмотреть reprepare/rebuild при смене схемы.

**B → D:** generated context/vector связан с документом, моделью/шаблоном/окном;
отдельно от raw citation content. D не сохраняет admission decisions.

**E → все:** только calibration и публичные требования до freeze. Holdout/oracle
не поступают implementers или model prompts. E оценивает packet sufficiency
отдельно от actual generated answer; нет ответа — нет answer PASS.

## 4. Волны выполнения

### Волна 0 — параллельные read-only задания

- A: полный veto map и D1–D3; проверить `_source_valid_body_blocks`, который
  помимо source проверяет query names. Не выдавать rename за разделение.
- B: использовать текущую source generation и chunker; описать schema/reader
  без нового retrieval engine. Установить, что реально persisted, что query-time.
- C: отметить все consumers и late expansion; предложить один общий assembly
  contract. Source-valid кандидату недостаточно пережить один selector hook.
- D: оформить исследования и стоимость; не скачивать/запускать модели.
- E: подготовить независимые inputs/oracle и workload.
- F: проверить контракт, бюджет и отсутствие подгонки до implementation.

**Выход:** frozen interfaces, ownership, scope, критерии сравнения. Пока D2 и
семантика request constraints не согласованы, источник не публикуется через
новую broad lane. Это реальный контрактный вопрос, не изменение тестов ради PASS.

### Волна 1 — admission без изменения retrieval representations

A и C реализуют согласованный host-only experiment. Acquisition сохраняет
исходные вопрос, индекс, порядок, scope и настройки. Изменяется membership
source-valid delivery pool; Mini/semantic model отсутствуют.

Проверить цепочку:

```text
native retrieval → reference preparation → source/request check
→ source-valid pool → selection/retention → rerank → projection
→ structural finalizers → final validation → public packet
```

В каждой точке записывать bounded IDs/spans и причину потери при включённой
трассе. Трасса off не меняет вызовы/выбор/права. Нельзя исправить только раннюю
сортировку и оставить прежнее позднее veto.

Параллельно B готовит структуру и reader в отдельной зоне; prepared optimization
пока не включается в причинный admission A/B. D продолжает cost design.
F проводит static review; runtime только после заморозки execution operands.

### Волна 2 — один admission experiment

**A-arm:** V3 admission + общий frozen experimental assembly/budget.
**B-arm:** source-valid delivery без whole-question ratio/numeric veto + тот же
assembly/budget. Это не «неизменённый production V3», если общий packing изменён.

Цель — понять, что даёт сохранение найденной информации. Равны native acquisition
universe и bytes вопроса, но admitted pools закономерно различаются. Если universe
отличается неожиданно, фиксировать causal mismatch и не объяснять gain admission.
Более широкий pool не считается quality PASS до анализа финальной выдачи.

Модельные semantic/Mini arms не добавлять после просмотра неудобных результатов.
Если B только увеличивает шум или не восстанавливает данные — разобрать один
конкретный loss path; не начинать новую матрицу heuristic/model вариантов.

### Волна 3 — подготовка структуры и скорость при неизменной выдаче

Только после зафиксированного решения по delivery policy C подключает B-reader.
Сравнить on-demand и prepared structure на **одном алгоритме**. Source path/raw
spans/order должны совпадать; generation-specific envelope identity проверяется
отдельно. Замена parser semantics или expansion одновременно отменяет чистую
атрибуцию ускорения precomputation.

Предвычислять structural spans/heading ancestry/table-list dependencies,
query-independent term counts и token estimates. Query-term scoring остаётся online.
Не предвычислять все комбинации final packets. Удалять повторные draft passes
лишь с отдельным объяснением эквивалентности/изменения поведения.

Публичные проверки: prepare → query → подтверждённое изменение источника → sync
→ query → restart → query; отсутствие stale sources/edges и forbidden read/write.
Не создавать отдельную unit/helper-матрицу. Использовать существующие integration
семьи; проверять конечный результат и реальное состояние SQLite/source.

### Волна 4 — только доказанный оставшийся retrieval/selection gap

- Если нужного raw текста нет **в acquisition pool**: отдельно contextual indexing
  или Late Chunking против уже имеющегося deterministic prefix.
- Если pool достаточен, но не помещается в бюджет: Budget vs Mini на том же pool,
  либо отдельная set-selection гипотеза. Калибровать заново, scores не cutoff истины.
- Если strict negatives не решены: отдельный contribution/abstention experiment
  против B, с полной ценой query-dependent scorer. Не объявлять broad control
  готовым production-фильтром.
- Project dense требует самостоятельной интеграции с explicit member transaction,
  generation/vector parity и актуальными условиями подготовки. Не включать обходом
  lexical-only guard; SDK/library успех не доказывает project MCP.
- Generated summaries, RAPTOR, ColBERTv2 и extra host decomposition не объединять
  в один следующий вариант. Выбирается максимум одна гипотеза на основании потери.

## 5. Набор и бюджет первого опыта

**Предложение**, числа не означают разрешённый запуск. E/координатор до runtime
фиксируют реальные commands, окружение, CPU/RAM/VRAM, полный ledger и prepare calls.

Known diagnostics: CAL02, H02, HOLD05/refunds, HOLD06/cargo. Они уже раскрыты,
не calibration и не holdout. Два дополнительных counterfactual fixtures H02:
заменить номер стеллажа и убрать только номер. Не менять originals, правила
маршрутов, полномочия, вопрос и ожидаемый основной ответ. Каждый corpus имеет
свой hash/generation. При изменении acquisition не приписывать всё admission.

Новая calibration: 4 случая (2 multifacet positives, 2 negatives).
Новый holdout: 6 случаев (3 positives, 3 negatives), минимум 2 новых семейства,
не совпадающих с calibration и не переименования прежних печей/паромов/маршрутов.
Старый закрытый holdout20 не открывать автоматически.

| Группа | Public contexts | Host attempts |
| --- | ---: | ---: |
| Calibration 4 + holdout 6, A/B | 20 | 20 |
| Diagnostics 4 + counterfactual 2, A/B | 12 | 12 |
| Legacy negatives 6, A/B | 12 | 0 |
| DefaultOff на тех же 6 negatives | 6 | 0 |
| **Всего первого опыта** | **50** | **32** |

Legacy six: owner, priority7, priority7–9, compound, Setext, unrelated. Source-only
контроли не являются проверкой host refusal. Prepare/sync, ошибки и любые docs
lookups учитывать отдельно; на этой стадии нет повторов ради улучшения scores.
Budget freeze между calibration и holdout; если calibration показывает source
defect — остановка до holdout, не расходовать остаток автоматически.

Эти шесть controls — ограниченный pilot, **не полная default parity** и не новый
замер всех девяти negatives V3. Перед promotion shared consumer изменений E
включает в отдельный согласованный integration workload все девять прежних
negative cases и существующие default-positive сценарии. Точные IDs и сохранённые
ожидания фиксируются до patch; не объявлять исторические 6/9 новым результатом.
Preparations, wave 3 update/restart и performance workload не входят в 50/32.
Для каждого отдельно фиксируются wall-time ceiling, memory, calls, условия
остановки/ошибок; transport failure — BLOCKED/UNKNOWN, без автоматического retry.

Для нового oracle фиксировать обязательные факты/отношения/условия и допустимые
альтернативные достаточные доказательства. Не требовать конкретного файла, если
другое исходное общее правило действительно отвечает. Старые exact-witness
метрики сохранять отдельным столбцом; новая разметка не исправляет прошлый FAIL.

## 6. Критерии решения и метрики

До outputs E/F формулируют минимальный meaningful gain на новых данных. Для
малого пилота рабочий критерий продолжения: хотя бы один новый полный positive
ответ и packet sufficiency на новом holdout без потери ранее полных positives;
counterfactual H02 сохраняет нужные факты. Это screening, не статистическое
доказательство универсального превосходства. Если gain есть только в известных
diagnostics — это локальное исправление, не обобщение.

Обязательные отдельные метрики:

1. Required facts в acquisition, admitted pool, final packet — локализация потерь.
2. Final packet sufficiency и actual semantic answer completeness.
3. Role/relation/condition/negation correctness, unsupported affirmative claims.
4. Exact citation bytes + semantic support; raw-document и envelope hashes различать.
5. `CURRENT_CONTRACT` empty-source; отдельно host refusal и объём distractors.
6. Scope/version/catalog/freshness/native binding/authority/state invariants.
7. Полный final DTO и submitted prompt, output, число calls/candidates/drafts.
8. Prepare/update/restart/cold/warm/query stage timings, memory и disk size.

Source-policy/authority defect останавливает ветвь. Любой новый negative false
positive — регрессия, даже если полезность positives выросла. Неизменные старые
6/9 FAIL тоже блокируют default. Честный отказ хоста, transport success и высокий
retrieval score не компенсируют нарушение source-packet контракта.

**Promotion решения:**

- B даёт пользу, negatives проходят и цена приемлема → продолжить проверку простого
  пути; модель не добавлять без нового bottleneck.
- B восстанавливает positives, но negatives FAIL → полезный recall diagnostic;
  требуется отдельное решение relevance/контракта, default OFF.
- Выдача не улучшается или только растёт → остановить эту гипотезу; записать причины.
- Prepared/off-demand тексты одинаковы и query work уменьшилось → кандидат
  оптимизации; считать build/update amortization, не только warm median.
- Нет измеримого ускорения → не объявлять предобработку выгодной по скорости.

### Предлагаемый численный performance gate

До performance-исполнения координатор фиксирует hardware, размер/тип корпуса,
конкурентность, trace mode, cache state, число парных измерений и требования
владельца к абсолютной задержке. Для плана предлагается цель: **минимум 20%
уменьшения median тёплой выдачи контекста** при одинаковых final raw spans и
настройках, без измеримой регрессии end-to-end ответа и без роста online LLM calls.
Это целевой критерий, не прогноз. На коротком пилоте разброс фиксируется отдельно;
при шуме вывод INCONCLUSIVE, а не подбор удачных повторов. Cold start/build/update
и амортизированная цена не должны скрываться за warm median. Если цель владельца
иная, изменить gate до просмотра результатов. Production p95 и абсолютный SLA
потребуют отдельного workload; текущие 50/32 его не доказывают.

Независимый read-only review плана: PASS_WITH_LIMITATIONS. Замечания о default
coverage, отдельных runtime budgets и численной цели скорости внесены выше.

Следующие уровни доказательства: текущий in-process public integration →
installed wheel/stdio → реальный клиент → отдельный production smoke.
Ни один ранний уровень не заменяет последующие. Использовать разрешённый CI и
текущие ограничения checkpoint; не запускать весь старый набор повторно.

## 7. Обязательные артефакты исполнения

В новой папке, сохраняя прежний архив:

- `CONTRACT_DECISION_RU.md`, `OWNERSHIP.md`, `PROTOCOL_RU.md`;
- code/config/source/model revisions, corpus/oracle/input hashes;
- preparation/update receipts и актуальные source bindings;
- original requests, raw public packets, реально submitted prompts/answers;
- отдельные packet/answer/negative/source verdicts, per-case paired differences;
- `COSTS.json`: offline/online calls, timings, memory, bytes, tokens или UNKNOWN;
- `RESULT_RU.md`, `INDEPENDENT_REVIEW_RU.md`, checkpoint со stop/continue решением.

Commit/push/deployment отдельно от исследования, по запросу владельца. Не считать
публикацию отчёта разрешением включить experiment/default.

## 8. Готовое задание координатору

> Выполни согласованную волну этого плана. Сначала прочитай AGENTS.md,
> ANALYSIS_RU.md, текущий checkpoint и CONTRACT_DECISION_RU.md, если он уже есть.
> Назначь A–F непересекающиеся файлы, coordinator единственный integration/runner
> owner. Параллельны read-only audit, подготовка структуры и независимых данных;
> измерительные model/runtime workloads последовательны. Повторно не выполняй
> закрытые contextual-late/BGE/V2/V3 опыты и не открывай старый holdout20.
> При отсутствии зафиксированного D2/runtime budget подготовь контракты/patch plan,
> но не начинай runtime. Не меняй default, вопросы, corpus, oracle ради PASS.
> Используй текущий FTS/OR, parser, prefix, generations и source validators;
> не строй второй retrieval engine. Первый prototype lexical-only, без новой
> модели и скрытого decomposition. Не своди admission к score cutoff. Проверь
> всю цепочку до final packet и отдельно empty-source negatives. Новые проверки
> только integration+, реальные components/storage, без retrieval/selection mocks.
> Итог — точные files/decisions, фактические calls/costs и независимые verdicts;
> никаких обещаний ускорения/качества без соответствующего измерения.
