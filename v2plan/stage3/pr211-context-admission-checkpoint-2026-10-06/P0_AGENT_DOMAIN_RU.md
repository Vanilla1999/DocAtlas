# P0: domain — поэлементный аудит (2026-10-06)

## Результат

**507/507 units, 48/48 текущих source-файлов**, все pinned SHA-256 совпадают.
JSON: `archives/p0-agent-domain-decisions.json`. Каждая строка сохраняет исходный owner, node_ids,
точный AST range, все unresolved expressions, конкретные статические consumers, guards и limitations.
Production/tests/gold/common runners/status не изменены; новые query dictionaries не добавлены.
AGENTS.md не найден в repository glob и проверенных ancestor locations `/`, `/tmp`, `/tmp/opencode`.

| Решение | Units |
|---|---:|
| REMOVE | 178 |
| SPLIT | 112 |
| TECHNICAL-RETAIN-CANDIDATE | 217 |
| OPEN | 0 |

## Статус evidence, не approval

REMOVE — последующая замена semantic rules, не выполненное удаление и не снятие guards.
SPLIT — в reason названы конкретные совместные semantic и structural/protocol duties.
TECHNICAL-RETAIN-CANDIDATE — локальные syntax/schema/identity/budget операции, не exemption owner closure.
OPEN — unresolved safety/corpus/identity boundary; не blanket technical decision.
D IDs — supporting family mapping из DICTIONARY_INVENTORY_RU.md, не доказательство принадлежности каждого expression всем ID.

Решения основаны на фактических исходниках/полных bodies ключевых mechanisms, входных expressions,
AST owners/локальных dependencies и существующих inventory/symbol-policy audits.
**Не заявляется полное ручное чтение всех транзитивных dependencies, runtime consumer closure или default-path audit.**
`static-edge-only` означает фактическую локальную Name-load/import reference; `unresolved` — direct caller не установлен.
Итог второго прохода: **483 static-edge-only, 18 unresolved, 2 fallback, 4 default**. Это bounded source reachability, не полный runtime graph. default означает обычный путь конкретного consumer при выполнении его условий; fallback — legacy compiler branch, не режим всего сервиса.
Не называем import default execution. Nested methods/properties/closures и wildcard bridges требуют отдельной проверки;
SDK/fallback/default label не придуман по filename.
Для public `extract_answer_units`, `build_project_code_graph`, `code_graph_diagnostics` и
`code_graph_context_diagnostics` дополнительно проверены реальные `answer_units.py`/`code_graph.py`
re-exports и exact importing loads: application evidence candidates/selection/support, project context и patch callers.
Эта подтверждённая facade цепочка не превращена в полный runtime graph.

## Подтверждённые границы

### D01/D02/D04/D05: query injection versus original attribution

`_project_answer_contract_part01._concept_queries` (332–365) содержит semantic_aliases public_tools/invocation/delete/preserve/scope;
`_inventory_subject` (403–423) подставляет Docs MCP, `_command_operation` (426–453) выводит известные команды из prose.
`project_retrieval_intent.build_project_retrieval_aliases` генерирует offline suite/DOCATLAS_OFFLINE/sync_project_docs/indexing lifecycle
и forbidden role/term policy. Это semantic proposal/source-selection producer, не source facts.
`documentation_query_plan.build_documentation_query_plan` смешивает direct original/typed needs с fixed config/contract/sync concept queries (575–590).
`_audited_host_lookup_rewrites` подставляет известные get_docs_context API/selection terms.
Direct query/DTO/parent policies сохраняются отдельно; `derived_parent_trace` (524–530) требует qualified, audited_rewrite и parent exact terms.
RU/EN surface/component templates не освобождены как grammar; original-span rebinding и unknown/negated tails сохраняются.

### D21/D24/D25/D28: relation interpretation versus source witness

`admission_grammar.canonical_phrase` через _WORDS нормализует EN/RU role nouns;
_FORMS/_ACTIONS/_STATES меняют meaning signature, несмотря на opaque arbitrary identities.
Fullmatch, literal spelling/case, original offsets, bounded unique targets, distinct binary sides и unknown→None — отдельные guards.
`admission_relations._mapping_assignment` (186–200) требует реальные backticked values, source-ordered correspondence/uniqueness;
`_table_mapping` (203–227) требует actual header/separator/nonempty data row и не принимает неизвестные conditions.
Passing structure не заменяет поддержанный semantic relation.

