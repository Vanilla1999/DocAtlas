# G — independent frozen oracle (2026-10-12)

## Freeze boundary

Initial criteria frozen after reading the full protocol, AGENTS.md, q46-admission STATE and original questions/corpus, **before reading any new implementation patch or method scores**. HEAD independently checked: `4849b8f796d9e3e25e2c49e58562ec6859978411`; branch `fix/main-flow-compact-evidence`; clean worktree. This report owns no repository files. Fresh runtime: **NOT RUN**.

## Immutable obligations from original corpus

- Q46 original: «Можно ли признать PASS, если оба режима логирования дали одинаковый неправильный ответ?» Required fact: **«Одинаковые неправильные ответы не дают PASS.»** Exact corpus character span `[6952,6996)`. Answer must deny PASS, not merely mention logging parity or PASS. Independent correctness in each mode precedes parity.
- Q16 original: «Какая диагностическая информация у события завершения, которой нет в начале запроса?» Required fact at `[1152,1209)`: completion contains **both `duration_ms` and `trace_incomplete`**, distinguished from request start. One field alone is incomplete.
- All original old10 and direct40 questions and their original corpus facts remain unchanged. For direct40 every supplied required span must be delivered; partial span coverage is not complete success. Historical delivery success is not generator-answer correctness.
- Exact source text, permitted source owner/scope/version/access/consent, current hash/generation and original character coordinates must remain valid. Read context does not grant `answer_supported` or `edit_ready` authority. No model score can override source policy.
- Negatives: correct source ownership alone does not establish the requested relation (OtherAPI). Unrelated topics and numeric conditions must not acquire supported answers from incidental anchors. Existing empty-source expectations remain binding until an explicit owner contract decision.
- `CURRENT_CONTRACT` and `EXPERIMENT_OUTCOME` are separate verdicts. Irrelevant sources violate an existing empty-source contract even when the host correctly refuses. Invalid source-policy admission is never an acceptable relevance tradeoff.
- Generator success requires all required facts, preserved negations/conditions/comparisons, evidence IDs and valid exact-source citations, and no unsupported additional claims. A correct answer from memory is not source-supported success. Unavailable generator implies generation/citation correctness **NOT RUN**.

## Pending independent archive/control inspection

The following independent historical inspection does not change the criteria above. No new method scores or implementation patch results were inspected.

## Independent raw archive audit

Inspection used only standard-library JSON, ZIP, text, SHA-256 and XML processing; no product imports. ZIP members were read directly, not trusted via previous reports or extracted summaries. All **three input hashes and six ZIP hashes plus six `head.txt` identities match the manifest**. Archive paths are under `/tmp/opencode/docatlas-review-evidence/`:

| Archive | SHA-256 | Head / run |
|---|---|---|
| `main-flow-fixed-087d4f2.zip` | `afd354a964254e677df60ea954a25c7c0e7a75e8b391aa707f7a2dc34265ec2a` | `087d4f22206cfd3db0b18af4a7c2a96e25ec1cec` / 38161642058 |
| `main-flow-extra40-2bdeabd.zip` | `423fb5154561839a28ad84838975e03f7edd5fdd8aec008b4f7a4c518121fb87` | `2bdeabdc7d355511c6229115e223510f2d43df4e` / 38212644546 |
| `extra40-lookup-f2feacb.zip` | `047854bec0fc3c2f2a96fc36c6a998f74838ca889b36fd6e6356e0b3bb4f50d9` | `f2feacb5d960f26d77c0b6e838eee5e4e7620e53` / 38217522078 |
| `compact-first-f5131e2.zip` | `8f843151a70619069b3ad1ca95bb9200223998c2fb1e9e7390c1fb8cd7ae653b` | `f5131e233c36322a3c47f153515eae0c44b54577` / 38225847479 |
| `compact-second-7bbb65c.zip` | `d22e38b4d67e89b0b903ac09210b97bf72c871ab6875248f5c2b32b22bcc2610` | `7bbb65c95b0f271dacb0546ba1d65b097e10144d` / 38227202274 |
| `docatlas-compact-d8af387.zip` | `aa539f453e108bc0a2b25e5fd8011af528f294f337e39e94ee1092fe966c1485` | `d8af387de507007f2b8c83f04aac78feb9b6760c` / 38227928058 |

