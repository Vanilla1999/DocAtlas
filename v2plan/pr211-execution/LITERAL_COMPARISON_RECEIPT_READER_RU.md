# Existing literal comparison: reader для сохранённых доказательств

Статус: подготовлен отдельный report-only slice; собственный runtime нового
reader **PENDING**. Production, pytest selections, protocol и mutation runner
этим изменением не редактируются.

## Фактическая причина

В CI126 (PR HEAD `d76f6ab85e12f482ad6bec1d43040899f4b0a532`,
merge `8120a80bbb0309a3ec0bf4add71f568666c76772`) существующий step16
`Compare historical and compact literal contract tests` завершился SUCCESS.
Это отдельный шаг от critical, чей baseline остановился на одном FAIL из59.

[Acceptance reader126](https://github.com/Vanilla1999/DocAtlas/actions/runs/38023053227/job/114129755653)
был независимо прочитан:592758 UTF-8 bytes,
SHA-256 `5ba00eacb3e432d650c6ef6d5f396db286397487189436fbdeec90940e5042a1`,
357 JSON records,0 parse errors.
Его console не содержит индивидуальных literal child receipts. Поэтому
aggregate SUCCESS не объявлен собственным proof для следующего retirement.
Снимок фактов сохранён в
[RUNTIME_EVIDENCE_d76f6ab8.json](RUNTIME_EVIDENCE_d76f6ab8.json).

Источник ограничения установлен чтением reader:
он рассматривает `literal-contract-comparison/comparison.json` только как
общий CONTRACT_ARTIFACT; дочерние `evidence.json` отфильтрованы. Поля
`baselines` и `evaluator_controls` summary не входят в прежний whitelist.
Общий logger также ограничивает длину списков и общий console budget.
Это наблюдение о formatter, не гипотеза о пропавших runtime jobs.

## Какие данные уже производятся

Owning producer:
[scripts/run_critical_mutation_gate.py](../../scripts/run_critical_mutation_gate.py).
Сверены base126 `f6ed25aebb6b2df77ac041e2ae6b1dda76bf3b92` и integration129
`1cf7d0de47793246db0a0016d53d45d8177bfd5b`; весь literal comparison executor
между ними побайтно одинаков.

Frozen protocol
[eval/task_level/literal_contract_mutations.json](../../eval/task_level/literal_contract_mutations.json),
blob `8f92ea6d9c0045bd32d407f407a80f8d7198673a`, объявляет51 mutations.

| Существующий запуск | Cases | Сохранённые данные |
| --- | ---: | --- |
|baseline-historical|303+399=702|JUnit counts/cases/roster, mode, input roster hash, source identity|
|baseline-compact|33+49=82|Та же структура, собственные cases и roster|
|Каждая из51 mutations, historical|Зависит от исходного killer|Junit, mutation path/anchor/before/after, validated/returncode|
|Каждая из51 mutations, compact|Собственный compact count|Та же структура и собственный observed count|

Полный успешный producer сохраняет2+51×2=104 child receipts.
`comparison.json` отдельно содержит обе baseline summaries, evaluator controls
и51 pairs. Его `passed` не заменяет содержимое child receipts.

[Pytest plugin](../../eval/task_level/literal_contract_reduction.py),
blob `063002257925e0fb50ab8eb542fd04deae4a57cc`, записывает
`<run>.imports.json` в `pytest_sessionfinish` того же процесса.
Producer сверяет schema/mode/exit, exact source path и SHA, импорт из disposable
checkout, затем копирует `source_identity` в JUnit часть `evidence.json`.
Это отличается от отдельного import-origin process в ordinary critical loop.

[Существующий CI workflow](../../.github/workflows/ci.yml),
blob `9136caaa257c38f8d41558abbdca9497dcab8991`, уже загружает всю папку
`$RUNNER_TEMP/literal-contract-comparison`. Никакой новый workflow, запуск,
провайдер, модель или повторный pytest для получения этих данных не нужен.

## Изменение reader

Добавляются два вида console records:

- **LITERAL_COMPARISON**: исходный verdict/schema/protocol/hash файла,
  historical baseline, обе summaries, evaluator controls, полный declared
  mutation roster, observed/declared child counts, missing/unexpected children.
- **LITERAL_CHILD_OPERANDS**: собственный hash файла, run/validated/returncode,
  case_mode, JUnit counts/roster/input-roster hashes, measured durations,
  observed counts по outcome и testcase class, группы точных первых строк
  неуспешных assertions с числом случаев, mutation identity/hashes/guard,
  corresponding observed mode summary, actual source identity из sibling JSON
  и hash самого import receipt.

Никакие testcase bodies, сохранённые вопросы, gold expectations или production
functions не запускаются reader. Он читает JSON и форматирует уже записанные
поля. Полные case lists остаются в исходных artifacts; групповая строка
сохраняет число случаев, но не выдаётся за полный список testcase identities.

`mutation.expected_failures` в сохранённом child receipt — историческое
ожидание исходного Mutant. Для compact producer использует отдельный
`compact_expected_failures` перед сохранением. Reader показывает это различие;
actual compact counts берутся из JUnit и corresponding comparison mode.
Историческое число не подставляется как compact expectation.

Reader отмечает отсутствующие/нечитаемые JSON, неизвестную schema, malformed
source identity, различия sibling source identity и копии внутри JUnit,
ошибочную run/mode/exit identity и missing/unexpected declared children
успешного summary в существующем `issues` ledger.
Сравнение копий source identity сохраняет различие JSON bool и int.
Это проверка целостности сохранённого представления; повторная проверка
production source SHA в исчезнувших disposable workspaces не заявляется.

Если сам producer `passed=false`, reader сохраняет этот факт. Он не
дополняет отсутствующие receipts успешными значениями и не выдаёт readable
report за quality PASS. Полный обязательный mutation roster по-прежнему
сверяется с owning versioned protocol при отдельном acceptance review.

## Порядок и ограничения private console

Прежние CRITICAL_OPERANDS и RECOVERY_OPERANDS остаются раньше новых literal rows.
Существующий CRITICAL_BASELINE также переносится перед literal, без дублирования
записи в полном ledger. Далее идут literal summary, оба baseline children,
15 согласованных question-plan pairs и остальные36 pairs. В каждой паре
выводятся historical и compact.

Первые15 names взяты из того же51-entry manifest; порядок предназначен только
для чтения:

`literal_inferred_facets`, `literal_missing_unresolved_state`,
`literal_complete_scope`, `literal_legacy_delegation`,
`literal_unknown_tail_hash_loss`, `literal_answer_authority`,
`literal_original_query_credit_lost`, `literal_lookup_required_credit`,
`literal_lookup_parent_promotion`, `literal_path_as_body_identity`,
`literal_reference_offset_shift`, `literal_punctuation_as_semantics`,
`literal_whitespace_preservation`, `literal_unicode_normalization`,
`literal_input_bound`.

Остальные36 не удаляются и не считаются пройденными, если console их не вместил.
Все104 rows не объявлены гарантированно видимыми до фактического запуска reader.

Прежний общий private console budget384000 bytes и резерв512 bytes сохранены.
Это ограничение diagnostic log, не потолок пользовательского evidence output.
Добавлены отдельные omission counters для LITERAL_COMPARISON,
LITERAL_CHILD_OPERANDS и CRITICAL_BASELINE. Полный JSON ledger и исходные artifacts
сохраняются; новые rows могут уменьшить видимую часть поздних больших V2 records,
и общий счётчик сообщает эти пропуски.

## Узкое исправление critical traceback

В127 добавлен `trace[-6000:]`, но прежний общий `_focused_bound` превращал
любую строку длиннее512 в prefix/hash. Поэтому console не сохранял задуманный
tail6000. Теперь только CRITICAL_BASELINE обрабатывает trace отдельно:
не более трёх failed entries и не более6000 символов хвоста каждого.
Сохраняются исходная длина, число пропущенных символов, обозначение tail,
число всех failures и число пропущенных failed entries.
Truncated trace не называется полным.

Это чтение уже существующего JUnit. Verdict, assertion guard, счётчики
evaluator и exit policy не меняются. Все остальные diagnostic строки
используют прежние bounds.

## Exact manifest и статическая проверка

| Path | Mode | Base blob | Proposed blob |
| --- | --- | --- | --- |
|scripts/summarize_acceptance_artifacts.py|100644|1caccbda8ed1bfef43dc50296a9da6c541121717|1fa3deb9b90200f634daca29efd6dc5359823173|
|v2plan/pr211-execution/LITERAL_COMPARISON_RECEIPT_READER_RU.md|100644|NEW|Этот документ|

Mode reader независимо прочитан в scripts subtree на integration128
`23af9fc5b5934bc651e40f510ec90c88e1642dcc`.
Proposed code:811 lines,44474 UTF-8 bytes,
SHA-256 `36b770120fde65643bb4df7489f6fa3e7b46573c6bd0c1839b176d95f86b4a0e`.
Base:590 lines,31389 bytes,
SHA-256 `29402476c49e4aabe9ff0b78d656908d207735280bdeb1d428224913ac9cd761`.

Обратное удаление только новых helpers/collector/priority insertions и
trace metadata восстанавливает base побайтно. Все imports и CLI flags прежние;
production/quality evaluators/corpus/thresholds/pytest names неизменны.
Blob readback совпал с подготовленным source.
Ни локальный Python, ни AST/import/pytest, ни новый CI job не запускались.
Independent source review запрошен; собственный runtime и фактическая полнота
console остаются **PENDING**.
