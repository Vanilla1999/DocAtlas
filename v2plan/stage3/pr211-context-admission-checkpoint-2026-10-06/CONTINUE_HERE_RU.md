# Продолжать отсюда: dictionary exit

**Актуальный checkpoint: 2026-10-06. Полное удаление словарей ACTIVE / NOT DONE.**

**Latest completed coordinated pass 2026-10-07:**
[FINAL_FINITE_CORPUS_PARALLEL_RU.md](FINAL_FINITE_CORPUS_PARALLEL_RU.md) и
[FINAL_INTEGRATED_EXIT_AUDIT_RU.md](FINAL_INTEGRATED_EXIT_AUDIT_RU.md).
Remotefinite membership+callers+transport/identity corrections, R1–R10 иlocal
source-map/project-state cleanup integrated/scopedapproved; boundedpublicationblockerNO.
Allagentsfinished. Final1970dictionaryPASS/14FAIL,2080combinedPASS/17FAIL,
oldmixed331PASS/311FAIL,MCPstdioPASS,qualityFAIL,frozen13/13match.
FullEXITNO: R11/R12 LOCALcatalog/filemembership иnegative-securitypolicy choices
остаютсяOPEN; remotefinite approval неразрешает localcorpusexpansion/guardremoval.
Следующийdecision exactpaths in integratedaudit§6; retrievalquality/releasegates
отдельно. Pendingactive заметки ниже historical. Rawgzip некоммитить/неудалять.

**Active final pass 2026-10-07:**
[FINAL_FINITE_CORPUS_PARALLEL_RU.md](FINAL_FINITE_CORPUS_PARALLEL_RU.md).
Owner approved finite explicit URL/file membership без discovery expansion.
Baseline42c72bd6; corpus/localresidual implementers и read-only full inventory
запущены в3isolated worktrees. Никакого живого crawl/networkauthorization.
Исторические «membership decision BLOCKED» ниже теперь superseded только finite
implementation decision; конкретный membership не выдумывать, fail-closed absentset.

**Latest completed 2026-10-07:**
[IDENTITY_ADMISSION_PARALLEL_RU.md](IDENTITY_ADMISSION_PARALLEL_RU.md).
Source identity/preference, core/admission literal cleanup иunknown adapter flags
implemented иindependently scopedapproved; corpus audit completed безmembershipdecision.
Finalcombined1662PASS/6FAIL (1617dictionaryPASS/5newFAIL +45technicalPASS/1knownFAIL),
stdioMCPPASS, self-hostqualityFAIL preserved. No full exit/releaseacceptance.
Все workers/reviewers завершены; active/pending заметки ниже historical.
Next: explicit corpuscontract ownerdecision/callerboundary prerequisite иremaining
source-map/projectstate/nonownedhelper audit. Localgzip не добавлять/не удалять.

**Active execution 2026-10-07:** пользователь разрешил handoff plan;
[IDENTITY_ADMISSION_PARALLEL_RU.md](IDENTITY_ADMISSION_PARALLEL_RU.md).
A identity / B admission / C read-only corpus auditor запущены в отдельных worktrees
от `9488cb66`. Ниже «не запущены» относится к предыдущему handoff snapshot.

**Handoff перед compaction 2026-10-07:**
[NEXT_PARALLEL_HANDOFF_RU.md](NEXT_PARALLEL_HANDOFF_RU.md).
Published baseline `9488cb66`, PR211. Следующий план: sourceidentity worker,
core/admission worker и read-only corpus-contract auditor; worktrees/ownership,
independent reviews и final integration у coordinator. Это план, не запущенные агенты.

**Latest 2026-10-07:** [DISCOVERY_LEGACY_EXIT_RU.md](DISCOVERY_LEGACY_EXIT_RU.md).
Discoverythematicranking/seeds, legacycompilerframes/composition, residualproof+
unithelpers иselectorvisibility исправлены; independent scopedreviews approved.
1431newtestsPASS, MCPstdioPASS; technical45pass/1knownred иmixedreds unchanged,
self-host qualityFAIL preserved. Nextremaining: curated/libraryidentity/preference,
explicitcorpuscontract иunownedcore/admissionhelpers. Старыеnexttask записи ниже
относятся кhistoricalsnapshots. Rawgzip остаётся локально внеGit, не удалять.

