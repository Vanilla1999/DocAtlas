# Remaining dictionary audit: legacy / consumers / recovery / source map

Дата: 2026-10-06. Primary `/tmp/opencode/docatlas-stage3-integration-active`.
Baseline **`adc9abf8cfc939ef1e44e8895c00b448b77033b3`**.
**Full dictionary exit NOT DONE.** Это bounded static production/caller audit,
не acceptance, не runtime trace и не доказательство отсутствия других правил.

## Метод и границы

Прочитаны `CONTINUE_HERE_RU.md`, `LITERAL_NEEDS_FOLLOWUP_RU.md` и исторический
`DICTIONARY_INVENTORY_RU.md`; current implementation проверена отдельно.
На старте tracked diff отсутствовал; единственный untracked artifact — прежний
`archives/p2-real-mcp-alias-ablation-v1.json.gz` (не тронут). Ниже номера строк
относятся к baseline. Проверены определения, вызовы и guards, а не только imports.
SDK patch и corpus filtering — параллельный ownership: их implementation/diff
не reviewed; наличие соседнего caller не означает approval этого caller.
Никаких production/tests/gold/freeze/thresholds/manifests изменений, запусков
качества, network, commit или push. Единственный новый файл — этот отчёт.

Здесь **LIVE** означает существующий условно исполнимый production call edge;
**DORMANT** — нет найденного вызова от default entry point либо guard делает
semantic branch недостижимым; **UNKNOWN** — внешние/direct SDK consumers или
фактическая runtime частота не установлены. DORMANT не закрывает dictionary exit.

## 1. Реальный default MCP путь и разрывы старой цепочки

* `_docs_server_schema.py:32–40`: admin/advanced по умолчанию выключены;
  `_docs_server_shared.py:105–119` строит handlers только доступной surface;
  `_docs_server_part01.py:94–111` возвращает `unknown_tool` до dispatch для
  отсутствующего handler. `get_code_context` в старом `project_tools.py:562`
  нельзя приписывать default surface по наличию import/ALL_SURFACE.
* `context_tools.py:293–335` → `UnifiedContextService.get_docs_context`:
  read-only; mutation contract не передаётся; `prepare_project_docs=False`,
  `allow_network=False`, `prefetch_auto=False`.
  `_unified_context_service_part01.py:87,174,190,196` → default none mutation
  и фактический `service.get_project_context` для выбранной project/deps lane.
* `_project_context_service_part01.py:61` / `evidence_requirements.py:180,329`
  → `build_project_answer_contract`; `_project_answer_contract_part02.py:8–25`
  возвращает hash полного вопроса, пустые subjects/obligations/probes и
  `component_scope_complete=False`. **Не вызывает compile_question_plan**.
* `documentation_query_plan.py:85–108` производит только original + до пяти
  explicit lookups; не создаёт `retrieval_need`, semantic components или aliases.
  `_docs_context_projection_core.py:104–112` повторно собирает authoritative
  queries и принудительно очищает `_component_contract`.
* Единственный найденный production вызов `compile_question_plan` вне самого
  compiler — `question_ownership.py:245–261`; его найденный внутренний caller —
  `frozen_ownership_mismatches():268`. Отдельный tooling caller:
  `scripts/run_question_surface_gate.py:35`. Default read до них не найден.

**Вывод:** manual QuestionPlan rules остаются callable legacy/tooling debt,
но не доказанный default execution. Старый D21/D22/D23 inventory нельзя читать
как список нынешних live dictionaries.

## 2. LIVE: recovery suggestions (diagnostic, не retrieval authority)

Call edge: `context_tools.py:383` →
`recovery_projection.py:_attach_recovery_diagnosis:236–304` →
`recovery.py:build_recovery_diagnosis:178,321` → `_suggested_questions:129–175`
→ `recovery_action:360–399`. Условие: canonical selection существует и answer
не supported; operational recovery имеет приоритет (`recovery_projection:275–288`).

Оставшиеся ручные правила:

| Правило | Эффект / классификация |
|---|---|
| `recovery.py:30–35 _IMPERATIVE_PREFIX_RE` | EN/RU implement/create/remove/refactor и т. п. вырезаются из subject fragment (`122–126`). **Manual NL transformation**, не syntax/protocol. |
| `:37–41 _LEADING_CODE_PATH_RE` | Вырезает leading source path вместе с `so/to/for/чтобы/для`. Path grammar техническая; стирание path/связки — отдельное manual rewrite правило. |
| `:23,163–165` fixed English wrappers | Создают новый question, в т. ч. `According to {path}, what does it say about …?`; это не доказанная semantic equivalence. |
| `:138–139` Cyrillic veto | Для RU suggestions не выдаются; language heuristic, не schema. Не доказательство same-language replacement. |
| `:115–119` generated-wrapper recognition | По фиксированному phrasing ставит exhaustion; технический one-retry ceiling смешан с распознаванием NL wrapper. |

`_problem_spans:105–112` уже literal bounded fragment, не clause dictionary.
`build_recovery_diagnosis:227–251` при projection-path **возвращается до
suggestions**; `_attach_recovery_diagnosis` вызывает без projection и может
дойти до них. Нельзя ни назвать всё recovery dormant, ни утверждать, что каждая
финальная docs_context проекция показывает rephrase.

`recovery_action:380–392` отдаёт `arguments_patch.question` coding agent, требует
не считать retry equivalent proof; автоматического нового retrieval вызова здесь
нет. Но host-followed guidance реально меняет следующий запрос. Сохранить
operational reason enums (`:46–53`), budgets, hard-stop/consent и non-automatic
handoff; убрать semantic rewrite, не делать безусловный retry/edit allow.

## 3. LIVE conditional source-map путь; query-dependent часть отдельно

Обычный route **не** открывает source scanning по prose:
`retrieval_routing.py:43–51` всегда `use_source_evidence=False`;
`:54–68` не разрешает обычный docs/api repo map. Поэтому строки
`_project_context_service_part01.py:262–294` сами по себе не доказывают live
query-driven source map в default read.

Но documentation-gap путь существует:
`_project_context_service_part01.py:349–360` →
`_source_ground_documentation_gap` (`_project_context_service_shared.py:92–121`)
→ `collect_project_source_facts(include_unmatched=True)` без question →
`source_map.py:159–193` → `_map_source_file:539–584`.
Условие — returned `create_reviewable_project_doc` action. Runtime частота и
прохождение до final public projection в этом аудите **UNKNOWN**.

| Source-map rule | Достижимость / решение |
|---|---|
| `_STATUS_TOKEN_RE:44`; `_extract_status_like_tokens:689–696` | **LIVE conditional** gap capture: manual status vocabulary + blanket Cyrillic literal selection; результат попадает в `content` (`720–721`), то есть влияет на compact facts/window, не только telemetry. Не protocol status enum. |
| `_QUERY_STOPWORDS:758–773` | Исполнимы в collector, но с пустым question gap-path список ничего не удаляет. Эффект **DORMANT default query route**, **LIVE direct SDK source-map call** с question. EN/RU stopwords не grammar языка программирования. |
| `_question_requests_generated_artifacts:531–536` | Literal generated suffix check смешан с EN/RU phrase list, который открывает generated-file scanning при `include_generated=None` (`168,243`). Gap question пуст; direct SDK с question — callable effect. Оставить explicit `include_generated` и source boundary; не заменять NL whitelist безусловным включением generated files. |
| `_KEYWORDS:56–94` → generic symbols `643`, references `678` | Programming grammar exclusion, не query semantics. **Сохранить**, не массово удалять как словарь. |
| `SOURCE_FILE_LANGUAGES:11–23`, imports/declarations/paths, AST, line offsets | Explicit suffix→language identities и syntax extraction. Техническая часть; не guessed library/topic mapping. |
| `_SECRET_ASSIGNMENT_RE:45–47`, source boundary, ceilings | Safety/authorization/budget; не grounds для dictionary removal. |

Другие реальные края: `code_context.py:49` и `_code_graph_part01.py:90` →
collector; advanced `project_tools.py:569` → `build_code_context`.
`project_state.py:_documentation_gap_evidence:258–273,327` вызывает repo map с
`question=query or "architecture"`: injected topic fallback **не техническая
identity**. Сохранён как отдельный candidate; полный внешний caller/доставку
этого authoring action ещё проверять. Direct SDK функции `build_project_repo_map`,
`build_project_source_evidence`, `collect_project_source_facts` принимают question
и explicit boundary/include_generated; внешние callers **UNKNOWN**.

## 4. DORMANT default, но остающиеся semantic compilers

