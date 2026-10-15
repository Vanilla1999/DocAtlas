# PR #211: v4 callers в task-level tests

Дата: 2026-10-08. Авторский rationale ограниченного test-only slice.

## CI evidence и граница

Исходная PR-база: `21fe472d983f394130849d6fd4e582043d58e9ba`.
Повторный advanced CI run `37802068737`, job `113396563670`, связан с head
`b68759e65f52317928ba22166248e679098024ae` и реально исполнял merge checkout
`964056442f67b0d913310d3f8a295deb3c90263e`. JUnit artifact `11560662642`:
109 failures, 513 passes. Exact set всех 109 failed nodes совпал с прежним
run `37796983129` / job `113378894588`; новых или исчезнувших nodes нет.
Это сравнение inventory, а не утверждение, что причины всех failures одинаковы.

Девять failures остановились на
`build_action_packet() got an unexpected keyword argument 'max_tokens'`.
После чтения producer и consumers выяснилось, что удаление аргумента само по
себе скрытые v3 expectations не мигрирует. Координатор отдельно разрешил
семь ABI/wire/host-binding cases, оставив два конфликтующих legacy tests без
изменений. Этот slice меняет только четыре test modules и настоящий документ:

- `tests/task_level/test_github_models_adapter.py`: только
  `test_required_once_retrieval_rejects_wrong_objective_error_and_malformed_packet`;
- `tests/task_level/test_runner_adapter.py`: только
  `test_codex_normalizes_successful_required_once_retrieval_metadata`;
- `tests/task_level/test_task33_codex_exploratory.py`: только
  `test_explicit_exploratory_delivery_is_persisted_as_non_causal`;
- `tests/task_level/test_task33_isolated_delivery.py`: общий `_packet` и четыре
  исходных max_tokens failure nodes. Timeout/capability/no-retry node сохраняет
  прежнее тело и получает действующий packet через общий fixture helper.

Production, evaluator implementations, one-call edit loop, test markers,
diagnostic manifests, golds, frozen protocols и CI gates не менялись. Другие
legacy nodes в этих же modules не переписаны ради зелёного результата.

## Действующий контракт

`docmancer/docs/application/_action_packet_part03.py::build_action_packet`
принимает явные evidence/target requirements и сохраняет целые admitted windows.
Producer и `model_visible_projection.py::project_patch_context` не принимают
retired representation cap. v4 использует `schema_version=4`,
`result=data|failure`, `completeness=complete|partial|unavailable`,
`edit_ready=False`; он не выдаёт прежний task scaffold, `status` или edit grant.

`eval/task_level/_github_models_part01.py::_required_once_retrieval_metadata`
и `runners/codex.py::_required_once_retrieval_metadata` уже принимают плоский
валидный `kind=patch_context` payload. Успех metadata требует совпадения
исходного objective, `result=data` и `completeness=complete`; Codex дополнительно
проверяет явно переданный `context_format=patch_context`. Вложенный
`delivery_strategy/action_packet` не является действующим wire format.

`eval/task_level/_isolated_delivery_part02.py::_deliver_with_worker` связывает
objective через `HostEvidenceSnapshot.validate(envelope)` до worker call.
Документ и поле из worker packet не определяют task objective. Broker проверяет
сам packet против host evidence, обязательные evidence paths/categories и
явные target assignments. Пакет с упомянутым в документе именем файла не
заменяет host-selected target source. Result/metrics используют v4
`result`/`completeness`.

Исторические evaluator ceilings продолжают действовать отдельно от uncapped
representation: broker сравнивает реальный размер с `envelope.token_budget`,
actionability сохраняет 2000-token admission gate. Превышение нельзя исправлять
обрезанием evidence producer, повышением числа в test или изменением gold.
Текущее разделение дополнительно закреплено
`tests/test_action_packet_v4_contract.py` и `tests/test_action_packet_v4_eval.py`.

## Миграции и сохранённые guards

