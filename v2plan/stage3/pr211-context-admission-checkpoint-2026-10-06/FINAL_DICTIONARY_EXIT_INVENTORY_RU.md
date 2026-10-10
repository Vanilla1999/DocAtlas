# Final residual dictionary inventory — baseline 42c72bd6

2026-10-07. Read-only production worktree:
`/tmp/opencode/docatlas-final-exit-inventory-42c72bd6`, HEAD
`42c72bd6d37700b6fe04890c25e8c4ac45bc9e57`.
**Full EXIT не подтверждён. Есть callable residuals, default effects и отдельный
Packs safety-credit repro.** Primary не читался/не менялся. Единственный новый
artifact этого child — этот отчёт; parent переносит его только после review.

## 0. Границы и как читать inventory

Прочитаны REMAINING_DICTIONARY_AUDIT_RU.md, CORPUS_POLICY_DICTIONARY_EXIT_RU.md,
IDENTITY_ADMISSION_PARALLEL_RU.md, DELIVERED_SURFACES_DICTIONARY_EXIT_RU.md,
READ_TAILS_DICTIONARY_EXIT_RU.md и PARALLEL_REMAINING_EXIT_RU.md. Старые списки
adc9abf8 не являются current inventory: compiler/proof/recovery cleanup уже
интегрирован. Проверены определения, найденные вызовы и guards на 42c72bd6,
не только imports. Дополнительно выполнены repository-wide regex/wordlist scans
`docmancer/**/*.py`, AST scan literal collections, templates/root SKILL и scripts.
Это source/caller inventory, не full runtime trace, indexed corpus audit или
сертификат отсутствия любой внешней SDK интеграции.

- **DEFAULT-CONDITIONAL**: найден edge от обычного read, эффект зависит от данных.
- **CALLABLE**: direct/advanced/CLI helper выполняется; default delivery отдельно.
- **DORMANT**: найденный default producer/guard исключает эффект. Direct invocation
  ещё возможен. UNKNOWN runtime frequency/external callers не превращается в EXIT.
- **Positive credit** ниже означает конкретный effect: allow, score, inferred
  obligation/edge/label/retained span, lexical attribution или отсутствие veto.
  Не каждый такой эффект является answer/edit authorization.
- Для negative-only detector честно указан negative effect и отсутствие positive
  authority repro. Не выдавать отрицательный guard за semantic proof bypass.

**ALLOCATED, не повторно implement/review:** corpus worker — `agent.py`, fetchers,
network/target fields и exact finite membership propagation; local worker —
`docs/domain/source_map.py`, `docs/domain/project_state.py`. Их текущие незавершённые
diffs не прочитаны. Здесь baseline references, не approval результата workers.
Source-map suffix priority и project-state `architecture` fallback остаются в их
allocation, не назначать residual implementer эти файлы.

## 1. Приоритетные nonowned residuals: действие и воспроизводимый credit

Пути в этой секции относительны корню worktree. Для коротких названий ниже
`A/` = `docmancer/docs/application/`, `D/` = `docmancer/docs/domain/`.

### P0 / R1. Packs HTTP path-name снимает destructive gate

**Файл:** `docmancer/mcp/registry.py:594–606`, `_derive_safety`.
`/search`, `/query`, `/list`, `/find` в path превращают POST/PUT/PATCH/DELETE в
`destructive=False`. Это смысл названия endpoint, НЕ HTTP grammar.

**Call chain:** local OpenAPI compilation `registry.py:311` записывает safety;
installer `_operation_grants` и dispatcher `:177` передают grant;
`mcp/safety.py:15–42` допускает operation, если destructive flag False.
Это Packs lane, не default Docs MCP `get_docs_context`. Transport invocation
не проверялся и не исполнялся; grant/credentials/network guards отдельно остаются.

**Executed offline repro:**
`check(package='p', operation={'id':'delete','safety':_derive_safety(
{'method':'DELETE','path':'/search/all'})}, allow_destructive=False,
has_credentials=False)` → `GateResult(allowed=True)`.
Тот же DELETE `/records/all` → `destructive_call_blocked`. Positive gate credit
доказан, реальный destructive HTTP request НЕ заявлен.

