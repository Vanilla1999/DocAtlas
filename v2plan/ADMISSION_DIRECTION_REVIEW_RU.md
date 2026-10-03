# Admission: рабочий продукт, причина потерь и направление упрощения

2026-10-03. Анализ исходников, сохранённых результатов и первичных исследований.
Новый runtime/replay не запускался. Рекомендация ниже — не готовый relevance
predicate и не разрешение на production replacement.

## 1. Продукт уже возвращает документацию?

Да, есть конкретное историческое подтверждение: [Kotlin live artifact](../eval/kotlin_smoke/task14_live_1_8_1.json),
2026-08-03, commit `0a4b6d1ccfa751e4327e6a35e3be88644d374177`:

- `kotlinx.coroutines@1.8.1`, вопрос `coroutines launch async example with code`;
- terminal status `succeeded`, `code_match=true`, pinned official citation;
- источник — `docs/topics/coroutines-basics.md`, то есть тоже Markdown.

Граница доказательства: [smoke runner](../scripts/kotlin_live_smoke.py) вызывает
`mode=library`; code gate допускает `launch` ИЛИ `async`+`await`. Это проверка
получения code-bearing context, не полного объяснения обоих API. Она не измеряет
нынешнюю live-работоспособность, все Kotlin-вопросы или качество всего репозитория.

Наш последний owner/1500 trial — другой, изолированный project-doc candidate.
В [context router](../docmancer/docs/interfaces/mcp/context_tools.py) library answer
и project context имеют разные projection branches. Поэтому потери candidate
нельзя выдавать за результат всего продукта или Kotlin library route.

## 2. Виноваты плохо написанные `.md`?

Такой диагноз не подтверждён. Markdown бывает сложным для extraction: заголовок
задаёт субъект, правило продолжается в другом абзаце, условия относятся к списку,
код подключается include-директивой. Это нормальные особенности документации;
границы Markdown не гарантируют границы полного смыслового факта.

Но в **32 из 36** потерь supported baseline claims полный annotated witness уже
есть в proposed windows. Четыре оставшиеся потери связаны с per-source discovery
cap. В этом сравнении основная проблема — наша обработка найденного текста.

Пример: вопрос `Does uv read pip.conf or PIP_INDEX_URL?`; документация прямо
говорит `uv does not read ... pip.conf or PIP_INDEX_URL`. Annotated witness найден,
но first refusal — `no_local_topic_witness`. Отрицательный ответ является фактом,
а не причиной считать документацию плохой или нерелевантной.

## 3. Что установлено на текущем candidate

Пересчёт [results.json](artifacts/typed-constraints-owner-1500/results.json),
с witness labels из [layers.json](artifacts/admission-layers-02/layers.json).
Join сделан по **(case_id, proposal_id)**: один source proposal может повторяться
в разных requests, поэтому одного proposal ID для атрибуции недостаточно.

- 80 cases; baseline supported claims: 49.
- Candidate supported: 15 = **13 сохранённых baseline + 2 дополнительных**.
- Потеряны 36 baseline claims; это не оценка текущего native продукта в целом.

| Первый отказ на полном annotated witness / discovery | Baseline claims |
|---|---:|
| Topic locality | 20 |
| Condition support unavailable | 8 |
| Per-source discovery cap | 4 |
| Subject binding | 2 |
| Required literal | 1 |
| Reason-contract mismatch (`httpx-06`) | 1 |

Первые отказы не являются независимыми причинными эффектами: после исправления
одного слоя может отказать следующий. `needs_review` не засчитан как recovery.
Typed compiler убрал установленный конфликт, но не восстановил baseline claims.

## 4. Где admission действительно переусложнён

Проблема — несколько владельцев допуска к чтению:

1. [project_doc_ranking.py](../docmancer/docs/domain/project_doc_ranking.py):680–686
   удаляет кандидата без qualified IDs, если нет context exemption.
2. [read_context_admission.py](../docmancer/docs/application/read_context_admission.py):80–105
   получает общий qualification verdict, интерпретирует reason strings, затем
   проверяет constraints и требует 3 terms + adjacent query pair в sentence.
3. [need_context_disposition.py](../docmancer/docs/application/need_context_disposition.py):130–181
   использует другой набор допустимых reasons и floor из двух body terms.
4. [need_context_projection.py](../docmancer/docs/application/need_context_projection.py):167–177
   содержит отдельную relation-shaped locality preference с `require_pair=False`.

Эти пути не обязательно все выполняются последовательно на каждом запросе.
Однако одинаковая обязанность «можно показать контекст» определяется разными
правилами. Общая wrapper-функция над всеми ними сама по себе не будет упрощением.

Кроме того, `_applicable_context` возвращает False как для wrong condition, так
и для unsupported формы. Диагностически это разные причины. Различить их в trace
полезно, но такое различение само по себе не разрешает unknown condition.

## 5. Что говорят исследования

Проверены первичные источники; это выборочный обзор, не доказательство отсутствия
других методов. Чужие результаты не являются measured gain нашего продукта.