**Latest parallel slice:** [PARALLEL_REMAINING_EXIT_RU.md](PARALLEL_REMAINING_EXIT_RU.md).
SDK/patch+standalonevalidator, corpus ranking/root inference, delivered MCP/static/
dynamic policy и live read tails реализованы, independent scoped reviews approved.
723newtestsPASS, stdioMCPsmokePASS, frozenpins13/13 unchanged. Technical45pass/1red,
oldvalidator19pass/12red и прочие mixedreds сохранены; self-host qualityFAIL.
Next OPEN: explicit bounded corpus contract/discovery priorities и dormant compiler/
proof exit; ниже планы предыдущих slices исторические. Rawgzip остаётся внеGit.

**Latest slice:** [LITERAL_NEEDS_FOLLOWUP_RU.md](LITERAL_NEEDS_FOLLOWUP_RU.md).
Semantic needs и NL clause/context inheritance удалены из default needs producers;
live recovery clause splitter отвязан. 447 новых tests PASS, MCP smoke PASS,
independent scoped approval; self-host quality FAIL сохранён. Ниже next-task
формулировки про эти два producers относятся к предыдущему snapshot.

**Публикация выполнена:** reviewed partial slice `58750962` pushed в
`origin/integration/stage3-v2-identity-pr1`. Следующий default-read slice запущен:
[DEFAULT_READ_FOLLOWUP_RU.md](DEFAULT_READ_FOLLOWUP_RU.md).
**Follow-up reviewed:** reference/ranking и structural units реализованы,
375 новых tests passed, stdio smoke PASS, оба scoped reviews approved.
Next task теперь live semantic needs в `question_retrieval_needs.py` и
`need_contracts.py`; original-coverage/quality red и advanced/corpus debt остаются.
Ниже сохранена provenance исходного pre-commit checkpoint; формулировки о local diff
и отсутствии commit описывают тот snapshot, не текущий опубликованный baseline.

**Post-review update:** [PRECOMMIT_REVIEW_RU.md](PRECOMMIT_REVIEW_RU.md).
228 новых tests passed; independent run 274 passed и scoped commit approval.
Cached scope, explicit nondelivery/consent и serialized-contract blockers закрыты.
Original 416 pins ниже — исторический snapshot; current pins:
`archives/dictionary-exit-reviewed-source-manifest.json`. Quality gate всё ещё red.

## 1. Решение владельца и границы

Сначала удаляем ручные смысловые правила и отвязываем consumers; затем улучшаем
полноту общими механизмами. Прежняя полнота и наличие доказанной replacement
больше не prerequisites удаления. Не добавлять aliases/topic regex/expected APIs,
не переносить словари в prompts, конфигурацию или другой модуль.

Оставляем: исходный вопрос + до пяти явных lookups → поиск → исходные цитаты.
Вопрос на языке документации; RU→RU и EN→EN — основной scope. Lookups независимы:
нет inferred equivalence или автоматического переноса coverage на original.
Цитата не удостоверяет полный ответ и не разрешает edit.

Не ослаблять technical guards: project/library/module/version/snapshot identity,
freshness, hash/span/provenance, consent/network, input/search/output budgets,
separate explicit mutation target/readiness. Existing tests/gold/thresholds и
224 frozen cases не менять. Красные результаты сохранять, не объявлять PASS.

## 2. Что реально готово

- В primary объединены два executor slices и последующие integration fixes.
- Удалены query aliases/semantic rewrites/generated probes, thematic/library boosts,
  NL tool/regex routing, answer/API generators и часть semantic admission/proof.
- Public `get_docs_context` не выводит mutation contract из вопроса; required paths
  сами по себе не означают `modify`. Explicit SDK mutation — отдельный guarded путь.
- Полезные selected quotes сохраняются без answer/edit/proof authority.
- Старые supplied support decisions перепроверяются; public attribution требует
  актуальный plan ID/origin/relation/text; anonymous traces — no-credit.
- Input limits и mandatory exact snapshot enforce fail-closed в обеих проекциях,
  включая fresh/supplied decisions и текущие caller public requirements.

**Проверки последнего состояния:** 146 новых tests passed; реальный stdio MCP
smoke PASS (lifecycle/consent/status/text fallback); independent scoped technical
approval — 15 snapshot + 7 limit probes passed. Не full CI или rebuilt-wheel release.
Frozen pins 13/13 совпали; 224 случая и существующие tracked tests/eval/workflows
не изменены. Commit/push/merge не выполнялись.

**Quality gate red:** `archives/dictionary-exit-self-host-v1.json`, useful 11/15,
Top-3 relevant 12/15; failures 01/08/12/14/15 и unchanged frozen floors.
Original coverage count=0 остаётся открытой attribution/quality regression.
Этот report снят до последних technical-limit corrections; не final release gate.
В нём false-supported=0, budget violations=0; эти нули не доказывают полную безопасность.

