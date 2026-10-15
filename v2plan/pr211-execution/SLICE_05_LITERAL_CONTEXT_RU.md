# PR211: узкий literal context slice — review note

Дата: 2026-10-09. Предыдущий runtime: `99106c9`, advanced job `113917342535`.
Текущий snapshot записан в общем worktree; commit/push этим агентом не выполнялись.
Локально — только source/AST/compile/hash проверки. Runtime нового slice: **PENDING PR CI**.

## Подтверждённый исходный барьер

В `99106c9-recovery-contract.json` 10 сценариев: 8 PASS / 2 FAILURE / 0 ERROR.
`exact_document_recovery` и `literal_anchor_context` вернули
`insufficient_evidence/required_evidence_missing`, `delivery_decision.deliverable=false`,
без источников. Finite membership setup прошёл. Mutation runner правильно отказался
считать этот baseline зелёным и не объявил mutations убитыми.

Source analysis показывает причину, которую новый CI должен проверить: небольшой
раздел Counters с реальным `meet_type` не покрывает буквальные terms всего длинного
TREASURE-вопроса. `qualified=false` удаляет его и из ranking, и из retained windows.
Exact-document fallback квалифицируется тем же правилом. В новом gate observer
сохраняет не только projection input, но и input явного delivery veto, поэтому
следующее падение не останется только непрозрачным финальным DTO.

## Контракт изменения

**Точная occurrence syntactic symbol из исходного вопроса в содержательном теле
текущего документа допускает частичный контекст. Это не даёт query coverage.**

- Исходный вопрос не меняется, новые probes/aliases/lookups не создаются.
- `qualify_evidence` и ratio thresholds не менялись. Его отказ по недостаточному
  буквальному совпадению сохраняется. Отказ по source/reference/policy не обходится.
- Source/member/catalog/scope сверяются заново. Scope/module и catalog hash
  берутся из действительно прочитанной строки `generation_sources`, а не из
  входящего `context_eligible`, rank score или утверждения о qualified.
- Canonical qualifier через `prepare_reference_probe`/`prepared_owner_rejection`
  проверяет raw-document SHA, window, body, owner, project/generation и lifecycle.
  Новый helper не пересчитывает тот же полный document SHA второй раз.
- Допуск требует body binding syntactic symbol из неизменного question. Title,
  path, link-only, identifier-only и identifier-prefix не служат таким свидетельством.
  После удаления всех вхождений identifier в структурном body unit должно остаться
  содержимое (значение/code/prose). Это структурная проверка, не NL entailment.
- Ranking и финальный admission пересчитывают решение. Private tag только переносит
  уже подготовленный candidate через representation selection; он не является
  capability или источником доверия.
- В публичном DTO остаются `partial`, missing `query-original`, false
  answer_supported/answer_available/edit_ready. Нового public schema поля нет.
- Partial window добавляется после квалифицированных направлений в тот же projector
  и canonical snapshot. Existing operational veto остаётся перед этим projector.

## Изменённые файлы

| Файл | Назначение |
|---|---|
| `docmancer/docs/domain/literal_context_admission.py` | Новый pure допуск точного исходного symbol в current body; отдельный от whole-question qualification |
| `docmancer/docs/application/source_reference_evidence.py` | SQL-derived member binding: doc_scope/module_path/catalog entry hash |
| `docmancer/docs/application/reference_query_tagging.py` | Private diagnostic admission tag на original; без qualified/credit promotion |
| `docmancer/docs/application/_project_docs_service_part03.py` | Сохранение уже acquired checked literal windows через representation selection |
| `docmancer/docs/domain/project_doc_ranking.py` | Recompute допуска из реального body, сохранение current/lifecycle/membership guards |
| `docmancer/docs/application/_docs_context_projection_core.py` | Admission и snapshot того же source window без покрытия query/answer/edit |
| `scripts/run_recovery_contract_gate.py` | Настоящие positives, source binding, replay/state transformations, delivery observer |
| `scripts/run_recovery_mutation_gate.py` | 12 конкретных intended failures, строгий roster/import/hash/guard proof |