For every saved old10/direct40/lookup row available in these ZIPs, I reconstructed emitted snippet ranges from same-call snapshot operands and independently checked: projected-source equality; exact corpus/raw-document and document hash; README path; public project identity vs raw project identity; project scope/unversioned version; nonempty snapshot identity; document ID format; raw char text/span; declared snippet lines; canonical public-envelope SHA-256; false answer/edit authority. Only actual emitted ranges (merging overlap or whitespace-only gaps) receive fact credit. Direct40 questions were compared with original JSON, and spans came from that file rather than the runner's `audit`. No audited source-integrity errors were found. This validates these saved operands, not all storage/access/version states; per-row snapshot ID was not independently recovered from a database.

Independent results:

| Archive phase | old10 | direct40 | short lookup | exact lookup |
|---|---:|---:|---:|---:|
| old10 baseline | 10/10 | absent | absent | absent |
| extra40 baseline | 10/10 | 28/40 | absent | absent |
| paired lookup baseline | 10/10 | absent | 4/12 | 0/12 |
| rejected aggressive compaction | **8/10** | 28/40 | 7/12 | 0/12 |
| intermediate compaction | 10/10 | 28/40 | 7/12 | 0/12 |
| final compaction | 10/10 | 28/40 | 7/12 | 0/12 |

**Frozen retention set (28 IDs):** `12,13,14,15,17,18,19,20,21,23,25,26,27,28,29,30,32,33,35,37,38,40,41,43,45,48,49,50`. Exact same set at original direct baseline and all three compaction phases. Incomplete: `11,16,22,24,31,34,36,39,42,44,46,47`. Final short successes: `16,24,31,34,36,39,47`; exact successes: none. Recovered lookup IDs `31,34,39` are not recovered original questions.

Old10 audit reused its existing independently authored literal-query fact obligations in `tests/test_project_context_quality_v2_protocol.py:274–301`, verified against original corpus. Q10 does not require the unasked project-policy addendum for the article question. The rejected archive loses **Q1 and Q9** under this oracle despite unchanged direct28. Its JUnit has 15 items, 1 failure; the other five archives have 15 items, no failure/error/skip. Therefore integrity/size and an aggregate direct40 score alone cannot establish completeness. These historical losses do **not** prove either current compaction risk below caused a fresh defect.

### Q46/Q16 independently observed boundaries

Final ZIP member `extra40-results.json`, records selected by numeric `.results[].id`. Both have unchanged original questions, `lookup_variant=no_lookup`, `lookup_queries=[]`, public `insufficient_evidence`, no sources, false answer/edit flags and empty validation snapshot.

| ID | Acquired member window | Stable chunk ID | Independently reproduced window SHA-256 |
|---|---|---|---|
| 46 | `[6919,7107)` | `child-aefd3978207191f7af083c7353118c9d422a136d` | `a4999c80a4ff1bd34eb63c5855cca1b7575afe24224a22fd99628cb30c27c9d9` |
| 16 | `[1024,2100)` | `child-f4934d98be2629717870adaf0d8ff223470c5204` | `fca78e50498ae130919876243d2bc8738e13f0f2a6ff6010f2ec5905b2d1ae33` |

Source windows occur at `payload.diagnostics.delivery_observations.returns[0].result.result_windows.items`; qualification at `payload.diagnostics.qualification_outcomes`. Full required spans lie inside the independently hash-reconstructed windows. Window text is reconstructed from frozen corpus; diagnostics here expose coordinates/hash, not delivered public text. Q46 observed canonical qualification matches only `pass`, 1/12, 0.0833; Q16 4/11, 0.3636, matches `события,завершения,в,запроса`. Both rejected for `insufficient_visible_match`, null literal admission, then `delivery=blocked_before_projection`. Q16 qualification visible end is 2098, member window end 2100: distinct observations, neither truncates its required fact.

Public fact delivery is historically **FAIL** for both; current literal-contract violation is **not established**. ADR0003 explicitly requires ordinary two-word or technical-plus-independent-word witnesses. Private receipt ledger and exact internal return-None branch were not recorded. Reports A/B/C were read only after initial oracle freeze, then challenged against raw data/source; their internal cause reconstruction is not an observed runtime trace. Downstream compaction cannot restore a publicly blocked empty packet. `git diff --stat d8af387… HEAD` contains four review documents only; old SHA results remain historical, not fresh HEAD results.

## Exact existing controls, with unchanged negative oracle

