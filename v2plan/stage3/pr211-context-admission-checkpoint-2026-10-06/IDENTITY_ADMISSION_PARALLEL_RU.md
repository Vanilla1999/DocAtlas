# Identity / admission / corpus — active parallel checkpoint

2026-10-07. User явно разрешил выполнение NEXT_PARALLEL_HANDOFF_RU.md.
**Bounded implementations завершены и scoped approved / PARTIAL.
Full dictionary exit NOT DONE.** Pending записи ниже — исторические этапы.

Baseline HEAD и origin: `9488cb66ab989f6f65bafbfae7d1eb3f844ce0a3`.
Published source manifest verified; только intentional local CONTINUE handoff
исключён из hash comparison. Production в primary при запуске не изменён.

## Запущенные allocations

- A identity: `/tmp/opencode/docatlas-next-identity-9488cb66`,
  session `ses_eecdf711fffe79znYgaHch3tdf`.
  Owns curated_sources.py, dart_official_docs.py, library service part01;
  новые source_identity tests/shard/report.
- B core/admission: `/tmp/opencode/docatlas-next-admission-9488cb66`,
  session `ses_eecdf4789ffexmzJIJb35aY97K`.
  Owns question_plan_core.py, admission_contract/local_binding/meaning.py;
  новые admission_literals tests/shard/report.
- C read-only corpus auditor: `/tmp/opencode/docatlas-next-corpus-audit-9488cb66`,
  session `ses_eecdf26a9ffeSk8fwrNVxP7pyv`.
  Только новый CORPUS_CONTRACT_OPTIONS_RU.md, production edits запрещены.

Все worktrees detached от одного baseline; primary пишет только coordinator.
Workers без commit/push/network и без изменения frozen tests/gold/thresholds.
В worktrees скопированы локальные handoff/CONTINUE и подключена primary .venv:
эти setup файлы не переносить как worker changes. Архив gzip только в primary,
не удалять/не добавлять. Старые manifests/reports не переписывать.

## Следующие действия coordinator

1. Получить bounded worker outputs, проверить allowlists и diff относительно baseline.
2. Независимые read-only reviews на завершённых worker slices; блокеры исправлять
   до интеграции. Новые allocation вне scope автоматически не запускать.
3. Интегрировать allowlisted diffs последовательно, общие consumers только отдельно.
4. Combined new tests, technical/old mixed reds, MCP checks, frozen pins;
   новый versioned self-host report и manifest. Quality сейчас FAIL, не waived.
5. После scoped approval commit/push в PR211 без force/merge.

Corpus exclusions BLOCKED до explicit bounded membership authorization. C только
формулирует варианты; решение не подразумевается текущим разрешением на работу.
Retrieval completeness и full release acceptance остаются отдельными gates.

## A executor returned; review pending

Identity implementation завершена только в A worktree, primary production untouched.
6 extraction files: три owned production, source_identity test/shard и
SOURCE_IDENTITY_DICTIONARY_EXIT_RU.md. Ecosystem inference / known-host preference
removed, firebase_firestore fail-closed без replacement URL; DTO/signatures unchanged.
Executor:50newPASS,95technicalPASS/1FAIL,189oldmixedPASS/32FAIL,
1477dictionaryPASS/4FAIL. Это не approval и не waiver четырёх dictionary regressions.
Independent reviewer `ses_eecdb22fdffenPwAA0bcXx0WnX` запущен на completed A worktree;
должен классифицировать эти reds и проверить guards до parent integration.
B и C остаются в работе; их production/topics не дублировать и не polling.

## C auditor returned; no membership decision implemented

C завершён; только новый CORPUS_CONTRACT_OPTIONS_RU.md в corpus-audit worktree.
Parent прочитал report, production/config/frozen artifacts untouched.
Offline normal-conftest:264PASS/10preservedFAIL. Actual indexed corpus/external SDK
UNKNOWN; membership описана как predicates, не как проверенный indexed URL set.

Основной prerequisite: non-manifest DocsPrefetchService не передаёт
allowed_domains/path_prefixes/seed_urls в agent.add, refresh передаёт. Это code-edge
inconsistency, не доказанное production outside-authorized fetch. Исправление caller
propagation вне A/B allocations; нового разрешения на implementation пока нет.