**Можно убрать сейчас fail-closed:** удалить только path exemption. Сохранить
HTTP-method conservative destructive classification, auth/rate/idempotence DTO,
operation-specific grants и network policy. Не вводить новые aliases/heuristic
endpoint descriptions, не делать missing safety permissive. Exact override fields
не расширять в этом slice. Это первый residual allocation.

### P1 / R2. Modality выбирает сохранение source span в обычном read

**Файлы:** `A/_docs_context_projection_core.py:60,718,803–873`;
`D/normative_language.py:11–27,96–110`.
`_expand_selected_snippets` в default `project_docs_context` использует EN
must/required/shall/invariant/only-after и forbidden vocabulary для `preserve_span`.
Затем удерживает старый span при refocus/expansion либо veto-ит expansion.
Это **DEFAULT-CONDITIONAL window selection**, не positive proposition proof.

**Concrete executed discriminator:** `_REQUIRED_RE.search('RelayClient must retry')`
и `_FORBIDDEN_RE.search('RelayClient must not retry')` оба True; bare
`RelayClient retries` не получает этот vocabulary bonus. Actual executable
branch `:828–842` делает keyword-triggered retained interval, затем requalification,
assignment, query coverage и token guards `:848–871`. Полный final-envelope
дифф этого branch не воспроизводился; не утверждать unconditional delivery.

**Remove now:** убрать NL predicate/import именно из preservation decision;
сохранить exact-term witnesses, explicit assignments, existing span/hash/budget
guards. Лучше одинаково сохранять уже выбранный authenticated span независимо
от wording, в пределах прежнего budget, чем терять negation/quoted condition.
Не переносить must/never в ranking/config/prompts. `normative_language.py` удалять
только после R3: у него другие реальные callers.

### P1 / R3. Action packet ещё классифицирует prose как policy/behavior

**Файлы:** `D/normative_language.py`; `A/_action_packet_shared.py:22–25,42–50`;
`A/_action_packet_part01.py:198,709–760,831–861`;
`A/_action_packet_part02.py:7–45,86–97,132–145`;
`A/_action_packet_part03.py` (consumer `_extract_facts`);
`A/action_packet.py:189`.

**Actual chain:** `build_action_packet` → `_extract_facts` → modality →
required_invariants/forbidden_changes; `_critical_fact_count`, ranking and
`_policy_witness_survived` reuse these facts. `_has_behavioral_contract` and
`action_packet.py:189` reuse modality in readiness. Source/trust guards and
negative mutation readiness are separate; cited prose classification не доказывает
mutation authorization. Это advanced/direct action packet, НЕ автоматически
default public docs surface.

**Executed positives:**
`classify_normative_modality('RelayClient.timeout means unlimited retries.')`
→ `required` (definition wording becomes normative).
`_extract_facts('RelayClient must retry.\nRelayClient must not retry.\npytest')`
→ required, forbidden, validation rows, omitted=0.
`_constraint_signature('RelayClient must retry') ==
_constraint_signature('RelayClient must not retry')` → True. Это NL removal
dictionary, используется conflict detector, не literal policy identity.

Дополнительный executed consumer repro: packet source_of_truth
`{evidence_id:'e', path:'RULES.md', authority:'canonical'}`, implementation_guidance
`{text:'RelayClient must retry.', evidence_ids:['e']}`, explicit public requirement
`{kind:'source_fact', proof_role:'project_rule', source_path:'RULES.md'}` →
`_promote_trusted_behavioral_witnesses` переносит row в required_invariants,
implementation_guidance становится пустым. Это конкретный positive category credit
от modality в настоящем consumer; не source authentication и не edit grant.

**Remove now fail-closed:** unknown modality/behavior from prose, no synthesized
required/forbidden fact categories; source quote can remain untyped cited data.
Оставить explicit structured task/target contract и source bytes. Нельзя заменить
removed behavioral detector на `bool(rows)` и тем самым grant readiness; unclear
behavior remains unresolved. `_constraint_signature` conflict removal требует
unknown/manual-review outcome, не пустого conflict set как доказательства harmony.

**Technical/decision split:** `_VALIDATION_START_RE` и `_validation_bucket`
содержат точные command families (`pytest`, `cargo test`, etc.) и запрещают shell
metacharacters. Это bounded command recognizer, но присвоение runnable validation
смысла/compile-vs-tests bucket не authentication и не execution permission.
Сохранить parser/metacharacter guards; если требуется ноль inferred command intent,
не распознавать `run pytest` из prose — unknown/manual, exact explicit command
может остаться source data. Не удалять safety regex ради dictionary count.

