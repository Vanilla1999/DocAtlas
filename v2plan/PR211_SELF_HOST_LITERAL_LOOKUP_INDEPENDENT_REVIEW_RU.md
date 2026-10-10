# PR211: независимый review явного lookup в новом self-host positive

Решение: **APPROVE** для указанных ниже байтов и узкого successor-контракта. Это статический review; результат нового CI **NOT RUN**. Исходный вопрос без lookup не объявляется исправленным.

База: `991638f28ecff659c320b45738edfaa8b9fd375e`. Проверены полный diff, изменённый node, окружающая fixture, текущий public query plan, literal qualification и публичный DTO.

| Файл | SHA-256 |
| --- | --- |
| `tests/test_project_docs_self_host_fixture.py` | `098c51af40c4ad37e7ddc07a4fd64abf6f2f4caaa7a8eced02cb41754e9a0569` |
| `v2plan/PR211_SELF_HOST_LITERAL_LOOKUP_REVIEW_RU.md` | `e9fe6d2d21bce91ced5accae87b0582ebbab07f96c6ce78589eefba1f85d2834` |
| Неизменный `tests/diagnostic_labels.project_docs_self_host_fixture.json` | `bc653faa03300249877061c2d5953fe882e528af4f66b487e4a28b6bd82246eb` |

## Фактическая база и граница вывода

Полные core JUnit на 991638f для Python 3.11, 3.12 и 3.13 совпадают. Новый `test_self_host_confirmed_prepare_binds_one_host_store_and_copied_project` во всех трёх прогонах проходит действительные cold-read verification, `fixture.prepare()`, generation/config/private-store assertions и затем падает на public-read status: `insufficient_evidence` вместо `ok`. JUnit показывает только этот status, без полного payload, operational reason, system-out или system-err. Ни CRLF, ни конкретный первый qualification reason этим исполнением не доказаны.

Изменённый тест проверяет подготовку и настоящее чтение из одного host-selected store с явно переданным lookup. Он больше не требует считать исходный вопрос достаточным для самостоятельного извлечения. Это изменение предпосылки публичного вызова обозначено автором прямо; оно не скрыто сменой ожидаемого status на фактический отказ.

## Текущий контракт

`domain/documentation_query_plan.py::build_documentation_query_plan` сохраняет исходные байты question и добавляет отдельный `query-lookup-1` с origin/relation `host_lookup`, без наследования parent coverage. Переданная строка `` `MirrorNeedle` explicit preparation `` — явный аргумент тестового хоста. Она не вычисляется из результата, не добавляет catalog members и не меняет source authority.

`application/context_query_probes.py::literal_query_probe` использует слова длиной от четырёх символов; backticks задают hard exact `mirrorneedle` через `domain/query_terms.py`. Исходный вопрос содержит `what`, `does`, `mirrorneedle`, `require`; неизменное RULES содержит `requires`, которое `technical_term_pattern` не принимает за `require`. В рассматриваемом literal probe совпадение 1/4 меньше текущего 0.4. Lookup содержит три буквально присутствующих слова; `explicit` и `preparation` также отличают его от исходного вопроса, что согласуется с отдельной проверкой distinctive body matches. Это статическое объяснение совместимости successor с текущим контрактом, а не восстановленный первый reason старого CI и не доказательство будущего PASS.

`context_selection_decision` считает coverage из атрибутируемых источнику query IDs; `_docs_context_payload.py` выдаёт source-backed `docs_context` с `retrieval_only`, `answer_available=False` и отдельными covered/missing IDs. Новые assertions проверяют именно эту границу: непустые context/snapshot, lookup covered, original не covered и явно missing, отсутствие answer authority. Ни original question, ни qualification/retrieval/thresholds/production DTO не изменены.

## Независимая проверка сохранности

Stdlib AST сравнен с `git show HEAD:tests/test_project_docs_self_host_fixture.py`:

- Все 24 прежних assertion expressions изменённого node сохранены; теперь их 29. Status/kind ожидание осталось положительным. Пять новых expressions не принимают пустой результат или неподтверждённый original credit.
- После удаления ровно одного lookup поля, diagnostic assignment, пяти новых assertions и message у прежнего status assertion AST node точно совпадает с базой. AST всего остального модуля точно совпадает без нормализации.
- Все шесть test function IDs, signatures и decorators прежние; diagnostic labels byte-exact. Другие пять положительных/отрицательных tests не изменены.
- `RULES` остаётся 88 байт с тремя CRLF, SHA-256 `867b29312611d6aeda55a87adf26b18cfe96631b26440a722d0de81c52082ee1`. Исходный question, cold call, catalog membership, config, source authority и прочие fixture bytes неизменны.
- Сохранены реальные cold/prepare calls и все прежние проверки private store, CAS None, content/snippet, полного CRLF source content, SHA-256, generation, catalog binding, local identity, `not_git`, auto-sync denial, stale/ignored absence и повторного prepare denial. Подмены фактического producer, успешного payload или qualification нет.
- Новый diagnostic сериализует фактический JSON payload и только ключи same-call snapshot. На этом синтетическом fixture он добавляет наблюдаемость отказа; источник и guards не подменяет.
- `git diff --check` PASS. Синтаксис разобран через stdlib AST. Production, runner, helper, gold/corpora, scoring, floors и workflows не менялись.

Runtime, локальные imports DocAtlas, pytest, installs, providers и clients не выполнялись. Следующий обычный CI должен подтвердить новый positive и полный прежний roster; исходный unsupported вопрос остаётся явно непокрытым по assertions. Никакой deferred retrieval fix этим review не утверждается.
