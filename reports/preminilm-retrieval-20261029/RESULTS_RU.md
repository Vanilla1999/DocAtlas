# Pre-MiniLM retrieval: сравнение с main

## Итог

Полное сравнение выполнено. **Улучшения полноты поиска не доказано.**

- `retrieval_text` сохранил все удовлетворённые эталонные требования main.
  На V40 наблюдаются небольшие сокращения: MiniLM forwards **−2,17%**,
  input-pair tokens **−2,57%**, MCP wire tokens **−1,52%**.
  Это кандидат для дальнейшей проверки эффективности, не победа качества.
- `rrf` с фиксированным распределением **128+128** потерял обязательный witness
  `V40-E01` ещё до MiniLM. Такой вариант не рекомендуется включать.
- На NEW20 у всех вариантов одинаковые **10 ошибок из 20**
  `section_compression_output_limit`; изменение FTS ranking их не устранило.
  Итоговый score по неизменному oracle — **12/26**, против **25/26** в native pool.
  Отдельный span-аудит показывает, что единственный незачтённый pool witness
  пересекает границу snippets: его исходные bytes не потеряны.
- Default остаётся `main`. Эксперимент не слит в main; после раскрытия NEW20
  алгоритмы, вопросы, oracle и бюджеты не подгонялись.

Зелёный CI означает завершённый проверяемый замер и сохранённые source/state
invariants, **не** прохождение всех quality-критериев.

## Что именно исполнено

- Baseline: установленный wheel
  `main@542900e573835aa17a3a21da924a0f7ed400bece`.
- Retrieval implementation freeze:
  `d38322439f3bf8d561c933ff6021d046d280d413`.
- Полностью измеренный candidate:
  `879f5e07951196fb967ceaff3515973a3e41e0fc`.
  Отличие от первого freeze — только исправление CI collector и его отчёт.
