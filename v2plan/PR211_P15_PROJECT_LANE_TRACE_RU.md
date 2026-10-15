# PR #211 — same-call trace отдельной project lane P1.5

Статус: report-only observation; actual result после изменения pending.
Base: 38da10d347ae2227eee6d1624db58dbf30938674.

В [P1.5 run 38000724676 / job 114057857626](https://github.com/Vanilla1999/DocAtlas/actions/runs/38000724676/job/114057857626)
mixed question `Explain ProjectRetryRule and TenacityRetryingContract.`
получил project lane not_found/no_reliable_context и library lane no_results.
Текущий top-level pipeline_diagnostics пуст; точный project first-loss из этого
общего результата не следует.

Production ProjectContextResult уже сохраняет project_docs.diagnostics.same_call_pipeline
(`_project_context_service_part01.py`, присваивание после сборки retrieval routing).
Private producer уже измерил planned_query_ids, retrieved_candidates и
qualification_outcomes. Новый fixture observer копирует только эти существующие
поля и существующие result status/context/source identity fields.

Один @wraps observer оборачивает actual.get_project_context и записывает реальные
выбранные scalar/list поля исходных arguments и DTO после единственного исходного вызова. Он возвращает тот
же result object без изменения. Новых retrieval/SQL/network/qualifier calls нет;
original query, lookup list, mode, scope, library/version и производственные
decisions не переписываются. Объект mutation_intent передаётся исходному методу
как прежде, но не копируется в JSON diagnostics.

Новая project запись входит в существующий service_returns. Уже принятый runner
печатает её через body-free formatter для неуспешных случаев. Raw document/text
в этот observer не добавляются; private qualification trace остаётся ограничен
существующим producer limit. Это диагностика, не новая source authority.

Изменён только eval/agent_developer_v1/mixed_retrieval_runtime.py и эта note.
Frozen 7 questions / 13 candidates / 6 facts / 2 negatives, oracle/scorer/verifier,
required CI gates и исторические отчёты не меняются. Точные imported source bytes
по-прежнему связываются existing same-process runtime manifest.

Library metadata fix является отдельным reviewed slice. Document-statement
locator contract здесь не вводится. Local execution/import/AST не выполнялись.
