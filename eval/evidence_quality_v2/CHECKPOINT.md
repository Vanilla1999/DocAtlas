# Evidence quality v2 — published execution checkpoint

Work branch: `fix/evidence-quality-v2-20260910`; one PR: #185. Do not merge automatically.
Baseline main: `e1daf4fa68f16f626068f2c58646e2ebfd4293f7`.
Verified product/publication HEAD: `5f7e70fa9d205c19d8d1e6f116b2526f7a7b0e59`.
This report-only update does not change production, source documents, questions,
annotations, thresholds, tool schemas or token budgets. Ordinary CI for a later
report commit must be checked separately; results below are not silently rebound.

## Published and executed, not just staged

| Step | Hypothesis or contract | Executed evidence | Change and result | Boundary |
| --- | --- | --- | --- | --- |
| P1 | Separate source support, sufficiency, citation integrity and first loss | Measurement tests, same-call capture, fixed candidate replay, final validation | Eval-only assessment/trace/cost/answer modules | Approved-witness recognition is not universal semantic judgment; unknown alternatives remain review items |
| P2 | Test outside original-15 on fixed real documentation | 80 tasks, eight pinned upstream projects, exact 14-document manifest | 40 development / 40 exposed validation, grouped by project | Exposed development benchmark, NOT hidden validation |
| P3 | Test canonical aliases, ranking, expansion and host lookups one factor at a time | 560 rows: 400 real handler calls and 160 same-candidate projector replays | A/B/C/explicit/duplicate/nearby each 29/48 recognized sufficient; no-expansion 19/48 | No blanket superiority claim; C/D are replays, not fresh retrieval |
| P4a/c | Safe literal hints were lost for unresolved broad questions; exact-original duplicate added no requirement | Neutral Pebble handler/projection tests and safety negatives in full core | Published `9fe3e017`: bounded hint fallback and exact-original dedup; no original/full/support fabrication | Exact API/path, normative-premise and unsafe evidence retain existing protections |
| P4b | Q05 permission condition was retrieved but lost during selection | Unchanged original-15 RED, same-call trace, ordering-column rollback and final regression | Published `f921c4b2`: single-operation condition-lead preference; original-15 now passes | Narrow preference, not a semantic classifier; neutral 400-token probe is explicitly characterization |
| P4d | Root/seed/ingest/format changes might break invariant fixture meaning | Eight subprocess/root variants, 40 handler calls, both projects populated | All three required facts preserved; eight distinct-identity isolation controls; zero observed violations | DISPROVED_ON_THIS_FIXTURE; no extra production patch justified |
| P5 | Missing returned fact might be a real documentation gap | Audit of 88 required claim records: 64 approved source witnesses present, 24 not established in selected sources | Published `89da2cf9`; NO_DOCUMENTATION_EDIT_JUSTIFIED; Q05 witnesses already present | No global absence claim. No source-doc edits, so editorial old/new-doc 2x2 is not applicable |
| P6 | Measure actual payload size separately from estimator and host behavior | Pinned tokenizer, real installed-wheel MCP, source-bound oracle/order input construction, answer/citation scorer tests | Published `a8d549e4`; 48 deterministic inputs and verified installed scripted trajectory | No live-model answers, provider usage, monetary cost or positional-effect claim |

Exactly three public tools, <=3 sources and <=800 engineering estimated serialized
tokens remain unchanged. Project docs_context remains retrieval-only, with
answer_supported, answer_available and edit_ready false. No public debug mode,
mandatory embeddings, reranker, LLM judge or additional DDD layer was introduced.

## Exact published-head verification

Run: https://github.com/Vanilla1999/DocAtlas/actions/runs/34582875049

The fail-closed workflow created the reviewed product commits, removed its
consumed carrier files, tested that clean tree and only then fast-forwarded the
branch. It did not merge the PR or publish a release.