Чужие dirty files, quality gold, expected source facts, workflows и глобальные
планы этим slice не редактировались.

## Проверки поведения, подготовленные для CI

Baseline roster остаётся 10, оригинальные 8 diagnostic scenarios сохранены.

1. Exact-document positive сохраняет принудительно пустой query lane и запрет
   global section scan. Требуется настоящий исходный факт `meet_type uses value 6
   for gem counters.` через публичный get_docs_context.
2. Original TREASURE positive требует тот же факт, текущие source bytes/path/scope,
   настоящий snapshot, отсутствие answer/edit authority, admission trace и отсутствие
   original credit. Canonical snapshot проходит штатный validator; quote/hash/identity/
   lines сравниваются с actual public row (URI может перевыпускаться при регистрации).
3. На реальном `before_projection` выполняются 11 transformations admission core:
   foreign project/scope/catalog/file hash/generation, stale, wrong window/body,
   forged raw snapshot tail, missing source reference, forged admission flags.
   Ещё 2 controls проверяют consent и explicit delivery veto. Ни один не должен
   дать источники. Это replay именно admission core; отдельный facade inspection
   target не используется как oracle допуска источника.
4. Через public API после подтверждённого fixture upsert проверяются четыре
   настоящих отрицательных source изменения: heading-only, bare identifier,
   link-only, identifier prefix.
5. Подтверждённая замена факта 6→9 должна выдать 9 и исключить старое 6. Затем
   removal из текущего catalog должен отозвать quote, даже если старый stored member
   и файл физически ещё существуют. Read-only availability не даёт authority.

Mutations: прежние 8 + отключение literal admission, ложный original credit,
допуск bare label, обход уникального catalog binding. Каждый имеет точный case/guard,
единственный anchor и compile-valid changed bytes. Baseline должен быть полностью
зелёным; crash/import/setup error, другой guard и любой произвольный nonzero не kill.

## Review corrections

- Root заметил transient metrics placement в exact return: исправлено; admissions
  и transformation counts существуют только в `literal_anchor_context`.
- Root нашёл redundant hash mutation: canonical owner binder уже проверяет тот же
  SHA, поэтому это не observable defect. Повторный SHA/window блок удалён из helper;
  mutation заменена обходом уникального member catalog hash сравнения. Raw-document
  tamper negative сохранён, но отдельный hash-mutant kill не заявляется.

## Static evidence и граница результата

`recovery-literal-static-audit.json`: AST/compile 11 tracked/import-proof files,
совпадение 9 module paths и actual-import roster, 10 case IDs, 12 уникальных mutation
anchors, compile всех mutated source строк. `git diff --check` PASS.
Никакие project imports/functions/pytest/install/provider calls локально не исполнялись.

Frozen inputs:

- TREASURE question: 262 bytes, SHA256 `2febcb8d2d4fa37fd257fb8005b453e48dfce221a6f32d19b76c0db062a7129b`.
- TREASURE source: 462 bytes, SHA256 `17f90dd3be04d16475952da73f92d919bbe9d9b51f8e76ffa7bf0a7e64a5fc47`.
- Original 100-question corpus: SHA256 `0616d67ef86e134365c5192701f9a6b6173e13326c08ba58a5b049147f3e81f1`.
- Exact path, architecture and finite catalog literals сохранены; их hashes в audit.

**Review:** независимый source review завершён APPROVE для CI; root исправления проверены.

**Открыто:** green 10-case CI baseline;
12 actual intended mutation kills; broader core/downstream regression results.
Новый helper не решает оригинальные вопросы без exact syntactic symbol, cross-language
paraphrase acquisition, source diversity/coalescing или whole-question original coverage.
Legacy original floor 12 и существующие quality criteria не снижались. Свежие
`0e45690-...-live.json` остаются исходным evidence для следующего retrieval slice.

## Независимое review

# Independent review — literal project context + recovery gates

