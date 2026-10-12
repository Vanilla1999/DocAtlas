# Подготовленный индекс и быстрый retrieval: анализ для DocAtlas

Дата: 2026-10-12. Статус: исследование и проект решения, **не выполненное внедрение**.
База кода/архива: `80fa1078842cfdddb4b7ecfd9d6faa681744fc39`.
Связанные документы: [причины потерь](../FILTER_ROOT_CAUSE_AND_GROUNDED_RU.md),
[план нескольких агентов](MULTI_AGENT_PLAN_RU.md).

## 1. Рекомендация

Развивать путь **«подготовить структуру и поисковые представления при индексации;
на запросе — найти, собрать ограниченный исходный контекст, проверить источник»**.
Первый шаг — перестать использовать буквальное покрытие всего вопроса и все его
числа как универсальный барьер допуска каждого фрагмента. Следующий — задействовать
подготовленные структурные связи и измерить реальную стоимость чтения/сборки.

Это не новый scalar fallback V3 и не обязательная дополнительная генеративная
модель на каждом запросе. Нейронные представления исследовать отдельно после
устранения потерь найденного текста. Предварительная обработка может убрать
повторный parsing/кодирование документов, но не может заранее доказать
достаточность ответа на произвольный будущий вопрос.

## 2. Что уже известно по нашим опытам

| Наблюдение | Основание | Следствие |
| --- | --- | --- |
| Найденный документ о споре отсекается: 8/21 слов и нет числа 14 | V3CAL02 raw packets | Retrieval score уже 1.0; улучшать только поиск бессмысленно |
| Правило диспетчера отклонено, посторонний «стеллаж 12» допущен | V3H02 B1/V3 | Admission не распознаёт самостоятельный смысловой вклад |
| V3: 1/4 → 3/4 новых полных positives, 6/9 strict negatives FAIL | V3 independent review | Узкая польза есть, общего решения relevance нет |
| Mini выбирает loading+cooling вместо cooling+incident | V2 HOLD01 | Полезна при ограничении уже доступного пула; не восстанавливает excluded |

### Важно: contextual indexing и reranking уже исследовали

Это исторические результаты других SHA/корпусов/границ исполнения; не новые
замеры нынешней ветки и не напрямую сравнимые с 1/4 → 3/4 V3.

- `experiments/grounded-partial/contextual-late/RESULT_RU.md`: четыре комбинации
  plain/contextual BM25 × plain/late embeddings. Конечная достаточность
  **34/48 у трёх контролей, 33/48 у комбинации**; во всех top20 найдено 47/48
  полных эталонов. Это projector replay, не новый end-to-end MCP/host run.
  Повторно использованы Jina rankings и 353 Qwen descriptions; не полная новая
  реализация Anthropic Contextual Retrieval.
- `experiments/grounded-partial/semantic-selection/RESULT_RU.md`: BGE улучшил
  top1 25→37/48, но конечный DTO остался **33/48**, path/snippet совпали на 80
  вопросах. Зафиксированная CPU median scoring 4.51 s относится к тому опыту,
  не Mini и не текущей машине/конфигурации. H1 закрыта отрицательно.
- `experiments/grounded-partial/contextual-late/SELECTION_RESULT_RU.md`:
  `retain_extend` не превысил 34/48, увеличил средний DTO на 28.6% и мог добавлять
  посторонний раздел Tables вместо правила о title. Это расширение **уже
  допущенных окон**, не предлагаемая замена раннего admission.

Следовательно, новый опыт должен менять конкретную границу потери и показывать,
что нужные bytes дошли до генератора. Повтор прежних матриц без новой гипотезы
не нужен. Больше контекста, лучший top1 или более дорогой индекс сами по себе
не являются улучшением конечного ответа.

## 3. Что заимствовать у Grounded

Публичный код `arabold/docs-mcp-server@c180d7c2679d7886d14d42eed36a827d9befe5d3`:
FTS с OR → BM25, опционально vector+RRF → группировка URL/близости →
content-type-aware assembly. Markdown добавляет родителей/соседей/детей.
Нет обязательного post-search правила «половина слов и все числа вопроса».