Предпочтительный кандидат для owner decision: finite explicit URL/file membership
без discovery expansion. Current seeds/caps не гарантируют exact membership;
immutable GitHub directory manifest имеет другую membership, не silent replacement.
Subtree option расширяет некоторые legacy sets и требует отдельного разрешения.
Ничего из этих options не выбрано; corpus exclusions остаются BLOCKED.
Source-map suffix priorities и architecture fallback — отдельные residual allocations.

A independent review pending, B executor running. C report переносить в primary
как отдельный allowlisted artifact при интеграции, не вместе с setup handoff copies.

## A independent review: scoped YES; dictionary regressions retained

Reviewer ses_eecdb22fdffenPwAA0bcXx0WnX: no owned production safety blocker,
minimal owned fix none. Primary production пока не интегрирован; B ещё в работе.
Normal-conftest independent runs:149PASS/4newFAIL и40PASS/1preservedMCPFAIL.
Literal ecosystem selection/explicit policy/deterministic ordering/caps retained;
no corpus widening. Real cloud_firestore exact API positive, firebase_firestore
unresolved. Function signatures/DTO fields match baseline, guard methods unchanged.
Public resolve_library→get_docs→refresh_docs unresolved probes give structured
source-required/confirmation results, без unchecked None dereference/network.

Все 4 new failures относятся к tests/test_dictionary_exit_discovery_literals.py:
- test_explicit_api_templates_and_package_pages_are_not_topic_tables: прежний test
  форматирует firebase_firestore.pubdev_api=None; wrong-package mapping теперь removed.
- test_actual_dart_resolver_caller_preserves_root_and_version_provenance: library_id
  None; прежний test требует automatic unversioned Riverpod guide registration для
  exact2.4.0, связанный guide-preference/multi-host lane удалён.
- test_removed_ecosystem_alias_does_not_expand_caller_target[pub] и [flutter]:
  прежние tests dereference unresolved identity, полагаясь на curated fallback.

Это новые contract/test conflicts, НЕ baseline reds и НЕ waived. Existing assertions
не менять; semantic inference/replacement URL ради green не возвращать. Scoped A
approval не является green dictionary-suite / full integration / indexed MCP /
quality или full dictionary exit acceptance. При final combined run сохранить эти
четыре exact nodes и counts отдельно от ранее known MCP failure.

## B executor returned; independent review pending

B worktree завершён, primary production untouched. Extraction ровно7files:
question_plan_core.py, admission_contract.py, admission_local_binding.py,
admission_meaning.py, new admission_literals test/shard/report. Setup .venv и
handoff/CONTINUE исключить. Unknown admission no legacy credit; NL binding/equivalence
guesses removed, literal evidence/DTO signatures/structural spans/budgets/hashes retained.
Executor94newPASS,1525dictionaryPASS (изолированный B, НЕ combined A+B), targeted
615PASS/1documentedMCPFAIL; oldmixed12PASS/390FAIL, four-file overlay42PASS/360FAIL
notfullbaseline. Старые assertions не менялись.

Reviewer `ses_eecd92f65ffewSmV8ElgGACzIq` запущен read-only на завершённом B.
Обязательная проверка debt: nonowned application adapter retains prequalified traces
on unknown witnesses. Main qualifier rejects old need lane; нужно distinguish
trace telemetry от реального false evidence/support/authority credit, concrete
repro/callchain до классификации blocker. Новый allocation пока не начат.

Все A/B/C executors завершены. A scopedapproved с4new preserved compatibilityreds,
C reportготов no membership decision, B reviewpending. Integrator final combined
tests/sourcepins/report/commit ожидают review и возможного concrete blocker closure.

## B review returned / approved slices integrated

B independent scopedYES:94newPASS,1525dictionaryPASS,615technicalPASS/1knownMCPFAIL;
oldmixed12PASS/390FAIL and scopedoverlay42PASS/360FAIL reproduced, notfullbaseline.
No owned-file blocker; function/DTO ASTs identical, spans/Unicode/hashes/bounds retained.

