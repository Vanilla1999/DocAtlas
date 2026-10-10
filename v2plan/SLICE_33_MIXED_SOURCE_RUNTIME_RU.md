# P1.5: реальные публичные чтения с сохранённым происхождением фактов

## Статус

Реализован current-contract migration существующего P1.5 gate. База `10277b269ff686320cb191da93747b73e1f37f4b`; общая библиотека P1.4 берётся уже с optional-sources correction `866cd50b`. Пакет подготовлен для независимого review и обычного CI. **Локальные AST/import/runtime не запускались: exec transport недоступен. Успешный P1.5 runtime пока не заявлен.**

## Что зафиксировано независимо от результата продукта

Исходный `eval/agent_developer_v1/mixed_provenance_protocol.json` не меняется: семь вопросов,13 исходных candidate rows с точными текстами/путями/URL/ролями, пять положительных случаев с шестью обязательными полными фактами и два отрицательных случая. Старые labels и public requirements остаются в каждом новом отчёте.

- Protocol git blob: `63a8ff66c1e1fd933af2cca1e888c19fbdf2126b`.
- Protocol raw SHA256: `d6d9c5ab02a90a1e41f51ad19795502f33d9ea80883a1dcc0a41ccf2123dd719`.
- Protocol canonical SHA256: `4559d02bd17977965dc8b7baf19471b3a00d56f5ee09dc37fc6de341aa757d71`.
- Исторический `results/mixed-evidence-provenance.json` внутри eval directory: blob `b0ab4ff3ee940689c638d7cc03fec5b8037a9207`, raw SHA256 `542ab4377d0ce5473dfffe0eced0331eff22fa2e31af1f65b4ff0f1680da7e47`. Он не перезаписывается и не reseal-ится.

Новый `mixed_provenance_contract_migration.json` задаёт явный crosswalk. Хеш и полный ожидаемый crosswalk сверяются оценщиком до выполнения/проверки отчёта.

## Текущий контракт и исходный смысл

Продукт возвращает цитируемые источники без answer/edit authority. Свободный вопрос больше не создаёт proof roles или ответную сертификацию. Поэтому прежнее `answer_supported=true` заменено отдельным требованием **полного исходного факта из прежнего разрешённого источника**, а отсутствие ответа и права изменять обязательно во всех случаях.

| Исходный случай | Явный публичный выбор источника | Сохранённый обязательный факт / отрицательный смысл |
| --- | --- | --- |
| project_rule_prefers_canonical_policy | project_path + scope=project | ARCHITECTURE: RetryPolicyLimit is two attempts. |
| project_rule_rejects_advisory_only | project_path + scope=project | Внешняя рекомендация о пяти попытках не становится project fact; пустой отрицательный ответ не даёт authority. |
| implementation_fact_rejects_external_claim | project_path + scope=project | packages/orders/README.md: JSON records keyed by order id; внешний XML не заменяет этот факт. |
| dependency_fact_prefers_dependency_docs | library=python:tenacity@8.2.3:reference + version=8.2.3 | Полный прежний API-факт из прежнего Tenacity URL с реальным exact-version binding. |
| dependency_fact_rejects_project_guess_only | тот же explicit library/version | Project-local guess не становится библиотечной документацией отсутствующего record. |
| document_statement_binds_exact_path | project_path + scope=project | Полный must-never-move факт именно из docs/release-policy.md; release-notes не получает этот credit. |
| two_claims_require_two_allowed_roles | project_path + scope=project + тот же explicit library/version | Обязательны оба прежних полных факта: ARCHITECTURE и Tenacity URL; один не заменяет другой. |

Эти host bindings берутся из исходных явно заданных source roles и URL/version. Тексты вопросов не переписываются; lookup_queries всегда пуст. Роли остаются metadata протокола и проверкой источника, а не выдуманным выводом planner. Допустимая отдельно атрибутированная цитата соседнего проектного документа сама по себе не считается proof: полный требуемый факт по-прежнему должен находиться на конкретном исходном пути.

## Как исполняется фикстура

1. Существующий `eval.evidence_quality_v2.runtime` пишет только исходные project documents в явный finite catalog и проводит реальный confirmed public member transaction в отдельный host-owned store.
2. Для advisory-only negative нужен непустой member grant. Единственный дополнительный `FIXTURE_STATE.md` содержит нейтральный infrastructure text, явно отмечен в crosswalk и **не может считаться question evidence**.
3. Все исходные удалённые кандидаты, включая conflicting advisory, сохраняют точные исходные URL и текст. Каждый получает отдельный явно заданный v2 target/record. Tenacity сохраняет python/tenacity/8.2.3/reference и official/exact binding.
4. Вызывается реальный `prepare_docs(action=prefetch_docs_manifest)`. Наблюдается запуск настоящего worker thread, затем его завершение и реальный `docs_status(action=job)`. Никакого ручного registry upsert, marker или поддельного ready результата в фикстуре нет.
5. Подменяется только сетевой ввод: DNS возвращает один фиксированный публичный IP для явно выбранных hosts; HTTPTransport возвращает неизменённые fixture bytes для точных URL и robots controls. Реальные URL/security, redirect/size/robots policy, parsing, index, public handlers продолжают выполняться. Неизвестный host/URL и любой read-time network event вызывают ошибку.
6. Реальные committed active children читаются отдельным SQLite mode=ro observation: child/parent/source/generation identity, тексты, все диапазоны, хеши и version/scope metadata.
7. Выполняется один настоящий публичный get_docs_context с исходным вопросом и вышеописанными source bindings. Наблюдаются один application retrieval и одна фактическая финальная валидация. Query engine, ranker, candidates, projector и source snapshots не подменяются.

