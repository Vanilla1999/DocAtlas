# ABC architectural comparison — decision

Date: 2026-09-19. Runtime/corpus: `95e61265656283d609bc1328c46c52b2bf1a069e`.

## Decision

No tested prototype is accepted as a drop-in production replacement. All lose previously sufficient cases. No main change or merge was performed; PR #194 was not modified by this experiment. Prefer A as the direction for architectural simplification, not as a proven ready patch. Do not add the tested B reranker as a mandatory dependency or continue expanding C until these exposed questions pass.

## Executions and artifacts

- Native/ABC run: 35426507850, artifact 10579161761. ZIP SHA256 `f1d57610d8c80bf07408c0136b8692dd8ab16f0441e255ec630bb981ef1e0ae6`.
- Policy-corrected cached replay: 35427157351, artifact 10578244938. ZIP SHA256 `77d631bd260342d5429cea733389b40e75a3a040f8a96e6fe24d66d59f20755f`.
- 30 fresh native calls reproduced the ordered source path/snippet pairs of all 30 old with-lookup outputs. This is not byte-identity of all metadata.
- 120 experimental payloads were built in each run. Primary results below use the corrected replay, not the first flawed policy adapter.
- All questions and lookup queries were fixed before scoring. Existing G01–G30 is an exposed related development set, not independent holdout and not proof of project-blind generation.

## Arms

R0: native public boundary with the fixed lookups.

A: same normally retrieved pre-window candidate pool, policy checks, source-local block alternatives, one FTS5/BM25 ordering using original question and fixed lookups, greedy packing. No neural model. Automatically derived anchors/relevance vetoes are not replicated as hard restrictions; this is part of the replacement being examined.

B: same pool and packer as A, scoring with one fixed `cross-encoder/ms-marco-MiniLM-L6-v2`, ONNX CPU, max_length 512, batch 16, two threads. Revision `233902d25c440f23af6f7d6e94d2946bac0bee0a`; ONNX SHA256 `5d3e70fd0c9ff14b9b5169a51e957b7a9c74897afd0a35ce4bd318150c1d4d4a`; 91,011,230 bytes. No model/threshold search or fine-tuning.

C0/C1: separate controlled index comparison. Same active indexed children, FTS5, queries, top-20 child cap and A packer. C0 indexes existing retrieval_text; C1 prefixes the real heading and first prose paragraph of the parent, at most 600 characters. Only original child text is emitted. This is NOT generative Anthropic Contextual Retrieval, NOT dense retrieval or Late Chunking. Only C1 minus C0 isolates the extra prefix; C1 minus R0 changes more than one mechanism.

All alternatives use existing source/payload builders and admission counter, at most 800 tokens and three source spans. Prototype metadata is simplified, read_next is empty, answer_supported/answer_available/edit_ready remain false. These are validated experimental DTOs, not integrated native handlers or full workflow parity.

## Manual context-sufficiency results

No LLM judge or weak-model answer generation. A packet is sufficient when its visible sources support the requested rule and material conditions without inventing a link between unrelated contract layers. Partial means only an important part survives. Extra topical text does not automatically erase a correct source, but policy and structure have separate acceptance gates.

| Arm | Sufficient | Partial | Miss | New sufficient vs R0 | Lost R0 sufficient |
|---|---:|---:|---:|---:|---:|
| R0 | 20 | 3 | 7 | 0 | 0 |
| A | 21 | 2 | 7 | 3 | 2 |
| B | 20 | 7 | 3 | 5 | 5 |
| C0 | 21 | 4 | 5 | 3 | 2 |
| C1 | 22 | 2 | 6 | 3 | 1 |

A gains G07/G16/G21 but loses G28/G29; G05/G06 also fall from partial to miss.
B gains G07/G16/G21/G22/G27 but loses full sufficiency on G01/G03/G23/G29/G30.
C0 gains G07/G16/G21 but loses G04/G29.
C1 gains G07/G16/G21 but loses G29; G06 also falls from partial to miss.
C0→C1 makes G04 partial→sufficient but G09 partial→miss. A one-question full-score gain is not strong independent evidence of general superiority.

Full answers by topic (omissions/current-history/workflow, ten each): R0 4/9/7; A 5/10/6; B 3/10/7; C0 4/10/7; C1 5/10/7.

Manual score vectors (2 sufficient, 1 partial, 0 miss), G01 through G30:

R0: 2 0 2 2 1 1 0 1 0 2 2 2 2 2 2 0 2 2 2 2 0 0 2 2 2 2 0 2 2 2
A:  2 0 2 2 0 0 2 1 1 2 2 2 2 2 2 2 2 2 2 2 2 0 2 2 2 2 0 0 0 2
B:  1 1 0 2 1 1 2 1 0 2 2 2 2 2 2 2 2 2 2 2 2 2 1 2 2 2 2 2 0 1
C0: 2 0 2 1 1 0 2 1 1 2 2 2 2 2 2 2 2 2 2 2 2 0 2 2 2 2 0 2 0 2
C1: 2 0 2 2 1 0 2 1 0 2 2 2 2 2 2 2 2 2 2 2 2 0 2 2 2 2 0 2 0 2

Interpretation controls: G04 needs omission information, not necessarily the entire companion-field list explicitly asked in G10. G30 can be answered by the generic concrete-missing-fact targeted-read/query rule; literal occurrence of 'comparison' is not required. G08 must not equate absence of safe evidence with proof that search never found anything. B's execution-budget paragraph does not answer G29's normal documentation-recovery question.

## Measured cost

Corrected CI stage means: A 0.0104 s; B 5.9494 s; C0 0.0160 s; C1 0.0169 s. These exclude shared native retrieval and model startup/download; C includes its experimental in-memory FTS work. They are not end-to-end production latency or a hardware-independent model speed claim.

Mean admission tokens: A 705.2; B 735.0; C0 710.5; C1 697.3. Max: 798/799/772/785 respectively.

All 2664 indexed children already had nonempty context_prefix. In the complete exported row set, existing retrieval_text is 1,831,047 UTF-8 bytes and the added C1 prefix is 839,289 bytes (~45.8%). This is string volume, not measured DB or RAM growth.

## First-loss observations

- G02: both public-contract paragraphs are in the normally retrieved pool; traces unqualified at match ratios .1667/.3333; neither reaches context_pack.
- G07: non-critical paragraph is found; trace .2308 and qualified=false; context_pack/public are empty.
- G09: omission rule survives to public; a missing-fact recovery rule is in the pool with trace .1667, absent from pack. The separate stopping paragraph is absent from the observed pool.
- G16: current-authority paragraph is found at match_ratio=.7, but exact_terms=[api] and missing_exact_terms=[api] make qualified=false. This is more specific than the previous claim that API merely attracts unrelated search hits.
- G21: correct root-first and after-gap passages are qualified and in context_pack. Their qualified variants are considered, but not selected in public. Diagnostics show 35 qualified variants and zero token-budget rejections. Internal generated query: `indexing split documentation sections parent child chunks`, despite the user asking about splitting searches.
- G22: vocabulary rule found, original trace .1333 and qualified=false; internal concept query includes `If my as I to or`.
- G27: at-most-one-rephrase paragraph found, trace .2 and qualified=false; absent from pack.

These locate the observed interval of loss, not every internal function. A ranking model placed only after all current qualification vetoes cannot recover most of these already-rejected witnesses.

## Harness defect and correction

The first adapter ran policy checks on early metadata but failed to add later taxonomy-derived source risks. Research notes therefore leaked into experimental packets. This was an experiment-adapter defect, not a demonstrated production vulnerability.

The one corrected replay restores existing project_source_taxonomy risks, runtime lifecycle_intent, verified project_file→project_doc adaptation and literal source-file binding. Algorithms, model, questions, lookup queries, prefix parameters and output limits were not tuned.

Corrected run: 120 payloads with no native validator errors, no budget overflow, at most three sources, no certification flags, and literal spans/file hashes additionally verified locally. Five limited controls passed: foreign project, stale, unsynchronized, explicit risk, taxonomy-derived research rejection. This is not the complete wrong-version/snapshot/injection/mutation/recovery suite and must not be called full production safety parity.

## Conclusion

The dominant verified problem in these residuals is automatic relevance/intent interpretation being used as a hard barrier to already found text; G21 additionally has a late selection loss. This justifies separating hard source eligibility from relevance and coverage. It does not prove that any tested replacement is ready.

Close the ABC comparison here. Do not sweep more models, invent new query-specific rules or expand budgets to force 30/30. Direction A is the preferred lower-dependency architecture; its current prototype remains rejected for promotion. B is not accepted into core; C is not established as the main fix. Independent cross-project and real-reader task validation remain unperformed, explicitly outside the claims of this result.