`_answer_units_part01._context_score.tokens` (593–605) содержит cleanup/cleaning/clearing→clear,
indices/indexing→index перед subset context matching (расширение D23). Regex tokenizer не делает это technical-only.
`_answer_units_part02.local_proof_for_obligation` содержит legacy MCP subject exemption (477–489),
public-tool subject fallback (572–577), doc-atlas shortcut (589–591), fixed config/contract location equivalents (605–620).
Lifecycle/current source (458–469), proposition/source_field (593–599), bound clause/qualifier и unsupported-obligation rejection (777) сохраняются.
`extract_answer_units` также SPLIT, не syntax-only exemption: exact Markdown/source offsets сосуществуют
с lexical proposition flags (250–254,292–299), paragraph flags (328–332) и workflow grouping (428–446).
`_generic_behavior_qualifiers` сохраняет actual escaped subject/action/object binding отдельно от how/what-does grammar и do/work exclusions.
`_inventory_facts` смешивает lexical intro/count anchor с actual table/backtick identifiers/count agreement.
Общие number-word normalization и inflection остаются неутверждёнными language exceptions, не blanket numeric technical retention.

`governance_value_proof._ANDROID_13_RE` имеет actual consumer `_android_requirement_is_bound` (264–317):
Android 13 включает special active/passive requirement direction branch, а не только shaped literal.
REMOVE относится к hardcoded platform interpretation; direction/polarity/requested subject/value и canonical source (398–399) обязательны в replacement.
_CANONICAL_AUTHORITIES/_GOVERNANCE_RELATIONS — metadata/typed enum отдельно от NL owner/scope/deferred/placeholder lists.

### D34/D26: current-source guards versus incoming claims

`qualify_evidence` (282–286) удаляет incoming witness/context acceptance flags, проверяет source policy (288–295),
пересобирает reference (297–301), bound subjects/exact terms (419–458), current-body admission (482–503).
`evidence_policy_rejection_reason` (211–225) сохраняет project/current/synchronized/risk/lifecycle;
последующие forbidden term/role checks (227–238) получают alias-origin policy, а transport не одобряет producer.
`prepare_reference_probe` проверяет project/snapshot/version/path/content/window/body identity и source owner;
`query_mentions` смешивает exact quoted/path spans с selected role/source/actor grammar.
`technical_terms` separator aliases сохраняются лишь с CLI/env/code/config shape guards (245–286);
irregular noun equivalence и prose→command-kind cue не являются автоматической технической нормализацией.

### D07/D08/D09/D17/D31: routing, mutation, graph

`select_public_docs_tool` (224–230) принимает actual returned public next_action отдельно от guessed STATUS/PREPARE/DOC words.
Tool/action protocol mappings не query dictionaries; без verified action остаётся read entrypoint.
`patch_request_plan`/`mutation_intent` требуют original requested/preserved targets, unresolved-gap/polarity checks,
unique positive local evidence, create parent context, отдельный destination collision witness.
`resolve_mutation_targets` (336–348) содержит filename-stem→CamelCase alias; source target guards сохраняются отдельно от heuristic.
`retrieval_routing` literal counters/byte limits/schema отдельно от NL navigation/connectivity/Service/Controller/Cubit/Bloc suffixes;
configured mode, bounded escalation и resolved-single-target stopping сохраняются.

Code graph source-derived DTO/import candidates сохраняют unresolved ambiguity;
`_resolve_python_import` (429) guessed external roots app/lib/src выделены как SPLIT.
`build_project_code_graph` (90–97) delegates semantic selection to collect_project_source_facts, не exemption всей функции.
`_has_reference_intent` и fixed State/Widget/BuildContext/Service/Repository/Cubit low-signal list — ranking semantic REMOVE.
Graph explicit limitations: not_call_graph/name_based_reference_resolution/regex_symbols_for_non_python (659–662).

### Corpus/safety/structural boundaries

Canonical serialization, actual SpanRef/hash/offset, immutable EvidenceSet validation,
complete Markdown/table/list/fence windows, byte/item budgets, public action schema и actual manifest/runtime APIs — local technical candidates.
Source_dependency_graph structural list/table/heading edges отделяются от NL subject/anaphora/cause interpretation;
validation текущего source/edge/closure не является answer proof.
Generated/package source-boundary lists — TECHNICAL-RETAIN-CANDIDATE: фактическая path-based corpus policy;
configured roots, symlink/root containment, gitignore order и work caps не снимаются. Это не approval полноты corpus.
Content_trust._RISK_PATTERNS — SPLIT: lexical threat detection отдельно от risk categories и safety rejection;
consumer не исполняет content, сохраняет cited-data/executable_policy=False и repository-contained scope.
Project_state actual hash/catalog/chunking drift и bounded handoff technical;
filename→overview и architecture template/default-query/section ontology — отдельная semantic граница.

## Пофайловые counts