### P1 / R4. Selector normalization, qualifiers, polarity и conflicts

**Exact files:** `A/evidence_candidates.py:24–46,85–102,145–165`;
`A/_evidence_selection_shared.py:65–91` (unused duplicate tables);
`A/_evidence_selection_part02.py:136–184,230–236,439–455`;
`A/_evidence_selection_part03.py:230,356`.

1. `_PATCH_FACT_RE` → `projected_text(...,'patch_context')` selectively adds
   lines with must/shall/pytest/etc. Repro with snippet `neutral`, content
   `alpha\nRelayClient must run pytest\nomega`, path RULES.md → projected
   `neutral\nRelayClient must run pytest\nRULES.md`; alpha/omega absent.
   CALLABLE patch selection/cost/content effect, docs_answer early returns raw.
2. `_QUALIFIER_PATTERNS` → `observed_qualifiers` → assignment `:356`.
   Repro `Proposed, not yet implemented, deprecated if required approval is required.`
   → six tags: conditional, confirmation_required, deprecated, negated,
   not_implemented, proposed. This is inferred semantic annotation; not proof.
   Explicit supplied `requirement.qualifiers` separate (and witness rejects them).
3. `_policy_polarity` → dedup exception; `_authority_conflicts` scans canonical
   display_text and removes must/not/be words. Repro normalize two canonical
   docs `RelayClient must retry` / `RelayClient must not retry` → polarity
   required/forbidden, conflict `{'relayclient retry'}`.
   CALLABLE select_evidence execution; actual result uses conflict veto.
   No positive support bypass reproduced: docs_answer `part03:369+` stays
   insufficient/context-only. Cannot clear veto and claim policy supported.
4. `requirement_value_visible('RelayClient','relay_client')` → True without
   explicit alias. Callers: action packet witness/scoring and library bounded
   RST selection `_library_docs_service_shared.py:249`. Camel→snake shape rule
   is inferred identifier equivalence, not a thematic wordlist; **technical
   spelling exemption is explicitly UNCERTAIN**, it must not be assumed exact
   identity proof. Remove derived variant now (literal-only), leaving DTO/API.

**Removal:** empty inferred qualifier output; use exact authenticated spans rather
than NL patch-fact selection. For dedup preserve semantically different bytes
without polarity dictionary (do not merge contradictory quotes merely because
NL veto removed). For conflict certainty return unresolved/manual when no
explicit conflict contract exists, not positive no-conflict authorization.
Remove duplicate tables in shared module too, not only currently active copy.
Source class, authority/version *supplied enum normalization*, hashes, stable child,
parent IDs, source/path scopes and rank tuple contracts remain technical.

### P1 / R5. Qualification still grants morphology-derived retrieval credit

**Exact files:** `D/technical_tokens.py:7–17`;
`D/evidence_qualification.py:528–543`; dormant comparison helpers `:115–148`;
anonymous relation-negation branch `:347–359`.

**Default chain:** project read/requalification → `qualify_evidence` →
`_visible_term_present` → suffix `s/es/ed/ing` and consonant-y rewrite.
Executed query-original authoritative query `retry`, body `retried` (terms retry,
original/direct protocol) → qualified=True, covered_query_ids=('query-original',),
context_only=True. This is **real lexical retrieval attribution**, NOT proof that
retried answers retry. General morphology is language equivalence, not exact
code-symbol grammar. Ordinary literal token matching is not itself a semantic
dictionary and can remain. Changing morphology may reduce recall; no floors waived.

**Remove now:** literal nonexact boundary matching, no suffix/stem canonicalization;
retain technical identifier boundaries. `_general_relation_is_locally_bound`
contains whereas/differs/rather-than/negation rules but no found caller: remove
dormant helper semantics too. `_visible_comparison_relation` already False.
Anonymous `query-relation-a` probe `RelayClient not enabled`, query_terms RelayClient,
body `RelayClient is enabled.` → negative `missing_visible_relation_negation`;
body `RelayClient is not enabled.` → qualified=True BUT covered_query_ids=().
Public original/direct mismatched relation ID is rejected BEFORE this branch.
Thus remaining not/without/never/no rules are CALLABLE diagnostic veto, not
default public semantic credit. Replace obsolete relation lane with negative
compatibility result, not unconditional qualify. Preserve policy rejection guards.

