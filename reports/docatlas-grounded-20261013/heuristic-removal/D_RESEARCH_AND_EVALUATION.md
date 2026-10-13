# D — independent NEW20 and research handoff

2026-10-13. **NEW20 prepared independently before outputs**, 8positive/6partial/6negative; four new document families: Click8.1.8, Requests2.32.3, pytest8.3.5, tox4.24.1. No product/test/benchmark/model workload, no delegation, no implementation edits or historical oracle changes. Original full primary-paper method sections were acquired/read, not only abstracts; mapping/deviations are in `METHOD_CONFORMANCE.md`.

## Fixed dataset paths / blinding

All paths relative to the worktree:
- `eval/heuristic_removal_holdout/FREEZE_MANIFEST.json`: pre-output byte hashes for original corpus, questions/oracle, builder, interface/rubric and research archive. It is a **data freeze**, not a substitute for coordinator code/config/prompt/model freeze.
- `eval/heuristic_removal_holdout/source-manifest.json`: public four-source provenance/root schema for prepare; pinned original bytes, upstream release and SHA256. Original `.rst`, no text conversion, source edits, synthetic facts or fixture mocks.
- `eval/heuristic_removal_holdout/INTERFACE.md`: E/coordinator consumable public schema and public local-project-docs prepare roots. `.rst` support confirmed by catalog declaration; no prepare was executed by D.
- `eval/heuristic_removal_holdout/rubric.json`: separate new generic metric rubric, **not copied/rewritten historical gold**.
- `eval/heuristic_removal_holdout/sealed/questions.json`, `sealed/oracle.json`, `sealed/witness-audit.json`, `sealed/build.py`: **do not read before code freeze**. The builder itself contains questions/facts and must remain sealed too. Coordinator should provide only paths/hashes and family/count summary to implementers; after recorded freeze runner can open questions and evaluator/reviewer can open gold. Same-user filesystem isolation is procedural, not cryptographic access control.

Four roots for public prepare: `corpus/click`, `corpus/requests`, `corpus/pytest`, `corpus/tox` underneath the holdout folder. Never prepare the enclosing folder or research/sealed artifacts. Per-case questions are unchanged and independently scoped to their project; compare frozen V0/VALL only on NEW20. The prior V40/H20 source metadata/source plans were consulted selectively for used document families (Vite, ESLint, Textual, Poetry, Black; Ruff, uv, MkDocs, Typer). Their cases/oracle remain untouched and **open regression**, never rebranded closed.

## Independent expectations and auditing

Facts were hand-authored by D from original source prose/code, then pinned by a data-only builder to literal original UTF-8 half-open byte spans, line ranges, SHA256 and exact source quotations. No production helper, retrieval output or model answer computes expectations. Negative/partial absent obligations are statements about **this finite supplied corpus**, not universal claims about everything a library can do. Related names or code examples do not supply an undocumented guarantee. Absence review used original pages and targeted full-corpus text inspection; only unrelated callback-signature occurrences appeared in the absence-topic search, not cryptographic support. This is AI-authored/AI-audited gold, **not independently human-verified**; reviewer may flag authoring errors but cannot repair gold post-output to manufacture PASS.

Conditions, negation, case, code/operator meaning, default-vs-example and relation/ordering obligations are frozen explicitly. Witness-set schema supports alternative source witnesses (OR) and compound witness sets (AND); only alternatives actually frozen count toward exact coverage. No post-output synonym stripping, Markdown/RST symbol deletion, lowercase normalization, new rescue witnesses or question rewrites. Missing unavailable obligations on partial cases must remain visible, not be answered inventively. Negative exact coverage has no denominator; strict `sources=[]` is a distinct metric, not vacuous coverage PASS.

The independent semantic rubric separately records exact fact coverage, context sufficiency/useful partial, strict negative empty-source, authorized source integrity, generated answer quality and unsupported claims. Label-hidden review initially receives question plus anonymized context, **without expected class/gold/arm identity**; subsequent reconciliation uses original documents and frozen facts. AI reviews must be identified as such. If generation is not authorized/executed, actual answer quality is **NOT MEASURED**. Source-valid attribution is not answer/edit authority or sufficient context. Never combine retrieval quality, safety, cost and readiness into one PASS.

## Acquisition limits and failures

`acquire.py` performs only public GETs to original GitHub release-tag raw files, arXiv versioned full PDFs, ACL full PDF and Anthropic engineering page.45s per fetch,12MB per-object ceiling, one attempt per planned artifact, no secret headers/cookies/tokens and no product transport. Four original docs plus six primary research artifacts: **10 HTTP200 responses**, lossless bytes/SHA in `acquisition.json`. Text extraction: local `pdftotext -layout`; original PDFs retained. Official SQLite documentation fetched separately only to verify FTS5 constants; receipt retained. Context7 lookup failed with monthly-quota error; fallback was explicit original SQLite docs, not inferred recent documentation.

The first acquisition launch used unavailable `python` and failed at shell startup (exit127, **zero HTTP requests**); corrected once to `python3`, not a product-quality retry. There were no source HTTP failures among the planned10. No article claim of empirical improvement transfers to this candidate. No licenses/full repository checkout or upstream runtime imported; selected original public docs define a small finite evaluation corpus, not full library documentation coverage. Release tags are locators, while SHA pins protect against tag mutation; source bytes must not refresh after freeze. The live Anthropic/SQLite HTML is pinned by bytes/date, not purported immutable publication revision.

## Remaining coordinator obligations

Before NEW20 opening: freeze actual product and all comparison configuration/transport/tokenizer/model/prompt, bounded execution ledger and financial permission. Preserve pre-output data freeze and original setup failures. Record blinding/unseal time. Run only approved public integration/installed/production-path workload, never unit or private-helper probes. Report per-arm/case gains/losses and all old strict negative failures; do not tune current patch with new closed outputs. D handoff does not certify any unrun product property or production readiness.

## Fixed SHA handoff (case content intentionally omitted)

Data-only verification found **27 hash/length-matching archived files**, **20 aligned unique opaque question/oracle IDs**, **26 independently authored required facts**, **33 literal exact witness occurrences**, and **112481 original corpus bytes**. This verifies artifact pinning, not product behavior. Four new document families and 8/6/6 class totals are public; class-by-case assignments/questions remain sealed.

| Artifact relative to `eval/heuristic_removal_holdout/` | SHA256 |
|---|---|
| `FREEZE_MANIFEST.json` | `7d1962363aeb11020752a30370c34a35f62c6431ae5d6bd2fa261f2d7e58a2ad` |
| `source-manifest.json` | `4e906611e10e65f56b21ab3c10c6225b5e41cefee0ca26d6f8c31718e0f021ba` |
| `sealed/questions.json` | `24b5f77958553494a1c57246c49f34c71b08d951c55fa4c2fae37faa9d936d78` |
| `sealed/oracle.json` | `0fa7e77b5d5be769f9ab271f30f23aa1f717f4fdbd8f5a63f4f46625fd2aac9d` |
| `sealed/witness-audit.json` | `10573597469f518f7e95682c76c1875a3c325df65a7cd1412dd240c2ef61ca8c` |
| `rubric.json` | `75e21515384472fafaf22cd7fc26c9dade6b5f2acb1020ef6511e94413462abd` |

Coordinator can transport the whole dataset directory byte-for-byte and verify this manifest; portable roots/snippets use relative paths, no temporary absolute source locator. Keep `sealed/` unopened by implementers during transport/review before freeze. Reports themselves are outside the dataset freeze; coordinator should hash them in the final report manifest.