| Область | Положительный контроль | Отрицательные/сохранённые ограничения |
|---|---|---|
| GitHub metadata | Реальный builder → projector → snapshot validator → flat JSON; matching objective должен приниматься | Wrong objective, error text и malformed packet остаются отвергнутыми; добавлены legacy envelope и forged `edit_ready=True`. Negative wrong-objective больше не проходит только потому, что весь fixture имел устаревшую форму |
| Codex JSONL | Реальные started/completed events с explicit patch format и flat structured content; один call, clean retrieval-policy audit и v4 metadata | Wrong objective, omitted format, legacy wrapper и edit grant не становятся successful retrieval |
| Source fidelity metadata fixtures | Непустая единственная source row с полным текстом, исходным path, SHA-256 и точными char/line coordinates; projector сохраняет sources | Даже AGENTS.md и declared canonical authority остаются `instruction_trust=untrusted_data`; `edit_ready=False`; snapshot validation остаётся реальным вызовом в тесте |
| Isolated boundary и timeout | Общий `_packet` создаёт валидный непустой v4 packet и проверяет текст/hash/non-authority | Capability denial до call; timeout после одного call; attempt нельзя повторить; прежние guards и counters сохранены |
| Host evidence/objective/usage | Host envelope и snapshot имеют исходные fingerprints | Boolean/float retrieval counts, revision/query/objective mismatch, некорректный usage, invented evidence, mutation host evidence остаются denied. Wrong objective проверяется изменённым host envelope до worker call; injected v3 task scaffold отдельно отвергается как invalid packet |
| Persisted handoff | Actual result/projection/persisted snapshot согласованы; источники не теряются | Существующий `<=1500` assertion сохранён; artifact set, source/evidence/usage fingerprints, no raw parent evidence, one retrieval/attempt, timing/usage значения и non-authority сохранены |
| Failed projection | Fixture соответствует v4 failure/unavailable, с canonical token estimate | Broker отклоняет failed projection и не сохраняет принятые packet/projection artifacts |
| Explicit exploratory target | Создаётся конкретный fixture source file; его полное окно добавлено к host-selected evidence, original target requirements сохраняются | Без target source вызывается прежний target-module guard; documentary filename mention недостаточно. Envelope budget сохраняется; sources/hash/span/assignment/fingerprint проверяются; exploratory tier, `causal_claim_allowed=False`, `server_request_id_verified=False` остаются прежними |

Реальные source validators и consumer functions выполнятся в подготовленном CI.
Этот rationale не выдаёт статическое чтение за успешно пройденный delivery.

## Два самостоятельных contract conflicts — без изменений

`tests/task_level/test_actionability_projection.py` сохранён побайтово от
`21fe472d`. Его positive требует `requirement_recall`, `requirement_precision`,
`critical_invariant_recall`, `behavioral_scope_coverage` равными 1 и
`mutation_ready=True`. Текущий actionability consumer для v4 намеренно не
сертифицирует normative/workflow claims, возвращает для этих метрик 0,
`mutation_ready=None` и отдельное unsupported warning. Реальная source/citation
coverage измеряется отдельно. Даже после удаления двух retired max_tokens
caller arguments остаётся этот контрактный конфликт; 2000 gate также остаётся.

`tests/task_level/test_task33_semantic_density.py` также сохранён побайтово.
Его frozen positive одновременно требует inferred mutation intent/ready,
`source_of_truth`, `target_surface`, `invariants`, `mutation_ready=True`,
`edit_ready=True` и сохранение нужных фактов в 2000 tokens. v4 не извлекает из
prose разрешение на editing или task scaffold. Исчезнувшие поля и grants нельзя
вернуть через fixture, а frozen 2000 потолок нельзя повысить, отменить или
объявить выполненным из-за наличия полного oversized evidence. Нужна отдельная
контрактная работа с явно сохранённой исторической acceptance границей.

Ни один из этих двух tests не помечен skip/xfail и не исключён из CI. Их red
status не скрывается семью мигрированными callers. Frozen retrieval 800-token
gate и отложенные retrieval problems также не затронуты.

## Локальная проверка

- `git diff --check`: PASS для четырёх owned modules.
- Stdlib AST parse: PASS. AST сравнение с `21fe472d` показывает изменения только
  в разрешённых function bodies и `_packet`; других functions/classes изменений нет.
- Все имена, arguments и decorators 53 test nodes сохранены (11/19/16/7 по
  modules выше); hashes совпадают с `tests/diagnostic_labels.json`.
- Два отложенных test modules побайтово совпадают с `21fe472d`.
- Pytest, repository imports, реальный builder/projector/validator, worker/server,
  Git fixture subprocesses и network/provider здесь NOT RUN. Runtime без
  зависимостей не заменён их скачиванием или permission workaround.

Команда для существующей подготовленной offline CI-среды после публикации
общего reviewed SHA:

```sh
pytest -q \
  tests/task_level/test_github_models_adapter.py::test_required_once_retrieval_rejects_wrong_objective_error_and_malformed_packet \
  tests/task_level/test_runner_adapter.py::test_codex_normalizes_successful_required_once_retrieval_metadata \
  tests/task_level/test_task33_codex_exploratory.py::test_explicit_exploratory_delivery_is_persisted_as_non_causal \
  tests/task_level/test_task33_isolated_delivery.py::test_isolated_broker_requires_verified_boundary_and_never_retries \
  tests/task_level/test_task33_isolated_delivery.py::test_host_owns_retrieval_evidence_objective_and_usage_contract \
  tests/task_level/test_task33_isolated_delivery.py::test_isolated_broker_persists_recomputable_evidence_and_bounded_handoff \
  tests/task_level/test_task33_isolated_delivery.py::test_isolated_broker_rejects_an_insufficient_model_visible_projection
```

Перед publication требуется independent review exact diff/hashes. После него —
общий CI inventory и полный required acceptance на конечном SHA; данные этого
slice не являются merge-ready verdict для PR #211.
