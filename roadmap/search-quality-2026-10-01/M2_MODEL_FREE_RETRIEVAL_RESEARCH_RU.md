# M2: упрощение начального поиска без новых моделей

2026-10-02. Исследование по уточнённому запросу пользователя: где усложнили,
что мешает и можно ли использовать механизм Grounded для первоначального поиска.
**Не runtime fix, не новый benchmark и не разрешение на установку моделей.**

## 1. Вывод

**Для начального поиска наиболее обосновано взять принцип FTS-only пути Grounded:
lexical passage retrieval по контекстному блоку, с одним BM25-порядком.**
Не нужно переносить сервер Grounded, его зависимости или добавлять Qwen.
В DocAtlas уже есть SQLite FTS5, source snapshots, parent/child structure и spans.

Точная проблема — не «FTS слишком слабый». На установленном MkDocs case FTS
находит материал; несколько следующих механизмов меняют порядок и окончательно
удаляют его. Отдельное короткое правило затем обязано повторить формулировку
длинного вопроса. Grounded сохраняет правило вместе с окружающим обсуждением.

Это основание выбрать **один model-free retrieval design**, но не объявить,
что он решает всю read admission, multilingual delivery или tight-budget packing.
Нельзя сохранить все downstream veto и обещать, что смена начального поиска
исправит end-to-end результат.

Предыдущая рекомендация `Qwen3-Embedding-0.6B + Qwen3-Reranker-4B` снята из
активного плана: она требовала новых runtime моделей, что не соответствует
уточнённому запросу. Ничего не установлено и defaults не менялись.

## 2. Где именно усложнили

Исследован текущий project-doc lexical read path, не все режимы retrieval.
HEAD — `2ffb84fe`; четыре production-файла имеют незакоммиченный draft.
Последняя locality-правка не проверена. Ниже различаются факты кода,
сохранённые причинные наблюдения и архитектурные предложения.

| Граница | Действующая логика | Что мешает |
|---|---|---|
| Индексирование | `structured_chunking.py:45–59, 400–506`: children с target 160 / hard 512 engineering tokens; retrieval prefix содержит source/heading | Exact spans — полезная основа. Но соседнее body-обсуждение не становится автоматически контекстом короткого child; retrieval unit и delivery unit недостаточно разделены |
| SQL-поиск | `_sqlite_store_part03.py:514–599`: AND, затем OR fallback/union; metadata filters; weighted FTS5 BM25 | Базовый поиск уже есть. OR тоже уже есть: «добавить OR» не является новым решением |
| SQLite ranking | Там же `:353–431`: к BM25 добавляются title/action/phrase/authority/length features | Получается другой objective, не чистый BM25. Конкретный вред каждого feature этим аудитом не доказан |
| Dispatcher | `_dispatch_part01.py:156–163` вызывает supplement → rerank → quota; `_dispatch_part02.py:232–272` заменяет within-source order на body/exact counts и parent-first promotion | Статистический retrieval order заменяется числом слов и новизной parent; последующая quota превращает preference в необратимую потерю |
| Передача score | `_sqlite_store_part03.py:290–297` возвращает `max(0, 1-index*0.05)`; `_project_docs_service_part03.py:773–779` переносит его в metadata; `project_doc_ranking.py:557–567` использует этот base | В дальнейшие множители попадает rank proxy, а не величина BM25 utility. Trace сохраняет исходные данные, но это не единый действующий score |
| Qualification/prefit | `evidence_qualification.py:291–524` смешивает source/reference checks, lexical ratio и typed admission; `project_doc_ranking.py:680–686` удаляет без qualified IDs/exemption | Недостаточное lexical совпадение становится запретом показать candidate, даже когда это не отказ source guards |
| Context rescue | `need_context_disposition.py:176–182`: два body terms; `read_context_admission.py:94–125`: три terms + pair; `need_context_projection.py`: precedence/list preferences | Несколько правил одного назначения. Общий iterator объединяет orchestration, не policy |
| Final selection | `_docs_context_projection_core.py:238–377, 664–672`: requalification, preferred proposals и checked fallback при пустом packet | Повторные source/span checks нужны. Но ordinary read context не конкурирует на равных в непустом packet; ранняя потеря также не исправляется final fallback |

Дополнительно в `project_doc_ranking.py:347–372, 717–770` есть repository-specific
path boosts (`docs/testing.md`, `wiki/commands.md`) и несколько heading/path/intent
множителей. `source_lane_allowed` (`:121–128`) выводит допустимость из keywords
и пути. Это не то же самое, что explicit scope/version/project guards; однако
менять source-policy semantics автоматически нельзя.