| Source | REMOVE | SPLIT | TECHNICAL candidate | OPEN | Всего |
|---|---:|---:|---:|---:|---:|
| `docmancer/docs/domain/_answer_units_part01.py` | 1 | 3 | 4 | 0 | 8 |
| `docmancer/docs/domain/_answer_units_part02.py` | 9 | 7 | 3 | 0 | 19 |
| `docmancer/docs/domain/_answer_units_shared.py` | 15 | 5 | 8 | 0 | 28 |
| `docmancer/docs/domain/_code_graph_part01.py` | 0 | 2 | 21 | 0 | 23 |
| `docmancer/docs/domain/_code_graph_part02.py` | 2 | 2 | 6 | 0 | 10 |
| `docmancer/docs/domain/_code_graph_shared.py` | 0 | 0 | 6 | 0 | 6 |
| `docmancer/docs/domain/_project_answer_contract_part01.py` | 4 | 7 | 7 | 0 | 18 |
| `docmancer/docs/domain/_project_answer_contract_part02.py` | 4 | 2 | 0 | 0 | 6 |
| `docmancer/docs/domain/_project_answer_contract_shared.py` | 32 | 1 | 1 | 0 | 34 |
| `docmancer/docs/domain/admission_contract.py` | 0 | 0 | 1 | 0 | 1 |
| `docmancer/docs/domain/admission_grammar.py` | 5 | 4 | 3 | 0 | 12 |
| `docmancer/docs/domain/admission_meaning.py` | 0 | 0 | 1 | 0 | 1 |
| `docmancer/docs/domain/admission_relations.py` | 5 | 8 | 0 | 0 | 13 |
| `docmancer/docs/domain/canonical.py` | 0 | 0 | 1 | 0 | 1 |
| `docmancer/docs/domain/compositional_question_plan.py` | 0 | 0 | 1 | 0 | 1 |
| `docmancer/docs/domain/content_trust.py` | 0 | 1 | 3 | 0 | 4 |
| `docmancer/docs/domain/context_blocks.py` | 0 | 0 | 7 | 0 | 7 |
| `docmancer/docs/domain/context_windows.py` | 0 | 3 | 4 | 0 | 7 |
| `docmancer/docs/domain/documentation_query_plan.py` | 11 | 5 | 4 | 0 | 20 |
| `docmancer/docs/domain/evidence_qualification.py` | 4 | 4 | 6 | 0 | 14 |
| `docmancer/docs/domain/evidence_set_validation.py` | 0 | 0 | 4 | 0 | 4 |
| `docmancer/docs/domain/governance_value_proof.py` | 9 | 9 | 5 | 0 | 23 |
| `docmancer/docs/domain/legacy_question_coverage.py` | 8 | 3 | 1 | 0 | 12 |
| `docmancer/docs/domain/library_source_options.py` | 0 | 0 | 4 | 0 | 4 |
| `docmancer/docs/domain/mutation_intent.py` | 8 | 3 | 10 | 0 | 21 |
| `docmancer/docs/domain/need_composition.py` | 5 | 5 | 1 | 0 | 11 |
| `docmancer/docs/domain/need_contracts.py` | 0 | 1 | 0 | 0 | 1 |
| `docmancer/docs/domain/patch_request_plan.py` | 9 | 2 | 4 | 0 | 15 |
| `docmancer/docs/domain/patch_requirements.py` | 0 | 0 | 1 | 0 | 1 |
| `docmancer/docs/domain/project_answer_contract.py` | 3 | 4 | 7 | 0 | 14 |
| `docmancer/docs/domain/project_evidence.py` | 0 | 0 | 9 | 0 | 9 |
| `docmancer/docs/domain/project_query_intent.py` | 4 | 1 | 3 | 0 | 8 |
| `docmancer/docs/domain/project_retrieval_intent.py` | 6 | 2 | 6 | 0 | 14 |
| `docmancer/docs/domain/project_state.py` | 1 | 3 | 4 | 0 | 8 |
| `docmancer/docs/domain/quality.py` | 4 | 4 | 8 | 0 | 16 |
| `docmancer/docs/domain/query_reference_binding.py` | 7 | 2 | 9 | 0 | 18 |
| `docmancer/docs/domain/query_terms.py` | 1 | 5 | 3 | 0 | 9 |
| `docmancer/docs/domain/question_component_rewrite.py` | 0 | 1 | 0 | 0 | 1 |
| `docmancer/docs/domain/question_premise_proof.py` | 4 | 3 | 2 | 0 | 9 |
| `docmancer/docs/domain/question_surface_normalization.py` | 0 | 1 | 1 | 0 | 2 |
| `docmancer/docs/domain/request_intent.py` | 4 | 0 | 4 | 0 | 8 |
| `docmancer/docs/domain/retrieval_routing.py` | 5 | 3 | 9 | 0 | 17 |
| `docmancer/docs/domain/source_boundary.py` | 0 | 0 | 8 | 0 | 8 |
| `docmancer/docs/domain/source_dependency_graph.py` | 3 | 3 | 3 | 0 | 9 |
| `docmancer/docs/domain/technical_terms.py` | 1 | 1 | 10 | 0 | 12 |
| `docmancer/docs/domain/technical_tokens.py` | 0 | 1 | 0 | 0 | 1 |
| `docmancer/docs/domain/tool_selection.py` | 4 | 1 | 7 | 0 | 12 |
| `docmancer/docs/domain/trust_contract.py` | 0 | 0 | 7 | 0 | 7 |