| Baseline место | Точный semantic debt и call edge |
|---|---|
| `question_frame_core.py:301–339` → `question_plan.py:675–690` | `sync/synchronize/refresh/update/reindex` + project-docs RU/EN surface → `ActionFrame("sync_project_docs")` → неназванные subject/expected API `sync_project_docs` + aliases. **D22 не закрыт целиком**: command-rule adapters пусты, но этот independent branch жив при direct compiler call. |
| `question_plan_surface_rules.py:208–225`; `question_plan.py:199–225` | Generic public-tool question инъецирует конкретные три tool names и per-tool purpose/usage facets. Сам protocol enum допустим; его использование как ответный inventory без literal names — manual inference. |
| `question_plan_surface_rules.py:229–243` | `which Python versions are supported` → неназванный `DocAtlas`, attribute `python_version`; domain answer injection. |
| `question_plan.py:76–95,98+`; `surface_rules.py:263–276` | Exact 1000-line-release wording → canonical release subject; storage-coordination/provider-timeout surface → тематические typed facets. Callable parser rules, не explicit task schema. |
| `surface_rules.py:107–143,146–185` | owner/version/defer/notification phrases → governance relation/value kinds и `expected="deferred"`. |
| `question_semantic_frames.py:79–107,130+,194+,236–288` | Comparison/condition/premise/decision/purpose/before NL frames → `_reusable_frame_plan` (`question_plan.py:506–690`) → facets. |
| `question_frame_core.py:54–109,122–140,280–298` | Question/action heads, politeness stripping, conjunction splitting, requirements recognition. Span DTO/validation технические; список NL cues нет. |
| `need_composition.py:14–21,68–78,108+` → `compositional_question_plan.py:7–23` → `question_plan.py:914–916` | NL independent-head/dependency/count/condition/set/mapping/precedence proposals. Protected quote/link mask и spans отдельно сохраняются. Не default literal needs producer. |

`question_ownership.py` frozen exact-question registry не обнаружен как default
arbitration caller на baseline; **не менять frozen cases** ради cleanup. Direct
compiler/tooling compatibility открыта, их удаление требует отдельного bounded
slice, а не заявления об отсутствии вызовов у любых внешних SDK пользователей.

## 5. Proof consumers: что действительно может выполниться

* `extract_answer_units` (`_answer_units_part01.py:163–189`) создаёт units с
  `proposition=False`. `local_proof_for_obligation` (`part02:418–424`) сначала
  допускает только strict supplied literal key/value equality (`351–390`), затем
  отсекает все structural units; definition/behavior/status/workflow дополнительно
  fail-closed. Literal equality не удостоверяет NL answer/edit authorization.
* `context_selection.py:61–73`, `retrieval_need_support.py:94–100` фильтруют units
  по proposition: с текущим extractor semantic proof loop не выполняется.
  Default projection также очищает components (раздел 1).
* `_answer_units_shared.py:15–17` импортирует governance prover; **import не
  execution**. Реальный conditional edge в `part02:685–695` существует только
  после proposition guard и supplied relation obligation. Direct caller может
  создать `AnswerUnit(proposition=True)`: governance proof тогда исполним.
* `governance_value_proof.py:32–80,88–125,264+,384–419` ещё содержит stopwords,
  own/defer/pin canonicalization, owner/requirement/state/same-policy regex и
  Android-13-specific requirement logic. **DORMANT default / LIVE explicit direct
  proof call**, внешнее использование **UNKNOWN**. `_GOVERNANCE_RELATIONS` и
  `_CANONICAL_AUTHORITIES` — typed relation/authority identities; не удалять их
  вместе с NL detectors. Этот вывод не review конкурентного SDK patch slice.
* `question_premise_proof.py:29–51,74–96,124–207`: causal/limitation cues,
  delete↔remove/preserve↔keep RU/EN action forms, public Docs MCP tool cardinality
  и metadata subject fallback (`177`). `premise_relation_proof` не имеет найденных
  production callers; **DORMANT direct-call compatibility**, не default proof.
* В `part02` остаются NL boolean words (`170–171`), inventory introducers/open-list
  (`69–80,115–119`), comparison verbs (`202–240`), location product exceptions
  (`566–582`), special relations (`319–348`) и generic subject exceptions
  (`438–444`). Часть branches достижима лишь supplied proposition=True; location
  к тому же после общего proposition guard. Usage/special non-governance relation
  fallback перекрыт negative planned proof (`650–659,685–695`), а не просто import.
  Это residual manual rules, **не** default successful certification.