- Ветка: `experiment/preminilm-retrieval-20261029`.
- [Предварительно зафиксированный дизайн и исследовательские основания](../../docs/preminilm-retrieval-research.md).
- [Машиночитаемая выборка измерений и provenance](MEASUREMENTS.json).
- [Завершённый CI 40957179011](https://github.com/Vanilla1999/DocAtlas/actions/runs/40957179011).
- [Полный artifact 12934683122](https://github.com/Vanilla1999/DocAtlas/actions/runs/40957179011/artifacts/12934683122):
  `COMPARISON.json`, freeze, installed wheels, actual MCP replies, NATIVE,
  MINILM, SQL, preparation/state/checkpoint receipts.
  ZIP SHA-256:
  `7acdd9e11817c8f0d63414d2f0628ffcadaa580919204401c660746e314a0ba9`.
  Retention CI artifact — 30 дней; сводка и код остаются в Git.

Фиксированы CPU ONNX MiniLM revision
`233902d25c440f23af6f7d6e94d2946bac0bee0a`,
`facet-guarded-lexical-v2`, `markdown-owner-v1`, Context Assembly adaptive,
MCP compact text fallback, offline inference и существующие ресурсные пределы.
В этой policy нет фиксированного финального top-5: `configured_top_k=None`;
работают facet/adaptive selection и неизменённый complete-packet cap 12 000 tokens.

| Arm | Acquisition до MiniLM | Цена одного native read |
| --- | --- | --- |
| `main` | Literal OR исходных слов; FTS5 BM25 по всем трём полям | 1 FTS statement, до 256 rows |
| `retrieval_text` | Тот же запрос, MATCH только по `retrieval_text`, weights 0/1/0 | 1 statement, до 256 rows |
| `rrf` | All-fields и retrieval-text views; RRF `k=60` | 2 statements по 128 rows; без backfill |

У публичного контекстного вызова в этих fixtures два native reads:
общий и `authority=source_of_truth`. Поэтому наблюдаем 2 FTS statements на
вопрос для main/text и 4 для RRF, а не 1/2. Предел fetched rows относится
к каждому read; он не равен всему SQL work или числу уникальных кандидатов.

`retrieval_text` **не body-only**: внутри поля остаются детерминированный
структурный prefix и metadata. Новый индекс, query expansion, модель и
инструкции агенту не добавлялись. Host-only переключатель:
`DOCATLAS_ACQUISITION_POLICY=main|retrieval_text|rrf`; отсутствие переменной
означает прежний main. Неверное значение отклоняется явно.

## Качество по неизменным эталонам

Здесь «требование» — documented witness/claim frozen oracle, не оценка
сгенерированного ответа. V40 проверяет union исходных координат; NEW20 —
literal byte witnesses, каждый из которых должен целиком находиться в одном
snippet. Эти критерии и знаменатели не менялись.

### V40: 40 вопросов

| Метрика | main | retrieval_text | rrf |
| --- | ---: | ---: | ---: |
| Требования в полном native pool | 32/32 | 32/32 | **31/32** |
| Требования в конечной выдаче | 32/32 | 32/32 | **31/32** |
| Положительные cases: source/fact contract | 24/24 | 24/24 | 23/24 |
| Partial cases: имеющиеся documented requirements | 8/8 | 8/8 | 8/8 |
| Negative cases: строгий empty-source contract | **0/8** | **0/8** | **0/8** |
| Ошибки доставки | 0 | 0 | 0 |
| Pool prefix@20: требования | 28/32 | 29/32 | 29/32 |
| Новые / потерянные требования final против main | — | 0 / 0 | **0 / 1** |

32/32 не означает 40/40 успешных вопросов: отрицательные случаи не проходят
строгий критерий пустой выдачи. Prefix@20 улучшился на одно требование, но это
не прирост final coverage и не доказательство эффективности меньшего pool cap.

### NEW20: 20 вопросов

| Метрика | main | retrieval_text | rrf |
| --- | ---: | ---: | ---: |
| Требования в полном native pool по frozen oracle | 25/26 | 25/26 | 25/26 |
| Требования в конечной выдаче | 12/26 | 12/26 | 12/26 |
| Положительные cases: source/fact contract | 4/8 | 4/8 | 4/8 |
| Partial cases: documented requirements | 3/6 | 3/6 | 3/6 |
| Negative cases: строгий empty-source contract | **0/6** | **0/6** | **0/6** |
| Ошибки доставки | **10/20** | **10/20** | **10/20** |
| Pool prefix@20: требования | 24/26 | 24/26 | 24/26 |
| Новые / потерянные требования final против main | — | 0 / 0 | 0 / 0 |

Ни одна из новых policies не исправила NEW20. Все вопросы остаются в знаменателе,
включая ошибки. 0/14 negative passes по двум наборам — отдельная нерешённая
проблема; это не измерение hallucination rate, поскольку ответы моделью не
генерировались.

## Стоимость: чистое сравнение на всех 40 V40 calls

| Метрика, сумма если не указано иное | main | retrieval_text | rrf |
| --- | ---: | ---: | ---: |
| Source-checked pool rows | 5 938 | 5 567 | 4 678 |
| Фактические FTS statements | 80 | 80 | 160 |
| Завершённые MiniLM forwards | 6 083 | 5 951 | 5 012 |
| MiniLM input-pair tokens | 1 272 043 | 1 239 371 | 1 039 656 |
| Source rows в конечной выдаче | 280 | 271 | 287 |
| MCP wire o200k tokens | 45 931 | 45 233 | 47 478 |
| MCP wire UTF-8 bytes | 161 263 | 159 005 | 167 067 |
| Контекстные вызовы, суммарно секунд | 305,99 | 297,19 | 246,90 |
| Контекстный вызов p50, секунд | 6,77 | 6,70 | 6,08 |
| Контекстный вызов p95, секунд | 17,32 | 17,67 | 9,97 |

`retrieval_text`: −132 forwards, −32 672 input-pair tokens, −698 wire tokens.
Наблюдаемая экономия невелика. RRF: −17,61% forwards, но **+3,37% wire tokens**
и потеря witness, поэтому его уменьшение работы не является улучшением с
сохранённым качеством. Меньше кандидатов не гарантирует короче итоговый ответ.

На NEW20 у каждого arm сохранены только 10 завершённых MiniLM receipts:
497 forwards и 247 464 input-pair tokens. На остальных 10 работа **неизвестна**,
а не нулевая. Поэтому эти числа нельзя складывать с V40 и объявлять полной
стоимостью 60 вопросов. Wire включает реальные error packets; успешные пары
показываются отдельно в JSON.

Для NEW20 полные wire totals: 60 992 / 61 021 / 61 037 tokens при одинаковых
210 796 bytes. Из них на 10 nonerror replies приходится
60 182 / 60 211 / 60 227 tokens. Малые различия tokenization совместимы со
случайными session capabilities и не являются качественным выигрышем.

Один последовательный инструментированный запуск, включая startup и observer
overhead, **не доказывает статистически значимого ускорения**. Это измеренные
MCP/tokenizer и MiniLM work counts, не paid API usage и не экономия всей
автономной сессии OpenCode.

## Причина регресса RRF: V40-E01

Вопрос о допустимых именах flat configuration file ESLint.
Required witness: `docs/src/use/configure/configuration-files.md`,
строки 19–30, исходные chars `[584,1141)`.

| Chunk | Rank main | Rank retrieval_text | В RRF |
| --- | ---: | ---: | --- |
| `[584,993)`: список имён | 137 | 137 | Нет |
| `[993,1324)`: размещение/export и пример | 141 | 143 | Нет |

Оба chunk находятся за границей top128 каждого входного списка. В RRF даже
`complete_candidates` не содержит пересечения с witness. При этом top128
обоих views полностью совпадают: **256 fetched rows → 128 уникальных**,
`resource_skipped_rows=0`. Второй authority read повторяет те же candidates.

Это проверено без сравнения случайных generation/evidence IDs:
нормализованные множества `main.pool[:128]`, `retrieval_text.pool[:128]`
и весь `rrf.pool` совпадают по path/span/text/source-content hashes.
Их SHA-256 записан в `MEASUREMENTS.json`.

Название секции `Configuration File` у RRF остаётся, но её scoring text
содержит только другой chunk `[1324,1739)`, без списка имён. MiniLM уже не
может восстановить отсутствующие исходные фрагменты. Во всех трёх arms
`budget_limited=false`: этот регресс не вызван output cap.

Доказан дефект **данного распределения 128+128** на двух сильно совпадающих
lexical views, а не непригодность RRF вообще. Иное распределение или backfill
не запускались задним числом; дополнительные SQL/read затраты не бесплатны.

## NEW20: доставка и граница измерения

### Ошибки после retrieval

У всех arms совпадает набор `section_compression_output_limit`:

- Click: NEW01, NEW02, NEW09, NEW10, NEW15.
- tox: NEW07, NEW08, NEW14, NEW19, NEW20.

Это явные серверные `SectionCompressionError`, не обрезка ответа OpenCode.
На этих cases MiniLM completion receipt не публикуется, поэтому его стоимость
не восстанавливается по длине короткого error packet.

У всех NEW20 cases в native диагностике только один известный Markdown owner.
`parse_markdown_parents` распознаёт ATX-заголовки `# …`; исходные RST-документы
здесь представлены одним owner `Document`:

| Source | Проверенный native pool | Owner scope, chars |
| --- | --- | --- |
| Click `options.rst`, все arms | 63 fragments; в source order точно восстанавливают весь файл, 26 719 bytes | `[0,26719)` |
| tox `config.rst`, main/RRF | 110 fragments; точно восстанавливают весь файл, 54 596 bytes / 54 374 chars | `[0,54374)` |
| tox `config.rst`, retrieval_text | 98–104 fragments; 49 363–51 986 source bytes в зависимости от вопроса | Тот же `Document` |

Ошибка возникает в `select_sections → fits → encode_sections`, **до выдачи
source references и до standalone text / Context Assembly**. Замороженный
section encoder использует default `docatlas.sections.v1`; cost полного
пакета — `max(o200k_tokens(packet), ceil(UTF8_bytes(packet)/4))`, limit 12 000.
Grouping и whole-section-prefix selection не оставляют меньшую непустую группу,
если весь acquired документ относится к одной секции. Для tox уже исходный
текст pool больше 48 000 bytes; metadata увеличивает размер пакета.

Это конкретная причина исследовать RST/section granularity и порядок упаковки,
а не обвинять Context Assembly или клиентскую обрезку. Простая замена рангов
FTS этот дефект не решает. Отклонённый trial packet, его точная стоимость и
MiniLM scores не сохранены: точный overrun Click и сработавшая ветвь cost здесь
не утверждаются. Один owner наблюдается напрямую; группировка отказавшего
вызова объясняется статическим кодом, не отсутствующим completion receipt.

25→12 — разница удовлетворённых frozen obligations между native pool и final,
а не новый подсчёт семантических фактов. На ошибочных cases приходится 14
documented obligations; 13 засчитывались в pool, ни одно не доставлено.

### NEW08/F2: не потеря исходных bytes

После завершения сравнения выполнен отдельный read-only span-аудит.
Score **не пересчитывался** и oracle **не исправлялся**:

- Первый literal witness F2: `docs/config.rst`, bytes `[7121,7242)`.
- Он пересекает границу двух acquired snippets:
  `[6800,7231)` и `[7231,7759)`; в main это pool ranks 4 и 2.
- Оба snippets точно совпадают с raw source; они смежны. Их конкатенация
  совпадает с raw `[6800,7759)` и содержит witness целиком.
- В одном отдельном snippet этого witness нет, поэтому неизменный NEW20
  literal-one-snippet критерий даёт `covered=false`.
- Второй witness F2, bytes `[7471,7632)`, засчитан уже исходным oracle.

Следовательно **25/26 нельзя интерпретировать как потерю retrieval одного
факта или его bytes**. Это ограничение формы frozen измерения. Формально
остаётся 25/26; новый union-based oracle потребовал бы отдельно объявленного
контракта и не должен вводиться ради улучшения текущего результата.

## Учёт исполнения и ресурсов

| Попытка | Benchmark context calls | Scope controls | Всего context calls | Public-handler preparations |
| --- | ---: | ---: | ---: | ---: |
| 1: неполный collector | 72 | 3 | 75 | 9 |
| 2: полное сравнение | 180 | 3 | 183 | 27 |
| **Всего фактически** | **252** | **6** | **258** | **36** |

В полном запуске: 27 acknowledged checkpoints и 27 фактических post-exit
DB/file verifications; 480 benchmark FTS statements и 0 scope-control FTS;
0 continuation calls, 0 automatic retries внутри запуска,
**0 paid answering-model calls**. Public preparations выполнены через
реальный установленный handler; context calls — через настоящий MCP stdio.
Protocol initialize/tools-list не считаются дополнительными context calls.

Вычислительная стоимость не нулевая: работали MiniLM и CI. При memory ceiling
1 500 000 000 bytes пики containers полного запуска:
main 1 309 753 344, text 1 274 888 192, RRF 1 151 655 936.
У всех `oom=0`, `oom_kill=0`, runtime exit code 0.
Это профиль стенда с verbose receipts, не production memory benchmark.

### Сохранённая первая неудачная попытка

[CI 40954589560](https://github.com/Vanilla1999/DocAtlas/actions/runs/40954589560)
на `d38322439f3bf8d561c933ff6021d046d280d413`.
[Artifact 12933662046](https://github.com/Vanilla1999/DocAtlas/actions/runs/40954589560/artifacts/12933662046),
ZIP SHA-256
`9f2e2adfa14cc8cd065775cd01147ec5d917440a59a77efaef1d12b9b30465fc`.

Main и text завершили по 16 benchmark calls/2 preparations, RRF — 40/5.
После shutdown не хватило `poetry/STATE.json` у main/text и
`eslint/STATE.json` у RRF; последний `NATIVE.json` остался пустым.
NEW20 до остановки не открывался. Эта попытка — **NOT ASSESSABLE** по качеству,
а не удалённый плохой результат.

MCP Python SDK 1.29.0 допускает 2 секунды на завершение после EOF, затем
останавливает процесс. Сериализация verbose NATIVE размером 60–77 MB в
`finally` не успевала. OOM events были нулевыми. Дополнительно host не мог
записать `CONTAINER.json` в созданный container-root каталог arm.

Исправлен только collector: parent после последнего tool response, до teardown,
запрашивает streaming atomic checkpoint через CI-only сигнал; worker выдаёт ACK
с hashes четырёх receipts. Во время измеряемых calls polling нет. После закрытия
stdio parent отдельно сверяет retained private DB/files с before fingerprints;
отсутствие DB — failure. Cleanup выполняется уничтожением изолированного
container. `CONTAINER-$arm.json` перенесён в host-owned evidence directory
без ослабления прав. Изменения прошли независимый статический review;
продукт, модель, алгоритмы, oracle и resource caps между попытками не менялись.

## Следующие идеи — отдельные эксперименты

1. **Структурные passage units до MiniLM, прежде всего RST.**
   Проверять не только ranking, но и совпадение единицы retrieval с единицей
   selection: маленькие source-bound passages, осмысленные section boundaries,
   сборка смежных исходных spans без потери условий на границе. По текущим
   результатам это приоритетнее ещё одной сортировки почти полного pool.
   Концептуальная основа — passage-level FirstP/MaxP/SumP у
   [Dai и Callan, SIGIR 2019](https://www.cs.cmu.edu/~callan/Papers/sigir19-Zhuyun-Dai.pdf);
   наша source-bound адаптация должна проверяться отдельно, не объявляться
   воспроизведением статьи.

2. **Literal phrase/identifier lane и действительно разделённые поля.**
   Для API/CLI вопросов исследовать последовательность терминов, близость
   и целые технические имена; оставить широкую lexical lane для recall.
   Основание для dependencies —
   [Metzler и Croft, SIGIR 2005](https://cs.uwaterloo.ca/~jimmylin/workspace/Ivory/docs/publications/Metzler_Croft_SIGIR2005.pdf),
   а не обещание воспроизведения их MRF. Отдельное чистое body field помогло бы
   проверить шум metadata, который остаётся в нашем `retrieval_text`.
   Нужны reindex/source-safety проверки и заранее ограниченный SQL budget.
   Не генерировать скрытые «правильные ответы» в query expansion.

3. **Комплементарный sparse retrieval и честный fusion budget.**
   [SPLADE-v3, 2024](https://arxiv.org/abs/2403.06789) — исследовательский кандидат
   для lexical mismatch и paraphrase; это новая модель и индекс, не бесплатная
   замена SQL. [Two-Step SPLADE, 2024](https://arxiv.org/abs/2404.13357) предлагает
   efficiency cascade с pruned/reweighted first stage и rescore исходными sparse
   vectors; опубликованные speedups нельзя переносить на DocAtlas.
   Для fusion сначала измерять дополнительное покрытие и overlap, затем
   сравнивать allocation/backfill и, при наличии отдельного training split,
   learned convex combination
   ([Bruch и др.](https://arxiv.org/abs/2210.11934)).
   Суммарные fetched rows не скрывают postings/SQL work.

Ничего из этого не подмешано в опубликованные arms. NEW20 теперь раскрыт:
следующей итерации нужны отдельный dev-набор и новый frozen holdout.

## Границы доказательства

- Реальные installed public-handler preparation, MCP stdio, SQLite и MiniLM;
  автономная клиентская сессия OpenCode/Terra не проверялась.
- Source/hash/span/scope/generation и фактическое состояние проверены;
  это не оценка качества сгенерированного ответа или semantic sufficiency.
- V40 исторически известен; NEW20 был процедурно закрыт для этой реализации
  до freeze, но это не внешний независимый benchmark.
- Baseline исполняет настоящий main wheel. Candidate с `policy=main`
  отдельно не запускался: default сохранён статически, не доказана независимая
  runtime byte-parity этой ветки.
- Отсутствующий completion receipt — неизвестная стоимость. Ошибка доставки
  не считается экономным успешным ответом.
- После сравнения изменён только отчёт. Его отдельный commit не выдаётся за
  новый execution candidate; все runtime числа относятся к `879f5e0`.