1. **OtherAPI/numeric/positive family:** `tests/test_project_context_quality_v2_protocol.py::test_public_partial_context_preserves_short_facts_without_cross_owner_or_numeric_credit` (lines 466–629).
   - OtherAPI original: `How does OtherAPI handle packet delivery during recovery?`. Indexed `docs/owners.md` says `OtherAPI validates session credentials before startup.` under OtherAPI; `Packet delivery resumes after each request.` belongs to DeliveryEngine. Correct own-owner credentials text still does not support delivery/recovery. CURRENT_CONTRACT requires insufficient evidence, **empty sources/context**, false authority. EXPERIMENT_OUTCOME can separately record a correct host refusal plus extra irrelevant sources; that does not turn the old contract green.
   - Numeric: `How are packets delivered with priority 7.`; indexed packet text has no 7. Numeric range: `How are packets delivered with priority 7-9 during concurrent recovery?`; neither condition may be invented or satisfied elsewhere. Existing compound (`batch/queue`, `batch\\queue` vs `batch queue`) and Setext-heading-only negatives remain in the same six-call family, not separate new tests.
   - Positive: `When do logs flow to disk during concurrent checkpoint recovery?` must deliver `Logs flow to disk after each request.` with source/hash/span and false authority. This is partial context, not proof of the unmatched recovery modifier.
   - Final ZIP `pytest/test_public_partial_context_pr0/qualification-review-proof.json`: positive status ok, one source; five negatives insufficient, zero sources. Five stored document hashes independently match saved text. Public indexed positive prevents vacuous always-empty acceptance. Existing code also asserts unchanged generation, stored rows, source files and catalog; saved JUnit records its pass, not an independent reconstruction of final database state.
2. **Unrelated with acquired candidates:** `tests/test_project_context_quality_v2_protocol.py::test_delivery_veto_observer_distinguishes_rejected_candidates_from_empty_acquisition[Как DocAtlas отправляет сообщения через квантовый канал?-True]`. Indexed fixture: `DocAtlas stores fixture records for local inspection.` Correct refusal, no sources/authority; candidate acquisition must be nonempty. Existing paired missing-topic parameter `[zzxqv_missing_fixture_topic_73291-False]` distinguishes empty acquisition. Each parameter makes **three**, not one, public calls: plain, observed, broken-observer; observer diagnostics must not alter results. Saved JUnit verifies execution; it does not archive a raw unrelated payload.
3. **Public source isolation:** `tests/docs/test_host_scope_contract.py::test_public_scope_never_implicitly_widens` (lines 21–109). Minimum meaningful parameters:
   - `[all-None-What constraints apply to `BackendOnlyAnswer`?-packages/backend/README.md]` positive backend visibility;
   - `[project-None-What constraints apply to `BackendOnlyAnswer`?-None]` excludes backend;
   - `[all-None-What constraints apply to `ForeignOnlyAnswer`?-None]` excludes foreign project.
   In each parameter, two real project preparations, then root SharedNeedle and foreign ForeignOnlyAnswer positive public reads before the actual tested read. Thus negative results cannot pass merely because foreign data is unindexed. Existing module/all-with-module parameters additionally constrain paths to backend. Preserve all five when using the already selected workflow. Hash/span oracle above is complementary, not a substitute for isolation.
4. **Stale hash public service read:** `tests/test_docs_service.py::test_get_project_docs_never_returns_hash_mismatched_stale_content`: positive OriginalNeedle read, edit file, second read must be empty and stale reason `content_hash_changed`. Real service boundary, **not** public MCP wrong-version/consent/access proof. `tests/test_retrieval_features.py::test_lexical_and_supplemental_paths_enforce_forbidden_sources` is complementary real retrieval/store filtering, not MCP admission evidence.

No existing oracle above may be silently changed for B1. Preserve source policy independently of topical veto: scope/version/hash/owner/native receipts/catalog/generation/consent/access and final exact-source validation remain mandatory.

## Reusable harness and bounded smoke proposal (NOT RUN)

Use `eval/evidence_quality_v2/runtime.py::{write_project,isolated_service,index_project}` and existing `scripts/run_project_docs_self_host_gate.py::_call_with_snapshot` observation around real `call_docs_tool_payload("get_docs_context",…)`. `index_project` executes genuine confirmed public `prepare_docs`, not mocked indexing. Environment patching isolates host state; retrieval/selection/storage/validation are real. In-process dispatcher/SQLite is **not** installed stdio/client/provider/production proof.

Canonical existing direct workload: `eval/main_flow_comparison/run_extra40.py`, **1 preparation + 40 direct reads**, contains Q46 and Q16 unchanged. Existing assertions only prohibit runtime/source-integrity errors; missing facts do not fail it. Independent acceptance must explicitly check Q46/Q16 facts, old10 and all direct28 IDs, envelope digest/authority, negatives and read-only state. Q16 FAIL must remain visible even if coordinator chooses a Q46-only minimum-improvement gate; claiming Q16 recovery requires its complete fact.