## 6. Уже технические / fail-closed, не remaining semantic dictionaries

* `admission_grammar.py:36–52`: `NEW_RELATIONS` только protocol identifiers,
  canonical phrase literal, parser всегда None. `admission_relations.py:7–11`
  всегда negative witness. `admission_meaning.py:20–34` поэтому даёт unknown,
  не paraphrase credit; `same_supported_meaning:49–56` unknown не принимает.
* `admission_contract.py` guards/DTO/route/status enums — explicit decision shapes.
  `choose_need_admission` имеет lexical parser call, но parser None; найденного
  external production вызова этой функции нет. Не обвинять этот module в старых
  удалённых `_WORDS/_FORMS/_ACTIONS` по historical D21.
* `question_plan_command_rules.py:11–24` все adapters None; surface normalization
  (`question_surface_normalization.py:20–36`) больше не RU→EN dictionary.
* `question_plan_proof.py:24–26,50–76`: literal tokens и explicit negative proofs,
  прежней `_semantic_terms` translation table нет. Не считать null-return fallback:
  prover возвращает negative object.
* `technical_terms.py:79–80,126–129`: literal spelling aliases/noun forms; прежних
  irregular-singular и command-cue dictionaries здесь не обнаружено. Значимость
  separators, env-var case, exact spans и technical kind enums сохранить.

## 7. Небольшой дополнительный live-execution, zero-effect default хвост

`context_candidate_ranking.py:_facet_aware_candidates:114–116` **вызывает**
`independent_sentence_spans` из `need_composition.py` даже в literal projection.
Это не import-only. `_HEAD/_DEPENDENT` исполняются; результат используется в
`independent_ratio:162–165`, только для `need_query_ids`. Default authoritative
plan имеет лишь original/host lookup, поэтому `need_query_ids` пуст
(`_docs_context_projection_core.py:176`), ratio всегда 0. Классификация:
**LIVE execution / DORMANT default ranking effect**, callable legacy ranking
effect с supplied need IDs. Удалить ненужный NL вызов/сигнал отдельным малым slice;
не объявлять entire need_composition dormant и не возвращать generated needs.

## 8. Приоритет следующих bounded slices

1. **Самый малый read cleanup:** убрать unused `independent_sentence_spans`
   ranking invocation/semantic ratio, сохранив positional rank contract и
   lexical/budget guards. Проверять original/lookup projection без need IDs.
2. **Recovery guidance:** отвязать imperative/path stripping и fixed semantic
   rephrase generation. Оставить original diagnostic fragments, typed operational
   repair/local inspection и at-most-one/non-automatic bounds. Не перемещать
   wrappers/verb lists в prompts/config; EN/RU отдельно, без manufactured equivalence.
3. **Source-map narrow split:** сначала status/Cyrillic summarization; затем
   NL stopwords и generated-artifact phrase authorization для direct SDK. Технические
   source syntax/identity maps и SourceBoundary оставить. Проверить gap capture
   отдельно от query-driven/advanced source navigation.
4. **Dormant compiler exit:** independent sync API injection, public-tool/Python
   subject injection и governance/frame compilers. Сохранить DTO/spans/protocol
   enums; direct-call tests/tooling нельзя выдавать за default MCP. Frozen ownership
   fixtures и исторические manifests не переписывать.
5. **Residual proof cleanup:** premise/governance/supplied-proposition vocab согласовать
   с SDK owner; не редактировать конкурентно общие consumers. Отрицательный default
   guard не является завершением удаления dormant rules.

UNKNOWN остаются внешние SDK callers, фактические delivered gap/recovery branches,
полнота package/config/template scan и качество после очередного slice. Никаких
предположений о полном exit или восстановленных frozen quality floors этот audit
не делает; прежние red quality results остаются действующими открытыми долгами.

Финальный `git status` показывает конкурентные изменения в SDK patch shards,
corpus fetchers, workflow/templates и новые corpus tests. Их diff не читался и
не оценивался; все приведённые выводы — baseline, не approval итогового concurrent
tree. Этот агент записал только `REMAINING_DICTIONARY_AUDIT_RU.md`.
