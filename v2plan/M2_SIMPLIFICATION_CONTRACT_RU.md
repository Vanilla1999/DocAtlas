# Контракт проверяемого упрощения

2026-10-02. Baseline: `2ffb84fe`. Контракт не объявляет M2 завершённым.

## Диагноз и ограничения после уточнения пользователя

**Сначала анализ причин и карта упрощения, не следующий эксперимент.**
Разбор текущего расхождения между диагнозом и реализацией:
[M2_SIMPLIFICATION_ROOT_CAUSE_REVIEW_RU.md](../roadmap/search-quality-2026-10-01/M2_SIMPLIFICATION_ROOT_CAUSE_REVIEW_RU.md).

- Общий iterator не признаётся единым read-relevance решением. Native sufficient
  в сохранённом парном benchmark не вырос: 41/48 → 41/48.
- Не добавлять новые lexical словари, request-shape исключения, relation-specific
  режимы locality или threshold tuning. Последний `require_pair=False` /
  `sentence_pattern` draft непроверен и не принимается как общее упрощение.
- Не запускать новый large-block/chunk/ranking trial вместо ответа, какие
  competing veto надо заменить и кто владеет read-selection решением.
- Следующий результат: active-callers ownership map, первый irreversible loss
  по существующим traces, список сохраняемых guards и конкретная migration
  diff-map. Не объявлять неизвестный relevance критерий уже решённым.
- Ни guards, ни полезные partial facts, ни существующие tests не ослабляются.
  Полный regression/held-out остаются обязательными gates будущей реализации,
  но число прошлых runs не считается доказательством общего улучшения.

## Актуальное направление: исследование без новых моделей

**Рекомендация Qwen3-Embedding + Qwen3-Reranker снята из активного плана.**
Она означала новую runtime инфраструктуру, которую пользователь не хочет.
Модели/зависимости не установлены; сохранённые результаты чужой статьи не
считаются доказательством исправления DocAtlas.

Исследование текущего кода, pinned Grounded 3.2.1 и первичных passage-retrieval
работ: [M2_MODEL_FREE_RETRIEVAL_RESEARCH_RU.md](M2_MODEL_FREE_RETRIEVAL_RESEARCH_RU.md).

**Рекомендуемая единая основа первоначального поиска — source-bound lexical
passage retrieval:** контекстные bounded blocks → один SQLite FTS5 BM25 order
→ candidate pool с exact snapshot/span binding. Это принцип FTS-only Grounded,
не перенос его сервера, параметров или нормализованного output.

```text
raw question + verified source/scope/version policy
  → contextual passage retrieval / BM25
  → bounded exact source-window proposals и packing
  → final source/applicability rechecks
  → отдельные support/coverage/permission decisions
```

