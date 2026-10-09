# Admission meaning: precheck сокращения отменённых inferred ожиданий

## Решение

Выбрано одно семейство: `tests/docs/test_admission_meaning.py`. Текущие `compile_admission_demands` и `same_supported_meaning` сохраняют буквальные входы и явно неподдержанное значение; семантические роли, equivalence и audited rewrite из прозы больше не выводятся.

На PR head `067dd56044fb1fe292af2d17783154c8a4b7c092` [actual JUnit reader](https://github.com/Vanilla1999/DocAtlas/actions/runs/37991321138/job/114029489614) сообщает для модуля **30 FAIL / 4 PASS**, без ERROR/SKIP. Общий результат каждой из трёх Python matrix — 6000 PASS / 1837 FAIL / 0 ERROR / 10 SKIP; `integrity_issues=[]`, `omitted_rows=0`. Это baseline, а не результат нового precheck.

| Группа | Definitions | Expanded cases | Действие |
|---|---:|---:|---|
| Исходный модуль | 9 | 34 | Сохранён полностью collected |
| Отменённые inferred ожидания | 5 | 30 | Архив + crosswalk; удаление пока запрещено |
| Действующие residue/reference guards | 4 | 4 | Остаются отдельными working tests |
| Новый independent contract control | 1 | 1 | Добавляется для runtime proof |

При успешном proof отдельный retirement может заменить 30 старых cases одним control: **34 → 5**, net **−29**. Текущий precheck добавляет один case и ничего не удаляет.

## Что именно допускает будущую замену

- 8 RU/EN pairs: ожидание общего semantic operator и одобренной парафразы.
- 10 изменённых аргументов/условий: старый helper сначала требует поддержанный смысл слева; эта предпосылка отменена. Буквальные inputs и запрет equivalence остаются.
- 6 quoted literals: отменено назначение semantic owner slot. Все шесть значений — `worker.run`, `for`, `для`, `--fast-mode`, `ΣClient`, `name?literal` — сохраняются, вместе с raw spans и hard_exact. Raw case не подменяется casefold.
- 5 questions: отменено создание inferred retrieval_need lanes.
- 1 reformulation case: отменено автоматическое audited parent credit для хорошей по старой грамматике переформулировки.

**Четыре содержательных guards остаются:** unknown question, неизвестная вторая clause, неэквивалентность and/or и ReferencePlan от другого вопроса. Их полные function AST сравниваются с frozen archive; это контроль сохранности, не замена исполнения самих тестов.

## Новый control

Один обычный pytest node читает архив как AST/literal data, не исполняя старые тесты. Он проверяет 50 исходных question occurrences (16+20+6+5+3), 18 исходных пар в обоих направлениях и дополнительные независимые границы:

1. Полный AdmissionDemand/RetrievalNeed сравнивается с literal expected dict: unknown operator, unresolved relation, пустые inferred subject/arguments/constraints, исходные character spans, неизменный query text и ожидаемые hard_exact.
2. Quoted values сохраняют точные occurrences. Проверены оба raw написания QueueHub/queuehub, casefold Σ→σ, Unicode combining mark и CRLF. Blank input отделён от непустого unsupported input.
3. Original query и исходные good/changed host lookup остаются отдельными lanes с точными строками и без parent credit.
4. Отдельный pure finite CatalogSource control проверяет реальную положительную membership resolution, input permutation, foreign scope, prefix neighbor, отсутствие/неполноту catalog и ambiguity. Он не заявляет proof body, filesystem access или качества retrieval.
5. Даже два одинаковых явно сконструированных «полных» AdmissionDemand/MeaningSlot DTO не создают semantic equivalence.

## Адресный production mutant и gates

В normal critical runner добавлены один target и один mutant: `admission_meaning_no_inferred_equivalence` меняет реальный `same_supported_meaning` с False на True. Exact anchor встречается один раз. Первым обязан сработать guard `critical_admission_meaning_no_inferred_equivalence` на forged complete DTO; раннего вызова API с безымянным assertion нет.

После ранее подготовленного intent precheck normal critical baseline меняется **30 → 31 cases**, число mutants **8 → 9**. Runner от `def _ignore` до конца, включая literal comparison protocol и его проверки, сохранён побайтно.

| Файл | Exact blob |
|---|---|
| `tests/docs/test_admission_meaning_contract.py` | `4e96ab4c771a3fb0d8cc5ee2bce3ffa4d2f6d3cd` |
| `scripts/run_critical_mutation_gate.py` | `36d155117a8111e572588af4cc1260b20d0e1114`; base `9dc4669bc37bcc06b68e182abe08cbad6778e67f` |
| `eval/task_level/contract_history/admission_meaning.py.txt` | `87434b28d5460eae97f7d59ed763e4a8a65aadbf`; точный исходный модуль |
| `eval/task_level/contract_history/admission_meaning.json` | `4c85b843c096df3612588c30a8d7dc4efb9aee5c` |
| `tests/diagnostic_labels.admission_meaning_contract.json` | `cfbbb912a175eb19d3a992f17eb9edb30643ca1f` |

Archive SHA-256: `3ecadb74c344ba2613adcf8a1c5ecbc937a8f42e77a88e538972102238dedfd7`. Frozen roster SHA-256: `a6614b8f127c742d7d9ef39c3df3c56f16a175cd52cad8f4b927c89ab694fdbf`.

## Последовательность приёмки

1. Независимый review exact blobs; сверка runner base и неизменности исходного модуля.
2. Публикация precheck без удаления старых cases.
3. На exact published SHA — зелёный baseline нового control и ожидаемый named kill: 1 failure, 0 errors, 0 skips. Полные normal critical/required gates продолжают действовать.
4. Только затем отдельный review удаления пяти выбранных functions, с четырьмя working guards и их helpers на месте, обновлением diagnostic registration и проверкой явных pytest selectors.
5. Общий acceptance на окончательном SHA.

Локальные import/pytest/server/provider вызовы не выполнялись. Production/retrieval/source-binding implementation и другие четыре предложенных семейства не изменены. Precheck не доказывает качество поиска, original-query coverage, installed/client acceptance; alias/intent mutants не засчитываются как proof admission API.
