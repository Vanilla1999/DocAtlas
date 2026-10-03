# Исправленный isolated owner candidate — один прогон при 1500

2026-10-03. **Выполнено, production не изменён, replacement не принят.**

## Решение

Case handling research adapter действительно было неверным. Исправление этой
ошибки **не восстановило ни один ранее потерянный supported baseline claim**.
Основной блокер остаётся native admission; повышение budget или очередная
перестройка selector не объясняют оставшиеся потери.

Следующая отдельная задача — проверка temporal-question vs applicability-condition
и reason-contract mismatch, не снятие topic/condition veto. В этом прогоне
grammar/thresholds/aliases/relations не менялись. 01–04 сохраняются изолированно.

## Что именно исправлено

Новый `corrected_admission_probe.py`, исторический `grounded_budget_probe.py`
и старые artifacts не переписаны.

- Case handling в отдельной diagnostic literal/subject проверке соответствует
  existing native qualification: normalized term проверяется в casefolded body.
- Source-bound subject допускает verified actual owner header через existing
  reference binding; source catalog/path не служит namespace certificate.
- Required literals остаются самостоятельным body requirement: owner не заменяет
  requested symbol occurrence.
- Conditions и topic измеряются независимо в layers JSON, даже при раннем отказе.
- Окончательный native `read_context_admission` veto сохранён **без изменений**:
  corrected candidate не разрешает окно, которое native read отказывает.
- Structural/source/hash/request/window checks и final DTO validator сохранены.

Это исправленный research adapter, **не новый полноценный general read predicate**.
Independent topic diagnostics не подменяют authoritative native topic decision.
Condition unknown не превращается в applicable, typed proof не выдаёт read credits.

## Paired условия

Все **80 frozen cases**, включая positives/partial/unanswerable/ambiguous/over_budget.
Только owner policy, только **1500 whole-DTO units**. Ни нового FTS query, ни новой
сетки budgets. Использованы те же archived hits, native order, source generation,
reference plans, proposals/IDs. Inventory IDs сверены с историческим owner 1500.
Source snapshot bytes сверены с frozen corpus. Archived SQLite открывается read-only.

Selector и serializer — прежние research functions. Новые annotations не передаются
в admission. Gold используется только после selection для оценки и attribution.
Baseline native payload 800 берётся из того же historical fixture archive.

## Результат

| Метрика | Исторический owner 1500 | Исправленный owner 1500 |
|---|---:|---:|
| Cases | 80 | 80 |
| Непустые packets | 17 | 18 |
| Supported required claims | 15 | 15 |
| Baseline supported claims | 49 | 49 |
| Baseline supported claims, потерянные candidate | 36 | 36 |
| Unanswerable cases с packet | 0 | 0 |
| Cases с evaluator review queue | 5 | 6 |

Recovered vs historical supported: **0**. Newly lost vs historical supported: **0**.
Новый packet — `ruff-02`, required claim `needs_review` (unrecognized relation),
не supported. Его наличие нельзя считать восстановлением fact или negative Green.
Maximum emitted corrected DTO — **1283 units**; все emitted packets проходят
existing final validator при 1500. Zero unanswerable packets не заменяет полную
negative/guard matrix.

36 baseline потерь:

- **32 admission:** annotated witness найден/proposed, но не admitted;
- **4 discovery pool:** прежний cap двух passages на source;
- **0 packing/final:** увеличение final budget не исправляет эти потери.

Все прежние six partial baseline losses сохраняются:
`fastapi-07`, `httpx-07`, `mkdocs-07`, `starlette-07`, `typer-07`, `uv-07`.
Полный claim-ID список и attribution сохранены в `summary.json` / `results.json`.

## Куда перешли прежние 78 missing_exact_or_subject first veto

Количество proposals, не claims. После normalized separate checks:

| Новый отказ/решение | Proposals |
|---|---:|
| missing_bound_subject | 11 |
| missing_exact_terms | 38 |
| no_local_topic_witness | 21 |
| condition_support_unavailable | 6 |
| missing_local_demand | 1 |
| admitted | 1 |

Таким образом, bug исправлен, но за ложным первым отказом обычно скрывался другой
native veto. Нельзя считать все эти 78 proposals false negatives одного слоя.

Все corrected inventory refusals: missing_bound_subject 11, missing_exact_terms 39,
no_local_topic_witness 168, condition_support_unavailable 25, missing_local_demand 4,
verified_local_demand 1. Admitted proposals 21; затем budget/source-row selection.

## Проверки

- **13 research tests passed**, включая uppercase body → correction, question echo
  → native veto, wrong API → отказ, forged bytes → source rejection, verified owner,
  wrong/forged owner и owner не заменяет hard body literal.
- **69 existing controls passed:** 01–04 APIs плюс read boundary, constraint roles,
  source-bound subject. Итого выбранные проверки: **82 passed**.
- Existing warning `asyncio_mode` остаётся environment warning.
- Не полный paired regression, не rollout Gate и не semantic completeness proof.

## Сохранение и повторение

`v2plan/artifacts/corrected-owner-1500/`:

- `results.json` — 80 final packets/abstentions, separate layers, historical traces,
  claims/attribution и assessment;
- `summary.json` — baseline losses, IDs, recovered/lost claims, review/negative cases;
- `provenance.json` — input SHA256, frozen protocol и четыре code hashes.

```bash
PYTHONPATH=. /usr/bin/python3.12 v2plan/corrected_admission_probe.py --input /home/viadmin/.cache/docatlas-experiments/grounded-budget-20261003-06 --output v2plan/artifacts/corrected-owner-1500-NEW
/usr/bin/python3.12 -m pytest -q tests/docs/test_grounded_budget_probe.py
```

Output должен быть новым. Исходные candidate/results, runtime, frozen gold и
чужие experiments сохранены. Никаких commits, production budget changes или rollout.