| Источник | Основание для решения | Ограничение переноса |
|---|---|---|
| [Callan, SIGIR 1994, Passage-Level Evidence in Document Retrieval](https://www.cs.cmu.edu/~callan/Papers/callan794.pdf), §1–2 | Короткие passages могут плохо совпадать с длинными queries; факт пересекает границы; all-or-nothing proximity имеет ограничения | Не даёт готового нашего admission, не доказывает, что больше chunk всегда лучше |
| [Hearst & Plaunt, SIGIR 1993](https://people.ischool.berkeley.edu/~hearst/papers/subtopics-sigir93/sigir93.html), A New Kind of Query / Experiments | Локальное обсуждение может не повторять глобальный subject; контекст и локальность имеют значение | Не разрешает binding по одному имени проекта; часть query идей в статье была предложением, а не реализованным результатом |
| [BEIR, NeurIPS 2021](https://datasets-benchmarks-proceedings.neurips.cc/paper/2021/hash/65b9eea6e1cc6bb9f0cd2a47751a186f-Abstract-round2.html) | BM25 — обоснованный простой baseline; проверять перенос между domains | Ranking не является проверкой applicability или достаточности; BM25 не лучший во всех задачах |
| [Joren et al., Sufficient Context, ICLR 2025](https://arxiv.org/html/2411.06037v3), §3–5 | Relevant/useful context, sufficient context и correct answer различаются; полезен и неполный контекст | Их autorater и selective generation используют модели; это не model-free алгоритм для копирования |

Последняя работа также показывает, что LLM может ошибаться при недостаточном
контексте вместо отказа. Поэтому `answer_supported=false` — важная граница API,
но не эмпирическое доказательство безопасного поведения downstream reader.

Grounded 3.2.1 — engineering comparator, не научная гарантия. Его проверенный
FTS-only путь отделяет поиск/assembly от подтверждения ответа и не имеет нашего
adjacent-pair gate: [pinned mechanism review](M2_GROUNDED_MECHANISM_CHECK_RU.md).
Topic-relaxed replay у нас уже был; повторять его под новым названием не нужно.

**Исследования обосновывают разделение обязанностей и passage retrieval.
Они не обосновывают наше правило «3 слова + соседняя пара» как общий semantic
filter и не дают готовую замену, сохраняющую все наши negative expectations.**

## 6. Что означает «продолжаем admission»

**Рекомендация: да, продолжаем его упрощение; расширение grammar и rescue-правил
как основное направление останавливаем.** Цель — один владелец read decision,
не универсальный model-free интерпретатор документации.

| Обязанность | Целевой контракт |
|---|---|
| Source/request eligibility | Existing source, security, scope, version, freshness, snapshot/span/request guards обязательны |
| Identity/applicability | Existing literal, verified subject и condition obligations сохраняются; unknown не становится applicable |
| Read relevance | Одно явно определённое решение о полезности контекста, одинаковое до packing и на final bytes |
| Support/coverage/edit | Отдельные existing decisions; read admission их не создаёт |

Проверяемая семантика целевого read-контракта:

- Полный ответ не обязателен для полезного read context — это уже предусмотрено
  [partial-query test](../tests/docs/test_read_context_admission_boundary.py):28–40.
- Независимый известный fact не сертифицирует неизвестный private tail.
- Отрицательный documented fact не равен wrong condition или нерелевантности.
- Wrong source/identity, unsupported обязательное condition, heading-only/echo
  и нерелевантный текст не получают нового разрешения автоматически.
- После изменения visible bytes решение пересчитывается; source approval или
  BM25 score большего блока не является разрешением для произвольного clipping.

Сохраняется открытый вопрос: **конкретный общий relevance predicate**. Нельзя
выдать архитектурную схему за его реализацию. Нельзя обещать одновременно общий
semantic abstention, отсутствие моделей/словников и полное сохранение фактов,
не показав это на данных.

## 7. Ограничения наших проверок, влияющие на следующий шаг

Все 8 `unanswerable` cases в [cases.json](../eval/evidence_quality_v2/cases.json) —
один шаблон `What is the guaranteed 99th-percentile latency in milliseconds for
our production <library> deployment?`, различается library. Это восемь corpus
вариантов одного negative scenario, не восемь независимых классов отказа.

В [read boundary tests](../tests/docs/test_read_context_admission_boundary.py):76–90
рядом с heading/echo есть lexical controls: 2 terms и перестановка слов. Их нельзя
выдать за независимую semantic разметку relevance. Existing expectations остаются
действующими; их возможный пересмотр — явное изменение policy, не «починка тестов».

[Protocol](../eval/evidence_quality_v2/protocol.json) явно помечает validation как
exposed, unseen validation как NOT_MEASURED. Повторный успех на этих 80 cases
сам по себе не устанавливает переносимость на Kotlin или другие repositories.

## 8. Следующий bounded шаг и условие остановки

Следующий эксперимент должен проверять **только admission**, а не очередную
комбинацию нового retrieval, hydration cap, compiler и selector:

1. Использовать изолированный native read path как baseline и одинаковый native
   candidate inventory для обеих сторон. API 01–04 остаются отдельным результатом.
   Одинаковый experimental DTO budget 1500; новый baseline измеряется заново:
   исторические 49 нельзя механически приписать новому arm.
2. До реализации зафиксировать одну read policy и точные competing veto,
   которые она заменяет. Не добавлять ещё один fallback. Если predicate пока
   нельзя сформулировать — остановиться на контракте, не писать parser «на вырост».
3. Проверить positives/negatives на substantive context, wrong subject/state,
   polarity, echo/heading, partial requests и unsupported forms. Frozen labels
   не менять; alternative witnesses оценивать отдельно и симметрично обоим arms.
4. Один paired replay: retention baseline claims, partial retention, erroneous
   read admissions и proof/edit flags считать отдельно. Снижение количества
   независимых relevance veto — самостоятельная проверка упрощения, не gain recall.

Продолжение оправдано, если один общий контракт заменяет конкурирующие правила,
сохраняет baseline facts и negative/guard behavior. Если снова нужны исключения
под case/library/relation — этот candidate отклоняется, рабочий маршрут сохраняется.
Held-out и полный regression потребуются перед интеграцией, но это не повод
сейчас запускать очередную сетку budgets или расширять grammar.

**Итог:** продукт не нужно «спасать от Markdown». Нужно сократить число разных
решений о read relevance, сохранив проверяемые ограничения. Research candidate
с retention 13/49 не является основой для production rollout.
