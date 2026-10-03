# Typed constraint compiler: реализация и paired replay

2026-10-03. **Research compiler реализован. Production replacement не принят.**

## Что изменилось

`typed_constraint_compiler.py` вызывает existing compiler и меняет только
`constraint_spans` у полностью распознанных single-frame questions:

- Frame fully parsed → exact original-query spans condition slots.
- Frame имеет empty conditions → constraints пустые, без повторного keyword поиска.
- Compositional contracts/prerequisites не меняются.
- Unsupported frame или несовпадение reference question → native contract без изменений.
- Subject, literals, relation, interpretation и remaining contract fields неизменны.

Нет temporal/library-specific разрешения по score или `startswith('When')`.
Existing state/exception grammar не расширена; unknown не становится applicable.

## Подключение только внутри research процесса

`typed_constraint_replay.py` временно заменяет compiler references в
`read_context_admission` и `admission_layer_probe`, вызывает предыдущий corrected
runner при **owner / 1500**, затем восстанавливает обе references.
Runtime files и permanent public route не менялись. Source/reference preparation,
proof qualification и остальные compiler consumers не заменялись.

Это целевая проверка compiler на existing read route, **не полная миграция
всех contract consumers**. Поля `native_read_allowed/reason` внутри новых layer
artifacts означают existing read function **с research compiler**, не неизменённый
native baseline; сравнение с unmodified compiler сохранено отдельно.

## Проверка контракта

Первый behavioral test был Red: ordinary temporal question сохранял whole-question
constraint. После реализации Green.

17 paired synthetic controls:

- Fully parsed EN/RU temporal вопросы → applicability=True при отсутствии условий.
  Это отсутствие applicability veto, **не read admission и не proof**.
- Temporal + parsed state: correct disabled state → True, wrong enabled → False.
- Default timeout state: correct/normalized not-enabled → True; wrong/missing
  state или wrong subject → False.
- Unless/except, unsupported event conditions, unsupported RU surface остаются False.
- Quoted `` `when` `` не становится condition marker.
- Composed precedence contract unchanged, independent private tail retained.
- Offsets проверены на wrapped questions; condition spans буквально извлекаются
  как `preview` / `disabled` из original question, не rewritten query.

## Paired replay — 80 frozen cases, одна точка budget

Тот же archived generation, native hits/order, source snapshots, proposals/IDs,
selector, serializer и source row limits. Нет новой сетки, поиска или reindex.

| Метрика | Corrected adapter, native compiler | Typed compiler |
|---|---:|---:|
| Cases | 80 | 80 |
| Packets | 18 | 19 |
| Supported required claims | 15 | 15 |
| Потери supported baseline claims | 36 | 36 |
| Unanswerable cases с packet | 0 | 0 |
| Cases в review queue | 6 | 7 |

Recovered vs corrected evaluator claims: **0**. Newly lost supported claims: **0**.
36 baseline потерь остаются: **32 admission**, **4 discovery/per-source cap**.
Existing literal annotated witness attribution не показывает packing/final loss.
Maximum emitted DTO: **1283**, budget 1500, ≤3 rows, no answer/edit credits.

Два admission transitions, оба на `fastapi-07`:

1. `condition_support_unavailable` → admitted.
2. `condition_support_unavailable` → `no_local_topic_witness`.

Condition refusals на inventory: 25 → 23; остальные admission layers не выключены.

## Новый packet и границы evaluator

Новый `fastapi-07` packet — owning `Dependency Injection` section из
`docs/en/docs/tutorial/background-tasks.md`. В нём буквально есть:

> In this example, the messages will be written to the `log.txt` file *after* the response is sent.

Это альтернативный contextual passage, а не доставленный frozen witness set.
Штатный evaluator возвращает `needs_review` для known timing claim и private tail;
ни одна часть не стала supported, proof/coverage/edit permission не выданы.
**Не считать такой результат успехом retention или доказательством нерелевантности
этого альтернативного текста.** Требуется отдельный source-based review equivalence,
без gold rewrite ради улучшения метрики. В этом задании review не выполнялся.

`fastapi-01` и исходный witness `fastapi-07` сохраняют другие subject/local-demand
refusals. `starlette-03` использует unsupported RU surface и остаётся закрытым.
Точечное compiler исправление не решает общую relevance или namespace binding.

## Решение

- Исправленный generic typed-constraint механизм сохранить **как research result**.
- Не внедрять production: baseline retention не восстановлен, comprehensive
  guard/negative/consumer migration gates не закрыты.
- Не увеличивать budget, не снимать topic veto и не добавлять новые grammar patterns
  автоматически. Дальнейший анализ должен отделять реальные unresolved binding/
  relevance от alternative-witness `needs_review`.
- API 01–04 остаются изолированными, старые candidate/results сохранены.

## Проверки и артефакты

**87 passed**: 18 research tests и 69 existing API/read/constraint/subject controls.
Existing `asyncio_mode` warning не изменился. `git diff --check` без ошибок.
Это не полный production regression.

`v2plan/artifacts/typed-constraints-owner-1500/`:

- `results.json`, `summary.json`, `provenance.json` — 80 results/claims/layers;
- `matrix_controls.json` — native/research contracts + applicability на 17 pairs;
- `paired_comparison.json` — precise admission transitions, recovered/lost claims;
- `compiler_provenance.json` — code hashes, previous-results hash, patch scope/restoration.

```bash
PYTHONPATH=. /usr/bin/python3.12 v2plan/typed_constraint_replay.py --input /home/viadmin/.cache/docatlas-experiments/grounded-budget-20261003-06 --previous v2plan/artifacts/corrected-owner-1500/results.json --output v2plan/artifacts/typed-constraints-owner-1500-NEW
/usr/bin/python3.12 -m pytest -q tests/docs/test_grounded_budget_probe.py
```

Новый output обязателен. Исторические artifacts не перезаписываются; source DB
читается read-only. Commits, rollout и unrelated edits не выполнялись.
