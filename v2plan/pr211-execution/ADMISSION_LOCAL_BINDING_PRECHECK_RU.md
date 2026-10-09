# PR #211: precheck текущего default/local-binding контракта

Статус: **precheck, без retirement**. Все 16 прежних test definitions / 43 expanded cases остаются collected.
Base: `38da10d347ae2227eee6d1624db58dbf30938674`.
Production, retrieval и старый diagnostic shard не изменяются.

## Причина и текущий контракт

[Фактический JUnit reader на 0855 / run 37996655986](https://github.com/Vanilla1999/DocAtlas/actions/runs/37996655986/job/114047940486)
показывает для `tests/docs/test_admission_local_binding.py` **42 FAIL / 1 PASS / 0 ERROR / 0 SKIP**.
Первый failure — `test_direct_default_statement_is_a_witness[RelayClient-7]`, `assert None is True`.
Это исторический runtime receipt. На base 38da общий core остановился на отдельной ошибке collection импортируемого helper; этот precheck не выдаёт его нули за новый успешный baseline.

Действующий domain API явно отменяет вывод property/owner/default/условия/anaphora из prose:

- `default_property(query)` и `bound_default_units(query, text)` возвращают `None`;
- `default_local_witness(query, text)` возвращает `(None, ())`;
- `retrieval_need_local_witness` сохраняет этот tri-state.

`None` означает отсутствие поддержанного semantic proof. Он отличается как от доказанного default (`True`), так и от semantic refutation (`False`).
Legacy subject/relation/title metadata не превращают текст в поддержанную semantic assignment.

Adapter `apply_retrieval_need_witness` обязан отклонить прежде qualified retrieval_need при unknown proof, убрать унаследованный need witness/context credit и сохранить постороннюю диагностику.
Для original/host_lookup lane он возвращает исходные trace values без изменения. Этот positive control нужен, чтобы реализация, стирающая всё подряд, не проходила только благодаря отрицательным checks.

Exact domain source: `86c67187b049e69ea30ff5fd4f3bc490fe641e68`.
Exact adapter source: `c08744ccd1b20f3c2acd10b6b8f2681840a0396a`.

## Независимый current control и сохранение входов

Одна новая функция:
`test_current_default_binding_keeps_unknown_without_inherited_need_credit`.

Она читает frozen archive как AST и допускает только конкретные формы исходного fixture:
literal/parameter/f-string/строковое сложение/dictionary/query assignment и один известный fixture-query call.
Reader не импортирует и не исполняет старые tests или helper. Исторические `is True`, `is False`, `is not True` хранятся только как часть frozen input identity, без использования в качестве новых ожиданий.

Сохранены все **43** исходных question/body/source records, включая составные свойства, локальные layouts, условия, polarity/owner changes, anaphora и неподдержанный хвост.
Current expected DTO/trace fields заданы независимо. Проверяются input immutability, точные строки/hash values, unknown ABI и отсутствие inherited proof credit.

- Archive — exact blob `f0d3676dc20f9b4785715405f4f6ced401c1df6f`.
- Source SHA-256 — `e3eec4a7f10584855352228cca65972f2747bb81e7d3693ec3253ac24ebcc676`.
- Frozen 16-function roster SHA-256 — `13fd8cc50b80d3811f842d5cffe4315f823844615786bcf4bd3d5aa7d81ca286`.
- Frozen 43-input roster SHA-256 — `2a1fd29dd230996a3621651b0829bf067d961f3919fa50a8e68b17372759dac3`.
- New control node hash — `7ef9e89d4840e644631e9e4bc77811b280a9e374f6de4309cfdc28e3ce8b94b4`.

Содержательный `test_recognized_condition_does_not_hide_unsupported_constraint_tail` и его `default_need` helper сохраняются побайтно в исходном модуле; current control дополнительно сравнивает их AST с archive.
Все остальные 42 старых cases также остаются collected в этом slice.
Будущий retirement требует отдельной проверки внешних fixture imports/consumers и selectors; этот precheck не утверждает, что таких импортов нет.

## Четыре адресные production mutations

| Mutation | Реальное изменение | Первый ожидаемый guard |
| --- | --- | --- |
| default_binding_unknown_not_true | domain witness `(None, ())` → `(True, ())` | critical_default_binding_unknown_abi |
| default_binding_unknown_not_false | domain witness `(None, ())` → `(False, ())` | critical_default_binding_unknown_abi |
| default_binding_unknown_cannot_qualify | unknown branch adapter `qualified=False` → `True` | critical_default_binding_unknown_veto |
| default_binding_nonneeds_not_erased | initial `dict(trace)` → `{}` | critical_default_binding_nonneeds_preserved |

Каждый source anchor имеет ровно одно совпадение; crosswalk хранит exact old/new blocks и независимо проверенные before/after SHA-256.
Оба изменяемых production modules добавлены в существующую import-identity inventory.
Original/host_lookup positive проверяется первым, затем неизвестный default ABI и adapter veto: каждый fault должен дать именно свой named guard.

Critical normal gate расширяется **31 → 32 baseline cases**, **9 → 13 mutants**.
Каждая новая mutation должна иметь **1 test / 1 expected FAIL / 0 ERROR / 0 SKIP** после зелёного normal baseline.
Весь runner после `def _ignore`, включая literal comparison, проверку intended killer и failing-baseline JUnit diagnostics, сохранён побайтно.
Старый source module и его прежняя diagnostic registration не меняются.

## Exact manifest

| Файл | Base blob | Proposed blob | Mode |
| --- | --- | --- | --- |
| tests/docs/test_admission_local_binding_contract.py | NEW | e9fe37b22014e57e9998667dbc5aacf573d19b15 | 100644 |
| scripts/run_critical_mutation_gate.py | 769c961ebebc40c31b49d7fa6fb15d13c15df5b3 | c0a3b41ef9f52a8104d5c2fe24e44642ce33134b | 100755 |
| eval/task_level/contract_history/admission_local_binding.py.txt | NEW | f0d3676dc20f9b4785715405f4f6ced401c1df6f | 100644 |
| eval/task_level/contract_history/admission_local_binding.json | NEW | f6df59efd8704264a9c223e57a172f45806c0702 | 100644 |
| tests/diagnostic_labels.admission_local_binding_contract.json | NEW | 3160f6017b021fabee6eeb5df563f4a79e7f7b3d | 100644 |

Static independent review пяти code/data blobs завершён: отдельно восстановлены 43 input records и их digest, source/roster hashes, четыре mutation before/after hashes и точность runner inverse diff.
Новый control содержит 253 строки, runner 693 строки. Это учёт размера, без нового size/token ceiling.

## Acceptance перед любым сокращением

Нужны review опубликованного source tree, actual **32 PASS / 0 FAIL / 0 ERROR / 0 SKIP**, все **13 intended mutation kills**, отдельный full core и сохранение живого tail guard.
Runtime receipt должен различать PR head и фактический Actions checkout, с явно проверенным совпадением деревьев либо точным описанием различий.
Пока такой receipt не получен, удаление старых 42 cases не разрешено этим precheck.

Fixture/literal/trace property не доказывает retrieval quality, source authority, finite membership, body fidelity или installed/client delivery: их реальные gates сохраняются.
Локальные imports/tests/subprocesses не выполнялись. Commits/refs не создавались.