**Главная сложность — несколько владельцев relevance и удаления кандидатов,
а не просто число строк.** Расщепление файлов или переименование iterator её
не устраняет.

### Установленный causal case

Из сохранённых traces и проверки Grounded, без нового запуска:

```text
DocAtlas native:
  нужный child на позиции 4
    → body/parent ordering: позиция 15
    → quota: потерян

Отдельная no-parent-diversity ablation:
  child проходит quota
    → qualification: 3/11 < 0.5
    → read locality: нет adjacent query pair
    → prefit не передаёт candidate projector
```

Native run не достиг qualification для этого child. Поэтому это последовательно
наблюдённые барьеры в разных условиях, не два независимых native отказа.
Полный causal разбор: [M2_GROUNDED_MECHANISM_CHECK_RU.md](M2_GROUNDED_MECHANISM_CHECK_RU.md).

## 3. Что действительно делает Grounded

Проверены локальные upstream исходники **3.2.1**, commit
`f2938c47bb8937c650f0d5ddb614f867773b29f4`, и прежние runtime artifacts.
Context7 использован для навигации; implementation facts сверены с pinned source,
не перенесены из `main` или документационного SQL-примера.

```text
Markdown structure + greedy grouping
  → экранированная исходная фраза OR исходные terms
  → FTS5 BM25 с library/version filter
  → initial hits
  → отдельная assembly
```

- `MarkdownPipeline.ts:24–43` и `GreedySplitter.ts:43–107` объединяют небольшие
  блоки с учётом major sections. `SemanticMarkdownSplitter` здесь не вызывает
  inference-модель: название означает структурную обработку.
- Defaults в `src/utils/config.ts:143–145`: 500 / 1500 / 5000 **символов**,
  а не tokens. Это их параметры, не предлагаемая конфигурация DocAtlas.
- `DocumentStore.ts:908–994` строит phrase OR terms без answer-derived aliases.
  `:2443–2486` ранжирует FTS-only hits по weighted BM25, без per-paragraph
  требования повторить половину слов вопроса.
- `DocumentRetrieverService.ts:28–145` отделяет assembly от initial search.
  Лучший initial score используется для порядка assembled results; он не
  сертификат каждого добавленного paragraph.

Grounded **поддерживает optional embeddings** (`DocumentStore.ts:2340–2442`).
Утверждение «в Grounded вообще нет моделей» было бы неверным. В сравниваемом
FTS-only запуске индекс имел **0 embeddings**; этот путь работает без них.

### Почему он доставил MkDocs rule

В существующем проверенном run:

- Правило уже содержится в **top-1 FTS chunk до assembly**.
- Initial body тождествен assembled body; expansion не добавил ему bytes.
- Блок: 3583 символа / 769 actual `o200k_base` tokens. Body conservative estimate
  — 896; с metadata он не проходит наш whole-DTO лимит 800.
- Само правило короткое; его lexical anchors частично находятся в окружающем
  обсуждении навигации. Grounded не распознаёт специально `wins → override`.

Следовательно, переносимый механизм — **сохранять context при retrieval**, а не
«добавлять соседей после неудачи» или «выдавать тысячи tokens».

### Что нельзя копировать буквально

1. Нормализованный output как source bytes: `SemanticMarkdownSplitter.ts:137–165`
   проходит через Markdown→HTML→DOM, используется Turndown. У нас доказательством
   остаётся точный span оригинального snapshot, не заново отрендеренный Markdown.
2. Полный assembled text и унаследованный score как approval visible окна.
3. Их limits: `limit` ограничивает initial hits, не наш DTO budget.
4. Porter stemming как multilingual решение: он не переводит RU-query в EN-docs.
5. Готовый сервер как дополнительную runtime ветку. Нам нужен принцип и контракт,
   а не второй retrieval stack. Прямой перенос кода также требует соблюдения MIT
   notice; пока код не переносился.

## 4. Исследования: выбранная основа и пределы

**Основная работа для этого решения — Callan, “Passage-Level Evidence in
Document Retrieval”, SIGIR 1994**, §§1, 2.2–2.3, 3–4:
<https://www.cs.cmu.edu/~callan/Papers/callan794.pdf>.

Она рассматривает именно granularity lexical retrieval без neural inference:

- Короткие passages хуже сопоставляются с длинными queries; нужный текст может
  пересекать фиксированную границу passage (§1).
- Простое объединение коротких paragraphs по размеру не гарантирует улучшения.
  В одном TIPSTER run best bounded-paragraph retrieval был хуже document-level
  на 27.9% AP; combination дала +4.3% (§2.2, Table 2).
- В её experiments overlapping windows работали лучше paragraph boundaries;
  сочетание document/passage signals было лучше отдельных signals. Оптимальные
  weights/sizes зависели от collection (§§2.3–4).
- Предварительный top-document cutoff может пропустить хороший passage внутри
  mostly irrelevant document (§3).

**Вывод для нас:** не требовать полного lexical самодостаточного совпадения
каждого атома; учитывать контекст passage и не терять его до bounded extraction.
Это не указание внедрить INQUERY, их weighting formula, overlap profile или ещё
несколько scorers. Предлагаемый BM25 design — адаптация, не буквальная
реализация алгоритма Callan и не перенос его процентов на DocAtlas.

Дополнительные первичные проверки, **не дополнительные runtime механизмы**:

| Работа | Что подтверждает | Чего из неё не следует |
|---|---|---|
| [Robertson & Zaragoza, BM25 and Beyond, 2009](https://www.staff.city.ac.uk/~sbrp622/papers/foundations_bm25_review.pdf), §§2.5, 3.4, 3.8 | Term weighting/length normalization; ranking score не обязательно обратим в probability; phrase matching имеет пределы | BM25 не проверяет истинность, applicability или permission. SQLite weighted BM25 не нужно называть полной реализацией BM25F |
| [Hearst & Plaunt, SIGIR 1993](https://people.ischool.berkeley.edu/~hearst/papers/subtopics-sigir93/sigir93.html), “A New Kind of Query”, experiments | Local subtopic может не повторять global topic terms; combining segment scores полезен на их corpus | TextTiling не обязателен: segments и paragraphs не имели значимого различия на их test; query preprocessing удалял NOT clauses, чего нам делать нельзя |
| [BEIR, 2021](https://arxiv.org/abs/2104.08663v4) | BM25 — сильный heterogeneous baseline; более дорогие методы сильнее в среднем, но не универсальны | Нет необходимости добавлять neural reranker до исправления установленной собственной candidate loss |

Не найдено исследование, которое одним lexical score решает одновременно
retrieval, exact source binding, semantic support, conditions, abstention и
permission. **Это разные задачи; обещать такую готовую замену было бы неверно.**

## 5. Один рекомендуемый design: source-bound lexical passage retrieval

Рекомендация касается **первоначального поиска**, не снятия admission guards.

```text
raw question + explicit lookups + verified source/scope/version policy
  → bounded source-local contextual passages
  → один SQLite FTS5 BM25 order
  → candidate pool с snapshot/span identities
  → exact source-window proposals и bounded packing
  → final source/applicability rechecks
  → отдельно support/coverage/permission
```

### Ответственность и карта замены

| Сейчас | В рекомендуемом design |
|---|---|
| Короткий child одновременно основная search и evidence unit | Contextual search span и compact delivery span раздельны; display остаётся exact slice |
| BM25 + additive features + body counts + parent-first | Один объявленный lexical retrieval order; остальные initial relevance reorderings заменяются, не добавляются поверх |
| Parent identity даёт promotion/overflow роль | Parent/atom identity используется для source-local boundaries и provenance; не доказывает relevance или redundancy |
| Число raw candidates быстро становится выдаваемым top-k | Поиск имеет отдельные bounded candidate/byte limits; packing решает публичный ≤800/≤3 packet |
| No qualification → раннее удаление; shape-specific rescue | После выделения hard checks один read-selection contract; proof refusal не становится неявным source refusal |
| Retrieval-only → возможная путаница с coverage | Candidate retention не даёт qualified IDs, public support или edit authority |

Уже имеющиеся parents/atoms/spans следует использовать как основу. Не вводить
неограниченный whole-parent read или grouping только уже найденных children:
последний не восстанавливает то, что initial search не нашёл.

BM25 определяет **порядок search blocks**, но не утверждает полезность каждого
маленького окна. Extraction/packing и отказ на нерелевантном visible context
остаются отдельной частью контракта. Начальный BM25 hit не наследует approval
после clipping. Не добавлять обязательную query-pair проверку как «доказанный
из статьи» этап.

### Что остаётся нерешённым до реализации

1. **Единая model-free read relevance/abstention policy.** Pure OR/BM25 может
   высоко ранжировать вопрос-эхо, heading-only и противоположную relation.
   Позитивный hit не гарантирует прохождения наших negatives. Нельзя заменить
   существующий отказ на blanket admission или объявить guards соблюдёнными,
   если исчезли проверяемые subjects/conditions.
2. **Window selection и полнота зависимостей.** Нужно сохранять subjects,
   условия, отрицания, intro+list и table keys в реально видимом span. Ни статья,
   ни Grounded не дают готовую совместимую реализацию нашего ≤800 DTO selector.
3. **Resource caps.** Новый search unit меняет стоимость hydration. Сохраняются
   финальный budget и guards; внутренние candidate/byte/window caps и quotas
   надо явно согласовать, а не незаметно увеличить ради recall.
4. **RU→EN.** Без общих lexical anchors этот путь не гарантирует discovery.
   Existing explicit lookups допустимы, но новые aliases, скрытый перевод,
   query generation и модели этим решением не разрешены.

То есть «взять их начало, оставить наше продолжение» разумно **по границам
ответственности**, но не как буквальная цепочка с прежними lexical veto. У нас
есть более строгие source/evidence/permission возможности; общее превосходство
downstream answer quality этим не доказано.

## 6. Почему это не повтор прежнего “coarse-index”

Повторно прочитаны сохранённые paired rows, новые requests не выполнялись:

- Native baseline/shared: **41/48 → 41/48** sufficient positives.
- Shared plain: **42/48**, но lost partial fact `httpx-07`.
- Coarse native/plain: **34/48**; добавились потери на других библиотеках.

Coarse arm в `m2_simplification_evaluation.py:134–145` менял child size до
768/1280 engineering tokens, оставляя старый selection/admission путь.
Section arm (`:48–74`) группировал только уже найденные children и продолжал
ранжировать по counts. **Ни один не является простой implementation Grounded
FTS-only pipeline**, но их регрессии нельзя игнорировать.

Поэтому не предлагаем повторить увеличение размера как fix. Изменение search
granularity оправдано только вместе с ясными boundaries и migration map старых
решений. Если нужны новые послабления для MkDocs, это не заявленное упрощение.

## 7. Что исследование позволяет решить сейчас

- **Да:** выбрать Grounded-style lexical passage retrieval как единую основу
  первоначального поиска без новых моделей и второго сервера.
- **Да:** убрать Qwen recommendation из текущего направления.
- **Нет:** объявить выбранный design production-ready, автоматически удалить
  source/exact/condition checks или принять другой budget.
- **Следующий документ реализации:** точный interface search span → visible
  window, active-callers migration diff, единый read-selection contract и
  перечисленные open decisions. Не новая матрица ranking knobs.

После согласования нужны paired non-regression при одинаковых source bytes,
requests и DTO budget, сохранение partial facts, негативные controls, полный
regression review и независимый held-out/reader gate. Exposed cases и
`needs_review` не закрывают M2.

В этом шаге изменены только анализ/контракт. Runtime draft не откатан и не
проверен заново; модели, зависимости, index defaults и тесты не менялись.

## Источники реализации и данные

- Grounded [query construction](https://github.com/arabold/docs-mcp-server/blob/f2938c47bb8937c650f0d5ddb614f867773b29f4/src/store/DocumentStore.ts#L908-L994), [FTS-only ranking](https://github.com/arabold/docs-mcp-server/blob/f2938c47bb8937c650f0d5ddb614f867773b29f4/src/store/DocumentStore.ts#L2443-L2486), [greedy grouping](https://github.com/arabold/docs-mcp-server/blob/f2938c47bb8937c650f0d5ddb614f867773b29f4/src/splitter/GreedySplitter.ts#L43-L107).
- [Source mechanism check](M2_GROUNDED_MECHANISM_CHECK_RU.md) и [raw summary](m2_grounded_mechanism_check.json).
- [Comparator conditions](audit/COMPARATORS_RU.md): budgets отличаются; на RU-query/EN-docs Grounded тоже находил historical distractors.
- Saved paired rows: `/tmp/opencode/m2-simplification-{baseline,final,coarse}-parity/rows.json`. Статистики выше относятся к этим runs, не последнему locality draft.
- Первичные PDF для чтения: `/tmp/opencode/m2-model-free-research/callan1994.pdf` и `robertson-zaragoza2009.pdf`; downloaded paper files не являются runtime model/dependency installation.