Smallest conceptual admission smoke: two original reads Q46/Q16, six-call partial family, one unrelated acquired-candidate parameter (three calls), and three scope parameters above (nine calls). **20 public context calls + 9 preparations = 29 public calls**, no retries/lookups. Each scope parameter independently prepares both projects. Stale-hash companion adds two public service reads and its fixture setup, counted separately. This smoke count is a proposal, not an already runnable subset flag: current extra40 runner supports all40 or lookup24, not an ID filter. Do not improvise local execution or private helper replay to realize two calls.

Under the unmodified executable runner, same smoke controls plus full direct40 cost **58 context calls + 9 preparations = 67 public calls**, before the stale-hash companion. Prefer the existing authorized `.github/workflows/main-flow-context-review.yml` as one combined smoke/regression run, rather than separately executing overlapping slices. Its exact selectors include the entire protocol file, entire scope file and stale-hash test. It already performs old10 (1+10), direct40 (1+40), paired lookup24 (1+24): **3 prepare + 74 context calls for these question groups alone**, not the complete workflow call count. Other controls/CLI/subprocess calls must be itemized, not hidden behind 15 pytest items. Workflow checks out PR head, trigger filters PR **base** branches; coordinator verifies eligibility and exact-SHA artifacts. G does not run CI.

If mechanism affects mixed lookup projection, reuse existing paired lookup arm separately; no original credit or hidden retries. If one workflow already runs both arms, do not rerun smoke unnecessarily. Method-inference calls and generator calls require separate approval, fixed prompts/model revisions and equal budgets; none performed here.

## Compaction risks: independently inspected code, historical limits

- **Adjacent unordered-item dependency:** `joint_context_candidates.py:118–124` splits same-indent siblings; `:143–153` closes intersecting atoms and omits containing-section alternatives when all substantive blocks are `list_item`. Two sibling bullets can state a permission then a limiting exception. The comment that bullet-only sections have no dependency is not semantic proof. `joint_context_selection.py:263–266` cannot favor an omitted alternative. Risk is failure to add an unadmitted sibling, **not demonstrated removal of an admitted occurrence**; original option and lineage preservation remain. Current public semantic defect **UNVERIFIED**.
- **Packet-wide host_lookup gating:** `joint_context_selection.py:151–170,235–250` disables containing sections, intros and seed envelopes for **every** source if any plan query has `origin=host_lookup`. `query_block_context.py:90–96` and `query_block_recovery.py:26–33` also stop packet-wide. This includes original-only attributed sources in mixed requests, not merely lookup sources. A prerequisite beside a direct command may not be expanded. Exact-source and authority guards remain. Public fact-loss and causal attribution **UNVERIFIED**.
- Raw rejected compaction archive actually loses old10 Q1/Q9; final restores both and retains direct28. This is evidence to require completeness before cost optimization, not proof current risks are harmless or already reproduced. Saved lookup arms provide no controlled same-seed counterfactual establishing lookup gating as a causal defect.

**No new public scenario is necessary for the initial admission decision.** If a pruning/mixed-lookup implementation needs to claim dependency preservation, first inspect reused raw stages. Only if existing data cannot exercise the relevant condition authorize one nonfrozen isolated document containing permission plus adjacent prerequisite, real public no-lookup and mixed-lookup requests. Require the prerequisite, unchanged hashes/spans and false authority in both initial outputs; an available read URI is not delivered text. Attribute failure to gating only with same admitted direct seed and excluded valid dependency alternative in raw evidence. Do not clip seeds/mutate private helpers to manufacture a branch.

## Additional frozen evaluation-only probe set

`G_FROZEN_ORACLE.json` contains original Q46/Q16, direct28 and four independently authored pre-result probes: paraphrase, negation, multi-fragment relation and hard negative. Probe expectations come solely from original corpus, and are **evaluator-only**, not model-visible. No provider transmission authorized. These are new question formulations on an already-known corpus, a narrow held-out-question set **not independent unseen-document generalization**. They must remain sealed from prompt/threshold tuning; if disclosed for calibration, relabel them development and do not claim holdout. Optional future probe budget: one shared preparation + four public reads per variant; one generator invocation per case, no retries. Actual runtime remains NOT RUN.

## Handoff / blockers