Adapter debt reproduced in retrieval_need_support.py:117–134: unknown default witness
None preserves prequalified qualified/need_local_witness flags. Downstream accepts
retrieval attribution, but payload retrieval_only and answer/editflags false;
qualifier removes forged metadata, projection rejects old lane. No production adapter
invocations found. Classification dormant fail-open attribution, NOT support/editbypass.
Minimal separate allocation ONLYadapter + new test/shard/report passed to B worker
ses_eecdf4789ffexmzJIJb35aY97K; prior reviewed7files remain unchanged.

Coordinator integrated approved A6+B7 files and C1report via allowlisted git patches,
excluding setup copies. Primary production now has reviewed A+B changes.
Combined normal-conftest dictionary run: **1571PASS / 4newFAIL**, exactly the four
recorded A discovery contract conflicts. Log:
`/tmp/opencode/identity-admission-combined-prereview.log`.
No old assertions modified, no alias restored, no waiver/fullgreen claim.
Adapter follow-up pending; final technical/MCP/quality/pins/review/commit still pending.

## Adapter follow-up executor returned; independent closure pending

SECOND4files толькоadapter/newtest/shard/report, prior B7files unchanged.
Original unknown default repro gives qualifiedFalse and clears inherited needcredit
without mutating trace. Non-need lane/ABI unchanged. No current supported literal-
default adapter contract invented; exact literal proof positive remains separate.
Executor47newPASS; B+new+technical185PASS/2FAIL, isolateddictionary1571PASS/1FAIL.
Дополнительный новый red:
test_dictionary_exit_admission_literals.py::test_application_adapter_really_calls_default_hook_but_unknown_is_consumer_debt
ожидает удалённый passthrough; assertion untouched, не waived. Combined A+B+SECOND
ожидает этот node плюс4A reds, фактический final run ещёpending.
Oldneed9FAIL identical in adapter-onlyoverlay, notfullbaseline.
Reviewer `ses_eecd31e3bffeVr7vk5NpR2VaSh` launched readonly SECOND closure.
Integrator MCPstdio beforeSECONDintegration:PASS. Final snapshot needs repeatchecks.

## Final integration checks / publication candidate

SECOND independent scopedYES:47newPASS,185targetedPASS/2documentedFAIL,
1571isolateddictionaryPASS/1FAIL. Repro closed, immutable input/ABI/context-only
preserved; hashesverified. Adapter remains dormant, no active authoritybypass claim.
Все18 worker extraction files интегрированы: A6+B7+C1+SECOND4; setup excluded.

Final primary normal-conftest combined: **1662PASS / 6FAIL**:
- dictionary-exit portion **1617PASS / 5newFAIL** — четыре A conflicts и B debt
  passthrough assertion перечислены выше. Не baseline reds, не waived.
- technical sixmodules **45PASS / 1preservedMCPFAIL**.
Log `/tmp/opencode/identity-admission-final-combined.log`.
Final stdio MCP smoke **PASS**. Self-host quality repeated **FAIL**:
[dictionary-exit-identity-admission-self-host-v1.json](archives/dictionary-exit-identity-admission-self-host-v1.json).
Ни старые assertions, ни gold/thresholds, ни frozen corpus не изменены.
Scoped source manifest:
[dictionary-exit-identity-admission-source-manifest.json](archives/dictionary-exit-identity-admission-source-manifest.json).

## Next / remaining boundaries

1. **Corpus membership decision still BLOCKED**: прочитать
   [CORPUS_CONTRACT_OPTIONS_RU.md](CORPUS_CONTRACT_OPTIONS_RU.md).
   Не расширять locale/topic/GitHub corpus. Finite explicit membership — предложенный
   вариант, не принятое решение. Prefetch policy propagation prerequisite требует
   отдельного bounded allocation; здесь не исправлялся.
2. Source-map suffix priorities / project-state architecture fallback и другие
   nonowned admission/retrieval support helpers остаются residual audit allocations.
   Нет full inventory exit claim инет reachabilityclaim solelyimports.
3. Retrieval completeness/quality восстановление — отдельная работа, без возвращения
   dictionaries ибез снижения frozen floors. Full CI/rebuilt artifact acceptance
   не выполнены; old mixed failures честно перечислены в worker reports.
4. Local literal/display checks не authenticate полную external source provenance
   и не дают terminal mutation authority. Existing guards обязательны.

Публикация только bounded reviewed slice, без force/merge. Raw gzip остаётся внеGit.
