# PR211: Context7 alias-input precheck

## Узкий scope

В существующий `test_current_alias_boundary_preserves_explicit_queries_without_inference` добавляются **21 исходный вопрос** из одной функции `test_russian_newcomer_queries_get_retrieval_only_aliases`. Новых test functions нет. Все **57 случаев / 19 функций** исходного Context7 модуля остаются collected, включая выбранный 21 случай. Остальные **36 случаев / 18 функций**, helper `_EmptyRequirements`, импорты и исходные тексты не изменяются. Все **70** случаев `test_documentation_query_plan.py` остаются прежними.

Выбранная функция, несмотря на имя, содержит 11 русских и 10 английских вопросов. Она проверяет три свойства сгенерированного alias: наличие заранее заданного `intent_id`, `force_context_only` и непустой `text`. В ней нет source body, finite membership, runtime authorization или фактического retrieval oracle. Именно этот словарный вывод topic alias отменён действующим compatibility API: `build_project_retrieval_aliases` возвращает `()` для свободного текста.

Другие Context7 сценарии не объявляются устаревшими по имени или по общей статистике FAIL. Их исходные negative neighbors, query/source/coverage assertions и runtime fixture сохраняются.

## Что усиливается

Прежний independent control вызывал production alias API на трёх конкретных вопросах. **Ни один из добавляемых 21 вопроса не совпадает с этими тремя.** Само наличие старого 49-case архива не означало, что эти новые входы уже проверялись.

Внутри той же test function теперь выполняются:

1. Проверка точных frozen archive, выбранного source span и records: `question`, исходный `historical_intent_id`, индекс и SHA-256 question bytes.
2. Прежние независимые original-only / explicit lookup guards для всех **24** вопросов. Исходный вопрос сохраняется полностью; заданный пользователем lookup остаётся отдельным запросом без parent coverage, выведенных ролей, forbidden terms или need fields. Явный path остаётся scope metadata.
3. Прежняя alias-проверка на старых трёх вопросах с исходным `critical_alias_no_generated_queries`.
4. Alias-проверка на добавленных 21 вопросе с `critical_context7_no_topic_router_aliases`.

Исходные intent IDs хранятся как история fixture; новый oracle не использует их для вывода результата или ответа. AST archive читается как данные: импорт старого модуля и выполнение его тестов при извлечении записей отсутствуют.

Все остальные top-level AST nodes исходного Context7 файла, включая helper, imports и native quality tests, сравниваются с архивом. Если выбранная функция присутствует, её AST тоже должен совпадать. Этот precheck не удаляет её.

## Адресная production-мутация

Новый mutant `context7_russian_topic_router_cannot_generate_aliases` меняет только disposable copy функции `build_project_retrieval_aliases`:

```python
if "установ" in question.casefold():
    return (ProjectRetrievalAlias(
        "installation_verification", "installation setup verification", True, "en",
    ),)
return ()
```

Это возврат предметного alias по русскому словарному stem. Условие **не достигается ни одним из старых трёх inputs** и достигается новыми records **0 и 1**. Первый actual assertion при этом fault должен находиться на новом record 0 и иметь ровно первую строку:

```text
AssertionError: critical_context7_no_topic_router_aliases
```

Прежде выполняются здоровые plan/lookup positives. Старый unconditional-alias mutant по-прежнему падает на своём прежнем guard. Ошибки collection/setup/runtime, другой guard или skips не засчитываются как intended kill.

- Source anchor count: **1**.
- Production before SHA-256: `d1940e93bf701033bf57ca3f0e3fe767326a275e497c1ece28d2154b3c489248`.
- Production after SHA-256: `7f9bb4c33c117987145c058a6f5860744eb5eaa3ee8ad08c19948957b7b9e25f`.
- Expected target: **1 test / 1 FAIL / 0 ERROR / 0 SKIP**, return code 1.
- Нормальная baseline остаётся **53 cases**, число mutants увеличивается **19 → 20**.

Runner сохраняет прежние target tests/counts/modules, первые 19 mutations и весь код начиная с `def _ignore`, включая literal comparison. Импортная проверка существующего normal runner — отдельный probe disposable checkout; новый same-process pytest import receipt здесь не заявляется.