Verdict: **APPROVE for ordinary PR CI**, based on source review and independent static checks. Runtime baseline and mutation kill evidence remain required; neither was run locally.

## Reviewed boundary

Six production files: `domain/literal_context_admission.py`, `application/source_reference_evidence.py`, `application/reference_query_tagging.py`, `domain/project_doc_ranking.py`, `application/_project_docs_service_part03.py`, `application/_docs_context_projection_core.py`. Two evaluators: `scripts/run_recovery_contract_gate.py`, `scripts/run_recovery_mutation_gate.py`.

The new route retains an already acquired source window with a literal original-question symbol in its body when the full original question fails the ordinary lexical ratio. It does not create a search alias, source read, index mutation, semantic answer contract or query coverage. It is deliberately narrow: ordinary prose without an explicit symbol does not automatically gain this route.

## Safety/source review

- `SourceReferenceContext` obtains member scope/module/catalog-entry binding from the immutable active-generation source record, after existing project/source/lifecycle/scope filtering. It attaches this binding only when the actual source text, chunk window, file/source hashes, path and generation checks succeed.
- Admission requires the original root question, complete prepared catalog, source identity and current member catalog-entry hash. Candidate project/module fields must equal the prepared binding. Incoming `qualified`, score and `literal_context_admission` flags cannot replace the fresh check.
- Canonical `qualify_evidence → prepare_reference_probe → prepared_owner_rejection` performs raw-document SHA, raw window/visible body, owner, project/generation/version/path and lifecycle checks. Admission only accepts the precise `insufficient_visible_match` result. Scope, consent, source mismatch and operational failures do not use the fallback.
- The project-context application still checks actual current member paths/content/catalog hashes before delivery; a stored record whose membership has been revoked cannot return a stale quote. The new helper performs no filesystem/store/network access.
- Project query retention may keep a previously tagged partial window, but ranking and projection recompute the source admission. The projector also retains its existing early operational/confirmation/delivery veto and explicit-path filtering.
- Literal context uses the full acquired window, with only normal boundary whitespace trimming, exact public line ranges, canonical source digest and snapshot binding. It is appended after qualified directions, receives no query IDs or assignments, and retains the failed original trace. Public answer/edit flags remain false.

## Evaluator review

- The mandatory positive preserves exact frozen TREASURE question/source and requires the actual `meet_type uses value 6 for gem counters.` fact, public DTO/source path/scope and real immutable bytes. It additionally asserts partial coverage, missing original ID and explicit no-coverage admission diagnostics.
- The 13 replay controls cover 11 source/binding mutations plus two operational vetoes. They use the actual prepared projector input; deliberate hostile fields are negative controls, not positive fixture trust grants.
- Four confirmed source updates exercise heading-only, bare identifier, link-only and identifier-prefix negatives through the public service. A confirmed value 6→9 update must show current value 9 without old value 6; catalog removal must revoke the quote. These are actual source/member transitions, not facade response stubs.
- Mutation reports require the complete 10-case baseline, exact original task/source hashes, actual imported module paths/hashes, changed source identity, specific case and guard, and expected return code. Import/setup exceptions, missing reports, unknown/skipped outcomes, timeouts and arbitrary nonzero exits are not kills.
- Source review supports the two potentially masked mutations: identifier-only data is not removed by the earlier empty/title/numeric placeholder filters; false original coverage reaches the explicit coverage guard because the final selection validator checks DTO/assignment consistency, while joint alternatives may not drop already claimed coverage. Their actual intended kills still require CI.

## Independent checks

AST parsing of all eight files; 12 unique mutation anchors and parsing of every mutated source; exact ten-case roster match; frozen question/source SHA match; `git diff --check`: PASS. Source hashes are in `recovery-literal-independent-static-audit.json`.

The previously reported misplaced `admissions` return reference was already fixed before this review snapshot. No additional concrete implementation blocker was found. Approval does not claim that broader original-only questions, all core tests, installed MCP clients or downstream gates are green.
