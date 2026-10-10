# PR #211: наблюдение фактического library/mixed return в P1.5

Статус: диагностический slice; production и provenance oracle не меняются.
Base commit: `0855fb491ec388100cce92e57fe64b889c4cd3e0`.

## Наблюдавшийся пробел

В обычном [P1.5 run 37996655934 / job 114044350172](https://github.com/Vanilla1999/DocAtlas/actions/runs/37996655934/job/114044350172)
результат на 0855: 2/7 cases, 0/6 verified facts, 0 runtime errors; 6/6 oracle self-controls прошли.
У `dependency_fact_prefers_dependency_docs` и `two_claims_require_two_allowed_roles` источников нет,
а сохранённый `pipeline_diagnostics` пуст. При этом actual retrieval/validation wrappers зафиксировали по одному вызову;
preparation, authority и state-difference checks не дали ошибок.
Это не позволяет назвать причину отсутствия library факта либо сделать вывод, что library retrieval вообще не выполнялся.

Сверенный source trace объясняет ограниченность observer:
`context_tools.py` при раннем explicit delivery veto вызывает `_observe_same_call_diagnostics`
только для `docs_context`. Explicit library/mixed запрос получает `docs_answer` и может вернуться раньше этого observer.
Само условие не доказывает, какой actual reason/status дал конкретный P1.5 case.

## Изменение

Существующий runtime wrapper сохраняет выбранные поля уже возвращённого unified DTO:
status/reason/mode, доступность context/answer, delivery decision, lane statuses и source identities.
Два дополнительных прозрачных wrapper наблюдают только реально происходящие `resolve_library` и `get_docs` вызовы:
они вызывают исходный bound method ровно один раз и возвращают тот же объект без изменения.

Library observation хранит фактические status, registry identity/version/local/stale;
для существующих result chunks — только source URL и lineage без document text.
Из уже возвращённых retrieval diagnostics копируются requested/used/post_guard, а из index witness — status/reason.
Никакой stage или qualification не вычисляется повторно. Отсутствие вызова остаётся пустым списком.

В failure-only CLI log добавлены эти service returns и выбранные поля уже сохранённого public result.
Существующий body-free renderer продолжает заменять текстовые body fields на длины/SHA-256.
Полные source bodies или произвольные DTO `__dict__` не сериализуются; поля выбраны явно.

Public request, single public call, finite HTTP allowlist, preparation, cold/read ordering, source snapshot,
state hashes, frozen questions/facts/source roles, oracle, cost assessment и verdict не меняются.
Ни одного production call для диагностики вне исходного пути не добавлено.
Служебный report/log растёт; стоимость публичного DTO оценивается прежним способом.

## Exact manifest

| Файл | Base blob | Proposed blob | Mode |
| --- | --- | --- | --- |
| eval/agent_developer_v1/mixed_retrieval_runtime.py | a384e125bb208eb2f8902fe62a4b98a5d4e73590 | 7f3897bf3d410b7a6433b8563b23166c7b117a54 | 100644 |
| scripts/run_mixed_evidence_provenance_gate.py | 7daab9ebeb8cdb7ff6839a13912641403d4a889b | 52fa2b86b3d5ca6aea831bbcd1b1d648dccf167b | 100644 |

Статически проверены точечные anchors и полное восстановление каждого base обратной заменой.
Нужны независимый static review и обычный P1.5 job на опубликованном SHA.
Новые runtime результаты не заявлены; локальные imports/pytest/subprocesses не выполнялись.
