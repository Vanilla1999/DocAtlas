# Evidence selection: measured results, 2026-10-25

## Decision

Selected accuracy-first candidate: **`facet-bundled-cover-v1`**, opt-in only.
It retained all 97 required witness groups on all 53 documented cases, including
all documented parts of partial-answer questions. It lost no control witness
relative to either fixed5 or B1. Its 124,905 context tokens are **11.19% above
fixed5 and 13.17% above B1**. This is an evidence-completeness improvement,
NOT a successful general token-cost optimization.

No tested candidate both passed the per-case no-lost-fact gate and used fewer
total context tokens than the controls. Defaults remain unchanged; no merge to
main or production-readiness claim was made.

## Frozen comparison

64 unchanged questions: V40 (40), New16 (16), Fresh8 (8). There are 42 fully
answerable, 11 partially answerable and 11 unanswerable cases. The table's
53-case denominator counts the first two groups and asks whether every
DOCUMENTED required part is present. The 97 denominator counts witness groups;
these groups are not uniformly sized atomic facts across suites.

All variants run actual non-editable installed wheels, real SQLite, public
stdio MCP and pinned CPU MiniLM under offline/two-CPU/hard-1GB constraints.
Same questions, translations and admitted/scored source pools are checked;
source bytes, identifiers, spans and citations are independently verified.
Gold is opened after delivery, never passed to selection or answering prompts.
The frozen input hashes are identical across all arms.

| Policy | Complete documented cases | Required groups | Actual model-context tokens | vs fixed5 | No control-fact loss |
|---|---:|---:|---:|---:|---|
| `fixed` | 50/53 | 90/97 | 112,334 | +0.00% | control |
| `adaptive-gap-b1-v1` | 49/53 | 92/97 | 110,369 | -1.75% | control |
| `mmr-budget-v1` | 49/53 | 93/97 | 110,239 | -1.86% | no |
| `facet-cover-v1` | 48/53 | 91/97 | 40,096 | -64.31% | no |
| `facet-guarded-v1` | 52/53 | 95/97 | 113,911 | +1.40% | yes |
| `facet-cover-v2` | 37/53 | 70/97 | 30,382 | -72.95% | no |
| `facet-guarded-v2` | 50/53 | 93/97 | 111,006 | -1.18% | no |
| `facet-bundled-v1` | 53/53 | 97/97 | 128,897 | +14.74% | yes |
| `facet-bundled-cover-v1` | 53/53 | 97/97 | 124,905 | +11.19% | yes |

Each arm has zero runtime and source-integrity errors. Strict empty-source
negative checks pass **0/11 for every arm**. This is not a measured hallucination
rate: `answer_supported` and `answer_available` remain false, but final answer
behavior was not obtained.

### Selected policy by suite

| Suite | Fully answerable coverage | Documented partial coverage | fixed5 tokens | B1 tokens | Selected tokens |
|---|---:|---:|---:|---:|---:|
| V40 | 24/24 | 8/8 | 99,040 | 100,925 | 100,954 |
| New16 | 12/12 | 2/2 | 8,053 | 5,023 | 18,216 |
| Fresh8 | 6/6 | 1/1 | 5,241 | 4,421 | 5,735 |

The final candidate saves 3.10% relative to the other fully covering bundled
candidate, NOT relative to fixed5 or B1. On New16 it bundles 13 already-acquired
sections of a short source into one unit, retaining unnecessary rules along
with necessary ones. This explains its large token regression on that suite.
One unit is not one original section. This behavior is a known limitation,
not a change to the token-accounting denominator.

Five V40 requests needed the explicit complete-packet budget fallback. Their
required witness groups were still retained in this run, but the algorithm does
not guarantee that on other inputs. Selected unit counts vary: V40 2-34,
New16 1, Fresh8 1-2. The maximum observed server RSS was 487,772,160 bytes.

### Problem cases, same corrected acquisition pool

| Fresh case | fixed5 required groups | Selected required groups | fixed5 context tokens | Selected context tokens |
|---|---:|---:|---:|---:|
| N01 ticket lifecycle | 4/4 | 4/4 | 604 | 986 |
| N03 import and publication | 2/3 | 3/3 | 695 | 567 |
| N04 export semantics | 2/4 | 4/4 | 674 | 995 |
| N05 consumer recovery | 2/6 | 6/6 | 625 | 827 |

