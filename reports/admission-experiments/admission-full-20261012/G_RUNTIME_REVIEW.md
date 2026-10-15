# G — independent runtime review, interim plus merged40 update

## Decision

**Experimental B1 restores public Q46/Q16 fact delivery and preserves every original direct28 success; not ready for default deployment.** Independently audited assembled direct40: **39/40**, only Q31 incomplete. Old10 remains **10/10**. Cost/irrelevant-source tradeoff is large; old empty-source contract is violated in **four individual negatives**, not merely the two failed pytest items. Host Q46 is source-supported and exactly cited; Q16 answer facts are correct but its citation violates frozen exact-quote criteria. No final claim that prompt alone suffices or a reranker is worth its total cost.

No product/model/pytest calls by G; only completed code diff and saved JSON/text/hash/XML inspection. Original frozen docs oracle unchanged. New independent code oracle frozen in `G_CODE_ORACLE.md` before SWE results for that case.

## Evaluator evidence

- `G_DEFAULT_OFF_AUDIT.json`: independent default-off direct40 facts/source envelope/authority checks.
- `G_B1_CONTROLS_AUDIT.json`: old10 + complete captured six-call family independent facts/source checks and unchanged old negative criteria.
- `G_B1_PARTIAL_AUDIT.json`: first timeout's 24 persisted rows (not a complete40 score).
- `G_RUNTIME_DATA_AUDIT.json`: independently revalidated combined40, exact part equality, generations, all control-ledger before/after source state, selected-source project/line bytes, model diagnostics IDs/ranks/spans and host output hashes.
- `G_HOST_CITATION_AUDIT.json`: actual host-visible original question/public source IDs/text/frozen host prompt and citation checks, plus valid S1/R1 IDs.

These external G artifacts do not replace raw files. Source policy is not awarded universal PASS merely because snippets/hashes are valid. Guard-code review, current native binding and concrete safety controls are complementary; explicitly wrong-version/access/consent denials remain untested here.

## Runner change reviewed: bounded recovery, no oracle change

Full diff of `eval/main_flow_comparison/run_extra40.py` read independently. Current runner SHA-256 **`da6d300518a0f598fcca7a2b5bc96811871bfe27d5428342d49b76d50eccbb84`**.

**APPROVE for documented bounded recovery**: `EXTRA40_SELECTED_IDS` parses integer IDs, requires a nonempty subset of the existing workload IDs and preserves original workload order/questions/facts/lookup variants. No hidden retries, source/provider substitution, benchmark-specific admission rule or frozen file modification. It records selected IDs, updates actual unique-question count and writes every completed row instead of every sixth row. Empty/malformed/out-of-range values fail or leave an empty string equivalent to unset; duplicate requested IDs collapse to one existing ID via set, not duplicate calls. Lookup selection (if enabled) selects both unchanged arms for chosen IDs.

Two bookkeeping limits, not reasons to discard successful evidence: `experiment` label still says “40 unchanged original requests” for a subset, so consumers must use `selected_ids`/actual rows; `Path.write_text` persistence is not atomic if interrupted during writing. Prefer explicit subset experiment label and atomic final rename for future saved-artifact reliability, suggestions only; G did not edit runner. The current recovered artifact parses and matches all merged records exactly. New per-row persistence adds measured evaluation overhead; do not call its change a product latency optimization.

## Default parity and exact source binding

Independently compared all40 live baseline-source B0 with completed-patch default-off outputs, original question/order plus public kind/status/support/authority and ordered source text/path/line/scope/version. **No differing IDs**. Runtime-local project/evidence/envelope identities not compared for equality across isolated projects; each current output's bindings/hashes independently revalidated rather than stripped and assumed valid. `DEFAULT_OFF_PARITY.json` agrees but was not sole oracle.

Default-off controls XML: **10 PASS**, no failures. Raw ledger: **14 prepare + 37 context calls**, matching planned control count. B1 raw ledger: **14 prepare + 36 context calls**; unrelated test aborted after two instead of its normal three reads. Thus B1 does not actually execute 37 control reads merely because the selected tests are the same. All recorded read states have exact `state_before == state_after`, no observation errors. Concrete observed state is generation + all `generation_sources` rows and catalog/source file hashes; not every database table, read capability/cache state or all process/network effects.

Execution receipts for default-off, default-off controls, first B1, recovery B1 and B1 controls independently match all three current product-file hashes and frozen input hashes. This binds same completed product files across these runs; no new commit identity is invented for the uncommitted patch. Stored-source content SHA-256 independently verified against saved content, and every ledger-emitted snippet located inside its independently indexed original file's declared lines under the requested project's locally derived identity.

## B1 delivery: merged evidence, not one uninterrupted run

`B1_COMBINED40.json.results` independently equals **first `live-B1` 24 rows + `live-B1-resume` 16 rows**, exactly IDs11–50 once, unchanged questions/no lookups. The merge is a reporting assembly from **two genuine preparations/generations**, not a single product execution or one initial database snapshot. Observed generations:

- `gen-7cdfd8d72dc74b4391da9f6ba1bd7141`
- `gen-d9b377a9f1a344f8ae92120d6a03e051`

Same-packet project/generation/source identity coherence, full frozen document/hash, raw-reference char spans, emitted snippet/declared lines, canonical public envelope digest and false answer/edit authority independently checked for **every source in all40**. Required facts computed only from frozen source/questions and actual emitted intervals, not producer `audit`. Results: **39 complete**, Q31 only incomplete, **all frozen28 retained**, Q16 and Q46 complete. Q31 remains a gap; neither score nor an aggregate success count repairs it.

First timeout preserved IDs11–34: independently **23/24**, Q31 incomplete. Original lifecycle log has **29 starts / 28 completions / one unmatched start**. Coordinator maps original ordered calls to four completed unpersisted35–38 and interrupted39; lifecycle log itself has no question field, so per-ID mapping uses coordinator execution/order evidence, not a fabricated trace. Recovery repeats four **lost-output** completed calls, not the already persisted24. Count those attempts separately: combined40 reports unique outcomes, not 40 total actual attempted reads. Based on coordinator mapping: **44 completed context attempts + 1 interrupted attempt**, two preparations; retain lost-result latencies/errors rather than treating recovery as free. No best-of selection: merge contains the first persisted results and single recovery result for each missing ID.

Observed sum/median/max of saved40 `elapsed_ms`: **174764.61 / 4369.17 / 8060.72 ms**. Live B0 direct40: **8821.86 / 201.76 / 513.25 ms**; default-off: **8949.44 / 202.13 / 515.35 ms**. These are sums and per-case sample median/max, **not p95**, not whole-process cost or controlled repeated benchmarks. B1 saved-row time is roughly **19.8×** B0 and excludes lost/interrupted work, model loads and host calls. Substantial irrelevant/broad/overlapping sources are visible in B1 old10; completeness improvement is not economical context proof.

## Negatives and public isolation: independent raw outcomes

| Scenario | Default current contract | B1 current contract | Observed B1 result |
|---|---|---|---|
| Ordinary positive logs fact | PASS | PASS | One source; exact source/envelope/fact checked |
| OtherAPI requested delivery/recovery | PASS empty | **FAIL** | Own-owner credentials source, one source, no delivery/recovery relation |
| Compound batch/queue vs batch queue | PASS empty | **FAIL** | One compounds source despite unchanged unrelated/composed negative oracle |
| Setext-heading-only topical match | PASS empty | **FAIL** | One Setext source with generic body; heading presence does not establish requested serialization relation |
| Quantum-channel unrelated task with acquired candidates | PASS empty | **FAIL** | Fixture-store source, one source, unrelated to quantum transport |
| Missing priority7 | PASS empty | PASS empty | Zero sources |
| Missing priority7-9 | PASS empty | PASS empty | Zero sources |
| Missing-topic empty acquisition | PASS empty | PASS empty | Zero sources |

B1 JUnit says **8 PASS / 2 FAIL**, but a failed family's first OtherAPI assertion prevented checking its later compound/Setext assertions. Raw family captured all six outputs before assertions, so independent evaluator detects **three changed family negatives**, plus unrelated = **four** changed individual controls. Keep original assertions and these FAILs, not just the green aggregate or owner's named OtherAPI example.

All B1 negative sources checked against allowed original documents and source envelopes where family snapshots exist; false answer/edit authority is retained. OtherAPI snippet is from its own correct owner, not DeliveryEngine; this is relation relevance failure, not proof of a foreign-source leak. Setext result illustrates that surfacing a substantive generic body plus heading is not the old topical witness; don't relabel it supported serialization evidence.

Scope raw ledger independently confirms all five cases and their **two actual indexed-source positives per case**: project root SharedNeedle and foreign ForeignOnlyAnswer both visible in their respective own project. BackendOnlyAnswer visible with all scope but absent in project scope; module/all-with-module return only backend; foreign question with all scope on primary project has no sources. All returned paths/text/project identities belong to requested project; no observed cross-project/module widening. Scope receipts corroborate JUnit PASS, not only universal emptiness. Stale hash service integration passes its unchanged OriginalNeedle-positive/edit/empty-stale outcome in JUnit; those direct service calls are not captured by public ledger, so independent before/after payload reconstruction for that scenario remains narrower than MCP ledger audit.

Owner explicitly accepts experimental unassessed relevance delivery; the four old negatives remain **CURRENT_CONTRACT FAIL**, not source-supported answers. Their **EXPERIMENT_OUTCOME host refusal/correctness is NOT RUN** at this checkpoint, so no claim that host always filters this risk. No observed authority/state/project-scope violation in the captured cases; universal source-policy PASS remains unjustified.

## Host generation and exact citations

Read raw `messages.json`, `answer.json` and per-call receipts, not B's self-evaluation as oracle. For both B1 generation cases, submitted logical input exactly contains original question + all actual public packet source IDs/snippet text, and frozen `HOST_PROMPT_RU.txt`; no expected answers/private fact spans/diagnostics supplied. Existing alias/transport is ADAPTED stateless client orchestration; provider backend immutable revision, effective temperature/budget, tokens/billing and provider-level retries are not exposed. Report unknowns, not zero.

