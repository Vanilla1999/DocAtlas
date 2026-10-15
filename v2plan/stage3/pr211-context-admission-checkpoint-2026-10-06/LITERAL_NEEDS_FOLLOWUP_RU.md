# Literal needs: следующий bounded dictionary-exit срез

Baseline: опубликованный `c4add087`. **Срез реализован и scoped approved;
full dictionary exit NOT DONE.**

## Цель и основание

Владелец согласовал удаление ручных смысловых правил до улучшения полноты общими
методами. Это архитектурный контракт, не исследовательское доказательство того,
что удаление semantic needs улучшает качество. Предыдущая alias-ablation показывала
потерю полноты; её результаты и красные quality gates сохраняются.

В обычном read-пути `SourceReferenceContext` и context variants вызывают
`compile_need_contracts → retrieval_needs`. Текущий срез убирает из этих двух
producers `_need_relation`, admission/comparison/compositional parsing, NL clause
splitting и наследование субъекта/условий. Grammar modules не удаляются вслепую:
их остальные consumers проверяются отдельно.

## Контракт

- Исходные bytes/Unicode spans вопроса остаются целыми; explicit lookups не меняются.
- Непустой вопрос — один unresolved literal root; без inferred subject/relation,
  expected count, category mapping, prerequisite или conditional semantics.
- Литеральные symbol obligations не смешиваются с source-locator obligations.
  Повторное одинаковое spelling в symbol occurrence не снимается глобально.
- Source/path/project/module/version/snapshot/hash/window/provenance, lifecycle,
  consent, budget и mutation guards не ослабляются. Context не становится answer proof.
- Старые tests/gold/thresholds/frozen corpus не меняются. Новые coverage/shards
  дополняют, а не заменяют красные проверки.
- Raw gzip архив остаётся локально вне Git и не удаляется.

## Проверка

Новые indexed public MCP cases проверяют полезные цитаты через явный lookup для
EN/RU, comparison/conditional/multiple-clause questions. Они не доказывают полноту
ответа на исходный сложный вопрос: проверяются цитаты, budget, snapshot integrity
и отсутствие answer/edit authority.

## Итог реализации и review

- `question_retrieval_needs.py` и `need_contracts.py` больше не выводят relation,
  subject, conditional/context inheritance, comparison sides или compositional needs.
  Один полный unresolved root сохраняет exact original span и literal symbols.
- `need_context_disposition.py` проверяет этот root как anonymous helper, без
  generated retrieval lane и public credit. Membership/current-source checks
  сохранены; context остаётся `retrieval_only`, не `supported`.
- Locator/body obligations разделены по occurrences, включая quoted catalog stem.
  Отдельный backtick symbol с тем же spelling остаётся mandatory.
- Review выявил forged quoted-stem plan для постороннего `Other.md`.
  `query_reference_binding.py` теперь проверяет literal locator против фактического
  canonical path существующими catalog tiers до выдачи binding.
- Live recovery `_problem_spans` больше не вызывает словарный clause splitter:
  bounded original diagnostic fragment, без guessed coverage/inheritance.

Последний integrator run: **447 новых tests PASS**, stdio MCP smoke **PASS**.
Independent reviewer: **313 passed**, scoped publication YES после исправления
forged-plan blocker. Отдельные новые tests: 65 literal-needs и 7 public/recovery.
Old mixed needs/contracts suites: **32 passed / 73 failed**, assertions сохранены.
Self-host gate повторно **FAIL**, frozen thresholds не менялись; новый raw report:
`archives/dictionary-exit-literal-needs-self-host-v1.json`. Он не заменяет старые
quality reports. Green новых tests не доказывает восстановление полноты поиска.

## Оставшаяся граница

Bounded caller audit не нашёл default execution admission_meaning/admission_contract/
question_plan/compositional_question_plan compilers: их importability не равна
выполнению. Direct-call/tooling compatibility остаётся отдельным OPEN audit.
Recovery fixed-wrapper/rephrase vocabulary остаётся diagnostic-only OPEN,
не используется автоматически как новый retrieval query. Advanced patch/corpus/
delivered-policy и оставшиеся semantic proof modules не объявлены очищенными.

Historical source manifests не перезаписываются. Current pins отдельным snapshot:
`archives/dictionary-exit-literal-needs-source-manifest.json`.