### P2 / R6. Source dependency graph still guesses NL ownership/causes

**Exact file:** `D/source_dependency_graph.py:12–16,37–49,63–64,118–129`.
Subject verb vocabulary, It/This noun list, causal verbs, conjunction ambiguity
veto and Examples/Aliases list exclusion. Source-local/hash-correct != technical
grammar for natural-language entailment.

**Actual edge:** `A/source_reference_evidence.py:171–172` →
`A/source_dependency_preparation.py:37` → `D/evidence_set_validation.py:93,130`
→ source_graph; need_context_projection also reads graph lists. Prepared source
bytes/current catalog/hops/spans guards apply. These helpers can alter bundles
and dependency validation even with no accepted semantic needs; inferred edges
are proposals, not answers. Default final legacy need lane remains rejected;
actual public delivery of an anaphora bundle UNKNOWN, not asserted from imports.

**Executed positive:** SourceKey(ScopeKey('p','v','s'),'d','a.md',digest(raw)), raw
`# H\n\nRelayClient handles work.\n\nIt retries.\n` → anaphora edge.
Replace last paragraph with `This rule prevents failure.` → anaphora AND cause.
`Items:\n- Examples:\n- alpha\n- beta\n` → only TWO list members; label line
is excluded by semantic list rule. These are concrete graph/set-shape credits.

**Remove now:** NL subject/anaphora/cause/definition inference and Examples/Aliases
exclusion. Keep Markdown headings/list/table syntax, exact SpanRef/hash/source
validation, complete-list sibling closure, cache keys and ≤2 hops/≤8 spans.
Do not interpret deleted dependency as proof of independence; keep unknown where
an answer contract actually requires NL relation completeness.

### P2 / R7. Retrieval need support residual state/behavior/requirement/exception

**Exact file:** `A/retrieval_need_support.py:24–79,103–112`.
if/when + enabled/disabled/not-enabled canonicalization; count/number/many;
must/required/need relations; exception→unnamed `raise` and `exception` subjects.
These are inference dictionaries, not relation DTO enums or Python syntax.

**Executed positives (proposal only):** `_need_obligations` for relation exception,
subject RelayClient → subjects raise/exception with code value_kind; requirement
text `how many RelayClient calls` → number + three relation obligations; behavior
text `when FeatureFlag is disabled` → FeatureFlag/disabled and FeatureFlag/not enabled.
`_state_condition({'text':'if FeatureFlag is not enabled'})` normalizes two aliases.

**Guard/caller classification:** only actual found call of adapter is its own
`apply_retrieval_need_witness:143`; production imports in project docs/projection
are not calls. `extract_answer_units` emits proposition=False; filtered units
`:94–97` empty, all three direct witness probes returned False, not True.
Default local witness unknown also vetoes inherited credit. **DORMANT default,
CALLABLE proposal effect, NO current positive support/edit repro.** Consequent
regex at :107 is behind match guard; no live default effect established.

**Remove now:** no NL obligations, unknown/negative typed witnesses for these
legacy relations; preserve original direct default hook call, input immutability,
non-need passthrough, cleanup of inherited metadata and fresh-witness-only adapter.
Do not restore removed passthrough to fix the preserved red below.

### P2 / R8. Code graph reference-intent boost is still topical

**Exact file:** `D/_code_graph_part02.py:57,99–100,452–454`.
`использ`, usage/used/uses/use/reference(s) → +7 `reference_intent_match`.
Actual `score_code_graph_file` → context items → advanced code/source callers;
ordinary docs route has use_source_evidence=False. Gap/source effects depend
on local worker callers; this file is NOT source_map/project_state allocation.

**Executed positive:** one parser-confidence references edge symbol RelayClient,
file a.py → b.py: question RelayClient score=2.5; `use RelayClient` score=9.5.
Only changed credit is `reference_intent_match:+7.0`. Remove NL detector/boost;
keep parsed edges, exact terms, confidence, syntax/resolved imports and budgets.

### P2 / R9. Library query list grammar and UI-prose cleanup