- Full offline core: **3660 passed, 10 skipped, 593 deselected**, 0 failures/errors.
  The selected command excludes advanced/live/live_network; it is not all tests.
  The existing direct original-15 test is included and passes without changes.
- Frozen 80-task matrix: 560/560 rows, zero operational errors and zero observed
  source-integrity/contract violations. Native A: 29 sufficient, 31 needs_review,
  20 insufficient of all 80. Primary denominator is 48 within-budget tasks.
- Documentary gap audit: PASS; no source-doc change proposed.
- Metamorphic fixture: 8 runs, 40 handler calls, 3/3 baseline facts complete,
  no semantic changes or observed integrity/isolation violations.
- Installed-contract self-tests: 7/7. Exact wheel built and installed in a fresh
  environment; real stdio MCP scripted task: 1/1, false-supported=0,
  contamination=0. One invalid-schema attempt is followed by one bounded repair.
  The independent existing report verifier passes, including its privacy rules.
- Host-input controls: four preregistered tasks x native/oracle x three orders x
  two repeats = 48 inputs. Exact source spans and fixed evidence budgets pass.
  pydantic-02 native is insufficient while its oracle is sufficient. All four
  oracles are sufficient. Several order controls are degenerate (one block or no
  blocks) and explicitly reported; they cannot establish positional sensitivity.
- Compileall and diff checks pass; consumed bootstrap/public-input/tokenizer/
  delivery workflows and the staged compressed patch were removed.

Artifact ID: `10192554093`; SHA-256:
`23daa238070d22ac5312bbb68af0c641eaac37108e382fd6cc409cc0326437a0`.
The artifact contains source.bundle, commit identity, JUnit/logs, full matrix
outputs/traces, ingest/config/package records, P5 audit, host inputs, wheel and
installed report/verifier output. Its retention is 14 days, not permanent storage.

Wheel: `doc_atlas-1.3.2-py3-none-any.whl`;
SHA-256 `28a60503428b26d2507c8af3ba5799dc0f7ce7a81fba3203ad55baa38bf17f55`.
MCP tools/list schema SHA-256:
`50c0bbbe02fb3b1426452d593f79751f915de4cc7e02a08f936758a896e44551`.
Installed report SHA-256:
`df8062bfc9163cc94c82a42d13bbdc342c81df952744fd22b684e6c797a3418a`.
This is a reviewed wheel, NOT proof of a public PyPI release.

## Comparative results and cost boundaries

One fixed diagnostic tokenizer is used: tiktoken 0.11.0, o200k_base. This does not
claim to be any current host model's tokenizer. The production byte estimator is
unchanged. Only one selected model-visible channel is counted, not structured
and text together. All questions, including unsuccessful ones, remain in size
and latency summaries.

| Series | Recognized sufficient / 48 | Actual tokens p50 / p95 over 80 |
| --- | --- | --- |
| DocAtlas A, published-head CI handler payload | 29 | 360 / 633 |
| Grounded 3.1.0 native lexical, limit 1, separate local replay | 21 | 433 / 1669 |
| Grounded 3.1.0 native lexical, limit 3, separate local replay | 32 | 1219 / 3072 |
| Grounded 3.1.0 native lexical, limit 5, separate local replay | 32 | 1848 / 4684 |

The separate Grounded replay verified the same 14 source documents in its actual
SQLite ingest, no missing/extra sources and no non-null embeddings. It completed
240/240 native stdio requests without operational errors. Source-paragraph
mapping is conservative; unknown alternatives require review, not automatic FAIL.
These latest local counts supersede the earlier historical 22/32/32 checkpoint;
they are not silently pooled with it. The local runtime/package and raw results
must accompany any reproduction; no independent hybrid-search comparison exists.

The deliberately simple common first-whole-paragraph adapter gives Grounded
7/48 and DocAtlas 29/48. It spends the three-block cap poorly. This is a negative
result for that adapter, NOT evidence that native Grounded is bad or a fair proof
of DocAtlas superiority. Native top-3 is not an 800-token DocAtlas envelope.
No token-savings factor at equal correctness is established by this table.

