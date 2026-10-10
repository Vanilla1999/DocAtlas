# PR #211: компактный контракт смешанного контекста

## Статус

Подготовлен один новый pytest-контракт и пять направленных мутаций production.
Ожидаемый полный critical gate — **54 случая / 25 мутаций**. Это целевой состав,
а не результат запуска: runtime для этого slice **PENDING**. Локальные импорты,
pytest, AST и subprocess не запускались. Проверка поведения должна пройти
обычным PR CI на общем конечном дереве production и controls.

Основа runner: `8f31dfccd02025b8355020aa4063952733c0689a` из опубликованного
`eb2c4f3b3e0065110a1bfe2c855e4a05803fa37a`.
Прежние 53 случая и 20 mutation blocks сохранены побайтно. Новый selector
добавлен последним; старые индексы, expected counts, guards, child execution,
timeouts, JUnit evaluator и сравнение literal-contracts не изменены.
Список origin-check modules дополнен 15 используемыми production/fixture modules.

## Независимый положительный вход

Оригинальный вопрос: `Explain LedgerCursor and RemoteDelayRule.`.
Проект содержит явный конечный catalog из трёх authored документов:
project scope, module `packages/alpha` и module `packages/beta`.
У каждого свой полный факт и Unicode-префикс перед literal; каталог задаёт
current lifecycle, source-of-truth authority и ожидаемый module scope.

Второй проект имеет отдельные root, host-selected store и исходный факт.
Его настоящий результат используется как foreign-root replay. Модульный
negative берёт настоящий результат beta при сохранённом текущем запросе alpha.

Библиотека `python:clear-pulse-fixture@2.7.1:reference` готовится реальным
explicit prepare через generic finite HTTP fixture. Host manifest разрешает
ровно `https://docs.clearpulse.test/2.7.1/reference.txt` и
`https://docs.clearpulse.test/robots.txt`; исходные bytes и version 2.7.1
заданы самим контролем. После preparation DNS/HTTP запрещены. Ни corpus P15,
ни его question mapping, oracle, golden facts или provider не используются.

Ожидаемые project identity, resolved scope, original query, полные тела,
SHA-256 и character/UTF-8 byte/line extents вычисляются независимо из этих
исходных данных и сопоставляются с единственным реально committed child.
Проверяются обе стадии source class: project storage `project_file` и
retrieval `project_doc`, а также library identity, exact version и все
присутствующие top-level/nested lineage carriers без сокрытия конфликтов.

## Что исполняется внутри одного pytest-имени

Это не обещание сократить runtime до одного действия. Один тест содержит:

- 4 native public reads: foreign project, основной project scope, alpha и beta.
  Каждый observer вызывает исходный метод один раз и возвращает его же object.
  Проверяется конечный snapshot фактического MCP ответа, включая оба источника.
- 28 detached projector replays с реальными captured inputs и canonical selection:
  root/module, malformed/missing contract, query/scope/path, consent/delivery,
  conflicts/lifecycle, source identity/hash/generation и exact-library veto.
- 1 отдельный same-ID collision replay с предварительно валидным library packet.
  Несовместимый project источник должен оставить library payload/snapshot целыми.

Native reads сохраняют fingerprint project/library databases, active generation,
project catalog/docs и registry records до/после. Replays запрещают новые
retrieval, SQLite access и continuation attachment. Invalid project proof
сохраняет точный ранее допущенный library packet; global/library veto остаётся
блокирующим. Оба здоровых lane дают полные исходные факты в одном итоговом
snapshot. Answer/edit и original-query coverage остаются без grants.

## Направленные ошибки и первая обязательная проверка

| Production fault | Intended assertion guard |
| --- | --- |
| Удалён вызов mixed hook внутри authoritative projector | `critical_mixed_both_lanes` |
| Пропущено сравнение current request root с producer root | `critical_mixed_request_root` |
| Пропущен фильтр producer-resolved module | `critical_mixed_resolved_module` |
| У новой project цитаты удалён последний символ | `critical_mixed_full_fact` |
| Producer записывает изменённый query в read scope | `critical_mixed_scope_producer` |

Все пять source anchors найдены ровно один раз в конкретных production blobs
ниже. Каждый mutant запускает только новый selector и должен дать ровно один
assertion failure с указанным первым guard. Ошибка import/setup, иной assertion,
неполный roster, skipped case или живой mutant не засчитываются.

Hook fault проверяется до требования о captured composer invocation.
Scope-producer oracle проверяется до mixed delivery, чтобы новый неверный scope
не маскировался вторичным отсутствием project источника. Foreign-root и module
replays сохраняют исходный current request; соседний источник несёт собственные
настоящие owner, generation, body и raw references. Full-fact oracle не заменяется
проверкой внутренней согласованности обрезанного projected snapshot.

## Exact manifest

| Path | Base blob | Proposed blob | Mode |
| --- | --- | --- | --- |
| `tests/docs/test_mixed_context_projection_contract.py` | NEW | `bd7435f507d9360030cb3c4c4411d2f485aefe90` | 100644 |
| `scripts/run_critical_mutation_gate.py` | `8f31dfccd02025b8355020aa4063952733c0689a` | `de247bb93baac2f328ab98aea130d82b4a7a6cbd` | 100755 |
| `v2plan/PR211_MIXED_CONTEXT_CONTRACT_RU.md` | NEW | Этот документ | 100644 |

Production зависимости для общего CI дерева:

| Path | Reviewed proposal blob |
| --- | --- |
| `docmancer/docs/models.py` | `9bb323e4c890e25dc5ef341d045609708ebe3ac0` |
| `docmancer/docs/application/_project_docs_service_part03.py` | `94fe9ee6629d14034d337fae879272c5b6d16a64` |
| `docmancer/docs/application/_unified_context_service_part01.py` | `483f04887c10f6c09e0ddd96d38e3a3a1c540a81` |
| `docmancer/docs/application/mixed_context_projection.py` | `dcdf502c9d9b2a3788c1bfc41d377ad3cf1ade63` |
| `docmancer/docs/application/model_visible_projection.py` | `3c377e64bf104b598bb68a0d062625c4fc83f5ef` |
| `docmancer/docs/interfaces/mcp/context_tools.py` | `c6e2bda4208a43b7764fe484928fd7ce55ed6183` |

## Границы результата

Новых обычных test functions — одна; прежние tests не удаляются.
Recovery scripts, retrieval grammar/ranker/thresholds и frozen P14/P15 inputs
не меняются. Этот контроль не подтверждает весь CI или закрытие P15.

Новая mixed augmentation требует независимо сопоставимого абсолютного текущего
project path. Relative/`~`/symlink aliases без такого pure proof сохраняют
прежний library packet; полноценная mixed delivery для них здесь не заявлена.
Это ограничение нового добавления, а не новая ошибка public API или разрешение
добывать root из candidate metadata.

Статическая сверка: обратные четыре runner edits восстанавливают исходный blob,
20 прежних mutation blocks и 10 selectors целиком сохранены; новый test имеет
одно pytest-имя. Exact blob roundtrip выполняется перед передачей на публикацию.
