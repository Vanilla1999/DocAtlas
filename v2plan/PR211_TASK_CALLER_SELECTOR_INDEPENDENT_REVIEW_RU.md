# PR #211: независимый review content-witness follow-up

Дата: 2026-10-08. Reviewer: `footprint_audit`; автор тестового diff: `trust_contract`.

## Вердикт и предел доказательства

**APPROVED для публикации этого узкого test-only follow-up.** Найденная в CI
неполнота положительных fixtures исправляется через существующий явный
`public_requirements` contract. Ожидание `complete`, валидаторы, source fidelity,
host binding и отрицательные контроли сохранены. Production, retrieval,
evaluator implementations и ceilings этим diff не меняются.

Это независимый статический review, **не runtime PASS** семи nodes и не
acceptance PR #211. После публикации требуются повтор тех же семи nodes и общий
CI на конкретном head/merge checkout. Старые reports не переписаны.

## Проверенные версии и границы diff

Сравнение follow-up выполнено с опубликованным work-branch commit
`5bf3b00493577f68c816c90bb667f5ca84eabf75`. SHA-256 замороженных файлов проверены
независимо и совпали с сообщением автора:

| Файл | SHA-256 |
|---|---|
| `tests/task_level/test_github_models_adapter.py` | `d72d467f6380553824413376e9bcb047e9f8af42c5754a41aab2a1d6707bf54e` |
| `tests/task_level/test_runner_adapter.py` | `36b5783cee52218830f94bd305523361f995432daf782d9db2db3b4b737dcfd4` |
| `tests/task_level/test_task33_codex_exploratory.py` | `ad8b7f1a228a4d096e1cc5dd984c0ac05e1f991f6f564c7be70ae683ec7363cf` |
| `tests/task_level/test_task33_isolated_delivery.py` | `57fe17f0e563c99855a09e49e13645120d0575b0f798fa9e673bc5d6c40996a7` |
| `v2plan/PR211_TASK_CALLER_CONTENT_WITNESS_REVIEW_RU.md` | `de30bf0986f6f4998519fbf3dd98fa5cecd5024b0905e6c75f282e0772bacf12` |

Stdlib AST comparison подтвердил: относительно `5bf3b00` меняются только
следующие три test bodies и общий `_packet`:

- `test_required_once_retrieval_rejects_wrong_objective_error_and_malformed_packet`;
- `test_codex_normalizes_successful_required_once_retrieval_metadata`;
- `test_explicit_exploratory_delivery_is_persisted_as_non_causal`;
- `_packet` в `test_task33_isolated_delivery.py`.

Все остальные top-level functions/classes и остальные top-level AST statements
в этих четырёх modules совпадают. Имена, аргументы и decorators всех 53 test
interfaces (11/19/16/7) совпадают как с `5bf3b00`, так и с исходным `21fe472d`.
Все 61 прежних assertion AST в четырёх изменённых bodies сохранены; добавлены
53 assertions. `git diff --check` и AST parse: PASS.

Исходные `_snapshot`/`_envelope` exploratory и `_evidence`/`_snapshot`/`_envelope`
isolated по AST совпадают с `21fe472d`. Четыре исходных
isolated test bodies follow-up вообще не меняет. Их nodes остаются:

- `test_isolated_broker_requires_verified_boundary_and_never_retries`;
- `test_host_owns_retrieval_evidence_objective_and_usage_contract`;
- `test_isolated_broker_persists_recomputable_evidence_and_bounded_handoff`;
- `test_isolated_broker_rejects_an_insufficient_model_visible_projection`.

## Что фактически показал предыдущий CI