A separate same-path, same-config/source/evaluator old-code/new-code replay of
all 80 questions retained 29/48 primary sufficiency on both main baseline and
this product tree. Ten results moved insufficient -> needs_review (eight
ambiguous, one partial, one within-budget); these are not credited as successes.
All runtime module origins were verified against the selected baseline checkout.
The paired primary difference is zero: comparative outcome INCONCLUSIVE. Do not
tune exposed validation misses or call fact groups independent experiments.

Handler timings include the expanded observer; Grounded timings include a
different native stdio path. They are recorded separately, not used as a fair
production throughput comparison. SQL-level internal operation counts were not
instrumented: one service retrieval/validation is NOT claimed to mean one SQL
query. Provider-reported whole-task input/output, cached/reasoning usage, money,
live host success and positional sensitivity are **NOT_MEASURED**, not zero.

## Host workflow scope and remaining evidence boundaries

The real installed harness result covers the existing module-definition task,
bootstrap, exact tools/list, bounded schema repair and source-backed retrieval.
It is not falsely reported as six installed lifecycle scenarios or autonomous
reasoning. Existing offline tests separately exercise guarded clean-Git prepare,
dirty-tree confirmation, precondition recheck, recovery and terminal job states;
those are backend/contract tests, not a live host trajectory. A dedicated full
installed lifecycle/job trajectory matrix is still outstanding.

The answer/citation scorer and its tests distinguish supported partial answers,
wrong-version/irrelevant citations, polarity violations, unknown extra assertions
and unjustified refusal. No actual model answers were collected here:
context_sufficiency x answer_outcome is empty and support ratio is N/A, not 100%.

Independent hidden validation, blind semantic adjudication of the review queue,
live host repetitions, full provider cost, installed lifecycle matrix and final
ordinary PR/platform/frozen acceptance results are separate remaining acceptance
items. This checkpoint does not relabel them green or assert market superiority.

## Reproduction

From a clean checkout with normal development dependencies and tiktoken==0.11.0,
set DOCATLAS_OFFLINE=1 and DOCATLAS_AUTO_VECTORS=0. Use an isolated HOME and output
outside the checkout. Module invocation intentionally keeps evaluator imports
available without editable installation:

```
python -m pytest tests/ -q -m 'not advanced and not live and not live_network'
python -m eval.evidence_quality_v2.run --output /absolute/external/native
python -m eval.evidence_quality_v2.documentation_audit --output /absolute/external/doc-audit
python -m eval.evidence_quality_v2.robustness --output /absolute/external/robustness
python -m eval.evidence_quality_v2.host_control --native-output /absolute/external/native --output /absolute/external/host-inputs
python -m scripts.installed_mcp_contract_self_test
python -m build --wheel --outdir /absolute/external/wheel
python -m scripts.run_installed_mcp_agent_benchmark --wheel /absolute/external/wheel/doc_atlas-1.3.2-py3-none-any.whl --source-commit FULL_CHECKOUT_SHA --planner scripted --task module_definition_supported --max-schema-repairs 1 --min-pass-rate 1 --output /absolute/external/installed.json
python -m scripts.verify_installed_mcp_agent_report /absolute/external/installed.json --expected-origin reviewed-wheel --min-task-count 1 --min-pass-rate 1 --require-schema-repair
```

## Invalid setup attempts, not algorithmic RED

Earlier wrong tokenizer cache, pre-normalization observer capture, malformed
lookup duplication and Grounded's default clean ingest remain historical setup
errors. The first P4-P6 publication attempt passed full core but stopped because
file-style invocation of installed_mcp_contract_self_test could not import eval.
Correct module invocation fixed the runner; no production behavior, corpus or
acceptance threshold was changed for that error. Failed attempts were retained
rather than converted to successful evidence.