**Exact files:** `A/_library_docs_service_shared.py:81–106,113–152,311`;
`A/_library_docs_service_part03.py:455–486,565–569`.
what-do/explain/meaning/semantics/describe + symbol nouns, and/or/plus separators,
mean/when/while termination. Repro `explain foo_bar and baz_qux` → inferred
public requirements `['baz_qux','foo_bar']`; `explain foo and bar` → unqualified=True,
then caller deletes all chunks. This is **CALLABLE library read requirement/veto**,
not explicit supplied requirement list. Unified dependency/library path can use
this read; runtime frequency not measured. This grammar is not protocol schema.

`_clean_library_section('copy\ntranslation\ntranslated by someone\nreal statement')`
→ `real statement`. `_NOISE_LINES` and translation-prefix list delete source prose
before library reranking; syntactic ¶/emoji filtering separate.

Remove NL requirement/list inference and text-label deletion; original topic and
explicit requirement contract remain. Do not treat unknown plain list as parsed
complete request. Keep RST directives/module/function/class syntax and literal
source symbols, exact version/source contamination guards, token budget/MMR.
No topic→scope replacement. Old refresh/rephrase next_actions strings are guidance
debt (not proof or automatic tool execution): replace with bounded inspection,
only returned action/explicit lifecycle authorization permits preparation.

### P3 / R10. Callable dormant dictionaries remaining in legacy helpers

**Exact files:** `D/_project_answer_contract_shared.py:48–53`;
`D/_project_answer_contract_part01.py:215–224`;
`D/patch_request_plan.py:21–39,52–54,128–136,207–349`;
`D/legacy_question_coverage.py` (whole old NL detector implementation).

- `_cardinality('two tools')` and `_cardinality('два инструмента')` → 2.
  No found producer call to helper; build_project_answer_contract empty-literal
  DTO does not use it. NL numeric words are not JSON numeric grammar. Can retain
  explicit digits with existing ≤32 bound, remove number word table.
- `build_patch_request_plan('delete lib/a.py').operation` → none because
  find_change_clause disabled; `_operation('delete')` direct → delete. Preserve/
  acceptance/rename NL branches are unreachable through current entry, but old
  dictionaries remain code. Remove these grammar branches behind compatibility
  negative adapter; keep PatchRequestPlan DTO, literal spans/path/target grammar,
  explicit structured mutation inputs and unchanged authorization guards.
- `legacy_coverage_gaps('How does exact-term recall improve without widening
  authority?', rows with relations recall_mechanism + authority_invariant)` → ().
  This is hardcoded approved-question exception, actual absence-of-gap credit;
  no found production caller anywhere in docmancer. Other EN/RU stop tokens,
  purpose/usage/comparison/condition/list/frame detectors are also callable
  negative compatibility. Make unknown legacy coverage explicitly unresolved,
  do not delete veto into empty success. Frozen question registries/tests untouched.

`D/_answer_units_shared.py:53–58` negation words and
`D/_answer_units_part02.py:44–46,82–89` negative-only compatibility helpers also
remain; no found active proof caller. Remove dormant NL detectors or keep negative
adapter; do NOT reinterpret negation absence as positive proof. Current strict
typed key/value equality, exact subject_kind/value_kind DTO and source hashes stay.

`A/model_visible_projection.py:62–77,1005–1043` actionable question/snippet regex:
direct `_needs_actionable_limitation('How do I configure RelayClient?',
'RelayClient works.')` True; answer `configure RelayClient to fast` → False.
No found caller of `_answer_text` in production. DORMANT public effect, callable
limitation exemption; remove NL actionability inference without re-enabling answer
approval. Keep quote/source materialization and hard budgets. This is not current
default supported answer proof.

## 2. Corpus/default membership: не назвать technical и не silently расширять

### R11 — local source boundary defaults (nonowned)

`D/source_boundary.py:14–23,159–179` executes in bounded source traversal.
`_PACKAGE_AND_TOOL_DIRS`: compiler caches/vendor paths смешаны с `archive-v0`.
Generated dir `generated/gen` and suffix markers approximate artifact identity,
not authenticated source fields. **Classification MIXED/UNCERTAIN**, not NL
query semantics, but genuinely default corpus membership dictionaries.
Pure executed predicates: archive-v0/vendor excluded=True; src=False;
gen/a.py and generated/a.py generated=True, src/a.py=False.

