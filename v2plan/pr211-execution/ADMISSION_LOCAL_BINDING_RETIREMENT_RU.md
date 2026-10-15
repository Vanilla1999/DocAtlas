# PR211: retirement устаревших default-binding ожиданий

## Изменение

Из `tests/docs/test_admission_local_binding.py` удаляются ровно **15 отмеченных функций / 42 параметризованных случая**. Их контракт требовал выводить из свободного текста владельца, свойство, условие или анафорическое значение default. Действующий domain API явно возвращает unknown: `None` для свойства/единиц и `(None, ())` для witness. Unknown не равен ни доказанному `True`, ни семантическому опровержению `False`.

Сохраняются побайтно **живой tail test, helper `default_need`, все импорты, docstring и все остальные строки вне 15 удаляемых source spans**, включая whitespace. Путь модуля остаётся. Никакие другие тестовые модули, production, corpus, runtime runner или лимиты не изменяются.

| Часть семейства | До retirement | После |
| --- | ---: | ---: |
| Старый модуль | 16 функций / 43 случая | 1 функция / 1 случай |
| Независимый current-contract control | 1 функция / 1 случай | 1 функция / 1 случай |
| Семейство вместе | 17 функций / 44 случая | 2 функции / 2 случая |

Сохранённый тест — `test_recognized_condition_does_not_hide_unsupported_constraint_tail`. Его исходный вопрос, исходный body и проверка `is not True` остаются без изменений. Companion control дополнительно сравнивает AST этого теста и helper с frozen archive.

## Собственный runtime proof, полученный до удаления

