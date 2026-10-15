# PR211: короткая диагностика уже сохранённых acceptance artifacts

## Назначение и граница результата

Новый reader читает JSON, JUnit XML и сохранённый stdout текущего CI.
Он использует только standard library, не импортирует production/evaluators,
не запускает retrieval, providers, subprocesses, tests или mutation gates.
Он показывает исходные verdicts, counts, failure records и hashes файлов.
Ни одного нового acceptance verdict или mutation kill reader не вычисляет.

Причина slice: большой advanced job log недоступен через текущий transport,
тогда как quality/critical artifacts уже сохранены. Читатель позволяет изучить
их выбранные поля через небольшой отдельный job log. Это изменение диагностики;
исходные required gates продолжают определять результат CI.

База существующих файлов: PR107
`321f36577577cb90a0422cee0de0b525b9cd658e`.
Root draft CI сохранён без дополнительных изменений; reader и shared V2 import
доработаны в пределах этих трёх paths.

## Источники данных и их фактическая форма

| Producer | Exact blob | Сохранённые поля/файлы |
| --- | --- | --- |
| `eval/project_context_quality_protocol.py` | `63f0657ab238a4e326be3a83e930ab6a8a93c5da` | Hermetic `project-context-quality-contract-result-v2`; live Legacy `project-answer-quality-live-result-v1`, original metrics, errors, `legacy_fact_acceptance`. |
| `eval/project_context_quality_v2_protocol.py` | `93833df4ec9587f34724b26fc42dd4ce7a1250e5` | `project-context-quality-v2-result-4`, `results`, `production_results`, original diagnostics, lane metrics, production errors. |
| `scripts/run_recovery_contract_gate.py` | `a3e4d05172bb2e124632ad535056a3a02b90df8b` | `recovery-contract-v2`: modules, frozen source/question hashes, cases, counts; `RECOVERY_FAILURE` records без source bodies в stdout. |
| `scripts/run_recovery_mutation_gate.py` | `4644eb82522eadeea7807fd067759cfce76a7e11` | `docatlas-recovery-evidence-*/baseline.json`, mutant JSON и stdout logs; `summary.json` записывается только после собственного успешного gate. |
| `scripts/run_agent_developer_gate.py` | `bf28d7c3cb9700a7822a3fcb14d1b5e4046c6bb2` | Schema1/protocol agent-developer-v1; baseline/target status, task counts/gaps, metrics, errors. |
| `scripts/run_agent_developer_adversarial_gate.py` | `9afd8eb0e5690648fc8f5a89a9536579dd59cec4` | Schema2/protocol adversarial-v2; passed, execution_errors, v1/adversarial counts, execution identity. |
| `scripts/run_critical_mutation_gate.py`, `_save_evidence` | `de247bb93baac2f328ab98aea130d82b4a7a6cbd` | `docmancer-mutation-evidence-*/<run>/evidence.json`: run, validated, returncode, junit, mutation. При baseline FAIL сохраняется исходный JUnit без validated receipt. |

Reader копирует поля, принадлежащие producer. Значение `validated: true` или
`mutants_killed` — сохранённое утверждение producer, не собственная валидация reader.
Critical rows имеют границу `stored_producer_receipt_not_revalidated`;
raw baseline JUnit rows — `mutation_credit: not_inferred`.
Повторы matrix/run не складываются в новый счётчик успехов.

## Поведение reader

- Каждый выбранный файл привязан к artifact-relative path и SHA256.
- Три quality filenames рассматриваются отдельно. Missing/ambiguous, unreadable,
  unexpected-schema и malformed selected arrays становятся issues в ledger.
- Обязательные top-level recovery/Agent Developer файлы проверяются отдельно.
  Одноимённый файл внутри source copy не подменяет отсутствующий top-level report.
- Отсутствие critical receipt/JUnit явно отмечается. Reader проверяет наличие полей;
  killer semantics, source hashes и mutation verdicts повторно не валидируются.
- Legacy rows показывают сохранённые checks и factual fragment checks,
  source identity/scope/line coordinates, snippet hashes и original fact-oracle summary.
  Полные snippet bodies и source hash material остаются в исходном artifact.
- При чтении recovery stdout перехватываются OSError и UnicodeError.
  Ошибка файла добавляет issue и не уничтожает ранее собранные записи.
- Provenance добавляется после decoded stdout fields: содержимое записи не может
  заменить наблюдённые reader filename/hash.

Ledger записывается до console output и сохраняет все selected records и issues.
Скачанные исходные reports сохраняют все исходные поля/bodies. V2 selected records
уже содержат прежнее bounded diagnostic representation; ledger не объявляется
восстановлением полного исходного V2 report из такого представления.

## Shared V2 printer и совместимость