Deleting these guards admits previously excluded files; explicit include_generated
does not override package/tool exclusions. **BLOCKED for permissive removal** until
explicit bounded local file membership decision. Alternative fail-closed removal
is to disable automatic scanning without exact configured membership, but this is
a functional contract decision, not invisible technical cleanup. Preserve symlink,
root/resolve/gitignore/exclude_paths/extension/byte/time/depth/file ceilings.
No relocation to prompts/config of the same guessed classes. Local worker is only
source_map/project_state; source_boundary needs separate allocation AFTER decision.

### R12 — project discovery / selection / advanced scan defaults

- `docmancer/docs/project.py:44–76,378–420`: ROOT_DOC_FILES, DOC_DIRECTORIES,
  MODULE_ROOT_DIRECTORIES/LIB_MODULE_ROOT_DIRECTORIES choose docs and assign
  filename/directory reasons; bounded scan prioritizes these sets. README and
  architecture include, arbitrary sibling basename/directory may not. Real local
  discover_docs edge; **source membership/topic layout guesses, not NL question
  aliases**. Exact catalog paths/roles are separate source-selection authorization.
- `D/project_doc_ranking.py:36–84,195–198`: evaluation/planning/history filename
  and directory deny lanes; research/dogfood/patch-review labels become risk flags.
  Executed source_lane_allowed roadmap/a.md=False, docs/a.md=True;
  docs/research/a.md gets research_artifact (source lane itself True).
  Default reranking/trust consumers exist. Deleting lane denials expands selection;
  labels can be opaque restriction debt, cannot become technical authority proof.
- `A/_patch_constraints_service_part01.py:116–171` and
  `A/_patch_constraints_service_shared.py:65–69`: README/CONTRIBUTING/ARCHITECTURE/
  ADR/docs glob candidates plus ARCHITECTURE_DOC_RE/doc-directory gate.
  Advanced visible-source membership, not prose proof (extractors now negative).
- `A/_patch_review_service_part02.py:420,432,486` fixed
  docs/research/docatlas-dogfood demotion/bucket is source-prefix policy, not NL
  semantic certification. Review ranking/bucket known explicit type enums remain.

**All membership/restriction removal BLOCKED pending explicit source contract**:
don't replace with whole-repo traversal or unbounded source set. Corpus worker's
finite remote URLs/files do NOT implicitly authorize a different local source
corpus. Fail-closed no-default-discovery could eliminate guessed selectors, but
requires owner decision on lost availability. Keep explicit catalog membership,
source dimensions/version/snapshot/hash, instruction trust and scope verification.
These are not a request to rewrite production config or current indexed corpus.

### ALLOCATED remote corpus/discovery tail (handoff boundary, not duplicate work)

Previous exclusions/locales/GitHub defaults in filtering/github and fetcher source
expansion belong to corpus worker. Discovery path boosts/stopwords and seed guide
preferences were removed in prior slices; don't resurrect them from old reports.
Explicit library/package/ecosystem identity→declared URL maps are not NL topics.
Exact finite selection must not remove their identity/version/provenance guards.

Adjacent **baseline remaining NL label ranking**:
`A/library_source_discovery.py:172–200`, `_python_candidates` uses
documentation/docs/reference/home/homepage labels → priority and confidence.
Executed registry payload project_urls Reference https://example.org/a / Other
https://example.org/b → high then medium confidence. Both actual evidence decisions
remain confirm, authority/version unconfirmed, requires_confirmation=True; no
automatic fetch approval. Actual `discover_library_sources` registry edge requires
network policy; no network was called here. Remove label bonus with deterministic
explicit URL order, preserve registry coordinate identity and confirmation.
**Ask corpus owner to cover this adjacent function or transfer ONLY this file**;
never concurrently edit discovery/network orchestration. `_flutter_targets_for_request`
in library service part02 (`:135–176`) is explicit identity/host → targets mapping,
not NL topic seed list; finite-contract boundary is corpus-owner integration, not
license to replace version or widen roots. Any exemption beyond exact supplied
identity/path remains explicitly uncertain and owner-reviewed.

## 3. Technical tables / already negative surfaces — не повторять закрытый exit

- `D/admission_grammar.py:36–52`: protocol NEW_RELATIONS; canonical_phrase literal;
  ordered_list_spans empty; parse_admission_frame None. `D/admission_relations.py`
  always False,(); admission meaning unknown. No remaining admission wordlist;
  no positive local meaning/equivalence repro. DTO slots/operator/route names keep.
