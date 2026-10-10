# PR211: deterministic guard for a complete filename collision

Статус: fixture-only correction после actual121; новый runtime **PENDING**.
Production binding, acquisition, public veto и strict mutation runner не меняются.

## Actual121

PR head `c2a6682d2438c9217c3bf26938dcd003391dbc75`.
CI merge `642a14289fddd06408400b4ee6cc5480945e7d1a`, тот же tree
`89106f59cf181510a25ee8b667a9ff4966a82fd6`.

[Acceptance reader114124354950](https://github.com/Vanilla1999/DocAtlas/actions/runs/38021212993/job/114124354950)
и сохранённый receipt `v2plan/pr211-execution/RUNTIME_EVIDENCE_c2a6682d.json`,
blob `5a4a03197ed8ad93e40157ec37ecb3cb5247ea3d`:

- Recovery baseline: passed12, failure0, error0. SHA-256 baseline JSON
  `c9872517f39c09344418d64cf2b6d087c2a8bf8cb5ba8fd2a101c72cef8def42`.
- `filename-collision-first-winner`: passed0, failure1, error0;
  единственный case `closed_literal_context`.
- Actual first guard: `recovery_filename_path_selection_not_naming_scope`.
- Required intended guard: `recovery_filename_catalog_ambiguity`.
- Artifact: `docatlas-recovery-evidence-qdt72c_n/filename-collision-first-winner.json`.
  SHA-256 `01ad81741f7954d13df86568e15144cbd5fef1f5c66a8cdde12a7b9d3eeef515`.

Это failure на другом guard, **не успешный intended kill**.
Поле actual first guard не показывает, какой path/opaque source ID пережил
ранний ranking. Такой подробный native trace этим receipt не доказан.

## Source-backed причина хрупкости прежнего контроля

Исходный mutant в `scripts/run_recovery_mutation_gate.py`
blob4644eb82522eadeea7807fd067759cfce76a7e11 добавляет `[:1]` к результату
`_structural_source_ids`. Настоящий контракт считает все совпавшие entries
полного разрешённого каталога, независимо от ranked hits.

В `query_reference_binding.py`06215d1e4deaa4c56a2c0afac135bd2f2a29a858
IDs сортируются как непрозрачные строки. При двух совпавших именах mutant
возвращает один ID и получает state `resolved` вместо `ambiguous`.
Позже `prepare_reference_probe` отдельно отвергает candidate, чья текущая
identity отсутствует в `source_ids`.

В `_sqlite_store_part03.py`96f35c1f02a97f58f05b15f154c2fc45487487dc
query сначала ранжирует rows, затем глобально удаляет одинаковые title+text.
Оба collision fixture members имеют одинаковое тело. Единственный surviving
candidate не обязан совпасть с ID, выбранным mutant. В таком случае public
результат остаётся пустым, хотя source-nomination контракт уже нарушен.

Таким образом, старый public no-source oracle не гарантировал intended kill
этого конкретного fault. Поздний независимый 1-of-2 catalog probe обнаруживал
ошибку надёжно, но под своим отдельным guard. Объяснение выше получено из
source; конкретный ранний winner actual121 не восстанавливается по догадке.

## Узкое исправление fixture

Existing `SourceReferenceContext.prepare` observer уже вызывает original ровно
один раз и возвращает его объект. Теперь он дополнительно копирует два поля
уже рассчитанного context: `plans[context.question]` и `naming_catalog`.
До каждого read список observations очищается.

Owning `SourceReferenceContext`14e8916cd686ad237440b3e6aa1da60e2c7ea191
создаёт полный catalog/root plan в constructor. Current
`_project_docs_service_part03.py`94fe9ee6629d14034d337fae879272c5b6d16a64
затем вызывает prepare для существующих root retrieval results, включая пустые.
Копирование не вызывает resolve/retrieval/SQL повторно и не меняет объект,
который получает production caller.

В каждом существующем collision negative до прежнего public assertion
проверяются реальные same-call plan и catalog:

1. Observation присутствует; catalog complete, ровно два fixture members.
2. Paths совпадают с двумя явно подготовленными файлами, content hashes — с
   независимыми исходными body strings. Project root identity и current
   generation связаны с root и последним успешным member transaction.
3. Plan относится к исходному вопросу, тому же scope/generation и полному
   inventory digest.
4. Единственный source locator имеет state `ambiguous`, соответствующий reason
   и **оба различных source IDs** этих фактических catalog rows.

Guard остаётся `recovery_filename_catalog_ambiguity`. При live `[:1]` fault
первые fixture/catalog bindings сохраняются, а последний пункт нарушается
независимо от того, какой candidate пережил retrieval. Missing observation
также не выдаётся за проверенное свойство.

После этого остаётся прежний обязательный public no-source/no-authority oracle.
Поздний `recovery_filename_path_selection_not_naming_scope`, полный naming
inventory при явном path filter, single-candidate observation, immutable
replays, fixture bytes и fingerprints не изменены.

Новых public reads, acquisition calls, SQL/source-body reads, retries или
обычных pytest функций нет. Добавленные checks читают сохранённые наблюдения;
для независимой root identity используется обычный fixture `Path.resolve`,
поэтому blanket zero-FS-calls не заявляется. Плановая новая работа — catalog
проверка в шести уже существующих collision reads, без фиксации количества
внутренних prepare returns.

## Manifest и проверка

Current121 owning helper и runner повторно прочитаны по точному PR head;
они совпали с ожидаемыми bases.

| Path | Mode | Base blob | Proposed blob |
|---|---|---|---|
| eval/agent_developer_v1/structural_filename_controls.py | 100644 | beff197e7c8a4280cfc1ca59cfa5674fe963eb61 | 301d274bc1fc665e3f5054e7bd5df288cc819532 |
| v2plan/pr211-execution/FILENAME_COLLISION_PLAN_GUARD_RU.md | 100644 | NEW | этот файл |

Четыре узких text edits; обратные замены восстанавливают base побайтно.
Созданный code blob прочитан обратно, exact content совпал.
Все12 recovery case names,33 mutants, anchors, intended guard strings,
strict runner validation и exit behavior прежние.

Локальных Python/import/AST/runtime запусков не было.
Следующий совместный CI должен подтвердить healthy12 и все33 intended kills,
включая именно `recovery_filename_catalog_ambiguity` для этого fault.
