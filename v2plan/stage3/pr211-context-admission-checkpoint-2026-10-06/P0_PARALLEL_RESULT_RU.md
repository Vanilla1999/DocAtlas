# P0: результат параллельной классификации

User-authorized parallel audit завершён и сведен. **P0 ACTIVE: classification/map
work завершена в pinned grouped scope; baseline provenance gate PARTIAL.**
Production/tests/gold не менялись. Technical retain candidates не approved P1
exceptions; REMOVE/SPLIT — решения audit, не выполненная migration.

## Реестр

[Reconciliation runner](p0_parallel_reconciliation.py),
[registry](archives/p0-parallel-reconciliation.json.gz).
Все **1954/1954** ранее REVIEW-REQUIRED units прошли parallel review:
**276 REMOVE, 469 SPLIT, 1209 TECHNICAL-RETAIN-CANDIDATE, local OPEN=0**.
С прежними 568 node-complete и 102 prior owner decisions покрыты **2624 grouped
units / 9874 nodes**. Historical candidate runner counters остаются историей
node-level классификации; новый owner-level registry не стирает nested nodes.
Проверены exact partition union, source pins, hashes, отсутствие duplicates.

Независимый reviewer оспорил два blanket retain proposals: `_symbol_from_line`
и `requirement_probe_query`. В итоговом registry они исправлены на SPLIT;
оригинальные agent outputs сохраняются как evidence, не тихо переписаны.

## Consumers

[Closure assessment](P0_PARALLEL_CLOSURE_ASSESSMENT_RU.md) разобрал 186 union keys:
96 technical/no semantic caller obligation, 38 bounded source roots, 50 known
classified semantic dependencies. Две оставшиеся finite maps затем закрыты:

- [Public attribution map](P0_FINAL_ATTRIBUTION_MAP_RU.md): 24 branches,
  78 hash/span pins, original/lookups/audited rewrites/fallback/joint/final crop.
- [Selector map](P0_FINAL_SELECTOR_MAP_RU.md): 21 branches, 10 facet branches,
  8 profiles/routes, witness → assignment → support/reselection.

Закрыто **как inventory/source map**, не как доказательство правильности semantic
equivalence или будущего replacement. Runtime execution всех branches не заявлен.

## Что мешает поставить P0 DONE

[Baseline linkage](P0_FINAL_BASELINE_LINKAGE_RU.md) нашёл и проверил actual frozen
failure log: README blob mismatch до retrieval. Gold менять не требуется, red
допустим. Но не найдены в обследованном checkpoint:

1. Executed-command/environment/exit record именно для frozen pytest запуска.
2. Same-P0 pinned execution bundle применимых required controls (core/advanced/
   adversarial/CI/release/P1), а не результаты другого HEAD или diagnostic replay.

213 artifact/member и 385 source/config pins совпали. Existing diagnostic traces
и green subsets не подменяют отсутствующий execution provenance.
Следующий шаг: найти exact execution records/CI artifacts и привязать к gate;
новый run оправдан только для конкретного отсутствующего evidence. Не повторять
четыре diagnostic lanes и не менять thresholds/gold ради закрытия.

P1 approval/freeze, packaging исправление, replacement и merge — отдельные этапы.