Заимствовать **разделение поиска и сборки**, а не точные defaults соседей или
обещание строгой relevance. Структурное соседство — повод рассмотреть исходный
блок, а не доказательство, что он отвечает на вопрос. Публичная реализация
не установлена как версия исторического Grounded-сервера.

Grounded 10/10 vs тогдашний DocAtlas 3/10 — исторический positive development
срез с разными бюджетами/чанкингом. Это не преимущество Grounded по negative
фильтрации, не результат на текущем V3 и не равный latency benchmark.

### Что уже есть у нас — не реализовывать второй раз

| Реальный путь | Найденный механизм | Практическое решение |
| --- | --- | --- |
| `docmancer/core/_sqlite_store_part03.py:480–562` | AND, затем OR fallback; при project_identity — AND+OR union и при успешном AND | «Добавить OR» не является новым исправлением project-поиска; порядок union не тождествен единой сортировке Grounded |
| `docmancer/core/structured_chunking.py:145–280,400–508` | Parents/children, heading paths, atoms, точные spans и IDs | Дополнять сохранённую структуру, не вводить другой Markdown parser |
| `docmancer/retrieval/contextual_indexing.py:124–190,261–311`; `core/_sqlite_store_part02.py:224–278` | Deterministic context prefix, отдельные display/retrieval text/hash | Сначала проверить существующий prefix, не заявлять его новым contextual improvement |
| `docmancer/retrieval/fusion.py:14–56`; `_dispatch_part02.py:8–101` | Dense/sparse/lexical и RRF | Переиспользовать там, где этот путь действительно разрешён |
| `docmancer/docs/application/project_docs_member_transaction.py:260–364` | Публичная project-member preparation — SQLite+lexical, vectors запрещены | Первый increment lexical-only; project hybrid требует отдельного контрактного изменения |
| `docmancer/core/_sqlite_store_part04.py:8–40`, `_part05.py:8–64` | Есть expansion; lexical adjacent внутри parent, hybrid adjacent внутри source | Сперва описать и согласовать границы, а не считать режимы одинаковыми |
| `docmancer/docs/application/source_dependency_preparation.py:14–51`; `domain/source_dependency_graph.py:72–104` | Query-time heading/list/table dependencies | Кандидат для persisted metadata с теми же правилами |
| `docmancer/docs/application/query_block_context.py:35–80` | Повторный parser, block counts и local BM25 | Предвычислять query-independent блоки и статистики; query scoring остаётся online |
| `docmancer/docs/application/joint_context_selection.py:139–224` | Перебор combinations/drafts, повторная validation | Измерить и ограничить работу, не объявлять автоматически узким местом |

Дополнительные ограничения аудита:

- `SourceReferenceContext` уже имеет per-call cache; graph/dependency и query
  embeddings тоже имеют небольшие LRU. «Добавить кэш» без карты hit/miss не план.
- Parent section не равен вложенному subtree. Название `page` не означает весь
  документ. Существующие comments и реальные границы lexical/hybrid различаются.
- Legacy заполнение `project_doc_sections` находится в недостижимой старой
  ветке; новый индекс строить через действующий member transaction/generation.
- Direct `DocmancerAgent.query()` и public dispatcher — разные пути. Проверка
  SDK-вызова не доказывает включение hybrid в публичном project MCP.
- Показанный в packets `score=1.0` может быть синтетическим rank score
  (`1−0.05×rank`), не BM25/cosine confidence. Не калибровать по нему отказ.
- Incremental embedding reuse уже есть, но generation validation может пройти
  всё поколение. «Пересчитали один vector» не значит «обновили индекс за O(1)».
- Для project Markdown spans относятся к исходному UTF-8. Для преобразованных
  PDF/HTML snapshot — текст loader, не исходный бинарный файл.

## 4. Исследования и их практический приоритет

### A. Contextual Retrieval — хороший кандидат для предварительной подготовки