## Второй проход: шесть OPEN и semantic consumer edges

- `_PRODUCT_RE` → REMOVE: `_subjects` (part01:218–225) превращает title-case prose в subjects; `_best_subject` ранжирует их. Это nomination, не копирование подтверждённой identity.
- `_TASK_RE` → SPLIT: bounded digit/suffix capture отдельно от task/задача→Task normalization и status obligation (part02:175–182). Оба regex входят в legacy fallback после typed-plan early return (109–117); public wrapper явно импортирует legacy builder (project_answer_contract:20,319), evidence_requirements:453 вызывает facade. Original spans и source binding сохраняются.
- `_RISK_PATTERNS` → SPLIT: detector (content_trust:75–76) → annotation (36–61) → candidate flags (evidence_candidates:208,361) → rejection (_evidence_selection_part01:354–357), witness exclusion (context_selection:47), rescue rejection (_project_context_service_part01:562–567). Уточнение первого прохода: **не warning-only**. Existing flags могут заменить re-detection; отсутствие match не доказывает безопасность или multilingual coverage.
- `_GENERATED_DIRS`, `_GENERATED_MARKERS` → TECHNICAL-RETAIN-CANDIDATE: `_generated_path` (176–178) проверяет segments/filename markers/configured patterns; scanner (107,125) отключает generated-фильтр при `include_generated=True`. source_map:167,242 берёт explicit override либо отдельно аудируемый NL cue (:531); cue не получает technical exemption.
- `_PACKAGE_AND_TOOL_DIRS` → TECHNICAL-RETAIN-CANDIDATE: `_excluded_directory` (:162) → scanner (:105–110) → source_map:523,189,246 → conditional project source/repo-map stages (:261,286). Generated override и gitignore negation не отменяют denylist. Starting root внутри исключённой директории — отдельный случай, не общий whitelist. Broad build/target/vendor/gen exclusions могут скрывать legitimate source; recall/retention approval не выдан.
- `_TOOL_WORD_RE`: declaration→globals export→answer_units facade, без named semantic caller; не смешан с отдельным `_TOOL_INVENTORY_ANCHOR_RE`.
- mutation `_CREATE_RE`, `_DELETE_RE`, `_MODIFY_RE`, `_RENAME_RE`: bounded AST scan **1141 tracked Python files, 0 parse failures**, без named load/attribute/exact-symbol string/import references; explicit `__all__` их исключает. Реальный operation plan/target authorization — отдельный путь. Эти четыре остаются unresolved по direct consumer, но limitation уточнена как declaration-only, не guessed active routing.
- `select_public_docs_tool`: подтверждены evaluate (:39) и test callers (:33,43,67,80); production MCP dispatch caller не установлен. Benchmark сам маркирован deterministic policy conformance, не live LLM evaluation. Тесты не запускались.

JSON содержит `second_pass` и pinned `bounded_consumer_source_sha256` для добавленной named closure. 18 unresolved остаются: bounded closure не подменяет universal DTO/dynamic/SDK graph. Safety/corpus approval и implementation остаются вне P0 scope, хотя механизм всех шести OPEN классифицирован.

## Проверки и ограничения

507 unique input owners/node_ids/order, 48 matching hashes, AST owner ranges и schema/decision/reachability enums проверены.
Consumers — фактические local Name-load/exact module ImportFrom или explicitly marked wildcard candidate loads;
второй проход добавляет named source chains и eval/test callers. Same-name helpers не связываются globally.
Первичный список ограничен 24 references на unit; дополнения второго прохода не обрезаются.
Local dependencies — конкретные local Call sites с actual definition ranges, максимум 30; не полный graph.
Дословные branch predicates в preserve требуют сохранения/re-evaluation обязанности, не approval выбранного lexicon.
Статические references не доказывают external SDK use/default execution/dynamic exports.
Повторная проверка: 507/507 ordered identities/node_ids и все unresolved expressions сохранены; 48/48 input hashes и дополнительные consumer hashes совпадают; все 48 строк report counts согласованы с JSON, добавленные reference ranges находятся в файлах.
No tests/baseline rerun: production не менялся. JSON/report verification не behavioral migration validation.
P0 inventory slice выполнен в пределах supported evidence; full repository/installed/default caller closure и approvals не закрыты.