## 3. Рабочее дерево и provenance

- Primary: `/tmp/opencode/docatlas-stage3-integration-active`.
- Branch: `integration/stage3-v2-identity-pr1`.
- HEAD: `9a7299e273edafe61095397ff10f4d776d8f97f6`; implementation **в локальном diff**,
  а не в этом commit. Также есть прежние незакоммиченные P1/P2 документы/artifacts.
- Current source/test/docs pins: `archives/dictionary-exit-current-source-manifest.json`.
  Это hash snapshot, не acceptance и не backup всех локальных файлов.
- По решению владельца `archives/p2-real-mcp-alias-ablation-v1.json.gz` (~33 MB)
  остаётся локально вне Git. Compact analysis/report публикуются; fresh clone
  не содержит полного исторического raw trace. Архив не удалять; внешнее хранилище
  пока не настроено.
- Executor worktrees `/tmp/opencode/dictionary-exit-retrieval` и
  `/tmp/opencode/dictionary-exit-admission` содержат **первые slices**, не final state.
  Их patches не применять повторно поверх primary.
- Все агенты завершились. Исполнение не идёт в фоне. Temporary executor logs/patches
  не считать единственной точкой восстановления; продолжать по primary и этому checkpoint.

Не делать reset/checkout/delete и не восстанавливать published intent ради baseline:
это вернёт удалённые словари. Не запускать `p1_approve_freeze.py` как read-only check:
он перезаписывает manifest. Frozen approved artifacts не переписывать.

## 4. Дальше — по порядку

### Следующий bounded slice: оставшийся default read

1. Проверить current callers и удалить ручные role/relation/source-language
   интерпретации в `docmancer/docs/domain/query_reference_binding.py`.
   Сохранить exact literal references, source/project/version identity и hash/span
   bindings; неизвестную связь не превращать в proof или право расширить scope.
2. Удалить live reporting/proof/comparison vocabulary priorities из
   `docmancer/docs/application/context_candidate_ranking.py:_relation_request_priority`.
   Оставить bounded lexical/structural ranking, без знаниевых boosts по теме.
3. Разделить structural answer-unit segmentation и semantic proposition detection
   в `docmancer/docs/domain/_answer_units_shared.py` и `_answer_units_part01.py`.
   Убрать copula/behavior/status dictionaries; сохранить deterministic IDs и spans.
   Не заменять удалённый proof безусловным `valid=True`.
4. Обновить remaining inventory; выполнить tests/public indexed MCP/stdio и review.
   Успех этого slice не означает full dictionary exit.

Сначала согласовать общие interfaces; затем можно два исполнителя на непересекающихся
файлах и независимый reviewer. Common projection/qualification edits интегрировать
последовательно. При следующем старте сначала проверить `git status` и source pins.

### После default read: explicit SDK / advanced patch

Проверить и удалить оставшиеся subject/behavior/policy/typed proof и semantic
patch aliases, сохранив explicit contracts и fail-closed authorization:

- `docmancer/docs/application/_evidence_selection_part02.py` — legacy matches;
- `docmancer/docs/domain/_answer_units_part02.py` — supplied-obligation proof;
- `question_plan*`, `question_premise_proof.py`, `governance_value_proof.py` —
  достижимые legacy parser branches, не молчаливое техническое исключение;
- `_patch_constraints_service_shared.py`/shards, `_patch_review_service_shared.py`/
  shards — `PHRASE_ALIASES`, inline aliases, low-value/stopword/policy keywords;
- `docmancer/docs/domain/source_map.py` — NL stopwords отдельно от grammar языка.

### Затем corpus / delivered policy

Поэлементно разобрать `docmancer/connectors/fetchers/pipeline/filtering.py`,
`docmancer/connectors/fetchers/github.py`, discovery registries,
`docmancer/mcp/agent_workflow_contract.py` и `docmancer/templates/`.
Не удалять schema/protocol/explicit identity→URL mappings по одному признаку table.
Не заменить topic dictionaries guessed root/locale scope; explicit URL/network/
version boundaries и source provenance должны сохраниться.

После каждого slice сохранять regessions, не ослаблять release floors. Улучшение
scorer/полноты — следующая отдельная задача, не обход remaining dictionary exit.

## 5. Какие документы читать

