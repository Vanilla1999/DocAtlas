# Grounded budget probe: 800 / 1500 / 3000

**Уточнение:** [разбор независимых admission layers](ADMISSION_LAYERS_REVIEW_RU.md)
выявил case-handling bug research adapter. Числа ниже описывают исторический
candidate; не являются quality benchmark исправленного native-style admission.

2026-10-03. **Исследовательский прогон выполнен; replacement не принят.**
Production files/defaults/route не менялись. Не production Gate A Green.

## Решения

1. Увеличение budget реально помогает некоторым delivery cases: `mkdocs-05`
   перестаёт быть budget refusal при 1500. Это не решает основной retrieval/read
   контракт: strict owner доставляет только 15 required claims против 49 baseline.
2. При strict owner 1500 → 3000 не добавляет supported claims. Не рекомендовать
   3000 как универсальное исправление; 1500 — полезная экспериментальная точка,
   не принятый production default.
3. Whole-owner сохраняет B1 restriction внутри одного owner; passage около cap
   может его потерять. Whole-owner не доказывает cross-owner completeness.
4. First-fit завершает 30 alternatives без combinatorial solver. Он теряет более
   выгодную комбинацию в отдельном counterexample; не оптимальный packing.
5. Снятие одного topic refusal при 3000 повышает supported claims до 25, но
   доставляет sources во всех восьми frozen unanswerable cases. Такой replay
   неприемлем как production admission.
6. Текущий кандидат не сохраняет baseline partial facts. Его нельзя подключать
   вместо действующего route. Не запускать следующую сетку tuning автоматически.

## Что выполнено

- Behavioral Red → Green для одного неизменного exact DTO при 800/3000.
- Новый rank-ordered selector, actual DTO counter и final validator.
- Native FTS passage query один раз на case; одинаковый inventory для budgets.
- P: intact passage; O: whole owner при пересечении code/list/table.
- Existing source/reference/read checks; diagnostic replay снимает только
  `no_local_topic_witness`, не source/hard-subject/literal checks.
- Все **80 frozen cases × 7 cells = 560 research rows**; native baseline при 800.
- Mutation exact snippet, B1 near-cap, B2 30 alternatives, oversized-first,
  deterministic ordering, final recheck refusal и first-fit counterexample.

Catalog adapter использует реальные ingest metadata: repository identity →
project identity, catalog authority → authority; только files с `project_docs`
и catalog path переводятся из `project_file` в research `project_doc`.
Freshness/hash/version/scope не подставляются ради approval. Это отдельный
research index из actual generation bytes, не public route integration.

## Итоговая таблица

Claims — сумма `required_supported` штатного `assess_context`, не permission.
Потери — supported baseline claim больше не supported в этом cell.
`needs_review` здесь означает непустую evaluator review queue, не PASS.
DTO percentiles считаются только по непустым packets. Время — только
selection/check/assembly/assessment, **не end-to-end retrieval latency**.

| Policy | Budget | Packets /80 | Supported claims | Baseline losses | Review cases | DTO p50 / p95 / max | Selection ms p50 / p95 |
|---|---:|---:|---:|---:|---:|---|---|
| P strict | 800 | 17 | 15 | 36 | 4 | 653 / 760 / 760 | 1.71 / 5.18 |
| P strict | 1500 | 17 | 15 | 36 | 5 | 653 / 1262 / 1262 | 1.14 / 3.60 |
| P strict | 3000 | 17 | 15 | 36 | 5 | 653 / 1262 / 1262 | 1.08 / 3.71 |
| O strict | 800 | 15 | 11 | 39 | 5 | 554 / 736 / 736 | 1.27 / 3.74 |
| O strict | 1500 | 17 | 15 | 36 | 5 | 653 / 1445 / 1445 | 1.24 / 4.13 |
| O strict | 3000 | 17 | 15 | 36 | 5 | 653 / 1576 / 1576 | 1.20 / 4.15 |
| O diagnostic topic replay | 3000 | 55 | 25 | 27 | 49 | 1223 / 2019 / 2360 | 6.06 / 24.75 |

Baseline: **49 supported required claims**. Strict cells не доставили sources в
frozen unanswerable cases, но это **не доказательство zero false admissions**
по всем negative families. Replay доставил sources в `fastapi-08`, `httpx-08`,
`mkdocs-08`, `pydantic-08`, `ruff-08`, `starlette-08`, `typer-08`, `uv-08`.

Strict owner 1500/3000 теряет ранее supported partial claims:
`fastapi-07`, `httpx-07`, `mkdocs-07`, `starlette-07`, `typer-07`, `uv-07`.
У `pydantic-07` known claim доставляется при 1500, у `ruff-07` — уже при 800;
у `httpx-07` packet есть, но required known claim evaluator не подтверждает.
Наличие packet нельзя считать partial retention.

На strict O inventory основными reasons были `no_local_topic_witness` (147),
`missing_exact_or_subject` (78), `condition_support_unavailable` (19).
DTO budget refusals: 5 при 800, 1 при 1500, 0 при 3000. Reasons — на proposals,
не взаимоисключающая классификация 80 requests. Discovery и refusal не смешивать.

## Проверки

- Новые tests: **6 passed**.
- Новые первые пять cases + existing 01–04 API controls: **34 passed**.
- Existing read/constraint/subject/shared controls + historical Gate A:
  **56 passed, 3 failed**. Те же известные B1, B2 и precedence echo failures;
  старый solver/predicate не изменялся. Это не полный paired regression.
- Final DTO validator не выдал ошибок для emitted research packets;
  `answer_supported=false`, `edit_ready=false`.
- Test diagnostics предупреждает про existing unknown `asyncio_mode` config.

## Ограничения выполненного прогона

Полный checklist плана **не закрыт**: отсутствует отдельная comprehensive matrix
mutations всех security/version/request/condition/negation guards, cross-owner
restriction delivery test, list/table/clipped variants и synthetic relevance
negative matrix. Нельзя утверждать общий B1 или applicability safety Green.
Raw/proposal bytes и candidate traces сохранены; отдельные metadata overhead,
SQL trace, parsed-atom counts и все budget cost decompositions ещё не выведены.
Result artifacts сохраняют baseline payload/observer, но runner пока не публикует
автоматическую consolidated loss/negative summary — таблица вычислена из artifacts.

Ранние технические прогоны 01–04 не quality evidence: исправлялись ошибки adapter
(`service.agent`, metadata identity, passage span fields, canonical path).
Не считать отказ всего inventory из-за `reference_path_mismatch` свойством метода.

## Артефакты и повторение

Итоговый полный sweep:
`/home/viadmin/.cache/docatlas-experiments/grounded-budget-20261003-06/`.
`results.json` содержит 560 rows; per-case файлы содержат payload, trace, assessment,
resource omissions и raw/proposal bytes. Native baseline — `*-baseline.json`.
Пути fixture влияют на identity/DTO overhead: несколько units между runs могут
различаться. Внутри одного sweep source/request identity неизменны между budgets.

```bash
PYTHONPATH=. /usr/bin/python3.12 v2plan/grounded_budget_probe.py --output /home/viadmin/.cache/docatlas-experiments/grounded-budget-NEW --budgets 800 1500 3000 --policies passage owner --diagnostic-topic-replay
/usr/bin/python3.12 -m pytest -q tests/docs/test_grounded_budget_probe.py
```

Output должен быть новым: existing results не перезаписываются. Runtime/foreign
`experiments/crosslingual_relevance/` не менялись, commits/rollout не выполнялись.
