# Completed selection and same-packet packing comparison — 2026-10-26

## Decision

The best measured profile in this continuation is the existing efficient
`facet-guarded-v1` / `global-margin-envelope-v2` selector with
`markdown-owner-v1` units, followed by **optional compatible-host
`adaptive-v1` metadata packing**. Do not add QA/NLI as a mandatory stage.

On 84 already-known questions, fixed-5 delivered all documented requirements in
65/70 full/partial cases (139/148 witness groups), while efficient facets
retained 70/70 and 148/148. Model-visible context was 120,863 tokens for fixed-5,
75,061 for the facet control and 72,664 after adaptive host packing. The combined
profile uses **39.879% fewer model-visible context tokens** than fixed-5 in this
run, with no lost control witness. This is NOT measured strong-model answer
accuracy, total dialogue tokens or provider billing.

The packing contribution itself is a strict same-response comparison:
**75,061 -> 72,664, a reduction of 2,397 tokens / 3.193%**, without changing one
selected evidence row, source-text byte, source order or full citation ref. No
individual input grew: 49 of 84 became smaller and 35 retained original v1.

Tested product commit: `5307d34b6160bd009ad282989f9f5cbd531e963d`.
Completed workflow: https://github.com/Vanilla1999/DocAtlas/actions/runs/40282567536
All five suite jobs and the comparison job finished successfully.

## What was implemented

`docmancer/docs/application/model_context_packing.py` is an opt-in **host-side
adapter after an actual v1 MCP response**, not a change to the default MCP wire
or `ModelContextSession.model_input()`. It compares three representation policies:

- `paths-v1`: store each exact source path once in a response-local catalog.
- `sections-v1`: store each exact path/section pair once, preserving whether
  the section field was originally absent.
- `adaptive-v1`: compare both with the original v1 projection. Accept a candidate
  only when o200k_base tokens, UTF-8 bytes and the conservative context-budget
  estimate do not increase; otherwise retain v1. This is a representation choice,
  not a semantic evidence threshold.

A present pair of source line coordinates is represented as an inclusive
`lines=[first,last]`. Every other non-factored field is retained. No text is
summarized, merged, deleted or rewritten. Full issued citations are unchanged;
bare `s1` is not accepted. The existing private packet and ledger remain outside
the answering-model prompt. An independently interpreted catalog must reconstruct
the complete original visible view, not just match a product decoder to itself.

`prepare_packed_context()` accepts a real MCP result and returns model-visible
context plus private metadata. `restore_packed_result()` restores the exact
machine packet; `resolve_packed_reference()` resolves only the full issued ref.
A compatible host must explicitly use these entry points instead of appending
both old and new views. Errors, access denials, lifecycle and patch-context
results retain their ordinary handling; the adapter is not an absence decision
or a source-access grant. See `model-context-packing.md` for the contract.

## Completed paired measurements

All selectors in this run use the same current product revision, source corpus,
translations, admitted-candidate fingerprints and independent frozen gold.
Packing alternatives use the **exact same response packet, ledger and random
citation nonce**, so citation tokenization cannot manufacture a packing gain.

| Pipeline | Complete documented cases | Required witness groups | Actual visible o200k_base tokens |
|---|---:|---:|---:|
| Fixed-5, existing v1 model view | 65/70 | 139/148 | 120,863 |
| Efficient facets, existing v1 model view | 70/70 | 148/148 | 75,061 |
| Efficient facets + paths-only packing | 70/70 | 148/148 | 74,883 |
| Efficient facets + path/section packing | 70/70 | 148/148 | 77,068 |
| **Efficient facets + adaptive packing** | **70/70** | **148/148** | **72,664** |

There are also 14 no-answer questions. All source-selection arms still fail the
strict empty-source criterion on those cases: **0/14**. That is not a measured
hallucination rate; no final answers were generated. The 70-case denominator
includes documented parts of partial questions, not unsupported parts.

| Packing mode on the facet responses | Token change | Smaller inputs | Larger inputs | Original-v1 fallback |
|---|---:|---:|---:|---:|
| Paths only | -178 | 36 | 45 | 0 |
| Path + section | +2,007 | 27 | 57 | 0 |
| **Adaptive** | **-2,397** | **49** | **0** | **35** |

Always using a new format is therefore worse for many short responses. The
adaptive policy wins because it prices the whole actual representation including
its catalog and explanation, not just repeated path characters. Its total UTF-8
bytes fall from 294,139 to 282,028. For all 84 facet inputs, independently expanded
visible fields and the original full refs match exactly. The same preservation
checks also run on the 84 fixed-control responses.

### Per-suite tradeoff

| Suite | Fixed complete documented cases | Facet complete documented cases | Fixed v1 tokens | Facet v1 tokens | Facet adaptive-packed tokens |
|---|---:|---:|---:|---:|---:|
| V40 | 32/32 | 32/32 | 99,065 | 37,670 | 35,790 |
| New16 | 14/14 | 14/14 | 8,093 | 18,255 | 17,839 |
| Fresh8 | 4/7 | 7/7 | 5,271 | 8,264 | 8,206 |
| SeleneMesh12 | 8/10 | 10/10 | 5,938 | 8,363 | 8,320 |
| QuillLedger8 | 7/7 | 7/7 | 2,496 | 2,509 | 2,509 |