У текущего non-GitHub public manifest path нет подтверждённого atomic staging контракта новой typed application ingestion lane. Этот пакет проверяет реальную подготовку и record-specific stored sources, **не приписывает ей atomic staging proof**. В отчёте это явная false claim boundary. Фиксированные Tenacity bytes являются авторскими данными исходного eval, не результатом проверки live official documentation.

## Что проверяется после чтения

- Полные исходные факты на требуемых исходных путях/URL; обе половины mixed case обязательны.
- Точное совпадение видимого source row с snapshot того же вызова, полный candidate-hash domain и отдельный хеш исходных source bytes.
- Привязка к реально сохранённому active child и parent/source/generation identity, проверка char/byte/line диапазонов и сохранённого display_text.
- Project identity/scope/authority для проектных цитат; конкретный library record/version/exact snapshot для библиотечных.
- Исторический wrong-role source не заменяет разрешённый source. Неизвестный инфраструктурный или локальный absolute path не принимается за исходный факт.
- Отсутствие answer/edit grants и отсутствующая у lookup возможность получить original-query credit.
- До/после равны реальные bytes каждого project/library database, catalog/document hashes, active generation и registry-record digest. Снимок берётся **до первого реального чтения, без warm-up**. Возможный first-read write из P1.4 этим gate не скрывается.
- Source count, UTF8 bytes и token estimate только измеряются; output800 или final-source3 ceilings не вводятся.

## Контрпримеры и воспроизводимость

Сохраняются те же шесть имён self-controls. Они используют явно маркированные `oracle_unit_control` DTO, которые не проходят actual-runtime guard. Контрпримеры проверяют чужую библиотеку/версию/generation/hash, project guess вместо исходного URL, неверный путь и полный смысл факта, crop при сохранённом источнике, отсутствующие/лишние/повторные bindings, forged coordinates, authority, подмену вопроса/lookup credit, read-time network и изменение хранилища. Runtime-source manifest проверяется отдельно против фактических байтов checkout, в том числе при resealed wrong hash.

Runner записывает все семь observed rows до verdict, включая ошибки подготовки. В console даются причины, отсутствующие факты и реальные state differences. Verifier повторно вычисляет frozen row identity, факты, guards, сводку и общий verdict; ошибочный или честно красный отчёт не превращается в green. Историческое доказательство не используется как нынешний результат.

Общий runtime helper получает фиксированный для P1.5 required-path profile. Его прежний P1.4 default и весь source/authority/capture body остаются без изменения. В реальном запуске manifest содержит SHA256 репозиторных модулей, действительно импортированных тем же процессом, и текущий Git SHA.

## Точный пакет

| Путь | Base blob | Proposed blob |
| --- | --- | --- |
| eval/agent_developer_v1/current_retrieval_runtime.py | 866cd50bdb4605e511f386ba5bd2c7ebe84aba76 | d26bfe6affb8e2412b6a19625f975d2265ce8094 |
| eval/agent_developer_v1/finite_http_fixture.py | NEW | db5cafe4f456da53bb6d8c06a7352ea4a73f8b83 |
| eval/agent_developer_v1/mixed_retrieval_runtime.py | NEW | 3c0236d3b9b0e46f87e6db54ebd06e16425a02a8 |
| eval/agent_developer_v1/mixed_provenance.py | 53f8063ffcd07f068da0e394f173151c9a4cc92e | 2356484e064d834b6bb1435ee035f35998515463 |
| eval/agent_developer_v1/mixed_provenance_contract_migration.json | NEW | d9b699efefee5e9030e00d38533da8a2c296ab7a |
| scripts/run_mixed_evidence_provenance_gate.py | 641536c9cca768e7bea43ef87d2266aa89e9a422 | c3124d822361e978db36d9d21a4f193ca62f532d |
| scripts/mixed_evidence_provenance_self_test.py | a69f917c864529cae553d8c6d604e0ebeb7559f2 | e7f3f9a8fcaf04acc03add6859ca47f8189042c1 |

Все семь blobs удалённо прочитаны обратно и побайтово совпадают с подготовленными строками. JSON corpus/crosswalk hashes, сохранение шести test function names и отсутствие trailing whitespace проверены статически. Python AST/compile и runtime ожидают обычного CI.

## Команды CI

```sh
PYTHONPATH=. python scripts/run_mixed_evidence_provenance_gate.py --output "$RUNNER_TEMP/p1.5-current-provenance.json"
PYTHONPATH=. python scripts/mixed_evidence_provenance_self_test.py --report "$RUNNER_TEMP/p1.5-current-provenance.json"
```

Workflow обновлён: controls и syntax выполняются отдельно при успешной установке зависимостей даже после quality FAIL; полный JSON сохраняется через always upload. Установлен DOCATLAS_OFFLINE=1; --write/continue-on-error не добавлены. Исходные triggers, dependency install, action pins и contents:read сохранены. Все required CI/downstream/installed-client gates остаются отдельными.

Root независимо прочитал все семь implementation/oracle файлов и проверил реальные producer contracts: fetch_transport._request_pinned сохраняет original Host/SNI при запросе к разрешённому IP; docs_manifest_service запускает именно наблюдаемый _run_prefetch_docs_manifest_job. Review допускает публикацию измерения текущего контракта. Успешные runtime/quality результаты не заявлены до CI.