[Anthropic, 19.09.2024](https://www.anthropic.com/engineering/contextual-retrieval).
Авторская инженерная публикация, не peer-reviewed статья.

Перед embedding/BM25 к chunk добавляется сгенерированное по документу короткое
chunk-specific пояснение. Оно создаётся при индексации. На запросе остаётся
обычный поиск; reranking — дополнительный компонент, не бесплатная часть offline.
У авторов retrieval failure `1-recall@20` менялся 5.7%→2.9% для contextual
embeddings+BM25 и →1.9% с reranking. Это не метрика полноты ответа DocAtlas.

Для нас: сначала дешёвый baseline `title + heading ancestry + raw chunk` с
полями разного происхождения. Это **не полная реализация Anthropic**. Генерацию
пояснений добавлять отдельной абляцией, если baseline теряет контекст сущности.
`generated_context` хранить отдельно от original bytes и не цитировать как источник.
Историческую цену авторов $1.02/миллион входных токенов нельзя использовать как
текущий полный бюджет индексации: она зависит от модели, prompt caching и размеров.

### B. Late Chunking — смысл документа без генерации пересказов

[Günther et al., arXiv:2409.04701v2, 02.10.2024](https://arxiv.org/html/2409.04701v2).
Вначале long-context encoder кодирует документ/большое окно, затем pooling
token embeddings выполняется в границах отдельных chunks. На запросе остаётся
один query embedding и обычный single-vector retrieval.

Raw span не меняется; контекст вне span влияет на вектор. Если этот внешний
контекст нужен для ответа, его всё равно надо доставить как исходный текст.
Модель должна поддерживать token-level output и подходящий pooling; произвольный
API, возвращающий один embedding строки, для этого недостаточен. Изменение
документа инвалидирует контекстное окно, а не только исправленный chunk.

Приоритет условный: длинные взаимосвязанные документы, подтверждённые discovery
промахи. Прежний отрицательный DocAtlas factorial не повторять; сперва исправить
доставку. Метод не является алгоритмом semantic admission.

### C. RRF и BEIR — простой контроль перед усложнением

[Cormack, Clarke, Büttcher, SIGIR 2009](https://doi.org/10.1145/1571941.1572114):
`RRF(d) = sum(1/(k + rank_i(d)))` объединяет ранги, не требует общей шкалы scores
и не даёт вероятности релевантности. Уместен для sparse+dense, если оба индекса
реально доступны. Его наличие не означает необходимость менять уже готовый RRF.

[BEIR, NeurIPS 2021](https://datasets-benchmarks-proceedings.neurips.cc/paper/2021/hash/65b9eea6e1cc6bb9f0cd2a47751a186f-Abstract-round2.html):
BM25 остаётся сильным baseline; reranking/late interaction имеют преимущества
в исследованных zero-shot задачах, но требуют вычислений. Нужен lexical-only
контроль; dense не включать автоматически ради названия «семантический».

### D. Sufficient Context и SetR — для недостающего смыслового этапа

[Joren et al., ICLR 2025, arXiv:2411.06037v3](https://arxiv.org/html/2411.06037v3):
разделять достаточность пары question+context и правильность уже данного ответа.
Это прежде всего полезная методика оценки. Авторский autorater модельный,
ошибается и добавляет query-dependent работу; не переносить его accuracy в продукт.
Предположения статьи о допустимом parametric knowledge/ambiguity не заменяют
наш строгий source-grounded контракт.

[Lee et al., SetR, ACL 2025, arXiv:2507.06838v1](https://arxiv.org/abs/2507.06838v1):
набор passages должен совместно закрывать информационные требования, а не только
иметь высокие независимые scores. Это соответствует проблеме «тариф + спор».
Полная система модельная; применение идеи set selection не равно внедрению SetR.
Обязательный LLM-decomposition на каждом вопросе противоречит цели дешёвого
быстрого пути, пока его добавочная польза и цена не измерены.

[AdaGReS, arXiv:2512.25052v1, 31.12.2025](https://arxiv.org/abs/2512.25052v1):
preprint о greedy set selection под token budget с relevance/redundancy objective.
Полезен как последующий кандидат упаковки. Похожие passages могут содержать разные
обязательные факты; similarity penalty не доказывает избыточность по смыслу.

### E. Что отложить

- [ColBERTv2, NAACL 2022](https://aclanthology.org/2022.naacl-main.272/): token-level
  late interaction, предвычисленные document vectors, query-time MaxSim.
  Не путать с Late Chunking. Выигрыш сжатия 6–10× — относительно ColBERT, не
  обычного single-vector индекса. Дополнительная сложность пока не оправдана.
- [RAPTOR, ICLR 2024, arXiv:2401.18059v1](https://arxiv.org/html/2401.18059v1):
  offline clustering/summaries/tree для обзоров длинных документов. Summaries
  могут ошибаться; для нас годятся как поисковые указатели с возвратом к raw
  leaves. Это адаптация, а не опубликованный reader-input контракт RAPTOR.
- [Lost in the Middle, TACL 2024](https://aclanthology.org/2024.tacl-1.9/):
  увеличение длины контекста не гарантирует использование нужного факта.
  Это основание ограничивать расширение и проверять финальный ответ, не прогноз
  конкретного поведения нашего текущего генератора.

## 5. Целевая подготовка данных

Поддерживать два представления одной ревизии документа:

| Слой | Содержимое | Назначение |
| --- | --- | --- |
| Канонический | raw bytes, immutable hash, source/scope/version/generation, char/byte/line spans | Чтение, источник и точная цитата |
| Структурный | section/parent/prev/next, тип блока, таблица+header, fenced code boundary, явные локальные ссылки | Ограниченная сборка исходных фрагментов |
| Поисковый | FTS по raw и отдельным contextual fields; optional embeddings, representation/model revision | Найти candidates, не сертифицировать ответ |

Хранить границы строк/блоков и token estimates заранее. Связи code→description
или exception→rule признавать структурными только при воспроизводимом основании
в документе. Иначе это derived hint, а не доказанный semantic edge. Не создавать
общую связь всех файлов одной папки и не требовать появления числа в каждом блоке.

### Обновление и кэш

- Ключи derived artifact: document hash + parser/chunker/representation revision
  + model/tokenizer/prompt revision и параметры, когда они используются.
- Contextual annotation/late vector могут зависеть от **всего документа**.
  Правка одного абзаца инвалидирует все зависимые представления, если более узкая
  область зависимости не доказана.
- Index generation публикуется атомарно; deleted/changed sources и их edges
  не остаются доступными через старые query cache entries.
- Кэш запроса должен учитывать исходный вопрос, scope/version/generation,
  effective source policy, режим, бюджет и ranking/assembly revision. Это не
  разрешение считать старые receipts новыми или переиспользовать модельный ответ
  между несовпадающими исходниками.
- Результат прошлой hash-проверки не заменяет актуальную проверку источника.
  Оптимизировать можно повтор одного и того же чтения/разбора в текущем вызове;
  изменение freshness guarantees — отдельное контрактное решение.
- Холодную загрузку embedding/reranker измерять отдельно от тёплого запроса;
  держать модель загруженной можно только с явным учётом RAM/VRAM.

## 6. Быстрый путь вопроса

```text
неизменный вопрос + явные scope/version
  → ограниченный sparse поиск [+ один query embedding, если dense включён]
  → объединённый source-valid пул с причинами попадания
  → ограниченные структурные варианты исходных spans
  → выбор и дедупликация под бюджет конечного пакета
  → актуальная проверка исходных bytes/scope и публикация по контракту
  → существующий генератор ответа
```

Цель первого кандидата: **0 generative LLM calls внутри retrieval**, без скрытого
agentic loop. Числа/идентификаторы остаются поисковыми сигналами и условиями
вопроса, но не превращаются автоматически в обязательный literal каждого passage.
Явный project/module/version/path scope и источник не отменяются высоким score.
Ответ с числами должен сохранять реальные исходные пороги и условия для вывода.

Это предложение нового experimental admission, не уже разрешённое ослабление
всех exact constraints. ADR 0003 §§Literal partial body context сохраняет
hard-exact/explicit identity и unresolved-name правила. Агент контракта должен
отдельно классифицировать ограничения; в первом опыте менять только whole-question
ratio/numeric veto, остальные действующие request constraints сохранять. Helper
`_source_valid_body_blocks` содержит query-dependent unresolved-name проверку и
не является готовым чистым валидатором источника.

Не заполнять остаток бюджета произвольными соседями. Не считать одинаковый query
ID доказательством одинаковой информации. При overflow явно показывать усечение;
не выбрасывать молча вторую сторону сравнения ради compact status.

### Нерешённая граница: строгие negatives

Широкий поиск может вернуть похожий, но бесполезный текст. Grounded не доказывает
соблюдение `sources=[]` на наших отрицательных вопросах. Поэтому source-valid
pool и публично релевантные sources — разные объекты. Диагностический opt-in
может измерять широкую доставку, но его nonempty negatives остаются FAIL старого
контракта. Если быстрый детерминированный путь не соблюдает этот контракт,
фиксируем ограничение; не маскируем его отказом генератора.

ADR 0003 также запрещает скрытую генерацию сервером вопросов/lookups/ожидаемых
ответов. Contribution scoring существующего original — отдельный experimental
сигнал, не источник новых authoritative queries. `PROJECT_CONTEXT_BUDGET` сейчас
имеет `max_tokens=None`, `max_sources=None`; общий фиксированный потолок 800/6144
отменён ADR. Предложенный bounded budget — явная переменная опыта/работы, не
восстановление старого default и не предположение о текущем автоматическом cap.

Модельный semantic selector допускается как отдельный последующий вариант,
если он улучшает итог сверх простой доставки и укладывается в задержку.
Ни Mini cutoff, ни подготовленные summaries заранее этого не гарантируют.

## 7. Как считать скорость и цену

В сохранённом V3 workload public acquisition занял суммарно **17.373 s**,
host generation — **117.571 s** при runner wall **136.946 s**
(`admission-v3/RESULT_V3_RU.md:49–55`). Там 57 public calls и 28 host attempts;
это суммы неодинакового workload, не latency одного вопроса. Но они показывают
важную границу ожиданий: ускорение parser/index не устраняет время генерации
ответа. Для воспринимаемой скорости важны также размер prompt и отсутствие
дополнительных последовательных LLM-вызовов. Почти двукратное повторение source
text в coordinate presentation исправлять отдельной абляцией, не смешивая
изменение generator/citation контракта с первым admission опытом.

Отдельно фиксировать `prepare_full`, `prepare_incremental`, restart/cold start,
query embedding, FTS/vector, source validation, expansion, packing, final host.
Считать полный submitted prompt, а не только source text. Измерять фактическое
число обработанных кандидатов, bytes/doc reads, model calls и размер индекса.

`C_total(N) = C_initial + Σ C_update + N × C_query`.
Если `C_query` не снизился, перенос работы в индекс не является доказанной
экономией. Если снизился, break-even зависит от числа вопросов между обновлениями.
Время и деньги считать отдельно. Сравнивать при одинаковом максимальном бюджете
**и** сообщать фактический расход и качество: пустой быстрый ответ не победитель.

На маленьком pilot выдавать per-case/min/median/max, не обещать production p95.
Отдельный заранее ограниченный performance-прогон нужен лишь после качественного
отбора кандидата, с одинаковой машиной, холодными/тёплыми условиями и трассой off.

## 8. Граница этой работы

Изучены первоисточники в интернете, текущий код и прежние отчёты. Три агента
параллельно проверяли индекс, контракт и исследования. Docs MCP вернул
`insufficient_evidence/source_unavailable`; документальные claims о репозитории
основаны на явных локальных файлах, а не на успешном MCP retrieval.
Установка моделей, подготовка нового корпуса, live эксперименты и deployment
не выполнялись. Числа из прежних отчётов не выдаются за новые measurements.

Независимый review этого анализа и плана: **PASS_WITH_LIMITATIONS** на уровне
проектирования. Ограничения — неполная default-parity матрица первого pilot,
невыделенный бюджет последующих волн и необходимость численного latency gate.
Они явно отражены в плане; это не review результата ещё не выполненного patch.
