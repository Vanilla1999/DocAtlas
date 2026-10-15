# PR #211: current member setup в Agent Developer gates

Дата: 2026-10-08. База `40032f7be3c6d0822e8c25a2e2c53acf9a46aeea`.
В CI 37822521243 Agent V1 остановился в legacy `sync_project_docs` без mutation
grant. Adversarial gate вызвал тот же V1 baseline и остановился там же, ещё до
собственных adversarial cases. Это реальный setup blocker.

Изменены `scripts/run_agent_developer_gate.py`,
`scripts/run_agent_developer_adversarial_gate.py` и один существующий caller
`eval/agent_developer_v1/model_benchmark.py::run_task`. Внутренний `_service` теперь
context manager, который использует существующие `isolated_service` и
`index_project` из `eval/evidence_quality_v2/runtime.py`. Новый общий helper,
production change или dependency на pytest/tests не добавлены.

Каждый прежний TemporaryDirectory по-прежнему получает точную копию своего
fixture. Adversarial setup_files применяются до подготовки, stale mutations —
после неё. ExitStack удерживает current host service и его isolated environment
до завершения всех прежних context/status/retry calls, включая continue/return
и exceptions. Наружу за lifetime service не используется.
Model benchmark получает тот же context lifetime вместо старого `_service(tmp)`;
его planner/provider calls, messages, turn limits и scoring не меняются и
в этой локальной работе не запускаются.

Подготовка выбирает все entries исходного finite catalog; oracle, expected
sources и question в её interface не входят. Catalog/документы не переписываются,
roles и authority не повышаются. Для explicit_manifest_monorepo сохраняются все
четыре entries, включая источники contamination negatives. Хеши catalog,
content, entries и cold CAS проверяет настоящий public prepare_docs transaction.
Новый assert требует отсутствующий cold home до записи, затем полное совпадение
expected/indexed paths, отсутствие excluded/unexpected, members=new_count и
нулевые changed_count/sources_deleted. Реальный store находится вне project.

Старый unsuccessful-sync branch заменён исключением настоящей подготовки или
assertion failure; они завершают gate с ненулевым кодом. Нет catch-as-PASS,
retry с обновлённым CAS, skip/xfail, continue-on-error или отбрасывания cases.
Отсутствующие catalogs у двух legacy fixtures остаются явным FAIL текущего
helper. Этот slice не обещает полного PASS Agent gates и не создаёт membership
автоматически из README/discovery/oracle.

Все прежние result/evaluator assertions сохранены. Public handlers, calls,
question/corpus/oracle files, target thresholds, source contamination, edit
authority, token budgets, retries, metric расчёт и mutation anchors не изменены.
Adversarial mutation по-прежнему требует успешный полный baseline в CI.
Self-host config conflict и semantic recovery/question-surface/critical gates
не изменяются этим slice. Deferred retrieval остаётся без изменений.

Проверены AST и git diff --check. Runtime новой версии локально NOT RUN;
следующий обычный CI должен показать фактическую подготовку и следующий исход.

AST всех statements от `mutation_before_calls` до конца каждого fixture lifetime
совпадает с базой. V1 содержит прежние 0 Assert и шесть новых setup guards; V2 —
те же 14 Assert. Остальные functions, кроме `_service`, `run_protocol`,
`_run_adversarial_case` и model benchmark `run_task`, AST-identical. Все 16 corpus files и diagnostic node
inventories неизменны; добавленные context managers не меняют roster.

| Файл | SHA256 |
|---|---|
| scripts/run_agent_developer_gate.py | 44df846e3ad2bd2989966d48e88650891d72e198b9790931bae888911dd9d480 |
| scripts/run_agent_developer_adversarial_gate.py | d43bcd10626729ccfe2f009a47388d4e173ac3f20261fc85f1a5fe28fb46d4b3 |
| eval/agent_developer_v1/model_benchmark.py | 5fa462f65fce0e5ebddfbdc714571b086009496cc3b4f5f2ed957dc413e43252 |
