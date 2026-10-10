# PR #211: чтение подготовленного member store без записи

## Подтверждённый дефект

На SHA `10277b269ff686320cb191da93747b73e1f37f4b` P1.4 runtime
[run 37977510748 / job 113979401576](https://github.com/Vanilla1999/DocAtlas/actions/runs/37977510748/job/113979401576)
зафиксировал нарушение `read_only` во всех 14 сценариях.
В каждом изменился только `store_sha256`; generation, catalog и исходные документы
остались прежними. Чтение самого отчёта не подтверждает качество retrieval:
остаются 3/10 discovery и 2/5 complete facts.

Причина по текущим исходникам: общий `_agent_instance()` при первом чтении создаёт
`DocmancerAgent`, затем обычный `SQLiteStore`. Конструктор создаёт extraction
directory и вызывает schema initializer, включая CREATE/DROP FTS5 probe.
Подготовленный store имеет правильные строки, но чтение меняет файл БД.

## Контракт изменения

- `MemberReadStore` открывает только существующий host-selected
  `MemberStoragePolicy`: ownership, точный путь, private regular files,
  rollback journaling. Нет provisioning, adoption, migration или repair.
- Каждое подключение использует SQLite URI `mode=ro`, `query_only=ON` и read
  transaction. Перед выдачей connection проверяются текущие schema/config/context
  hashes, active generation status и active FTS projection.
- Полный существующий validator фактических source bytes, parents, spans,
  retrieval hashes и FTS выполняется при первом чтении каждого нового generation.
  Повторная проверка того же immutable generation не перечитывает весь корпус.
  Изменившиеся status/config/projection проверяются на каждом connection.
- Read agent кешируется отдельно. Обычные default/per-library/staging write agents
  и явный confirmed member transaction сохраняются.
- Read callers: project query и exact-document fallback, project source state,
  active diagnostics, source continuation, document-component reads.
- Отдельный accessor включается только у локального member service с переданной
  host policy. Общий SDK и isolated library stores этим slice не мигрируются.
- Условия P1.4 `read_only`, снимки до первого чтения, вопросы, факты и source
  roster не меняются. Нет прогрева, новых output ceilings или provider calls.

## Проверки в коде

Существующий `test_real_service_retrieves_committed_fixture_member_bytes`
сохраняет три Git fixture варианта, прежний вопрос/команду, 50113 байт программ,
исходные identities, scope negatives и реальные public snippets. Раньше тест
заранее создавал writer agent; теперь materialize не создаёт ни read, ни write agent,
и fingerprint всех app-storage файлов/каталогов снимается до первого чтения.

Дополнительно проверяются запрет schema initialization и SQL DELETE при чтении,
отсутствие extraction directory, отдельный writable agent и настоящий confirmed
member update. Тот же read agent должен увидеть новую активную generation, вернуть
новые исходные байты и не изменить storage во время повторного чтения.

Один новый parameterized contract проверяет семь причин отказа без repair:
missing database, foreign owner, missing schema, missing generation column,
missing active generation, obsolete FTS projection, incompatible vector generation.
Существующие тесты не удалены. Имена функций 34 → 35; диагностический SHA
базового roster воспроизведён до обновления manifest, параметры не входят в этот SHA.

## Статус

Подготовлены точные GitHub blobs. Локальные imports, AST, pytest, installs и runtime
не запускались: локальный executor недоступен. Независимый review подтвердил маршруты и read transaction;
по его замечанию добавлены обработка SQLite Row IndexError и реальный old-column
negative control. Commit предшествует runtime; фактический итог новых тестов и повторного P1.4 должен
быть зафиксирован из CI на опубликованном SHA. Этот документ не является PASS
certificate и не закрывает оставшиеся retrieval quality / downstream gates.
