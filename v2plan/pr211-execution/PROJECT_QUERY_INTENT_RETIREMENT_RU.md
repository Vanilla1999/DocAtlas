# Project query intent: retirement после actual proof

## Изменение

Удалены только пять classifier-only functions / **31 expanded cases** из `tests/docs/test_project_query_intent.py`. Один mixed test `test_documentation_files_do_not_imply_code_symbol_evidence` остаётся collected. Его полный function block, все вопросы, source texts/scores, исходная `release_history` premise и оба ranking assertions сохранены побайтно. Нужные imports и `fake_chunk` сохранены; убран лишь неиспользуемый после удаления decorators import pytest.

Этот retirement уменьшает уже расширенную precheck-сборку с 33 до 2 cases. По отношению к исходному семейству до добавления нового control итог **32 → 2**, net **−30**. Один remaining mixed case и один доказанный current-contract control — отдельные collected nodes.

## Реальное evidence

[Advanced job 114035684048](https://github.com/Vanilla1999/DocAtlas/actions/runs/37994136625/job/114035684048), run `37994136625`, attempt 1, подтверждённый PR head `2acfaa4fdac8cc599d84ae1c48836335e9cd29a7`:

- Normal critical baseline: **30 PASS / 0 FAIL / 0 ERROR / 0 SKIP**, exit 0.
- Все **8 intended production mutants killed**; normal critical section завершилась PASS.
- `project_query_intent_no_inferred_roles`: anchor count 1, actual **1 test / 1 FAIL / 0 ERROR / 0 SKIP**, exit 1.
- Intended killer: `tests/docs/test_project_query_intent_contract.py::test_current_project_intent_preserves_literals_and_never_infers_roles`.
- Exact guard: `critical_project_intent_no_inferred_roles`.
- Baseline roster SHA-256: `e1e594cd89c78e4c812b9b7c5ae713808041c57e3a84dd9ed4012b52df3618f9`.
- Mutant roster SHA-256: `5543c4fc19c6dad0e4853efcb14590f43d3b23eaa50c329d52e5119da8415ea4`.

Весь CI run имеет conclusion failure из-за остальных gates. Этот proof разрешает узкий retirement classifier expectations; он не делает mixed ranking test или полный acceptance зелёными. Legacy premise оставшегося теста требует отдельного review/migration.

## Сохранность и exact manifest

| Файл | Base blob | Proposed blob |
|---|---|---|
| `tests/docs/test_project_query_intent.py` | `73505df55c4533e2426c460f9b26ad8517179a5c` | `331f3c1918a554142aec69cd2450e73620bc8948` |
| `tests/diagnostic_labels.json` | `1358fda27ea28e14919f3556c1e62ec5839a6413` | `ce99caa7cf3372ba754e4efde5d72d26e33ecfea` |
| `eval/task_level/contract_history/project_query_intent.json` | `af69b43d49771697bbc266872105058e41ba77d7` | `75cdda23bbbb1e4864a754cfd53bf211739f5bf5` |

Рабочий модуль — 43 строки, один исходный test node. SHA-256 всего сохранённого function block: `6f6a60601566a0660ae4307ef5b7982773c4baefd85f3cc794a014192ca0df43`.

Archive `project_query_intent.py.txt` остаётся exact blob `73505df55c4533e2426c460f9b26ad8517179a5c`. Frozen source descriptor, все шесть roster entries, их исторические строки/actions/counts и frozen roster hash `fc5f914afdd9fb2458620b3a2486bfa3517fd14d74712f08cd068f28db7b8975` не изменены. Новый control продолжает проверять архив и substantive working ranking AST.

В diagnostic manifest изменён ровно один `module_node_hashes` value — на `b59c81023d1f4a1bd0c7b09e028d6988a51d06e93fe72492f47a4e25b2dca1e5`. Behavioral label сохранён, node overrides для удаляемых функций отсутствуют. Replacement control/shard и critical runner этим slice не изменены.

## Сборка и границы проверки

Проверены current `ci.yml`, `direct-question-validation.yml`, оба Task33 workflows, pytest/config/conftest, diagnostic loader/tests, critical runner и module-size checker. Удаляемые node selectors в этой обязательной цепочке отсутствуют; core jobs собирают каталог tests, normal critical вызывает сохранённый replacement control. Сам старый module path остаётся доступен.

Локальные import/pytest не выполнялись. После публикации нужны повторная сборка diagnostic inventory, replacement control и общий acceptance на конечном SHA. Production/retrieval и оставшийся ranking guard не изменены.