Существующий focused helper block перенесён из
`scripts/run_project_context_quality_v2_gate.py` в standard-library reader.
Его текст побайтно прежний, кроме optional emit callback и соответствующего
output call. Сохраняются ровно три case IDs:

- `v2-paraphrase-cache-reset`;
- `v2-natural-architecture`;
- `v2-natural-request-flow`.

Все прежние module names доступны через явный re-export:
`_FOCUSED_CASE_IDS`, `_focused_fields`, `_focused_bound`,
`_focused_qualification`, `print_focused_stage_records`.
V2 CLI по-прежнему один раз получает report, сохраняет его, вызывает прежний
acceptance checker и выводит те же focused records перед прежним exit verdict.

Artifact callback получает V2 record после исходного bound. Reader console
не применяет bound повторно: повтор добавлял бы новые оболочки списков и раньше
обрезал вложенные поля. Другие selected records сокращаются только для console.
Transport allowance 384000 bytes включает provenance header; оставлено место
для итогового omitted-row receipt. Это не product output ceiling и не acceptance threshold.

Bounded consumer review охватывает пять существующих quality/release modules:
`tests/test_project_context_quality_acceptance.py`,
`tests/test_project_context_quality_protocol.py`,
`tests/test_project_context_quality_v2_protocol.py`,
`tests/docs/test_project_context_quality.py`,
`tests/test_release_gate.py`.
Прямые acceptance imports и CLI caller сохраняются. Private helper bindings
сохранены независимо от того, используют ли их именно эти callers.
Exhaustive repository-wide import search не заявляется.

## CI wiring и execution identity

Меняется только существующий job `acceptance-diagnostics`. Он дожидается core
и advanced jobs и скачивает существующие named quality/critical artifacts.
Download pattern сохраняет artifact-name directory, как в уже наблюдённом
core-JUnit download layout; CLI arguments явно указывают эти directories.
Исходный JUnit summary script не меняется и запускается даже после предыдущего
diagnostic download failure. Новый reader также запускается после такого failure
и записывает missing evidence. Always-upload сохраняет оба diagnostic ledgers.

Нового job, установки dependencies или product/test command нет.
Все gate producer commands, artifact producer names и final required-ci aggregator
побайтно прежние. Consumer run_id/run_attempt/checkout_commit описывают запуск reader;
они не доказывают сами по себе, что каждый producer receipt относится к тому же
source tree или run attempt. Эта проверка остаётся обязанностью исходных CI receipts.

Reader exit0 означает отсутствие зарегистрированных diagnostic issues при чтении
выбранных файлов/полей; он не означает успешность gates. Exit2 сообщает issues.
Ни один результат reader не меняет исходный gate verdict и не даёт mutation credit.

## Exact manifest и статическая проверка

| Путь | Mode | Base blob | Proposed blob |
| --- | --- | --- | --- |
| `scripts/summarize_acceptance_artifacts.py` | `100644` | `NEW` | `bc9ce82a80bbb7279f962a1d2587372c2975fe4f` |
| `scripts/run_project_context_quality_v2_gate.py` | `100755` | `fce272e8ee24fcb199c91a27d773d7b1dbb3d380` | `c261ce9c9bc07f427a005b4d2222d346e491a92d` |
| `.github/workflows/ci.yml` | `100644` | `2b515dc9e148e4c6bae8a72f1bce8350de848f7a` | `9136caaa257c38f8d41558abbdca9497dcab8991` |

Этот note — четвёртый путь:
`v2plan/pr211-execution/EXISTING_ACCEPTANCE_ARTIFACT_READER_RU.md`, NEW, mode100644.

Все три code/config blobs roundtrip точные. Удаление shared import и возврат
исходного focused block восстанавливает весь V2 base побайтно. CI prefix до
acceptance-diagnostics и suffix от required-ci побайтно прежние. Каждое уточнение
root draft reader имеет bounded inverse.

| Proposed file | SHA256 |
| --- | --- |
| `scripts/summarize_acceptance_artifacts.py` | `da8a6294c527912953afe643ebf54377a7859ee13a23a55374b82c1615358eea` |
| `scripts/run_project_context_quality_v2_gate.py` | `7954b7abf11580f42f4280810c34cc792f30497234b70e70303248750cdc2c9a` |
| `.github/workflows/ci.yml` | `c021498c626506339fb7081186160f6e20d31ee9e9cc5ceb6a24986433bcd849` |

Локальные Python/import/AST execution, tests, установка dependencies и runtime
не выполнялись. На момент подготовки независимый static review и первый actual
reader job остаются pending. Новый Legacy floor PASS, V2 quality PASS, critical
baseline или intended-kill receipt этим изменением не устанавливается.