- Основа исследования: [Callan, SIGIR 1994](https://www.cs.cmu.edu/~callan/Papers/callan794.pdf).
  Короткие passages могут терять context и хуже соответствовать длинным queries;
  простое увеличение/слияние paragraphs тоже не гарантирует улучшения.
- SQLite FTS5/parents/atoms/spans уже есть. Новые модели, aliases, скрытый перевод,
  generated queries и второй retrieval stack не входят в направление.
- Initial relevance reorderings должны заменяться одним объявленным порядком,
  не добавляться поверх. Смешанные source/exact/constraint проверки сначала
  выделяются и сохраняются; их снятие не разрешено.
- Смена первоначального поиска не решает последующие lexical veto автоматически.
  Общий read-selection/abstention contract и extraction зависимых facts остаются
  открытыми решениями; BM25 score не становится approval clipped window.
- Не копировать Grounded chunk sizes и не повторять coarse-index как fix:
  сохранённый coarse arm дал 34/48 против 41/48 native при прежнем DTO budget.
- RU→EN без общих lexical anchors этим design не гарантируется. Не объявлять
  superiority DocAtlas/Grounded из разных budget/policy условий.

Следующий результат — interface search span → visible window и active-callers
migration map, с явными open decisions и сохраняемыми resource caps. Не новая
матрица ranking arms. Runtime/code/index defaults в этом analysis шаге не меняются.

Исполнительный [TDD-план для ограниченного coding-агента](M2_MODEL_FREE_RETRIEVAL_TDD_RU.md):
по одному шагу, с allowed files, behavioral Red/Green и public-boundary controls.
Gate R фиксирует ресурсы до passage builder; Gate A фиксирует общий read-decision
до его реализации. Наличие плана не означает, что эти открытые решения согласованы.

## Исторический контракт предыдущего этапа

Ниже сохранён контракт предыдущего этапа. Arms — история выполненных ablations,
а не список следующих заданий. Этот docs update не снимает runtime draft и
не означает, что он повторно проверен или принят.

## Разделение решений

1. **Source eligibility:** оригинальные identity, scope/version, lifecycle,
   snapshot/hash/span и risk проверяются до нормализации и после slicing.
   Нормализация DTO не может исправить чужую identity или снять risk.
2. **Read relevance:** admissible context не означает proof. Нельзя объединять
   все разрешения typed topical fallback с более строгим original-read route.
3. **Prefit inventory:** сохраняет проверенные original-read windows и только
   те typed preferences, которые уже предлагает final selection. Один iterator
   этих preferences используется в обеих стадиях. Prefit result не кешируется
   как final approval.
4. **Locality:** heading/link-only, query echo и scattered terms не получают
   новое разрешение через prefit. Existing original-read floor/pair не меняется.
   Typed proposal по-прежнему обязан пройти свой source/subject/condition
   classifier и уже существующий relation/list preference.
5. **Budget:** 800 whole-DTO admission tokens, максимум три sources; существующие
   candidate/source/module caps и structural overflow не увеличиваются.
6. **Proof и permissions:** qualification/coverage thresholds неизменны;
   read context не выдаёт answer/edit readiness. Никаких generated lookups,
   aliases, дополнительных source reads или gold-dependent ranking.

Это **частичное упрощение orchestration**, не универсальный semantic relevance
scorer. Typed grammar и original-read policy ещё остаются разными механизмами.
Называть их одним полностью новым решённым admission contract было бы неверно.

## Выполненные диагностические arms (история)

- Baseline native: старый prefit + parent-first promotion.
- Shared native: общий guarded preferred inventory, старый retrieval.
- Plain: исключена parent-first promotion; body/exact score, quotas неизменны.
- Tied: parent novelty влияет только на одинаковые body/exact keys.
- Section-first: coarse scoring parent groups из уже найденных children
  (до 5000 символов/group), затем fine child ordering. Это не full index retrieval.
- Coarse-index: отдельная экспериментальная генерация с target/hard 768/1280
  engineering tokens вместо 160/512, затем штатное visible-window packing
  при прежних 800 whole-DTO tokens. Profile остаётся UNVALIDATED; production
  defaults и accepted-profile guards не меняются.

Во всех arms одинаковые frozen questions/source bytes/policy. Section-first
и coarse-index разнесены: широкая preference и реальная крупная retrieval unit
не одно и то же. Метаданные corpus/labels не входят в selector.

## Acceptance

- Подтверждение witness retention и final delivery, а не только final score.
- Не допускаются новые budget/source/snapshot/risk нарушения и негативные
  regressions первого rejected trial.
- Existing partial facts `httpx-07`, `pydantic-07`, `ruff-07` не теряются ради
  `mkdocs-05`.
- Needs-review не считается sufficient; анализ formatting/union limitations
  отдельно от operational и safety failures.
- Полный `tests` — парно на baseline/current; legacy failures не скрываются.
- Exposed benchmark не заменяет независимо размеченный held-out corpus или
  reader risk/citation evaluation. Если таких данных нет, это открытый gate,
  а не основание выдать синтетические тесты за независимое доказательство.

Новый scorer/threshold, production chunk-profile change и массовое удаление
boosts не принимаются автоматически, если эти bounded experiments не проходят
non-regression. Отрицательный результат — завершённая проверка гипотезы,
но не завершённое исправление всего pipeline.