[Critical job 114066061733](https://github.com/Vanilla1999/DocAtlas/actions/runs/38003248365/job/114066061733), run **38003248365**, attempt **1**:

- PR head: `1c6c2c8454cdd6fe797fe80e85f3b651aef01a0a`.
- Checkout commit GitHub PR merge: `64caa3caf213a6a67d44c92546660ef1ced23d87`.
- Его родители: `d2ed5c4c73dc3b7d56276fc37591cba8a4ae123c` и указанный PR head.
- Checkout tree и PR-head tree одинаковы: `8a544267409f0dbf3ab498dfa864c07b13cdfb73`.
- **Normal baseline: 32 PASS / 0 FAIL / 0 ERROR / 0 SKIP, return code 0.**
- **Все 13 intended mutants killed.** Каждая из четырёх default-мутаций дала ровно **1 test / 1 ожидаемый FAIL / 0 ERROR / 0 SKIP**, return code 1, anchor count 1 и свой intended guard.
- Используются normal `EVIDENCE` records. Записи сравнения historical/compact literal с `case_mode` не подменяют baseline.

| Направленная production-мутация | Intended guard |
| --- | --- |
| `default_binding_unknown_not_true` | `critical_default_binding_unknown_abi` |
| `default_binding_unknown_not_false` | `critical_default_binding_unknown_abi` |
| `default_binding_unknown_cannot_qualify` | `critical_default_binding_unknown_veto` |
| `default_binding_nonneeds_not_erased` | `critical_default_binding_nonneeds_preserved` |

Baseline roster SHA-256: `cd00681fc050a2f1e9fba4c08557d257e4cbce6aafdb5e59236c5c454f17d200`.
Target roster каждой default-мутации: `e3cf7ed8bfc9dcc0156f33d8e60a10ecb4e9c278252b93998ed561c709fa38fb`.
Actual before/after source hashes, killer node, counts и guard перенесены в `runtime_proof` crosswalk без замены источников.

Контроль имеет здоровый положительный pass-through для original/host_lookup и сохраняет полный trace до проверки unknown-вектора. Поэтому always-empty адаптер падает именно на положительном guard. Старые 43 query/body/source records остаются проверяемыми входами с независимым digest; historical assertions сохраняются как история и не служат новым gold.

## Полнота и сохранность

Исходный архив `eval/task_level/contract_history/admission_local_binding.py.txt` остаётся точной копией blob `f0d3676dc20f9b4785715405f4f6ced401c1df6f`:

- Archive SHA-256: `e3eec4a7f10584855352228cca65972f2747bb81e7d3693ec3253ac24ebcc676`.
- Frozen 16-function roster: `13fd8cc50b80d3811f842d5cffe4315f823844615786bcf4bd3d5aa7d81ca286`.
- Frozen 43-input roster: `2a1fd29dd230996a3621651b0829bf067d961f3919fa50a8e68b17372759dac3`.

Все 16 mapping entries, source lines, исходные вопросы/тексты/source metadata и historical expectation descriptions crosswalk неизменны. Удаление выполняется только по 15 уже отмеченным source spans. Остальной текст модуля сохранён, поэтому восстановление удалённых spans воспроизводит исходные bytes.

Аудит внешних потребителей и selectors выполнен на точном base **79**, commit `08b5d27cc4b919cfde52df84a8c25e8c6df30a2d`, tree `b857adec62508099722670dc7c515ec57c0b2ebe`: **1273 Python-файла**, **39 workflows**, остальные shell/config файлы — **1363**; дополнительно **184 JSON configuration/diagnostic файла**. Всего **1547** exact path/blob entries. Правила отбора и SHA-256 списка зафиксированы в crosswalk.

В этом объёме нет внешних ссылок на удаляемые 15 имён или импортов `default_need`. `experiments/language_aware_context/packing_regressions.py` выбирает старый module path; путь и живой тест сохранены. Critical runner выбирает неизменный companion control. `tests/test_dictionary_exit_callable_residuals.py` содержит отдельный одноимённый по теме тест, не импортирует этот helper и не изменяется.

В `tests/diagnostic_labels.admission_contract.json` меняется только hash node roster старого модуля:

- До: `3ba94d12fe9ebfcae5c86d5041dcb96979116aa6eeef2d57afd5b25d07e08382`.
- После: `bd27a14da5fb3e380f9fc87e802e34ad9053f69c18e0b463155b2550444e9560`.

Behavioral label, все остальные registrations и companion control shard остаются прежними. Hash рассчитан по действующему `tests/diagnostic_labels.py`: SHA-256 отсортированных base node IDs, соединённых newline без завершающего newline.

## Граница результата

[Full core reader 114068441329](https://github.com/Vanilla1999/DocAtlas/actions/runs/38003248365/job/114068441329) на том же proof run дал для **каждой Python 3.11 / 3.12 / 3.13**: **6031 PASS / 1748 FAIL / 0 ERROR / 10 SKIP**. `integrity_issues=[]`, `omitted_rows=0`, полные cases находятся в artifacts. Старый default module: **42 FAIL / 1 PASS**, первый failure — `assert None is True`. Это состояние до retirement, а не расчёт будущего PASS.

Рабочий модуль, companion control, archive, crosswalk, domain API и witness wrapper на base79 имеют те же blobs, что на доказанном PR head. В base79 уже добавлен другой relation slice: его runner `7331b5a85b99887ec64334388a7b23c8eed687e5` расширяет suite до **53 cases / 19 mutants**. Этот runner здесь не меняется; proof **32/13** не объявляется доказательством **53/19** или всего base79 tree.

Финальный совместный runtime на опубликованном SHA, полный core, downstream и installed/client acceptance остаются обязательными. Удаление устаревшего semantic compiler не доказывает качество original-query retrieval, source binding, finite membership или полноту MCP delivery.

## Manifest для точного применения

| Путь | Base blob / статус |
| --- | --- |
| `tests/docs/test_admission_local_binding.py` | `f0d3676dc20f9b4785715405f4f6ced401c1df6f` |
| `tests/diagnostic_labels.admission_contract.json` | `a429929eb2ae3cbdb53b201eb4a0605b512a8990` |
| `eval/task_level/contract_history/admission_local_binding.json` | `f6df59efd8704264a9c223e57a172f45806c0702` |
| `v2plan/pr211-execution/ADMISSION_LOCAL_BINDING_RETIREMENT_RU.md` | Новый файл |

SHA-256 нового working module: `a9462c8e5a190af1e4117d40fd27f2758731ea00d7645a8cd8c362fca7a754b5`.
Все четыре файла — mode `100644`. Production, frozen archive, companion control `e9fe37b22014e57e9998667dbc5aacf573d19b15` и critical runner не изменяются.
