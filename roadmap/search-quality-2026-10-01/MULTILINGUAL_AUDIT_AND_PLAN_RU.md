# Удаление языковых зависимостей: checkpoint и план

Baseline: `acf9a277f9ca8edb49f7205beede19ac9df19be4`.

Этот документ восстановлен по сохранённой истории разговора. Исходный
незакоммиченный файл и материалы шага 07 отсутствуют в новом worktree;
они не считаются восстановленными результатами тестов.

## Решение

Убрать ручную EN/RU грамматику как обязательный gate доставки документации.
Сохранить identity/version/scope/freshness/snapshot/safety guards, буквальные
identifiers, цитаты и budgets. Понимание ответа остаётся задачей host-модели.
Удаление regex само по себе не обеспечивает cross-language recall.

Шаги 01–04 исправляли recovery/lifecycle/contract/authority; их не откатываем.
Шаг 05 исправлял evaluator. Шаг 06 — partial diagnostic, не rollout.
English-only workaround шага 07 был отклонён; шаг 07 не закрыт.
Grounded также ограничен tokenizer/model: его нельзя считать доказательством
универсального multilingual качества.

## Подтверждённые участки для проверки

- `docmancer/docs/domain/query_terms.py`: NL словари и script restrictions.
- `docmancer/docs/domain/admission_grammar.py`: ограниченная EN/RU грамматика.
- `docmancer/docs/domain/evidence_qualification.py`: смешанные metadata,
  forbidden-term и lexical qualification проверки.
- `docmancer/docs/domain/documentation_query_plan.py`: query aliases/rewrites.
- `docmancer/docs/application/context_query_probes.py`: повторная qualification.
- `docmancer/docs/application/_docs_context_projection_core.py`: final delivery.
- `docmancer/docs/domain/lifecycle_policy.py`: metadata policy сохранить;
  question-to-lifecycle inference проверять отдельно.
- `docmancer/docs/domain/content_trust.py`: не удалять security detectors без
  отдельной замены и проверки data/control boundary.

## Этапы и gates

1. **M0 — inventory:** найти активные callers и разделить source eligibility,
   relevance и semantic support; отдельно certification и mutation lanes.
2. **M1 — совместимый refactor:** отделить существующие metadata checks от
   text exclusions. Не менять reasons, порядок проверок, packets/defaults.
   Gate: language-invariance tests и существующие guard regressions.
3. **M2 — query/intent boundary:** raw Unicode question, typed constraints,
   bounded lookups; неизвестная грамматика не блокирует read-only lookup.
   История и mutation не открываются автоматически.
4. **M3 — multilingual retrieval:** отдельный измеряемый эксперимент с
   фиксированными corpus/model/budgets; проверять recall до и после cap.
5. **M4 — delivery:** убрать NL grammar/ratio как универсальный semantic veto
   из read-only path; повторно проверять actual spans и source guards.
6. **M5 — removal:** удалять obsolete rules только после миграции callers;
   legacy certification/security требуют отдельного review.
7. **M6 — acceptance:** installed MCP и настоящие host ответы, citations,
   unsupported claims, abstentions, latency/cost и независимый holdout.

Матрица: EN/RU/ES/JA/AR, cross-language и mixed-script queries; negation,
conditions, comparisons, exact identifiers, wrong identity/version/snapshot,
stale/history, unsafe sources, question echo и unrelated exact-ID distractors.
Нельзя подставлять English lexical trace другому языку или считать quote binding
доказательством правильного ответа.

До завершения gates не объявлять multilingual rollout или закрытие шага 07.
Шаг 08 не начинать. Push/merge не выполнять.