| Документ | Роль |
|---|---|
| **Этот файл** | Latest status, next bounded task, рабочие paths и запреты |
| [DICTIONARY_EXIT_EXECUTION_RU.md](DICTIONARY_EXIT_EXECUTION_RU.md) | Owner change, реализованные slices, checks, найденные/fixed blockers, remaining ledger |
| [DICTIONARY_INVENTORY_RU.md](DICTIONARY_INVENTORY_RU.md) | D01–D38 историческая карта; не current implementation status каждой строки |
| [P0_FINAL_ATTRIBUTION_MAP_RU.md](P0_FINAL_ATTRIBUTION_MAP_RU.md) | Producer/crop/public attribution dependency map; code hashes теперь исторические |
| [P0_FINAL_SELECTOR_MAP_RU.md](P0_FINAL_SELECTOR_MAP_RU.md) | Technical selection/assignment/support границы; не подтверждение current source pins |
| [P1_SAME_LANGUAGE_AMENDMENT_RU.md](P1_SAME_LANGUAGE_AMENDMENT_RU.md) | Same-language scope amendment |
| [P1_APPROVAL_RU.md](P1_APPROVAL_RU.md), [P1_CONTRACT_RU.md](P1_CONTRACT_RU.md) | Frozen исходный contract/limits; порядок удаления superseded owner change |
| `archives/p1-approved-freeze-manifest.json` | Approved freeze pins; неизменяемые 224 cases/159 assertion ledger |
| [P2_STATUS_RU.md](P2_STATUS_RU.md), [P2_REAL_MCP_ABLATION_RU.md](P2_REAL_MCP_ABLATION_RU.md) | Исторические replacement/ablation experiments, не текущий next task |

`docmancer/docs/application/DICTIONARY_EXIT_INTEGRATION.md` — исторический отчёт
первого admission executor, **не** latest combined state. Не повторять уже исправленные
там integration actions. `DICTIONARY_EXIT_PLAN_RU.md` — frozen исторический порядок,
не требование сначала доказать replacement после нового owner decision.

## 6. Актуальные integration files и проверки

Critical consumers: `documentation_query_plan.py`, `evidence_qualification.py`,
`project_doc_ranking.py` в `docmancer/docs/domain/`; `reference_query_tagging.py`,
`context_query_probes.py`, `_docs_context_projection_core.py`,
`model_visible_projection.py`, `evidence_requirements.py`, selector shards,
project/unified context service shards в `docmancer/docs/application/`;
`docmancer/docs/interfaces/mcp/context_tools.py` — actual public boundary.
Consumer contracts не менять конкурентно. Не добавлять topic fixes ради одного gold case.

```bash
PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest -p no:cacheprovider -q tests/test_dictionary_exit_*.py
```

Восемь новых modules и их `tests/diagnostic_labels.dictionary_exit_*.json` —
current new-only test inventory. Новые tests классифицировать отдельным shard;
`--noconftest` не считать repository validation. Технические existing suites:
`tests/docs/test_target_security.py`, `test_content_trust.py`,
`test_reference_hash_domains.py`, `test_review_source_capabilities.py`,
`test_finalized_mcp_output_integrity.py`, `test_mcp_boundary.py`.
Mixed positive-proof/compatibility tests тоже запускать и записывать red,
а не исключать автоматически из отчёта.

```bash
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH="$PWD" TMPDIR=/tmp/opencode PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 DOCATLAS_AUTO_VECTORS=0 DOCATLAS_REGISTRY_API_URL=http://127.0.0.1:1 .venv/bin/python scripts/docs_mcp_stdio_smoke.py
```

Smoke создаёт/коммитит только свои disposable fixture repositories, не primary.
Self-host report — отдельный unchanged quality gate, сохранять в новый versioned
artifact и указывать SHA/config/time slice, не перезаписывать старый красный result.
# Latest: local/security bounded pass completed (2026-10-07)

[LOCAL_SECURITY_COMPLETED_RU.md](LOCAL_SECURITY_COMPLETED_RU.md) и
[LOCAL_SECURITY_FINAL_INTEGRATED_AUDIT_RU.md](LOCAL_SECURITY_FINAL_INTEGRATED_AUDIT_RU.md).
Primary original checkout на PR211 branch. NEXT06/07 preserved localWIP0ce30227
на separate next07branch безpush, не включён вPR211; artifacts untouched.
D1exact10docs/codeempty иD2inertdata/no-broker integrated/scopedreviewed.
161newPASS,2096combinedPASS/95FAIL unwaived, boundedpublicationblockerNO.
FullEXITNO/NLvetoRETAINED; freshquality иinstalledparity UNKNOWN, lastqualityFAIL.
Reinstall/indexrebuild/livenetwork forbidden, historical statuses ниже не newacceptance.
