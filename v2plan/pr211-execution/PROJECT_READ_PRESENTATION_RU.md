# PR211: acquired project windows and the bounded control view

Статус: узкий product slice, исходники reviewed; новый runtime и directed fault **PENDING**.
Исходный published base: PR head `cadeef515ea78c78338821f38b15fed3bde7c993` (118).
Runner base: slice119 `015135ccd27685ba888b4a74250f08c252907ed3`.
Ни frozen V2/P14/P15 вопросы, ни gold, ни qualification thresholds здесь не меняются.

## Подтверждённая причина, actual118

В reader job [114118025694](https://github.com/Vanilla1999/DocAtlas/actions/runs/38019193867/job/114118025694)
получены все три `V2_DELIVERY_OPERANDS` заголовка. SHA-256 точного decoded log:
`c531b3800493f54970adadb724b84a49ccbb12535d86aebc254bc5612f3bb7c2`.

Для `v2-natural-request-flow`, исходный вопрос:

> Как проходит запрос get_docs_context от MCP-входа до выбора источников?

Исходные три host lookups:

1. What does the documentation request boundary accept?
2. How does the application pass a project question to retrieval?
3. How do retrieved chunks become selected visible sources?

| Наблюдаемая граница | Actual118 |
|---|---|
| Member result | success, requires_confirmation=False; 31 windows, 15 qualified |
| Project routing control, до fit | 27 items; 18,457 projected bytes |
| Project routing control, после fit | 20 items; 12,016 projected bytes |
| Project stage | budget_exceeded=True, status=insufficient; item limit20, byte limit65,536 |
| Project public-delivery operand | status=success; deliverable=False, partial_navigational_context |
| Unified operand | status=success; deliverable=False, required_evidence_missing |
| Public | sources=[], context unavailable; projector не достигнут |

Byte ceiling не достигнут. `fit_stage_items` применяется к уже полученным Python objects:
считает routing projection и ограничивает представление. Он не выполняет retrieval,
SQL, source read, network call или time-budget execution. Это не доказательство
превышения acquisition work.

Исходники: `retrieval_routing.py` blob4594c7cf235181249b1be0d6b0252a0c87cf2e2d,
`_project_context_service_part01.py` blob4bbc35fe1ccb6c947a74b1eb58662521a9d51554.
Последний перед delivery проверял общий `routing_budget_issues`, включая этот
post-acquisition control-view overflow.

По точным stable IDs/raw spans из 15 qualified member windows девять дошли до
Project и Unified; шесть отсутствуют на этих границах. Внутренние IDs всех27
prefit items не записаны: нельзя утверждать, что каждый из шести удалён именно
fit20, а не предшествующей source diversity. Пример пропавшего уже qualified окна:
`docs/modules/project-context-retrieval.md` [2053:2526],
`child-01d6277855a187ec8ef4785b6595ac807b6f744b`, lookup2.
Project и Unified содержали одинаковые20 окон. Этот slice исправляет первую
подтверждённую границу, не приписывает ей все оставшиеся quality failures.

## Контракт изменения

Сохраняются два разных представления одной конечной acquisition:

- Прежний bounded control: обычный rerank, diversity, fit20/64KiB, routing record,
  warning, downstream selection/support/snippets/metrics выполняются в прежнем
  порядке над прежним prefix. Остальные stage bounds не изменены.
- Read presentation: отдельный pure rerank уже возвращённых текущих members
  с `retain_found_windows=True`; остаются public-query qualified traces или
  повторно проверенный strict literal body context. Это не новый вызов facade,
  не включение его retention protocol и не новый search schedule.

Сохранённый набор формируется только после прежних catalog membership,
whole-source hash, catalog-entry hash и resolved evidence-path checks.
Rerank сохраняет lifecycle/current checks и не добавляет query credit.
Существующая annotation обрабатывает union, после чего bounded prefix немедленно
отделяется. Она по-прежнему принудительно ставит `instruction_trust=untrusted_data`
и проверяет path attribution. На дополнительных уже полученных windows возможны
её обычные `Path.resolve` вызовы: **zero-FS-calls не заявляется**. Новый путь
не инициирует acquisition/SQL search/network/source-body read.

В конце, после всех прежних answer/support решений, exact missing windows
присоединяются к context_pack; trust source inventory обновляется без answer grant.
Source count, overflow, found bytes и lookup coverage не дают original coverage,
semantic proof или edit authority.

Разрешение read delivery требует одновременно:

- Непустой реально admitted read pack и обычный read, не patch-retention запрос.
- Project status success/partial_success, отсутствие invalid-catalog blocker,
  consent и dependency confirmation blocker; итоговый status также success/partial_success.
- Dependency, если она есть, success/partial_success, без requires_confirmation
  и stale_before_refresh.
- Ни одного budget issue других stages. Все семь прежних append sites отдельно
  отмечены typed stage keys; reason strings не разбираются и не удаляются.
  Исключается только quota materialized `project_docs` control view.

`ProjectDocsResult` в current models9bb323e4 не имеет delivery_decision.
Его status/consent outputs сохранены. Явный ProjectContext delivery veto ниже по
цепочке остаётся обязательным для Unified и MCP; это отдельный replay control.

Существующая explicit patch retention ветка и её completion/ACK contract не менялись.
Facades без такого протокола не получают его автоматически. Public projector
по-прежнему заново проверяет immutable source identity/body/span/current scope,
query attribution и source eligibility.

## Проверка без новых обычных pytest функций

В существующем
`test_real_service_retrieves_committed_fixture_member_bytes[none]`
добавлен вызов helper после всех старых cold-read, 50,113-byte protocol, read-only,
late write/generation и повреждённых ancillary-ledger guards.
Остальные два git_kind не выполняют новый helper. Все35 имён/116 collected cases
модуля и прежние assertions сохраняются.

Новый helper создаёт отдельный private host store и finite24-doc project через
неизменённые `write_project` / `index_project`.
Независимые тела используют AlphaWindowRecord/BetaWindowRecord и Unicode λ;
в frozen V2/P14/P15 corpus они не добавляются.

Планируемая фактическая работа, **не receipt PASS**:

1. Один настоящий public read. Identity-return observers проверяют один member,
   Project, Unified и final-validation return; четыре настоящих dispatcher calls:
   два исходных с различными authority filters и два явно переданных lookups.
   Все limit20; одинаковый положительный конечный token budget, scope/root/class
   неизменны. Новые queries/fallback calls не допускаются.
2. Независимые24 SQL children подтверждают полный body, raw SHA, stable ID,
   project owner, generation и различные UTF-8 byte/character spans.
   Member должен вернуть все24 qualified только по авторским host lookups.
3. Bounded control остаётся20, сохраняет actual budget warning и routing fields.
   Project и Unified должны содержать те же24 exact current windows и delivery=True.
4. Public проверяется на обе host directions, отсутствие original coverage,
   answer/edit=False, полные тела **каждого реально выбранного** source и его
   same-call immutable SQL binding. **24 public sources не обещаются.**
5. Одиннадцать отдельно обозначенных member/dependency operand replays:
   project consent/stale/catalog/error; stale windows, foreign paths,
   changed body/catalog hashes; dependency overflow21→20, explicit consent
   при success и stale-before-refresh при success. Они вызывают настоящий
   ProjectContext над копией полученного member DTO; повторный search запрещён.
6. Ещё пять отрицательных проверок: explicit Project delivery=False через
   настоящий Unified/MCP; больше пяти host lookups; oversized original;
   injected dispatcher TimeoutError без повторной попытки; отсутствие completion
   у подставленного patch facade. Это faults/replays, а не новые genuine acquisitions
   или измерение wall-clock timeout implementation.

Для injected `TimeoutError` проверяется действующий public error contract:
`status=failed`, `error.reason_code=network_required`,
`error.exception_type=TimeoutError`, `error.where={tool:get_docs_context,
handler:None,phase:execution}`. Классификация взята из неизменённых
`_docs_server_part01.py`9e6e57df и `error_contract.py`7b24f4b9;
она не означает выполненный network call или разрешение повторной попытки.
Обязательные одна прерванная попытка и отсутствие sources сохраняются.
Черновое ожидание `status=error` исправлено по source review до запуска.

Fingerprint всех host-storage files/directories, generation, catalog и fixture
docs сравнивается до холодного native read и после всего helper. Replays не меняют
исходный DTO. Расширение одного pytest case не выдаётся за сокращение вычислений:
число внутренних операций и их cost должны быть измерены новым CI.

## Directed mutation

Critical runner119 получает один existing-node selector и одну fault:

- `project_read_preserves_already_acquired_windows`: удаляет только final append
  read presentation к bounded pack; source anchor ровно один.
- Intended guard: `critical_project_read_preserves_acquired_windows`.
  Member24 и bounded20 checks выполняются раньше. Старые small native reads
  не теряют дополнительных окон, потому что их bounded prefix уже содержит их.
- Старые30 mutants и runner execution/strict validation сохраняются побайтно.
  Target этого slice: **55 baseline cases /31 directed mutants, PENDING**.
  Последующие отдельные cap-precheck additions могут изменить joint target.

## Точный manifest

| Path | Mode | Base blob | Proposed blob |
|---|---|---|---|
| docmancer/docs/application/_project_context_service_part01.py | 100644 | 4bbc35fe1ccb6c947a74b1eb58662521a9d51554 | ca3a36829898bd76d3a21afd82f2f0bd92881e90 |
| eval/agent_developer_v1/project_read_presentation_controls.py | 100644 | NEW | 6cee024ec37691e919c1ccfa636c58cdd77f8f87 |
| tests/test_mcp_delivery_member_transaction.py | 100644 | 45b3f7488361e2e66948ca812dcc7b139b6790cd | efabde91b03e810472180ac89a45935cd639f0d1 |
| scripts/run_critical_mutation_gate.py | 100755 | 015135ccd27685ba888b4a74250f08c252907ed3 | 7565f0c22d74697224931b321cc1360a8f0799ad |
| v2plan/pr211-execution/PROJECT_READ_PRESENTATION_RU.md | 100644 | NEW | этот файл |

Production990lines; existing member test990; helper356; runner879.
Exact source/blob roundtrips и inverse edits выполнены как text processing.
Локальных Python/import/AST/pytest/runtime запусков не было.

## Remaining boundaries

Current `_docs_context_projection_core.py`15cc1f04 lines603–610 отдельно
отклоняет source без нового направления: `no_new_direction`.
Поэтому наличие24 windows в Unified не означает24 публичных источника;
наличие delivery не означает полный V2 answer или четыре требуемых факта.
Эту отдельную selection policy здесь не расширяем и не скрываем слабым oracle.

Actual нового совместного SHA, новый native/helper baseline, intended fault kill,
V2 flow quality, installed/client/downstream acceptance остаются pending.
Ни одна старая quality failure не объявляется снятой только по этому source review.