- question_plan/surface/frame/composition/premise/governance and unit proof modules
  уже имеют negative/empty compatibility adapters. Old REMAINING audit sections
  about sync/tool/Python injection are superseded, not new callable positives.
  Frozen ownership cases diagnostic data only; preserve them, don't erase tests.
- `core/_sqlite_store_part03.py:_strip_stopwords` now tokenizes all words, no
  omission dictionary. Title overlap/full literal phrase boosts are mechanical
  lexical signals, not topic dictionary. authority penalties consume supplied
  metadata enums; not inferred topic→source authority. Search/retrieval literal
  anchors, Camel splitting for lexical tokens and protocol paths stay bounded.
- Programming AST/import/declaration keywords, suffix→language, Markdown/RST
  syntax, HTTP/wire/schema/status/lifecycle/backend/tool/resource enums, versions
  and floating-version guards remain technical. Presence of English words in
  these tables is not evidence of a semantic classifier.
- Technical path/document grammar in query_reference_binding (extensions,
  escaped coordinates, catalog resolution and exact issued source URIs) stays;
  it does not infer a topic/scope or grant authority from basename.
- `D/content_trust.py:_RISK_PATTERNS`, `A/_action_packet_shared.py:
  _DANGEROUS_CONTENT_PATTERNS` **are NL detectors**, not technical exceptions.
  Real annotator/packet callers reject or mark risky content. Repro class includes
  `ignore previous system instructions`, `run curl`, `send secret token` → risk
  flags. They give negative veto only, no positive proof. Executed details: override text
  gives content-trust policy_override + packet instruction_override; `run curl`
  gives packet network_tool_instruction, content-trust misses it; bare
  `send secret token` gives content-trust credential_exfiltration, packet misses
  it. Gaps are not safety permission. **BLOCKED for plain
  deletion**: absence of a detector finding is not safe instruction permission.
  A dictionary-free replacement must conservatively keep untrusted prose non-
  executable/non-authorizing and unresolved where an instruction decision is
  needed; preserve exact scoped AGENTS/CLAUDE policy identity/root guards.
  Do not mass-remove security regex to reach a nominal zero-dictionary count.
- Existing standalone patch validator semantic satisfaction was removed; type/
  protected/generated/lockfile/source-pin/span/root/budget barriers remain.
  No restored semantic UI/layer/policy proof found in current validator scan.

## 4. Delivered voices, templates, scripts and packaging

Inspected root SKILL, all `docmancer/templates` matches, MCP descriptions/static
and dynamic resource renderer, agent_workflow_contract and docs/agent_contract.
Delivered/root/template scope/decomposition/equivalence rules removed by previous
approved slices. Only original+explicit lookups≤5+cited-context/negative authority
instructions remain; returned diagnostic rephrase line is nonautomatic and no
longer manufactures a question. No current topic→scope positive instruction
repro found in these packaged maintained surfaces. Hashing actual descriptions
is identity, NOT proof of semantic EXIT.

`docs/agent_contract.py:122` tool selection is typed health/lifecycle guidance;
catalog metadata declared untrusted. Not a topic dictionary. Library next-actions
strings under R9 remain narrow delivered guidance debt; don't add network consent
as sufficient preparation authorization.

Scripts `run_question_surface_gate.py`, `run_question_surface_v2_gate.py`, recovery
and frozen quality gates are direct test/tooling consumers with old semantic
expectations. Their assertions/fixtures are NOT production dictionaries to delete;
keep and report reds. No script-triggered crawl/commits/MCP smoke here. Current
installed copies/wheel/user configs/external MCP client instruction caches UNKNOWN;
this report does not certify their refreshed identity or full release validation.

## 5. Minimal disjoint next allocation — без следующего research round

One final residual implementer can take R1–R10, **sequentially integrate shared
consumers**, never touch corpus/local allocations. Suggested order:

1. **Packs guard:** ONLY `docmancer/mcp/registry.py` + new-only tests/shard/report.
2. **Selector+read+packet shared closure:** exact union of R2–R5 production paths:
   `D/normative_language.py`, `D/technical_tokens.py`, `D/evidence_qualification.py`,
   `A/_docs_context_projection_core.py`, `A/evidence_candidates.py`,
   `A/_evidence_selection_shared.py`, `A/_evidence_selection_part02.py`,
   `A/_evidence_selection_part03.py`, `A/_action_packet_shared.py`,
   `A/_action_packet_part01.py`, `A/_action_packet_part02.py`,
   `A/_action_packet_part03.py`, `A/action_packet.py`.
   No second worker editing any of these common consumers concurrently.
3. **Disjoint callable cleanup:** `D/source_dependency_graph.py`,
   `A/retrieval_need_support.py`, `D/_code_graph_part02.py`,
   `A/_library_docs_service_shared.py`, `A/_library_docs_service_part03.py`,
   `D/_project_answer_contract_shared.py`, `D/_project_answer_contract_part01.py`,
   `D/patch_request_plan.py`, `D/legacy_question_coverage.py`,
   `D/_answer_units_shared.py`, `D/_answer_units_part02.py`,
   `A/model_visible_projection.py`. New-only behavioral tests/shard/report.
   Keep public DTO/function signatures and source equality positives unchanged.
4. **Owner decisions first, not edits:** R11/R12 + negative safety detectors.
   Exact files listed above, separately authorized local membership/opaque-policy
   behavior. Finite remote contract alone doesn't settle these questions.
5. **Corpus-owner transfer only if needed:** library_source_discovery.py label
   bonus. No duplicate fetcher/agent/network/target implementation.

Regression probes per R1–R10 are given above with exact inputs/outputs; implementer
should promote them to NEW negative/positive tests, plus real caller paths and
source/hash/immutability/budget regressions. Do not rewrite old assertions, frozen
gold/corpus/thresholds/manifests. Dictionary removal may reduce lexical retrieval;
quality restoration is separate, without aliases/topic replacement or lowered floors.

## 6. Actual offline run and retained exact red ledger

Normal repository conftest; no `--noconftest`, no production/config edits:

```sh
PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/test_dictionary_exit_*.py \
  tests/docs/test_mcp_token_footprint.py tests/docs/test_mcp_boundary.py \
  tests/docs/test_finalized_mcp_output_integrity.py tests/test_support_surface_policy.py \
  tests/docs/test_target_security.py tests/docs/test_content_trust.py
```

**Actual: 1676 passed / 6 failed / 1 existing multipart warning, 6.20s.**
This chosen technical module set has 14 more passes than the historical final
1662/6 run; not a regression/fix count or full-CI comparison. Exact remaining reds:

1. `tests/test_dictionary_exit_admission_literals.py::test_application_adapter_really_calls_default_hook_but_unknown_is_consumer_debt`
2. `tests/test_dictionary_exit_discovery_literals.py::test_explicit_api_templates_and_package_pages_are_not_topic_tables`
3. `tests/test_dictionary_exit_discovery_literals.py::test_actual_dart_resolver_caller_preserves_root_and_version_provenance`
4. `tests/test_dictionary_exit_discovery_literals.py::test_removed_ecosystem_alias_does_not_expand_caller_target[pub]`
5. `tests/test_dictionary_exit_discovery_literals.py::test_removed_ecosystem_alias_does_not_expand_caller_target[flutter]`
6. `tests/docs/test_mcp_boundary.py::test_patch_constraints_debug_compaction_preserves_contract_fields`

First five are already recorded new contract/test conflicts, sixth preserved MCP
answer_available=True assertion on nonauthorizing packet. **Not waived/not green**.
No rewrites. Self-host quality historical FAIL remains; no new quality run,
stdio transport, release/wheel/indexed-corpus or network acceptance claimed.

Executed extra here-doc probes were in-memory imports/calls with
PYTHONDONTWRITEBYTECODE=1/DOCATLAS_OFFLINE=1. Initial exploratory ScopeKey constructor,
wrong safety helper import and candidate key names caused harness errors, then
corrected and rerun; not hidden passing tests. Predicates/graph/helper outputs
are distinguished above from public final-envelope delivery. Tests write only
normal temporary fixtures, no crawl/network/production artifacts. No commits,
push, subagents or primary changes. Only this new checkpoint is approved scope
for extraction; all implementation/authorization decisions remain with parent.
Final `git status --short`: pre-existing untracked `.venv` плюс только этот новый
checkpoint; tracked production/tests/scripts/config diff отсутствует.
