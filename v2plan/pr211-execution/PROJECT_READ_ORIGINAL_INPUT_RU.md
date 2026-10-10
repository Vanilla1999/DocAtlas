# PR211: исходный длинный вопрос и действующие границы работы

## Наблюдение и текущий контракт

На опубликованном HEAD `0065ce62cacaa31a41e4567717e3c67d602f578b`
(merge `e4084e51b73725990a107e8b8fc930a8edb46f75`, tree
`628bb7a2eb16f740ce84384925531040f7ec9f5e`) critical baseline имеет
60 cases, один FAIL: `critical_project_read_request_work_bound`.
[Acceptance reader130](https://github.com/Vanilla1999/DocAtlas/actions/runs/38024963940/job/114135542071)
прочитан полностью: 642613 UTF-8 bytes, SHA-256
`db7554f76f20570a38c61035d9af43bf85cdb45792f1dd048fe85278b8211a8c`.
JUNIT_FOCUSED сохраняет helper line321 и label `oversized_original`.
Соответствующий неизменённый input `"x" * 4001` взят отдельно из exact
fixture blob `cb8bb289c5e7ce5b170011beffc33213c326ad69`, line317.
Critical mutants после нездорового baseline не запускались.

Предыдущие hash-domain проверки этого case уже пройдены; это новый первый
наблюдаемый отказ. Он не означает превышение measured retrieval work.

Независимый source review установил различие контрактов:

| Источник | Exact blob | Действующий контракт |
| --- | --- | --- |
| `docmancer/mcp/_docs_server_tool_data.py` | `48f61bc14fa40de5552014775fc10ad3f256a814` | Public question: string, minLength1, без maxLength. Explicit lookups: максимум5, по500 символов. |
| `docmancer/docs/interfaces/mcp/context_tools.py` | `28fd767567e5c32124d84496a5937a87ee62164c` | Непустой исходный question передаётся application без обрезания. |
| `docmancer/docs/domain/_project_answer_contract_part02.py` | `54ab01212e66a0ad3a55cc79119cd721b20c3660` | Hash полного вопроса; historical4000 отмечается в input_limits, не создаёт public veto. |
| `docmancer/docs/domain/question_plan.py` | `fb52a3cd561e24e4f127f20786dbd9bbcbb55b0a` | Внутренняя legacy обработка ограничена4000; эта граница сохраняется. |

CURRENT_WAVE_DECISIONS сохраняет действующие operational work/read/call/time
bounds, но не вводит отсутствующий public question ceiling4000.
Старая PROJECT_READ_PRESENTATION note перечислила oversized original среди
отрицательных проверок без основания в owning public contract.
Настоящее уточнение заменяет только это ожидание. Новый числовой потолок
не добавляется; production/schema/legacy parser этим slice не меняются.

## Узкая миграция существующего control

Тот же исходный `"x" * 4001` сохранён. Вместо раннего veto observer перехватывает
один application call и проверяет полное побайтно неизменённое значение question.
Затем observer намеренно возбуждает TimeoutError до retrieval. Dispatcher отдельно
запрещён. Guard `critical_project_read_original_input_fidelity` требует:

- ровно один вызов с полным original;
- отсутствие публичных sources;
- status=failed вследствие контролируемого прерывания.

Это проверка передачи input, а не здоровая native retrieval длинного вопроса,
не качество ответа и не доставка подставленного DTO. Старый source/context не
подставляется в ответ длинному вопросу.

Проверка шести explicit lookups сохраняет прежний
`critical_project_read_request_work_bound` и запрет достижения application.
Поздние independent dispatcher TimeoutError/no-retry, patch completion,
storage-state и все ранние native source/body/owner/catalog guards неизменны.

Нет новых pytest functions, selectors, fixture documents, native reads,
member preparations или dispatcher acquisitions. Один прежний public control
заменён одним public control; label `oversized_original` явно мигрирует в
`long_original_identity`. Исходные24 тела и первоначальный public read неизменны.
Это не сокращение вычислительной стоимости helper.

## Directed fault

`project_read_original_is_not_truncated` меняет единственный production anchor:

```python
    question = args.get("question") if isinstance(args.get("question"), str) else ""
```

на тот же expression с `[:4000]` перед передачей исходного вопроса.
Все ранние реальные вопросы существующего selected case короче4000;
fault должен дойти до intended final guard, а не сломать другой source scenario.

- Killer: `tests/test_mcp_delivery_member_transaction.py::test_real_service_retrieves_committed_fixture_member_bytes[none]`.
- Expected: ровно1 assertion failure,0 errors/skips;
  `critical_project_read_original_input_fidelity`.
- Source before SHA-256: `4265329b1f34321234a8754098277cc986ddc342c56e9f08eb53f641e67381b2`.
- Source after SHA-256: `bf939bd50a99cdcf320e6115ae0ed4ab9acee6c289e2e202dbcf4786d02621bc`.
- Source anchor count1; source import уже входит в owning runner inventory.

Все38 прежних mutants,49 import owners,16 selectors и61 baseline cases остаются.
Append добавляет один fault: следующий target **61 healthy /39 intended kills**.
Executor, JUnit/import validation, historical/compact literal comparison и
его input-bound mutation не изменяются. Новый runtime **PENDING**.

## Reviewed manifest

| Path | Mode | Base blob | Proposed blob | Physical lines |
| --- | --- | --- | --- | ---: |
| `eval/agent_developer_v1/project_read_presentation_controls.py` |100644|`cb8bb289c5e7ce5b170011beffc33213c326ad69`|`11a71021d2f1bb52aff95f53467d9c70ef77f911`|369|
| `scripts/run_critical_mutation_gate.py` |100755|`6d418ac161d0dbbc1d7b1d5459266a73c51cb83d`|`e8acf1d3e91cdc37b1eb1b1296f57a9bbf9044c2`|959|
| `v2plan/pr211-execution/PROJECT_READ_ORIGINAL_INPUT_RU.md` |100644|NEW|этот документ| |

Helper SHA-256: `0ecbe5cfe8925511359e56a47411e4ab7ed8011a519ba6dffd435453efbf36c8`.
Runner SHA-256: `b6e4dd01963cdce7fec9cbfc2ea5ef44b969a0d16fcf52dbb442508111dc51eb`.
Exact inverse восстанавливает оба base source; helper/native corpus вне
объявленного control и старый executor побайтно неизменны.
Независимый code/contract review получен до commit. Runtime/AST/import/pytest
локально не выполнялись; новое доказательство ожидается в существующем PR CI.