## Frozen identities

| Объект | SHA-256 |
| --- | --- |
| Полный raw Context7 archive | `a573bb62e7546920dd4738456b860420ce8db72fe359b6f1d61ebccfbb3f16b8` |
| Выбранный roster: definition 46, source lines 20–51, 21 case | `39591084bef65604349d5f6237066b9a2492c1d83c4f38dbf033ba2bceee9f81` |
| Исходные 3 questions | `fad4c95805cf51cd3257f244b00c81d3be13a6b116efa962904dd555d1aaa186` |
| Новые 21 полных input records | `eb8a4ac593d8659f59a8081d5140109dd2684b5a23c3abd9c66c198fcd9820c6` |
| Итоговые 24 questions в прежнем порядке | `77a8c8ff1372debd437a24fe1ca43ffeff6c9453907dfd534cd71714205ed7e1` |

21 пара question/intent независимо переписана из source и сверена с literal decorator data. Прежние три строки, включая Unicode, combining mark, whitespace и CRLF, остаются точными. Новый raw archive — тот же Git blob `6a9e2564f60b696e2e6f64e5f53512728f9e6c34`, что исходный модуль.

## Имеющееся runtime evidence и следующий gate

Base PR head: `80c8fbbb3e8c379467a9075f93f7165d080f8432`. Реальный checkout merge: `f04b42774b00dadbca48ca579ca9ea234442b750`. Их деревья одинаковы: `a838749f57ff0165ab925590656f64e0799a2e05`.

[Advanced job 114075319327](https://github.com/Vanilla1999/DocAtlas/actions/runs/38006157209/job/114075319327) на этом опубликованном дереве подтвердил **53 PASS / 0 FAIL / 0 ERROR / 0 SKIP**, все **19** intended kills. Это доказательство предыдущего control с тремя inputs; оно не подменяет новый **53/20** прогон.

[Full core reader 114077935805](https://github.com/Vanilla1999/DocAtlas/actions/runs/38006157209/job/114077935805): каждая Python 3.11/3.12/3.13 — **6057 PASS / 1680 FAIL / 0 ERROR / 10 SKIP**, `integrity_issues=[]`, `omitted_rows=0`. Context7: **45 FAIL / 12 PASS**; documentation query plan: **45 FAIL / 25 PASS**. Это агрегаты исходных модулей, не переименование всех 90 failures в obsolete.

Перед последующим retirement нужен actual green normal baseline **53** и все **20** intended kills на одном опубликованном source tree, с именованным новым guard и правильным target roster. Только после этого отдельный review может удалить выбранную функцию / 21 случай. Полный core/downstream/installed/client acceptance остаётся отдельным обязательством.

## Manifest и сохранность

| Путь | Base blob |
| --- | --- |
| `tests/docs/test_project_retrieval_alias_contract.py` | `15a933aaae55582ac6c633070098e00762b46676` |
| `scripts/run_critical_mutation_gate.py` | `7331b5a85b99887ec64334388a7b23c8eed687e5` |
| `eval/task_level/contract_history/context7_newcomer_alias_inputs.py.txt` | Новый raw archive |
| `eval/task_level/contract_history/context7_newcomer_alias_inputs.json` | Новый crosswalk |
| `v2plan/pr211-execution/CONTEXT7_ALIAS_INPUT_PRECHECK_RU.md` | Новый note |

Control, raw archive, crosswalk и note имеют mode `100644`. У существующего `scripts/run_critical_mutation_gate.py` сохраняется исходный mode `100755`. Контроль остаётся одной обычной test function; diagnostic node hash `7ae433f3e026f13b67f5a6f9683def90a046b08f59204a1688a75df148b4799a` и все selectors остаются прежними. Existing alias archive/crosswalk, исходный Context7 файл, documentation-query-plan файл и production не изменяются.

## Source review

2026-10-10: root и independent reviewer APPROVE exact control, runner, raw archive и crosswalk.
Reviewer независимо пересчитал source/input/combined/production mutation hashes;
root сверил точные diff, неизменность исходного archive blob и mode100755 runner.
Этот source review не заменяет pending actual53/20 и не разрешает retirement до него.