| Case / arm | Required answer facts | Exact citation/grounding | Task outcome |
|---|---|---|---|
| Q16 B0 | Absent | Honest insufficient, no invented citations | **FAIL original task**, grounded abstention behavior correct |
| Q46 B0 | Absent | Honest insufficient, no invented citations | **FAIL original task**, grounded abstention behavior correct |
| Q16 B1 | **PASS** both completion-only duration_ms/trace_incomplete | **FAIL exact quote** | Semantically correct but strict source-supported acceptance **FAIL** |
| Q46 B1 | **PASS** identical wrong answers do not give PASS, independent checks before parity | **PASS** both IDs and exact citations, no unsupported substantive extra claims | **PASS** this source-supported answer |

Q16 quote emitted by host:

> Поля: `interface`, `operation`, `status`; завершение содержит `duration_ms` и `trace_incomplete`.

Original source has a newline and two spaces between `duration_ms` and `и`: quote is **not** a continuous exact substring of delivered snippet or corpus. It matches after whitespace normalization, but frozen contract did not permit this; do not silently weaken criterion, repair output or retry to get PASS. Q46 two quotes are actual continuous source substrings under supplied IDs and support denial/independent correctness/logs-not-oracle relations.

S1 Q16/Q46 return sufficient=true with valid IDs; this agrees with independently sufficient public fact packets but does not fix Q16 citation correctness or become a new veto. R1 orders full actual B1 packets (10 sources Q16, 7 Q46), valid complete permutations/useful IDs. This is **ADAPTED public-packet client orchestration**, not author RankGPT reproduction and not reranking the archived native21 pool. Do not rank R1 quality against C/D/E as identical-pool experiment. No R1-selected-packet generator outcome provided; ranking labels are diagnostic, not G final PASS.

## Diagnostic compact model executions: independent bounds and checks

Independently matched candidate IDs/window spans/text SHA-256 to current-head archived native member pools and recomputed ranks from saved scores. Models did execute, but these runs are **saved-pool offline diagnostics**, not public integration of their selection/pruning path.

| Method | Saved execution / independent useful-fact rank | Limit |
|---|---|---|
| mMARCO mMiniLMv2 canonical FP32 CPU | 21 forwards; Q16 11 candidates, Q46 10; useful window rank1 in both | Uncalibrated threshold=null; no public selection/host outcome |
| Qwen3-Reranker canonical BF16 CPU | 21 forwards; same native21 IDs; useful rank1 both | yes/no logit difference not probability; no calibrated relevance-negative experiment |
| XProvence R5/P1 FP32 CPU | 21 joint forwards; useful rank1 both; P1 retains Q16 `[1110,1313)` containing required `[1152,1209)`, Q46 exactly `[6952,6996)` | Exact-source adaptation; no public pruned packet/host outcome or net benefit proved |
| CRAG released evaluator FP32 CPU | **17/21 scored**; Q46 useful rank2 among8 scored; Q16 useful 746 tokens **not scored** | Four oversize pairs skipped, no silent truncation; groups INCOMPLETE_NOT_CLASSIFIED, full CRAG correction/web/refinement/generation NOT RUN |

For XProvence every saved retained/dropped raw interval independently reconstructs original Unicode text/hash, exact UTF-8 offsets where supplied, and partitions the original windows without gaps/overlap. Retained mandatory facts survive in these diagnostic two cases. Decoded flattened compression is **not** treated as exact quote (Q16 decoded spacing differs); only original retained spans may be delivered/cited. This does not prove neighboring conditions/permissions or admitted whole-window lineage preserved for general pruning; real source wrapper/current-contract review still needed. No top-k selection inferred where scores/order alone were saved.

CRAG receipt status independently matches partial scores and oversize omission; PopQA released thresholds are not DocAtlas-calibrated. Model downloaded-byte snapshot is not an author immutable checksum. No full-pool or corrective-algorithm reproduction claimed. No host answers for compact model branches provided here, so useful rank1 is not counted as source-supported task success.

## Frozen code smoke and pending final evidence

`G_CODE_ORACLE.md` independently verifies the actual baseline `_tab_fixture` source, three unchanged Dart listing copies, reference SHA-256 and exact method/default/assignment spans. Require both notifier arguments plus controller assignment and initial web; no app/code-edit/runtime effect inferred. Narrow Dart synthetic smoke separate from docs40 and SWE-Bench. Runtime/code-pruning/host outcomes **PENDING**, no result inspected before freeze.

Still pending: compact-method selected/pruned actual public packets and matched host outcomes/net costs; negative-host source-supported refusal; compression/code smoke; final accounting of lost/recovery work and actual model-visible inputs; holdout if generalization is claimed. No need to rerun already independently audited default or first24. G's conclusion is improved bounded delivery with demonstrated contract/cost/citation tradeoffs, not production recommendation or universal host sufficiency.