Независимо прочитан сохранённый concrete cases artifact для advanced run
[37805723255](https://github.com/Vanilla1999/DocAtlas/actions/runs/37805723255):
head `5bf3b00493577f68c816c90bb667f5ca84eabf75`, исполнявшийся merge checkout
`2f2252616deb2cd64b2a4bcce48f64e894b2bb2d`, 622 cases, 517 PASS, 105 FAIL,
0 errors, 0 skipped. SHA-256 сохранённого cases JSON:
`217cfbedfd7ac6c877a09d8b14ea57c9ded232b1552a866bf26f593b84a7c655`.

Во всех семи перечисленных cases действительно записан `failure` с фактическим
`partial` вместо ожидаемого `complete`. В JUnit нет полного payload с `missing`.
Следовательно, `visible_content_assignment_required` пока является выводом из
прочитанного producer и fixtures; его точное runtime значение проверяют новые
assertions. Авторский report проводит эту границу корректно.

## Проверка текущего контракта

Независимо прочитаны цепочка producer/selector и потребители metadata/broker.
Следующие файлы побайтово совпадают с исходным
`21fe472d983f394130849d6fd4e582043d58e9ba`:

- `docmancer/docs/application/_action_packet_part03.py`;
- `docmancer/docs/application/evidence_requirements.py`;
- `docmancer/docs/application/_evidence_selection_shared.py`;
- `docmancer/docs/application/_evidence_selection_part02.py`;
- `docmancer/docs/application/_evidence_selection_part03.py`;
- `docmancer/docs/domain/_answer_units_part01.py`;
- `docmancer/docs/domain/_answer_units_shared.py`;
- `eval/task_level/_github_models_part01.py`;
- `eval/task_level/runners/codex.py`;
- `eval/task_level/_isolated_delivery_part02.py`.

`build_requirements(..., profile="generic")` не выводит content obligations из
обычного objective. Evidence/target paths задают identity obligations.
`_evidence_selection_part03.py` требует хотя бы одного assignment с `unit_id`
для полного patch selection и иначе добавляет
`visible_content_assignment_required`. Явный string в `public_requirements`
создаёт mandatory `required_fact` с provenance `public_task_contract`;
`_legacy_requirement_matches_unit` сопоставляет его точному `unit.text` и даёт
`generic_fact` witness. Это существующее подтверждение literal coverage;
никакое разрешение редактировать или утверждение о правильности решения из
него не следует.

Оба required-once consumer требуют совпадения исходного objective, валидного
flat v4 payload, `data` и `complete`; Codex дополнительно требует explicit
`patch_context`. Поэтому сохранение положительного `complete` и отдельная
проверка отклонения настоящего valid partial соответствуют проверяемому ABI.

## Review fixtures и сохранённых guards

| Участок | Вывод независимого review |
|---|---|
| GitHub metadata | Единственное исходное предложение становится явным literal requirement. Проверяются requirement ID, mandatory/provenance, source identity/path, unit ID/hash/span и отсутствие `missing`. Реальный второй builder/projector без requirement оставляет те же полные sources и valid partial; matching-objective consumer обязан отказать в success. Прежние wrong-objective/error/malformed/wrapper/edit-grant negatives сохранены. |
| Codex normalization | Тот же explicit content witness, настоящий projector/snapshot validator и прежний complete positive. Дополнительный valid partial идёт через настоящий JSONL structured-content lane; правильные objective и format не дают success при `partial`. Все четыре прежних negative variants сохранены. |
| Exploratory delivery | Authored docs quote добавляется к прежним evidence/target identity requirements. Без actual target window fixture требует точную target-path причину partial и прежний broker rejection. С target window остаются complete, target identity, два целых sources, hashes/spans и новая связь docs quote с настоящим unit. Exploratory/unverified tier, non-causal claim и envelope budget сохранены. |
| Isolated broker | Обе заранее написанные строки fixture явно перечисляются как literal requirements; source остаётся одним полным window. Проверяется каждый assignment, source identity/path, точный срез текста и SHA-256 unit. Поддельный fixture создаёт пакет относительно собственных bytes, после чего неизменный broker test проверяет его против оригинального host snapshot. Это сохраняет проверку host authority. |

Objective, source text, source coordinates и исходные host helpers не изменены.
`edit_ready=False`, `instruction_trust=untrusted_data`, отсутствие восстановленного
v3 scaffold/intent, подлинные validators, usage/capability/attempt/revision/query
guards и пересчёт token estimate сохраняются. `<=1500`, `envelope.token_budget`
и остальные frozen ceilings не повышены. Дополнительные assignments могут
влиять на размер packet; существующие budget assertions остаются runtime gate.

Формирование требований из строк **авторского fixture** здесь проверяет caller
ABI и host binding. Review не считает его доказательством semantic actionability,
полноты ответа на objective или права исполнять содержащуюся в источнике команду.
Actionability, frozen semantic-density и deferred retrieval conflicts остаются
за пределами этого slice.

## Следующая обязательная проверка

Actual pytest, builder/selector/projector execution, workers, installed/client
delivery и новый общий CI при этом review **NOT RUN**. Project modules локально
не импортировались, зависимости не скачивались. Одобрение относится к ровно
указанным frozen hashes; окончательные outcomes должны быть записаны отдельно
после публикации и исполнения на указанном SHA.
