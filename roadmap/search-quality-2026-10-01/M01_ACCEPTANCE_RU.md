# M0 / M1 — приёмка

Baseline плана: `d521b358` (runtime соответствует `acf9a277`).
Приёмка относится к inventory и совместимому metadata extraction, **не** к
удалению всех языковых зависимостей и не к M2–M6.

## M0 — закрыт в scope inventory

- [x] Production caller inventory: `check_m0_inventory.py` → `m0_inventory.json`:
  **58 call sites, 15 definitions** на 14 boundaries.
- [x] Source-reviewed цепочка MCP → routing → planning → retrieval/tagging →
  ranking/need selection → visible-window projection → public output.
- [x] Учтены compatibility wrapper, hint qualification и callback consumers:
  variant retention, support units, continuation/recovery bridges.
- [x] Eligibility, text exclusions, relevance и semantic support классифицированы
  в `M0_READ_PATH_INVENTORY_RU.md`; intent-generated forbidden words не названы
  security policy.
- [x] Read/library/patch lanes разделены; `test_public_read_library_and_patch_branches_remain_separate`
  выполняет публичный handler с контролируемой facade и real projection spies.
- [x] Scope/version/snapshot/reference guard owners указаны; новая metadata
  функция не объявлена заменой их validators.

Static inventory не доказывает выполнение всех динамических branches и не
выявляет произвольные alias calls автоматически; callback consumers просмотрены
отдельно. Controlled routing trace — без настоящего retrieval backend.
Quality protocol/model selection относится к M3 до эксперимента, а не к runtime
изменению M0. Независимые multilingual gold данные ещё не созданы: M3 не закрыт.

## M1 — закрыт как совместимый extraction

- [x] Existing metadata checks вынесены без изменения порядка/reasons;
  wrapper сохраняет text/catalog exclusions для всех legacy callers.
- [x] Language-invariance и negative metadata mutations проверены.
- [x] **7 686** policy comparisons с actual baseline функцией совпали.
- [x] Чистый baseline worktree сравнивается с отдельным worktree, содержащим
  **только M1**, без M2 правок: `m1_isolated.patch`.
- [x] Одинаковый 212-case набор на обоих: **211 passed, 1 failed**;
  один и тот же известный `flow_mcp` failure. Новый regression не обнаружен.
- [x] Non-empty original/lookup/exact-path projection fixtures дают одинаковые
  полные payload и snapshot hashes в baseline и isolated M1.
- [x] Текущий guard/reference/trust/patch набор: **177 passed**.
- [x] Defaults, budgets, permissions, retrieval/model/provider M1 не меняет.

## Артефакты

- `m0_inventory.json`, `check_m0_inventory.py`;
- `m1_isolated.patch` — точный isolated runtime diff;
- `m1_control_tests.log`, `m1_isolated_tests.log`;
- `m1_control_projection.log`, `m1_isolated_projection.log`;
- `m01_guard_tests.log`, `check_metadata_boundary.py`.

Control: `/tmp/opencode/docatlas-m1-control`, clean `d521b358`.
Isolated M1: `/tmp/opencode/docatlas-m1-baseline`, тот же HEAD плюс extraction.
Python: `/home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python`.
Production imports идут из cwd каждого worktree через `PYTHONPATH=.`.

## Ограничения не скрыты

Существующий baseline `flow_mcp` failure не исправлен и не превращён в PASS.
Приёмка M1 — отсутствие наблюдаемой регрессии при extraction, не зелёный продукт.
Три DTO fixtures не доказывают эквивалентность каждого возможного packet.
Installed-wheel/stdio, multilingual recall, host answers и holdout acceptance
не выполнялись: это дальнейшие gates, а не результат M0/M1.

M2 изменения остаются отдельно в текущем worktree, не входят в isolated M1
доказательство. M2–M6 не закрыты; шаг 07 открыт, шаг 08 не начат.
При этой приёмке новые commits/push/merge не выполнялись.
