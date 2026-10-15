# Alias-only retirement после доказанного precheck

## Решение и предел сокращения

Из collection удалён только `tests/docs/test_direct_question_retrieval_intents.py`: 19 функций / 49 исторических cases, проверявших генерацию aliases, semantic relations и catalog roles из свободного вопроса. Текущий контракт этих действий не выполняет. Один current contract test был добавлен отдельным precheck и уже прошёл baseline и адресную production mutation.

Итог этой семьи — 49 исторических cases заменены одним текущим contract control; чистое сокращение 48 cases относительно исходной семьи. В текущем slice удаляется 49 cases, потому что replacement уже был добавлен предыдущим commit. Полный suite count и final acceptance после удаления ещё должны подтвердиться в CI.

Это не исправление качества retrieval. Проверки реального source content, ranking, finite membership, original-query credit, authority и downstream quality остаются независимыми; `tests/docs/test_project_query_intent.py` и `tests/docs/test_direct_docatlas_questions_15.py` не меняются.

## Фактическое основание

Непосредственно прочитан лог обычного PR CI на `589a6366e33278fe542a0e3c971d2502e5e9f99f`:

- Main run: https://github.com/Vanilla1999/DocAtlas/actions/runs/37975999319
- Advanced job: https://github.com/Vanilla1999/DocAtlas/actions/runs/37975999319/job/113974342691
- Обычный critical baseline: 29 tests, 29 PASS, 0 failures/errors/skips, return code 0.
- Все семь обычных critical mutants убиты; alias mutant даёт ровно один ожидаемый assertion failure, 0 errors/skips, return code 1.
- Advanced job в целом красный из-за независимых downstream gates. Его общий статус не объявляется зелёным.
- Исторический literal comparison 702/82 и 51 mutations не приписывается alias API и этим slice не меняется.

Current control сохраняет точные исходные EN/RU/Unicode/CRLF вопросы и отдельно заданный host lookup. Он проверяет положительное существование original query, исходный текст, distinct provenance и required credit, отсутствие inferred roles, затем отсутствие generated aliases. Поэтому пустой planner не проходит guard.

Адресная mutation возвращает настоящий `ProjectRetrievalAlias("inferred_query", "invented lookup", True, "en")` из production helper. Gate перед сохранением evidence проверяет совпадение roster с baseline, exact failure count, отсутствие errors/skips и первую строку `AssertionError: critical_alias_no_generated_queries`. Collection crash либо failure другой проверки credit не даёт.

### Наблюдённые identity и метрики

| Поле | Значение |
| --- | --- |
| Baseline roster SHA-256 | `1811e244c7cf8030882d7be896253dc7ddba6bf383453b08055e0c662f07a1db` |
| Mutant roster SHA-256 | `8da8e109f727ed0e60616bd1252127b9f431cf18eec4060eaa0e0e19846eac2a` |
| Production source before SHA-256 | `d1940e93bf701033bf57ca3f0e3fe767326a275e497c1ece28d2154b3c489248` |
| Production source after SHA-256 | `486399aeb7a48cf8d25c9a988963a7aa507043344b3900cc7aa07de2c98fee74` |
| Mutation anchor count | 1 |
| Killer | `tests/docs/test_project_retrieval_alias_contract.py::test_current_alias_boundary_preserves_explicit_queries_without_inference` |

## Архив и crosswalk

Удаляемый модуль и сохранённый `eval/task_level/contract_history/direct_question_retrieval_intents.py.txt` непосредственно прочитаны и равны byte-for-byte; оба имеют git blob `6d81ce383b273a73e0679aad48d6a10495b91c48`.

Сохранены исходные вопросы, отрицательные соседние примеры, параметризация и старые assertions. Архив читается как data, не импортируется. Уже выполненный baseline прошёл фактическую AST-проверку 19 функций / 49 cases, соответствие полному crosswalk и независимому frozen hash:

- Архив SHA-256: `23e0e84815cf887cdd1ab5bd4c4caa550580982e9b5fd52ae9a2beb4075c7791`.
- Frozen roster SHA-256: `0c244ebb644ffb18366fb3bbcaf8fb1a26c32e35758db056530af91f9d56da48`.
- Crosswalk blob: `fb27cd3225cce1b29f95b89dafc62f2e0564aa68`.
- Replacement blob: `7d10931d6509897899ac5ce1b826cf2909d73d9a`.
- Replacement diagnostic shard: `5d56b9100d9e3e9c65b245a165bfa34172c487e4`.

Crosswalk, diagnostic shard и archive не меняются. В replacement изменён только один комментарий: прежняя совместная collection явно обозначена как этап precheck. Исполняемое тело и все guards byte-identical; актуальный статус retirement зафиксирован здесь. Формулировки precheck в прежней note/crosswalk сохраняются как история доказательства.

## Точный состав slice

База чтения `10277b269ff686320cb191da93747b73e1f37f4b`; root подтвердил, что относящиеся к slice blobs остаются неизменными в более позднем `841e770e644dba369ab441ba2ec9f2a8807cac7f`.

| Путь | Действие | Blob |
| --- | --- | --- |
| `tests/docs/test_direct_question_retrieval_intents.py` | Удаление из collection | Прежний `6d81ce383b273a73e0679aad48d6a10495b91c48` |
| `tests/diagnostic_labels.direct_questions.json` | Удалены только module label и module node hash старого модуля | `e8bdbb0f4feb8fb4e7e3c7cbe410562647b7ecd5` → `7d675cb3de6f9faea438170918cd150d70e9f1eb` |
| `tests/docs/test_project_retrieval_alias_contract.py` | Только уточнение исторического комментария; executable body unchanged | `7d10931d6509897899ac5ce1b826cf2909d73d9a` → `15a933aaae55582ac6c633070098e00762b46676` |
| `v2plan/pr211-execution/ALIAS_CONTRACT_RETIREMENT_RU.md` | Эта proof note | Новый файл |

Соседняя registration `test_direct_docatlas_questions_15.py` сохраняет label и node hash без изменения. Никаких production changes, новых skip/xfail, изменений pytest selectors либо ослабления thresholds здесь нет.

## Проверка selectors перед удалением

Непосредственно прочитаны `.github/workflows/ci.yml`, `direct-question-validation.yml`, `task33c-pr-checks.yml`, `task33c-actions-probe.yml`, `scripts/run_critical_mutation_gate.py`, `pytest.ini`, `pyproject.toml`, `tests/conftest.py`, `tests/diagnostic_labels.py`, `tests/test_pytest_collection_hygiene.py` и `tests/test_diagnostic_labels.py`.

Core и direct-question workflow выбирают каталог `tests/` с markers. Оба Task33 workflow перечисляют пять существующих файлов action_packet/task_level; старого alias module в списках нет. Critical gate выбирает новый replacement node. Collection hygiene фиксирует каталог tests и исключения runtime, не старый module path. Diagnostic hook получает complete_modules из объединённого manifest: удалены и label, и node hash старого модуля, существующие registrations оставлены. Эквивалентного `scripts/check_test_selection` в прочитанном git tree нет. В этой проверенной цепочке нет selector, который после удаления обращался бы к отсутствующему файлу.

## Проверка после публикации

Локальные imports, AST/compile и pytest не запускались. После отдельного root review нужны обычные PR CI: отсутствие collection/diagnostic errors, green current alias baseline, повторный named mutation kill и required acceptance на конечном SHA. Уже полученное доказательство `589a636` не выдаётся за результат будущего commit или готовность PR к merge.