The original eight-dialogue totals are NOT directly comparable: this study uses
the translation-admission fix and one search per question, without the earlier
scripted follow-ups/history replay. N04's sources are now admitted, but fixed5
still omits snapshot and creation/access conditions; bundling retains them.

## What the experiment established

Literal per-clause ranking is not evidence sufficiency. The very cheap first
facet-cover variant lost V40-B01, T01 and E01, plus N05 deduplication, despite
sometimes increasing aggregate fact coverage. Contextualizing every clause also
proved insufficient: its strong full-question prefix may dominate a specific
requirement, and the measured v2 variants regressed.

The bounded structural candidate avoids splitting some interdependent short
procedures. Its final variant omits automatic B1 extras when every probe winner
is such a bundle, but still retains a B1-union guard for long-source cases. It is
NOT a complete replacement of score-gap heuristics with a semantic verifier.
No trained sufficient-context or NLI judge was implemented. Exact costs are used
for packet limits and ranking ties, not as proof of a globally minimal evidence set.

Observed summed MCP times over 64 requests: fixed5 170.81 s, B1 209.68 s,
selected candidate 362.62 s. Median per-question V40 latency was 2.97 s, 3.83 s,
and 7.11 s respectively. These are single CI runs on separate runners, not a
controlled repeated latency benchmark; extra local scoring is nevertheless real.

## Runs and provenance

- Round 1: `f4a885a49494bedb65154af48403a378b1b8d208`, run
  https://github.com/Vanilla1999/DocAtlas/actions/runs/40219786995 ; 320 stdio
  searches and 320 baseline public-handler calls.
- Round 2: `95c7bf4bedeefa98a565ec44c83b5df0aa7c526d`, run
  https://github.com/Vanilla1999/DocAtlas/actions/runs/40221157968 ; 192 new stdio
  searches and 192 new baseline calls; first-round results reused unchanged.
- Final: `41f2072d450bf9692e8a81deb59a9d85c54d6eef`, run
  https://github.com/Vanilla1999/DocAtlas/actions/runs/40222270221 ; 64 new stdio
  searches and 64 new baseline calls; 512 prior searches reused, not repeated.

Total targeted comparison: 576 stdio searches + 576 public-handler baseline
acquisitions + 72 language preflights. All three data suites are known regression
and development sets, NOT blind holdouts. No significance or out-of-domain
non-inferiority claim follows from selecting the winner on these same cases.

Final comparison artifact: `12610112356`,
SHA-256 `fa62ad35bca2bb7ec262fbbb4cec8e4b2b1256886594db51a1d19542f23931b2`.
Raw JSON reports, per-request traces, exact source and output hashes, and public
answer prompts are retained in the linked runs (30-day CI retention).

## Actual answer-replay attempt

Run https://github.com/Vanilla1999/DocAtlas/actions/runs/40222585412 uses replay
source `e42e167f4273531bde9d8b73a91800cdb66481cf` and the frozen public contexts
of fixed5, B1 and the selected candidate (eight questions each). Its configured
model is the existing repository benchmark's `gpt-5.6-luna`; no fallback or
substitution is allowed. Maximum planned calls: 24, bounded output 4096 tokens.

Actual result: **`blocked_missing_provider_credential`**, **0 model calls**,
**`provider_usage=null`**. `OPENAI_API_KEY` was not available to that CI job.
No final answer accuracy, token billing or model-availability result exists.
Do not interpret the blocked job as a passed quality gate. Even a successful
one-shot replay would not establish complete autonomous-client/history economy.

Replay artifact: `12610167074`,
SHA-256 `262c014d152c4547c8fdafdc7aeba45572fb47aef6fa31f0bae0c817d76081ee`.

## Integration / release boundary

At the tested selection head, Documentation language installed MCP, MiniLM
sections installed MCP and Compact model context installed MCP passed. The
release-artifact gate failed; the repository is not fully green. This study
neither fixes nor excuses unrelated release checks. PR #227 remains a draft,
stacked on unmerged PR #225, with the selection opt-in and defaults unchanged.