The selector is NOT cheaper for every question or suite. Most overall savings
come from V40. New16 remains an over-selection problem: a short common parent
retains unrelated rules and uses more tokens without a coverage improvement.
Fresh8 and SeleneMesh spend additional context to recover missing requirements.
The adaptive **packing step alone** never increases any tested input.

Five fixed-control incomplete cases become complete: Fresh8 N03 (2/3 -> 3/3
witness groups), N04 (2/4 -> 4/4), N05 (2/6 -> 6/6); SeleneMesh S02 (4/5 -> 5/5)
and S04 (5/6 -> 6/6). No required group retained by fixed-5 is lost by facets.

## Runtime and integrity boundary

The test used non-editable installed wheels, real SQLite, pinned CPU MiniLM,
public stdio MCP, no product scorer/retrieval mocks, serving-time network
disabled, two CPUs, and a hard 1,000,000,000-byte container memory limit. Gold
was assessed only after actual delivery. Data, questions, translations and
oracle files were not changed to improve scores.

Execution: **168 stdio searches, 168 uncompressed public-handler acquisitions,
34 language preflights**. Host formatting adds no retrieval or model calls.
All 10 selector/suite arms had zero runtime and source-integrity errors.
**1,670 actual-response tamper controls** rejected altered text, path, lines,
ref, catalog, authority, policy and missing/mixed private ledger; unscoped refs
were also rejected. This is an integration observation, not a universal security
proof or an increase in the original reader's permissions.

Observed summed MCP time was 190.606 seconds for fixed-5 and 305.072 for facets.
The extra local selection work is real. Adaptive packing measured 0.345 seconds
summed across the 84 facet responses in the already-warm, fixed-order host
comparison. Tokenizer caches were warmed by earlier format checks. These single
CI timings are NOT cold-start or production latency benchmarks and do not prove
that the whole pipeline got faster.

## Relationship to the semantic checker experiments

`semantic-preservation-results.md` records the preceding QA/NLI work. Strict NLI
made 459 classifications and removed no group on the 84-question study. A small
apparent context-token delta was caused by random short-reference nonce
encoding, not reduced evidence. QA short-span agreement is not a certificate
that all caveats, conditions and multi-hop dependencies are present.

The verified QA unknown-state rollback and shared inference budgets remain.
QA/NLI modes stay experimental. The new packing step deliberately does not
claim to solve question sufficiency: it avoids that uncertain decision by
preserving all selected evidence verbatim. A more compact representation still
needs actual answering-model testing before claiming unchanged final answers.

## Provenance and reproduction

Current run: https://github.com/Vanilla1999/DocAtlas/actions/runs/40282567536
All artifacts were generated from tested SHA `5307d34b6160bd009ad282989f9f5cbd531e963d`.

| Artifact | ID | SHA-256 |
|---|---:|---|
| Paired comparison | 12632624221 | 6c4e063f039a59ce4355493e19b944bc5982fc6ec7e354d15140c9e03f84fcf1 |
| V40 | 12633317907 | 585b0be1dfb5eccf76c66c58a7ed9a30907b2feb7112810074488f86954fc5f6 |
| New16 | 12632742194 | 7a0ecb845b57644eb7e6857dcd50ffde2843be8b02a0cf4c5bf681df89715c88 |
| Fresh8 | 12633226360 | 2b9272a4cfb4137fa061cd9edfbad728714b8bcc26e6175884cfb4ed187d7ba2 |
| SeleneMesh12 | 12633185804 | 79f05a560ba1b1bf889d993817a2a702190a5fe736088658a7f675cb84114b6f |
| QuillLedger8 | 12632457792 | 9cd137ea8c34cc9e0e8863fddad98f0fcdeea50dc342abe7054adf02a4cb268e |

Downloading those suite archives and recomputing
`eval/compare_packing_selection.py` reproduced the published CI `PAIRED.json`
exactly. Each archive contains issued responses, original expanded packets,
packed views, independent witness assessments, actual model diagnostics,
frozen input hashes, execution details and tested-source archive.

The old coverage workflow is now reconciled with the integrated selectors.
It still freezes immutable input/oracle/dependency bytes, but no longer rejects
every later implementation against obsolete `95c7bf4` code. Both current controls
execute at one revision; no historical policy-label equivalence is assumed.
Earlier experiments and their failures remain in Git. No test was deleted or
required witness weakened to make this comparison pass.

## Release boundary

No strong answer model was called: `answer_model_calls=0`, `provider_usage=null`.
The original total strong-model dialogue-token objective remains unverified.
A previous live answer replay was blocked by missing provider credentials; this
run neither supplies credentials nor silently substitutes a different model.
All 84 questions are known development/regression data at this stage, not a new
blind or real-user out-of-domain evaluation.

On tested SHA 5307d34b, coverage comparison, MiniLM sections, compact context,
documentation language and answerability-observation safety workflows passed.
The separate release-artifact gate is still **red**. This report does not diagnose
or excuse that failure, claim a fully green repository, merge main, or turn on
new behavior globally. The same draft PR #227 continues to depend on unmerged
translation-admission PR #225. A compatible host must explicitly opt into
packing; ordinary MCP clients continue receiving their existing v1 representation.