Before implementation: coordinator freezes allowed variants, host/evaluator prompts and hashes, candidate bounds/calibration split, model revisions/precision, execution/data/provider permissions, budget and explicit relevance-contract delta. B1 must not bypass source-policy veto or silently revoke empty-source negatives. New models/downloads/inference/provider transmission are not approved by tool availability.

After implementation G must review exact diff/SHA, independently validate stage IDs and retained/dropped spans, every old10/direct28 obligation, Q46/Q16 separately, negative payloads/state, actual host-visible inputs/answers/citations and full costs. Auto-judge is auxiliary. No method agent awards its own final PASS. This initial assignment writes only this report and the G-owned JSON; final review is pending a separate permitted assignment.

**Fresh runtime / generation / citation correctness / method comparison: NOT RUN.** No local product execution/import/pytest/AST/install, model/download/provider/CI, nested agents, repository edits, commits or external messages performed.

## Coordinator-supplied current-HEAD archive: independent follow-up

After the initial freeze/report, coordinator supplied already-completed run **38232527945**, saved at `/tmp/opencode/docatlas-review-evidence/admission-full-20261012/current-head-ci/`. This is **saved evidence inspection, not a new runtime or workflow invocation**. The coordinator explicitly says `main-flow-context-review.yml` was not launched in this phase; matching JUnit names do not establish which workflow produced the artifact. Read `CURRENT_HEAD_RECEIPT.json` for navigation, then independently checked the actual records, not its summary as oracle.

`head.txt` matches `4849b8f796d9e3e25e2c49e58562ec6859978411`. Independently calculated SHA-256:

| Raw file relative to `current-head-ci/` | SHA-256 |
|---|---|
| `extra40-results.json` | `8395cc9c62f2f9d1fc3d4a1ca60786b996b6f990c277a8272d28e442118dd285` |
| `extra40-lookup-results.json` | `dc9111799221c3e77ef39c17b7c0bfa6a9ea2fc04c7939fa10f3197774bc821a` |
| `pytest/test_frozen_main_flow_question0/main-flow-proof.json` | `fd1a8938fa2a8b7b8b7848dfa27a807a5774001a4d92957572957192808d14ed` |
| `pytest/test_public_partial_context_pr0/qualification-review-proof.json` | `49d0297364bef7d0e09a62c27bf35dc1c4c617c0ba56d2e1f0ce583a497d6660` |
| `integration.xml` | `d5ddbcfba6806f2ca1f35d4bb537253945206e665163003f30351e4fcdd88ecc` |

First three match coordinator receipt; last two independently recorded here. No ZIP was present in this supplied directory tree, so **current-run ZIP/remote artifact authenticity was not independently established**; local file hashes/head bind the inspected evidence, while run association is coordinator-supplied.

For all 74 question records, independently revalidated same-call raw source text/span, exact snippets and declared lines, public-envelope digest, corpus/document hash, project/path/document identity, unversioned scope and false read-context authority. Independently merged actual emitted ranges for direct40/lookup facts from frozen questions. **Direct28 retention set unchanged; Q46/Q16 still FAIL public fact delivery**. Their complete acquired windows independently reproduce the same window hashes above; both public outputs have zero sources and delivery blocked before projection. Short successes remain `16,24,31,34,36,39,47`; exact lookup successes remain none.

All 10 old-question emitted snippet lists are exactly equal to the independently audited final-compaction old10 snippets; after rechecking current source bindings this transfers the same independent required-fact result **10/10** without trusting current `summary`. Partial-family raw results independently show positive ordinary one source and five empty negatives with false authority; saved stored-source hashes match their saved text. Current JUnit contains the same 15 exact item IDs, zero failures/errors/skips. Scope and stale-hash outcomes have JUnit execution receipts, not separately archived raw public payloads. No host-generation/citation correctness or implementation improvement is demonstrated.

## Integration-only preflight and minimal permissible selector proposal

This section **supersedes any blanket recommendation to run the workflow without selector review**. User no-unit-tests is binding. Classify selected functions by real execution boundary, not filenames, private assertions, or tmp_path. Static source inspection at this HEAD finds:

| Existing selected target | Actual boundary | Decision |
|---|---|---|
| `test_query_trace_off_on_off_preserves_real_sources_and_retrieval_calls` | Real confirmed preparation, public MCP reads/SQLite; observing wrappers call originals; three child processes make real reads plus schema rejections; diagnostic sink failures do not replace retrieval | Integration; permissible, optional logging regression |
| `test_delivery_veto_observer_distinguishes_rejected_candidates_from_empty_acquisition` (two params) | Real public MCP reads against real prepared store; three actual reads per parameter | Integration; keep |
| `test_frozen_main_flow_questions_deliver_source_bound_facts` | Real confirmed prepare + ten public MCP reads and independently bound source/state checks | Integration; keep unchanged |
| `test_public_partial_context_preserves_short_facts_without_cross_owner_or_numeric_credit` | Real confirmed prepare + six public MCP reads, original documents/SQLite/state and independent hashes | Integration; keep unchanged |
| `test_cli_trace_off_on_off_preserves_lexical_fact_and_json` | Real SQLite ingest + three CLI subprocess reads | Integration; permissible, optional CLI/logging regression |
| `test_lexical_and_supplemental_paths_enforce_forbidden_sources` | `RetrievalDispatcher.run` with real `SQLiteStore.add_documents/query`, no FakeProvider/FakeVectorStore instantiated on this lexical path | Component integration, not public MCP; permissible complementary filter control |
| `test_lexical_compact_results_limit_sections_per_source_when_configured` | Real dispatcher + real SQLite population/query, counts section distribution | Component integration, not unit; omit from minimal admission slice as unrelated mechanics |
| `test_expand_bypasses_sections_per_source_cap` | Real dispatcher + SQLite adjacent expansion | Component integration, not unit; omit from minimal admission slice unless expansion changes |
| `test_public_scope_never_implicitly_widens` (five params) | Two real confirmed public preparations per parameter, positive public indexed-source controls, scoped public query | Integration; keep all five for combined regression |
| `test_get_project_docs_never_returns_hash_mismatched_stale_content` | Real confirmed member service sync, SQLite/project file read, edited file, second service read rejects stale hash | Service integration; keep, do not claim public MCP version/access proof |

The three lexical retrieval functions use `_agent` which returns a real `SQLiteStore`, and `_populate` calls actual `store.add_documents`. Stub vector configuration is not an invoked mock on these lexical paths. Their true boundary is component integration. **No selected unit target was demonstrated at this HEAD**, so I cannot honestly propose excluding these three *as unit tests*. Private observer/state/count assertions inside a real integration scenario do not create separate unit execution. This does not bless whole `test_retrieval_features.py`: many neighboring functions instantiate FakeProvider/FakeVectorStore and must not be included by broadening selection.

**Minimal named combined integration-only proposal**, without repository edits or execution:

```text
tests/test_project_context_quality_v2_protocol.py::test_frozen_main_flow_questions_deliver_source_bound_facts
tests/test_project_context_quality_v2_protocol.py::test_public_partial_context_preserves_short_facts_without_cross_owner_or_numeric_credit
tests/test_project_context_quality_v2_protocol.py::test_delivery_veto_observer_distinguishes_rejected_candidates_from_empty_acquisition
tests/docs/test_host_scope_contract.py::test_public_scope_never_implicitly_widens
tests/test_docs_service.py::test_get_project_docs_never_returns_hash_mismatched_stale_content
```

Then reuse **one existing direct40 invocation** (1 prepare + 40 public reads) for Q46/Q16 and exact direct28 retention; no duplicate target calls added to old10. Add existing paired lookup24 only when mixed-lookup mechanism requires it or the coordinator's already authorized combined workflow runs it once. These five pytest selectors expand to ten integration items: one old10, one partial family, two unrelated/empty-acquisition params, five scope params, one stale-hash service control. They make **1+10**, **1+6**, **2+6**, **10+15** prepare/context calls respectively for the first four families: **14 public preparations + 37 public context reads**, plus stale-hash's one confirmed service sync and two service reads. With direct40: **15 public preparations + 77 public context reads = 92 public calls**, plus those three service operations. This is bounded existing-workload accounting, not a claim of runtime performance or provider cost. Keep per-case actual-call receipts in any permitted run.

Optional target additions above are genuine integrations but not needed for first admission acceptance if logging/transport/retrieval mechanics are untouched. Explicit node selectors avoid accidental new unit collection when files evolve. If any true unit target is discovered in a changed selector set, **exclude its exact node ID from the proposed execution only**, do not delete/skip/rewrite the test or call it integration because it has tmp_path. Coordinator must review the authorized execution mechanism/selector permissions before any next run; G has not changed workflow/repo files or launched CI. Existing saved current-HEAD evidence makes an identical baseline rerun unnecessary.

Oracle remains frozen and unchanged. Fresh runtime **NOT RUN**; current-HEAD archived baseline **independently inspected**; generator/citation correctness **NOT RUN**.
