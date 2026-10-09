# PR #211: retirement отменённых admission-meaning ожиданий

Статус: узкое сокращение после фактического normal critical proof. Следующий full core обнаружил ошибку collection из-за удалённого общего helper; ниже зафиксировано её восстановление. Acceptance на конечном SHA ещё требуется.
Base retirement: `a348cafb4807a5b4af852e0029cf6b98ff7a3f91`.
Base helper fix: `38da10d347ae2227eee6d1624db58dbf30938674`.

## Полученный runtime proof

[CI run 37998331818, attempt 1 / advanced job 114049950632](https://github.com/Vanilla1999/DocAtlas/actions/runs/37998331818/job/114049950632),
шаг **Run critical mutation gate** для опубликованного PR head. Фактический GitHub checkout — PR merge commit; совпадение source tree независимо проверено:

- PR head SHA: `a348cafb4807a5b4af852e0029cf6b98ff7a3f91`.
- Фактический checkout commit SHA: `0e84988d21bb06a86c14714e077098e5cf0cb5d9`.
- Checkout tree и PR head tree: `8e10b447f3f6d7e8ee09ac5e1de05f73eacd6ad4`, **полностью равны**.
- Родители merge checkout: `d2ed5c4c73dc3b7d56276fc37591cba8a4ae123c` и указанный PR head.
- Normal baseline: **31 PASS / 0 FAIL / 0 ERROR / 0 SKIP**, return code 0.
- Все **9 target production mutants** получили ожидаемые kills; итог normal gate — PASS.
- `admission_meaning_no_inferred_equivalence`: один production anchor, **1 test / 1 FAIL / 0 ERROR / 0 SKIP**, return code 1.
- Killer: `tests/docs/test_admission_meaning_contract.py::test_current_admission_meaning_preserves_literals_without_inferred_equivalence`.
- Точный guard: `critical_admission_meaning_no_inferred_equivalence`.
- Normal baseline roster SHA-256: `2452628f600f2730e2491a23666561137b3a3d8c2d6bf4dacbee6db9cb58c424`.
- Admission mutant roster SHA-256: `47cf9c22cb0a4a9a60c6d498876dd2b3d51044c1cd1cf05652c9235690042d81`.

Proof прочитан из normal `EVIDENCE`, `KILLED` и успешного шага, отдельно от historical/compact comparison.
Checkout SHA подтверждён actual job log; оба Git commit tree независимо прочитаны через GitHub. Runtime receipt относится к merge checkout с теми же исходниками, что у опубликованного PR head.
Mutation меняет реальный `same_supported_meaning` с False на True; одинаковые caller-supplied complete slots первыми нарушают именованный guard.
Это достаточное основание для данного retirement, но не полный CI и не готовность PR к merge.

## Что убрано

Только пять функций, чьи положительные предпосылки требуют отменённого semantic compiler:

| Исходная функция | Cases | Сохранённое обязательство |
| --- | ---: | --- |
| test_supported_ru_en_frames_preserve_roles | 8 | Исходные RU/EN bytes, полный unknown DTO, raw spans |
| test_changed_arguments_conditions_and_unparsed_tails_are_not_audited | 10 | Все пары, условия/хвосты и отсутствие semantic equivalence |
| test_quoted_literals_and_original_offsets_are_preserved | 6 | Все шесть literals, explicit identities, casefold/hard_exact и исходные координаты |
| test_actual_query_planner_emits_original_derived_need | 5 | Original query остаётся отдельной direct lane с исходными bytes |
| test_only_fully_verified_reformulation_can_derive_original | 1 | Original/good/changed bytes и отдельные host_lookup lanes без parent credit |

Эти обязательства проверяет уже прошедший независимый current control.
В quoted `for` connective [14, 17) и quoted occurrence [19, 22) различаются по исходным координатам.
При retirement current control, его finite-reference positive/foreign/prefix/missing/incomplete/ambiguity checks и directed production mutant не менялись. Follow-up ниже усиливает только сохранение двух общих fixture helpers по frozen AST.

`pytest` import удалён. `demand()` был ошибочно признан неиспользуемым по локальным вызовам: его импортирует другой collected module. Follow-up восстанавливает этот helper побайтно, включая исходное assertion; поведение потребителя не меняется.
В рабочем модуле сохраняются точные прежние `demands()` и `demand()`, необходимые imports и все четыре содержательных функции:

- `test_unknown_question_does_not_disappear`;
- `test_question_with_an_unsupported_second_clause_is_not_fully_supported`;
- `test_arguments_with_and_or_are_not_made_equivalent`;
- `test_mismatched_reference_plan_cannot_verify_a_rewrite`.

Весь contiguous block этих четырёх функций и оба helper сохранены без изменения bytes относительно frozen archive.
Current control сравнивает AST каждой живой функции и обоих shared helpers с frozen archive.
Это проверка сохранения исходников; runtime этих четырёх guards остаётся самостоятельным обязательством общего CI.

## Учёт и сохранение истории

Рабочий legacy module: 9 definitions / 34 cases → **4 definitions / 4 cases**.
Вместе с неизменным independent control семья имеет **5 collected cases** вместо 35 до retirement.
Сокращение — **30 cases**, без отключения live guards.

Frozen archive остаётся blob `87434b28d5460eae97f7d59ed763e4a8a65aadbf`,
SHA-256 `3ecadb74c344ba2613adcf8a1c5ecbc937a8f42e77a88e538972102238dedfd7`.
Все девять historical roster entries, source lines, case counts, action mappings и frozen roster hash сохранены.
Crosswalk меняет текущий статус/scope, добавляет actual proof и точный retirement ledger.

В `tests/diagnostic_labels.admission_contract.json` меняется только module node hash:
`9a6c79966a0235648037cce467c4aacb47825e19db9837d24221cc342afd588a` →
`964abdbdef8f5e41b0107bdb9fd757842d8296ebbbb986a2473d520fa434af1b`.
Label остаётся behavioral; основной diagnostic JSON и другие регистрации не меняются.

Исходный module path сохраняется.
Проверены current core/direct-question/Task33 workflows, pytest configuration, inventory hook и critical runner:
в этой acceptance цепочке нет явного selector на одну из пяти удаляемых функций.
Это не утверждение об отсутствии historical references во всём репозитории; archive/crosswalk ссылки намеренно остаются.

## Exact manifest retirement (исторический)

| Файл | Base blob | Proposed blob | Mode |
| --- | --- | --- | --- |
| tests/docs/test_admission_meaning.py | 87434b28d5460eae97f7d59ed763e4a8a65aadbf | 307457b4704847a20ae67c3f043def715192fec9 | 100644 |
| tests/diagnostic_labels.admission_contract.json | c7296179030f7bac424638eda24cdce43611bae9 | a429929eb2ae3cbdb53b201eb4a0605b512a8990 | 100644 |
| eval/task_level/contract_history/admission_meaning.json | 4c85b843c096df3612588c30a8d7dc4efb9aee5c | 1d302adcc304e71207d61329bc2243a0f42f1ca4 | 100644 |

В момент retirement current control имел blob `ddecc43b1cbd744b9f1e47d5d48a22c37f03a371`.
Critical runner остаётся `769c961ebebc40c31b49d7fa6fb15d13c15df5b3`.
Production/retrieval, frozen source bodies/questions и source-binding/quality/installed/client obligations не меняются.
Нужны independent review и обычные acceptance jobs на конечном опубликованном SHA.
Локальные imports/pytest/subprocesses не выполнялись; commits/refs не создавались.

## Follow-up: восстановление общего fixture helper

[Full core Python 3.11 / job 114057857971](https://github.com/Vanilla1999/DocAtlas/actions/runs/38000724569/job/114057857971)
на PR head `38da10d347ae2227eee6d1624db58dbf30938674` завершился collection ERROR:

`tests/docs/test_admission_mapping_assignments.py:5` импортирует `demand` из `tests.docs.test_admission_meaning`.
Фактическая ошибка — `ImportError: cannot import name 'demand'`.
[Общий JUnit reader 114058136097](https://github.com/Vanilla1999/DocAtlas/actions/runs/38000724569/job/114058136097)
подтвердил для каждого Python 3.11/3.12/3.13 **0 PASS / 0 FAIL / 1 ERROR / 0 SKIP**, integrity issues пусты.
Это остановка collection; нули не означают прохождение остальных тестов. Historical 31/9 normal critical proof выше остаётся историческим и не заменяет полный прогон.

Восстановлен ровно исходный `demand()` из frozen blob `87434b28d5460eae97f7d59ed763e4a8a65aadbf`.
Удаление только этого добавленного блока побайтно восстанавливает предыдущий working blob `307457b4704847a20ae67c3f043def715192fec9`.
SHA-256 restored helper с завершающим LF — `5f2d41e36c2adee81b294a78316736955076abf575ab5c934a9149561f7b162b`.
Точный new working SHA-256 — `8fa012052657ab5e6426a677ae8e0a338c207aee39c070af9f581556ee892fe9`.

Current control дополнен сравнением AST `demands` и `demand`; раньше он сохранял только четыре test function AST.
Test names, collected case counts, module node hash, diagnostic shard, frozen source/roster и historical runtime receipt не изменены.
Проверен конкретный внешний consumer, blob `af245d2112267b68a9a55b9873a034e7462481e9`; это не exhaustive inventory всех импортов репозитория.
Работа остальных legacy mapping assertions и новый full core остаются runtime обязательством: восстановление импорта не объявляет их PASS.

| Файл | Base blob на 38da | Proposed blob | Mode |
| --- | --- | --- | --- |
| tests/docs/test_admission_meaning.py | 307457b4704847a20ae67c3f043def715192fec9 | add20a09db326dbb6497017b01b38b28b3f0129a | 100644 |
| tests/docs/test_admission_meaning_contract.py | ddecc43b1cbd744b9f1e47d5d48a22c37f03a371 | ff3e04a9ea4c5917908a1ea8c5dc2a2cae8781ae | 100644 |
| eval/task_level/contract_history/admission_meaning.json | 1d302adcc304e71207d61329bc2243a0f42f1ca4 | a94ff790f90afd6f3d11fdca24c2def86dbfb435 | 100644 |

Crosswalk обновляет только текущий working hash, сохранение shared helpers и честный integration-failure ledger.
Ни один старый вопрос/assertion потребителя, production source, selector или critical mutant не изменён.
Локальное выполнение отсутствует. Нужны independent review и повторный full core на следующем опубликованном SHA.
