# PR #211: независимый review setup Agent Developer gates

Дата: 2026-10-08. База: `40032f7be3c6d0822e8c25a2e2c53acf9a46aeea`.
Решение: **APPROVE** для трёх файлов с SHA256 ниже. Это review миграции
fixture setup; результат runtime/Agent acceptance этим решением не объявляется.

| Файл | SHA256 |
|---|---|
| scripts/run_agent_developer_gate.py | 44df846e3ad2bd2989966d48e88650891d72e198b9790931bae888911dd9d480 |
| scripts/run_agent_developer_adversarial_gate.py | d43bcd10626729ccfe2f009a47388d4e173ac3f20261fc85f1a5fe28fb46d4b3 |
| eval/agent_developer_v1/model_benchmark.py | 5fa462f65fce0e5ebddfbdc714571b086009496cc3b4f5f2ed957dc413e43252 |
| eval/evidence_quality_v2/runtime.py — существующий helper, без изменений | 4b5cc5471b6b19ec8ed8f453f1caf937f4590f950f90cf302aedaab846ac9565 |
| v2plan/PR211_AGENT_GATE_FIXTURE_REVIEW_RU.md — author report | 43328b6708d06f1bfc6115e3c3bed00227bb504f8e0b111fc9c94fb64122d0a9 |

## Контракт подготовки и отрицательные ограничения

Прочитан существующий `isolated_service`/`index_project`, а не только новый
вызов. Это cold production factory с host-selected private store вне проекта,
затем настоящий `prepare_docs(action="sync_project_docs", mutation=...)`.
Mutation содержит explicit confirm, выбранный storage path, SHA256 всего
catalog, content hash и catalog entry hash каждого authored member, а также
ожидаемую generation. Проверяются host policy и тот же объект config/store.
Неуспешный transaction завершается исключением; повторного запроса с новым CAS
или обхода consent нет.

Новый `_service` выбирает все entries finite catalog через неизменённый helper.
Oracle, вопрос и expected source set не участвуют в подготовке. Все 16 tracked
файлов `eval/agent_developer_v1/projects` byte-identical базе. Четыре entries
explicit_manifest_monorepo, включая supporting/contamination sources, сохранены
с прежними roles и authority. Catalog не синтезируется из discovery/glob.
Два legacy fixtures без catalog по-прежнему дают явный FAIL. Project
`docatlas.yaml`, roots, code_files, пустой или невалидный catalog отвергаются
существующим helper; эти проверки не убраны.

Шесть новых Assert проверяют cold home до записи, полное совпадение
indexed/expected paths, отсутствие missing/failed и unexpected paths,
members=new_count=числу authored paths и нулевые changed_count/sources_deleted.
Прежняя ветка unsuccessful legacy sync заменена fail-closed исключением или
assertion failure; setup failure не превращается в PASS/skip и не исключает
case из условия успешного gate.

## Lifetime и все callers

Во всех трёх callers `ExitStack` находится в том же `with`, после прежнего
`TemporaryDirectory`. Он входит в `_service(tmp, project)` и выходит до
удаления project; context остаётся активен для всех прежних read/status/retry
вызовов, return/continue и exceptions. Adversarial setup_files по-прежнему
предшествуют transaction, stale mutations по-прежнему выполняются после него.
Существующий helper сериализует environment через RLock, задаёт isolated HOME,
XDG и DOCATLAS paths, offline/no-auto-vectors и восстанавливает весь environment
при выходе. Его существующий registry временных home для replay не изменён.
Внешние finally всех трёх callers AST-identical базе.

Независимый полный поиск охватил 1254 Python paths, разрешение alias imports и
прямых imports `_service`. Найдены пять импортёров V1 gate: adversarial gate,
model_benchmark, installed_mcp_contract, installed_mcp_benchmark и
test_product_scope. Только первые два используют `_service`; оба переведены
на новый context manager. Внутренний V1 caller также переведён.

Первоначально review обнаружил пропущенный `model_benchmark::run_task`:
старый `_service(tmp)` после смены сигнатуры давал бы TypeError. Третий файл
устраняет именно этот дефект. `GitHubModelsPlanner`, его provider/client вызовы,
action validation, сообщения, лимиты turns/calls, scoring и отчёт не изменены.
Передаваемый planner/token создаётся прежним кодом; его исполнение в рамках
этого review не запускалось.

## Статические проверки сохранения gate

AST comparison против базы подтвердил:

| Файл | Изменённые functions | Assert до → после |
|---|---|---|
| V1 gate | `_service`, `run_protocol` | 0 → 6 |
| V2 adversarial gate | `_run_adversarial_case` | 14 → 14 |
| model benchmark | `run_task` | 0 → 0 |

Ни один прежний Assert не удалён. Остальные functions/classes/constants и
module statements, кроме перечисленных functions и добавленных imports,
AST-identical. Прежние imports сохранены. Во всех трёх fixture lifetimes
весь AST начиная с `mutation_before_calls` и до конца тела совпадает с базой:
handlers, evaluator, отрицательные controls, thresholds, source contamination,
edit authority, budgets, retries, mutation anchors и итоговые метрики сохранены.
Первый TemporaryDirectory context item также совпадает с базой.

`ast.parse`, компиляция AST без исполнения и `git diff --check` — PASS.
Локальные imports репозитория, pytest, provider/model calls, installations и
runtime subprocesses не выполнялись. Требуется обычный CI на опубликованном
конечном SHA. Оставшиеся missing catalogs и отдельные semantic/retrieval gates
не считаются закрытыми; deferred retrieval и workflow не изменены этим slice.
