# Аудит CI DocAtlas после step7

Срез: `ae81aaae82794bfcbf6c0ee777bfc2f76e0e0def` и локальные исправления CI.
Документ описывает проверки и ограничения, а не объявляет весь CI зелёным.
Вопросы, эталоны и подробные результаты blind holdout не читались.

## Последний подтверждённый полный core: 3f790c9c

Полный прогон выполнен на `3f790c9cfe104667c80a8df69c5f2d26a6ab6457`
с зависимостями uv.lock и `ORT_DISABLE_TELEMETRY=1`:
**79 FAIL, 1456 PASS, 10 SKIP, 136 deselected, 0 ERROR, 25 warnings; 281,36 с.**
Это завершённый полный прогон, а не арифметическое ожидание по целевым проверкам.

Точная сверка с официальными95 FAIL на ae81aaae:
**16 устранены, 79 прежних остаются, новых failures нет**.
Проверено, что все16 исправленных сценариев проходят; для одного переименованного
self-host теста проверен его текущий преемник. Два временно новых pruning-fixture
failures из прогона c932 теперь также проходят в полном наборе.

| Точка падения оставшихся проверок | Число |
|---|---:|
| Квалификация и diagnostics | 30 |
| Форма ответа, status или mock contracts | 29 |
| Отсутствующий факт / полный блок | 8 |
| Корпус или frozen protocol | 5 |
| Отдельный review продуктового договора | 5 |
| Импорт удалённого private module | 2 |
| **Всего** | **79** |

Эти группы описывают точку FAIL; они не признают все старые ожидания устаревшими
и не разрешают массово ослабить проверки. Оговорки и конкретные примеры ниже
сохраняются.

Текущие артефакты: `core-final-vs-official.json` (также
`core-confirmed-vs-official.json`), `remaining-79-classified.json`,
`core-confirmed-failures.json`. В них записаны commit, точные node IDs и SHA-256
исходных JUnit/логов. Исторический81-failure срез c932 сохранён в
`core-final-vs-official.c932.json`; прежняя82-классификация тоже сохранена.

Этот подтверждённый полный core-прогон относится к3f790c9c. Финальное
изменение replay binding на72a215a1 отдельно проверено повторной сборкой wheel
и официальным installed bilingual/large-packet сценарием: PASS. Это отдельный
уровень проверки, не полный core на72a215a1. Исторический installed-wheel PASS
для c932/3f790c9c сохранён; итоговый installed результат72a215a1 указан ниже.

## Что действительно было красным

GitHub CI основной ветки:

- [До step7, 610d9da6, run 42040910239](https://github.com/Vanilla1999/DocAtlas/actions/runs/42040910239): core Python 3.12 — 95 FAIL, 1431 PASS, 10 SKIP, 136 deselected.
- [После step7, ae81aaae, run 42117494090](https://github.com/Vanilla1999/DocAtlas/actions/runs/42117494090): core Python 3.12 — 95 FAIL, 1438 PASS, 10 SKIP, 136 deselected.
- Совпадает точный набор всех 95 красных node IDs. Число 63 в предыдущем отчёте относилось к выбранному поднабору, а не полному core CI.
- Отдельно от core появился регресс step7: bilingual-context-integration раньше проходил на трёх платформах, затем стал падать на всех трёх. Его причина — счётчики кандидатов/пропусков после pruning. Этим занимается основная ветка step8; равенство 95 core FAIL не исключало этого регресса.
- Installed MCP harness проходил на обоих коммитах.

Проверенные дополнительные причины красного CI:

1. Реальный холодный ответ `status=not_prepared` не разрешался advertised output schema. MCP SDK отвергал корректный ответ до чтения документации.
2. Installer fixtures не учитывали уже установленную настройку `DOCATLAS_MCP_COMPACT_TEXT=1`.
3. `context_tools.py` превысил лимит 1000 строк: 1037. Проверка uv.lock в этом job проходила; причина не в lock.
4. Self-host smoke ожидал старый cold status и не доходил до настоящей подготовки и проверки фактов.
5. Advanced recovery/mutation и systemic retrieval gates ссылаются на удалённые приватные функции/модуль. Такие import/crash не являются доказательством качества и не должны засчитываться как mutation kill.

## Исправления

### 34836f83 — cold response, installer, diagnostics extraction

Исправления продукта:

- Разрешён фактически возвращаемый `not_prepared` в двух advertised schemas.
- Наблюдение same-call diagnostics вынесено без изменения поведения в `_context_diagnostics.py`; основной handler снова меньше 1000 строк.
- Self-host fixture использует системный/TMPDIR временный каталог, без жёсткого `/tmp`.

Исправления проверок по действующим контрактам:

- Cold smoke проверяет `not_prepared/member_store_uninitialized`, отсутствие источников и прав на ответ/изменения, наличие явной команды подготовки с подтверждением.
- Installer ожидает актуальную compact-text настройку, сохраняя проверки пользовательского environment.
- Lookup coverage разрешена только для собственного lookup и никогда не переносится на original query.
- Project `db_path` не имеет права перенаправлять host-selected MCP store; проверяются отсутствие foreign writes и неизменность конфигурации.

Основания: `docs/adr/0003-context-first-project-reads.md`, `docs/modules/evidence-selection.md`, `docmancer/core/config_resolution.py::resolve_mcp_config`, `v2plan/mcp-storage/FRESH_PLAN_RU.md`, `docs/mcp-docs-server.md`.

Проверено: 35 целевых сценариев (28 + 7 после окончательной правки self-host), installer shell smoke, module-size gate, diff check. Это source/editable runtime, не установленный wheel и не реальный OpenCode.

### 4767035c — ONNX Runtime telemetry opt-out

Первый локальный полный прогон был остановлен automatic approval review: pytest неожиданно вызвал HTTPS к Microsoft telemetry endpoint; payload не был установлен. Этот отклонённый вызов не повторялся.

Read-only проверка выявила:

- В неприкреплённой установке загрузился ONNX Runtime 1.31.1 вместо 1.26.0 из uv.lock.
- Локальные `onnxruntime/Privacy.md` и бинарник подтверждают 1DS uploader и endpoint `mobile.events.data.microsoft.com`.
- [Официальный Privacy.md](https://github.com/microsoft/onnxruntime/blob/main/docs/Privacy.md) указывает полный штатный opt-out `ORT_DISABLE_TELEMETRY=1` до инициализации. Один `disable_telemetry_events()` после импорта может быть поздним для initialization event.

DocAtlas теперь выставляет opt-out до любых собственных runtime imports; CI выставляет его до pytest collection. Перенаправления передачи на другой endpoint или обхода запрета нет. Если внешний клиент сам импортировал ONNX ранее DocAtlas, этот предыдущий initialization не относится к гарантии нашего bootstrap.

Новый отдельный прогон с явным opt-out завершился без прежней блокировки: 90 FAIL, 6 ERROR, 1437 PASS, 10 SKIP, 136 deselected, 206.33 с. Из 96 красных результатов 82 совпадают с прежним CI, ещё 14 — одна дополнительная средовая причина (ниже).

### 444ef0c2 — реально локальный offline registry и изоляция transport fixtures

Исправление продукта: `default_registry()` при `DOCATLAS_OFFLINE=1` использует только LocalRegistry. Отсутствие необязательных файлов больше не создаёт HostedRegistry HTTP-клиент. До исправления он создавался даже при offline и падал в этой среде на SOCKS proxy без socksio — 8 FAIL + 6 ERROR. Исправление не отключает прокси для настоящих HTTP запросов: оно устраняет незапрошенный сетевой fallback из offline пути.

Два оставшихся `config_shadow` сценария обновлены по host-selected-storage контракту: явный валидный prepare успешен, поколение повторной операции остаётся тем же, чужой DB не создаётся, проектная конфигурация неизменна.

Vector fixture использует зарегистрированную подмену DNS и реальный SDK с `MockTransport`; только у этого mock HTTP client отключено наследование прокси. Поиск, индекс, фильтры доступа, источники и факты настоящие. Тест доказывает доставку/изоляцию векторного runtime, а не качество семантической модели.

Дополнительно обнаружен drift OpenAI SDK: latest установил 3.46.0 с httpx2, lock фиксирует 2.38.0 с httpx. Целевая финальная проверка выполнена с зависимостями uv.lock (ORT 1.26.0, OpenAI 2.38.0): **28 PASS, 4.04 с**, diff check PASS. Эти сценарии покрывают 14 средовых результатов и 3 прежних CI FAIL. Полный merged core должен запускаться основной веткой отдельно; арифметическое ожидание 79 старых FAIL не выдаётся за уже выполненный полный прогон.

Ни один тест не удалён и не переведён в skip. В первом commit одно название теста уточнено вместе с diagnostic inventory; число сценариев не изменилось.

## Оставшиеся 82: группировка по точке падения

Это классификация красных результатов полного прогона ДО последнего safe follow-up. Группа показывает, на чём остановился тест; она не автоматически признаёт ожидание устаревшим и не снимает FAIL.

| Группа | Число | Интерпретация |
|---|---:|---|
| Квалификация/приватные диагностические ожидания | 30 | Старые `qualified=True`, `matched_terms`, `budget.input/output`, точный состав ranking fields, старые retention вызовы. В текущем source-only контракте наличие исходника не доказывает семантическую достаточность. Нужен перенос значимых требований на конечную выдачу, не blanket update assertions. |
| Форма выдачи, статус, прежние mock contracts | 29 | Ожидание ровно одного фрагмента, отсутствие дополнительных provenance полей, `ok` против `truncated`, либо status как суррогат answer proof. Есть также старые синтетические входы без действующей scope/snapshot привязки. Требуется отдельное подтверждение каждого свойства. |
| Не хватает факта/полного блока в конечном тексте | 8 | Приоритет для продуктового разбора. Среди них два request-flow сценария зависят от дрейфующего frozen self-host protocol; остальные включают complete HTTPX block, condition lead, restriction+cause и dispatch checklist при малом бюджете. |
| Корпус/замороженный protocol не соответствует активным файлам | 5 | Четыре `witness text is absent` и один точный старый roster catalog roles. Нельзя менять gold под текущую выдачу: сначала зафиксировать исходный корпус или явно версионировать protocol. |
| Отдельный review продуктового договора | 5 | Три local-map случая, vector project route и tiny refusal budget. Они не разбираются безопасным механическим исправлением. |
| Исправлены последующим 444ef0c2 | 3 | Два host storage expectations и vector transport fixture. |
| Импорт удалённого private module | 2 | Language flow/packing experiments импортируют `_docs_context_projection_core`; реальные outcomes не выполнены. |
| **Всего** | **82** | Подробные node IDs и сообщения: `remaining-82-classified.json`. |

### Важные уточнения, чтобы не перепутать название теста с доказанным дефектом

- `test_public_removal_lifecycle_partial_source_integrity_trace_and_read_only`: off/on/off trace parity проходит. Позднее падает равенство patch_context и docs_context: patch содержит ещё один абзац Storage after return. Этот FAIL не доказывает изменение результата при включении логирования.
- `test_raw_owner_documents_and_private_meanings_never_leak_to_public_dto`: проверка отсутствия приватных полей проходит; падает вложенный старый guard, требующий `qualified=True` у исходного вопроса. Это не доказанная утечка приватных полей.
- `critical_mixed_same_call_snapshot`: условие одновременно требует старый точный набор шести полей source. Появление новых provenance/source URI полей ломает это условие; до него актуальный validator проходит. Нельзя по одному имени guard заключить, что сломан snapshot binding.
- `test_callable_scanners_empty_code…`: запрещённые чтения/сканирование не происходят (guards проходят). Builder создаёт unresolved current_behavior из переданного bare filename без hash. Это подозрительное утверждение о выбранном контексте, но не доказанное чтение чужого кода.
- `test_public_scope_never_implicitly_widens` на вопрос о foreign token возвращает нерелевантные, но принадлежащие текущему проекту README. Прямое расширение до чужого проекта этим FAIL не установлено.
- Tiny refusal budget проверяет размер JSON с пробелами, а публичный estimator — canonical compact JSON; показано 155 против 150 при canonical estimate146. Нужно определить единую wire serialization границу, не повышать лимит до PASS.

## Как переносить сломанные gates на актуальную публичную границу

| Gate | Что сломано | Корректная следующая граница |
|---|---|---|
| Recovery contract | Импорт `_docs_context_projection_core`, часть сценариев напрямую строит private projection | Тот же frozen вопрос и те же source bytes: явный cold `prepare_docs`, затем реальный `call_docs_tool_payload(get_docs_context)` или установленный stdio. Проверять цитату/hash/span/scope, отсутствие answer/edit authority, consent и конкретные recovery actions. |
| Recovery mutation | Текстовые mutants ищут удалённый файл/строки | Сначала зелёный публичный baseline на тех же источниках. Затем mutants действующего producer/validator: потеря цитаты, forged query credit, пропуск source/hash/scope guard, auto_execute. Засчитывать только именованный ожидаемый guard; import error/crash/timeout — инфраструктурный FAIL. |
| Systemic retrieval | `_expand_selected_snippets` удалён; patch может влиять на отсутствующий или больше не вызываемый этап | Реальный публичный baseline с неизменными фактами. Актуальные ablation точки регистрировать отдельной версией protocol, доказывая вызов изменяемого этапа. Старую контрфактическую оценку не объявлять работающей после простого переименования hook. |
| Language flow/packing | Старый `_prefer_missing_baseline_candidate` hook больше не задаёт текущую joint selection | Сравнить две явно заданные политики сборки на одинаковом подготовленном корпусе через публичный tool result. Сохранить прежние вопросы/обязательные факты и отсутствие переноса lookup credit. Не восстанавливать private shim только ради import PASS. |

## Артефакты аудита

Рядом с отчётом опубликован компактный пакет, без всех временных журналов:

- `github-ci-comparison.json`: точные списки 95 failing node IDs до/после step7 и jobs.
- `core-final-vs-official.json`: финальный полный core, точные исправленные и оставшиеся node IDs, хеши исходных JUnit и log.
- `remaining-79-classified.json`: текущая классификация; `remaining-82-classified.json` сохраняет предыдущий этап.
- `bilingual-installed-result-72a215a1.json`, `bilingual-selection-summary-72a215a1.json`: результат финального установленного пакета.
- `bilingual-wheel-provenance-72a215a1.json`: происхождение wheel, зависимости и хеши.
- `replay-payload-comparison.json`: побайтное сравнение обычных порций до/после исправления reader replay.

В последующих разделах сохранены названия исходных рабочих журналов и каталогов
для истории проверки; опубликованные переносимые результаты перечислены выше.

## История: полный merged core на c9320920

Основной агент выполнил полный core на merged tree с pinned dependencies:
**81 FAIL, 1454 PASS, 10 SKIP, 136 deselected**.
Точная сверка node IDs с официальным CI ae81aaae:

- 79 старых failures остаются;
- 16 из95 старых больше не падают (для одного переименованного self-host сценария проверен PASS его преемника);
- два новых failures — True/False arms существующего `test_pool_pruning_runs_only_when_the_whole_pool_misses_the_budget`.

Новые два failures не относятся к исправленным счётчикам. Оба —
`KeyError: evidence_id`: старый unit probe передавал только `snippet` и пустой
snapshot. После добавления continuation проверяемый вход связывается fingerprint
до точки, в которой этот probe намеренно прерывает selector. Коммит `1fd30e8f`
добавляет fixture source identity/hash и snapshot; исходные ожидания pruning и
обе ветки сохранены. Production не менялся. Весь `test_step7_context7_path.py` —
**7 PASS**. Тесты не удалены и не пропущены.

79 остающихся старых failures распределяются так:30 квалификация/diagnostics,
29 форма ответа/status/mock contracts,8 факт/полный блок,5 корпус/protocol,
2 removed private import,5 отдельный product-contract review. См. оговорки выше:
это группировка места падения, не массовое признание ожиданий недействительными.

Историческая сверка: `core-final-vs-official.c932.json`.
Результат целевой проверки: `step7-pruning-fixture.xml`.

### Отдельно проверен официальный bilingual installed-wheel сценарий

**PASS на Linux, Python3.12.14**, точная команда CI:
`python -I eval/opencode_compat/installed_stdio.py --bilingual-selection --large-packet`.
Запуск шёл из каталога вне checkout, с установленным wheel в отдельной venv и
зависимостями uv.lock. Для445 packaged файлов docmancer подтверждено байтовое
равенство product c932; последующий commit меняет только test fixture.

В merged RU+EN ответе: candidate_rows449, pruned_rows447, eligible_rows2,
selected_rows2, omitted_rows447. Оба независимых обязательных факта доставлены.
Strict schema, source hash/span fidelity, отсутствие metadata-only evidence,
неизменность файлов/SQLite, retained source references и large-packet arm прошли.
Это воспроизведение исправления прежней bilingual count regression на Linux;
проверку macOS и реального OpenCode не заявляем.

Артефакты: `bilingual-selection-final/RESULT.json`,
`bilingual-wheel-provenance.json`. Wheel SHA-256:
`1cbcededdd1d8b86c61f693da3da298d84e56578067762e366c5436c9b525374`.

### Финальный installed wheel после replay-binding исправления: 72a215a1

Повторная сборка точного `72a215a10006febaaa114a7ef5b66f84dd698d20`, установка
в новую venv и та же официальная CI-команда
`python -I eval/opencode_compat/installed_stdio.py --bilingual-selection --large-packet`:
**PASS, exit 0**. Зависимости uv.lock, Python 3.12.14, Linux; ORT telemetry отключена.
Для 445 файлов пакета подтверждено байтовое равенство исходному commit.
Исторические wheel/RESULT/provenance для c932 не изменялись.

Merged RU+EN: 449 кандидатов, 447 pruned, 2 eligible, 2 selected, 447 omitted;
оба обязательных факта доставлены. Strict schema, fidelity hash/span,
отсутствие metadata-only evidence и read-only files/SQLite проходят.
Ранее выданная reference остаётся читаемой после 128 references.
Large packet сохраняет 18 исходников и обязательный факт; trace не меняет результат.

Новые артефакты:

- `bilingual-selection-72a215a1/RESULT.json` — полный результат;
- `bilingual-selection-summary-72a215a1.json` — краткий итог;
- `bilingual-wheel-provenance-72a215a1.json` — точный commit, зависимости и hash результата;
- `bilingual-wheel-72a215a1/doc_atlas-1.3.2-py3-none-any.whl` — проверенный wheel.

SHA-256 wheel:
`0d1d4b084da693071496aefce4f03e6e0963c4deefc2848970236e1a33b6c618`.
Это installed MCP stdio на Linux; macOS, реальный OpenCode и полный core на 72a215a1
этим прогоном не заявляются.
