# T05 native Markdown structure and T06 safety follow-up — 2026-10-01

Follow-up measurement: [HEADING_REMOVE_ONE.md](HEADING_REMOVE_ONE.md) isolates
the two-body-match heading threshold, with 68 additional development executions.

## Implemented factor

The previous B changed only FTS strings. It remains available as **B_FTS**,
preserving that historical diagnostic without silently attributing its results
to parser repair. New **B** uses installed `markdown-it-py` **4.2.0**, CommonMark
heading token line maps, and existing `ParentSection`/`RetrievalChild` types.
No packages/models downloaded; product files and `uv.lock` unchanged.

Original UTF-8 Markdown bytes remain the canonical artifact. Token line maps
select original source offsets, never coordinates of rendered/converted HTML.
Setext, multiline/indented ATX headings and their section hierarchy are recognized;
headings inside code, raw HTML examples, quotes and lists do not become page
owners. References inside a description do not rename its owner. No query,
expected API, answer phrase or review label enters the parser.

Production child atomization, contextual prefix generator, 160/512 chunk limits,
native FTS weights (6/2/0.5), query frontend, filters, hard gates and whole-unit
packer are unchanged. Newly correct headings/boundaries can change chunks and
prefix text: B−A is the **representation package**, not an isolated ranking claim.
Supported plain ATX parents and all children/prefixes compare equal to baseline.

One process-local parser hook covers both indexing and source-bound validation;
imported aliases and parser-dependent cache are restored after exceptions.
Never install it in a concurrent MCP server. P before/after B retained the exact
DTO and SQL-search count at the same controlled fixture path.

## TDD and safety

- Setext owner integration: actual assertion RED (old B owner was not the API),
  then GREEN. Legacy FTS-only integration remains under the B_FTS name.
- Nine structure controls cover links to other APIs, classes with the same method
  name, repeated declarations, warnings/lists/examples, literal spaces and */**,
  Unicode/CRLF, renaming, reordering, code/HTML/quote headings and cache restoration.
- Retaining production prefix exposed a faulty B/D test comparison across random
  temporary identities. The test now rebuilds both at the same owned path; it
  still requires identical pool hash, not relaxed score/text normalization.
- New T06 guard **failed**: old assembly could restore an unsafe child previously
  removed by `_eligible_rows`. It now requires the same hard-policy stable-ID
  allowlist for seeds and immediate neighbors; denied neighbors cannot be skipped
  over to reach a farther block. Final source/reference/DTO validation remains.
  This is a safety repair, not a relevance optimization.
- Additional adversarial version/heading neighbor test exposed that the allowlist
  alone does not check cross-child version equality or forged heading metadata.
  Assembly now also compares neighbor/seed versions and the parsed source heading
  path. This test is GREEN; the 204-run matrix below precedes this last guard
  refinement. A subsequent final-code rerun is recorded below.
- Final harness plus adjacent product suites: **169 passed**. Full offline gate,
  namespace isolation, hybrid and answer generation not run in this stage.

Logs: `/tmp/opencode/ablation-structure-{red,green,regressions,regressions-green,
neighbor-red,safe-regressions}.log`. Collection errors are not counted as RED.

## Final development replay

### Final-code guard verification

**Same-root follow-up:** the driver now accepts an explicit `ABLATION_RUNTIME`,
separate from its output directory. Rebuilt fresh indexes on the original safe
batch's fixture paths, refusing to start if those runtime directories existed.
All **204/204 executions** were successful and audit-clean, maximum **800** tokens.
All **102/102** first-repeat DTOs equal the earlier safe-code batch exactly;
all 102 second repeats match, and all 34 B/D pools and same-call controls match.
Thus the earlier manual review and 3 real assembly wins / 1 loss also describe
the final guarded code on these inputs; this is reproduction, not new independent
semantic evaluation. The synthetic B loss is likewise unchanged.
Artifacts: `/tmp/opencode/ablation-structure-{readme,four-docs,mechanisms}-same-root/`;
summary: `/tmp/opencode/ablation-structure-same-root-verification.json`.
The different-root rerun below remains preserved as a confound diagnosis.

Repeated all 204 executions after the version/heading guard refinement:
**204 executed, 204 audit-clean, maximum 795 tokens**. All 102 repeated DTOs
matched within their panel; all 34 B/D pools and same-call B controls matched.
Results: `/tmp/opencode/ablation-structure-readme-final/`,
`/tmp/opencode/ablation-structure-four-docs-final-v2/`, and
`/tmp/opencode/ablation-structure-mechanisms-final-v2/`; mechanical summary:
`/tmp/opencode/ablation-structure-final-verification.json`.

The first multi-panel command timed out after completing README; the partial
four-doc directory is excluded, and four-docs/mechanisms were rerun completely.
These new output directories also change the controlled fixture root between
old and new batches. Thus cross-batch DTO identity is not a valid guard-effect
comparison: source IDs/metadata and contextual prefixes change. Visible snippets
matched the prior batch except README case 6 D_L and four-doc cases 2/13 A/B.
Synthetic mechanism snippets all matched. No new semantic review or revised
win/loss counts are claimed; the table below describes the earlier batch only.
Future code-version comparisons must retain the same fixture root across batches.

Same small replay driver, ordinary separate processes, no OS isolation or hidden
labels supplied. Sources/questions saved first; code and input hashes checked
before/after each execution. Fresh indexes use the same owned fixture path within
each panel, eliminating temporary-root identity as an A/B/D confound. Arm order
alternates. Questions remain original-only; no model-created lookup changes.

Final runs after the neighbor safety repair:

| Panel | Questions | Physical executions | Sufficient A / B / D_L |
|---|---:|---:|---:|
| Real README | 12 (11 answerable) | 72 | 8 / 8 / 9 |
| Four real docs | 16 (12 answerable) | 96 | 9 / 9 / 10 |
| Synthetic setext mechanisms | 6 (6 answerable) | 36 | 2 / 1 / 1 |

**204 planned / 204 executed / 204 canonical-audit-clean**, maximum 800 DTO tokens;
no answer/edit authority granted. All **102** arm/case DTOs matched their second
repeat exactly. All **34** B/D candidate pool hashes matched, and the same-call
B control equaled standalone B's visible DTO. No new global search in assembly.
Results before the safety fix are retained separately and excluded from this table.
The 408 total physical runs across both code versions are not independent tasks.

### Representation result

All 28 real-doc A/B DTOs were identical: these ordinary ATX documents did not
exercise the heading defect. This is not evidence that structure never matters
or that the arms are generally equivalent.

The six synthetic mechanisms use native setext API declarations, reorder/rename,
a foreign API with the same exception, a condition moved to another paragraph,
and negation. Owners are correctly indexed by B, but qualification still removes
useful target units. In case 4 A's whole-page unit includes the target rule; B
returns only `Client.gamma()` startup prose mentioning `Client.alpha()`, not the
requested cancellation rule. Its owner remains gamma: no false alpha owner or
answer certification is created, but the packet is insufficient.

A separate post-run ingestion/qualification diagnosis of case 1 reproduces the
mechanism using real candidate objects and untouched qualification: the verified
owner is `Client.alpha()`, body matches only `cancellation`, so
`heading_context_used=false` and `missing_exact_terms=['client.alpha']`.
The current heading-context requirement of at least two body matches couples
soft overlap to exact-identity admission. This is not proof that BM25 failed.
The diagnosis is not an original uncapped first-loss trace.

### Assembly result

On 23 answerable real questions, same-call D_L−B: **3 wins / 1 loss / 19 ties**.
Wins: README tool table; four-doc report status definitions; cleanup scopes and
configuration preservation. The latter accepts source-supported alternative
evidence rather than requiring one exact list sentence.

Loss: four-doc case 6 asks about a changed snapshot on continuation. B includes
`source_changed` and the no-silent-latest-file condition. Its seed is also in D's
saved pool and is expanded successfully within its owner. The enlarged unit is
then omitted as **`whole_child_exceeds_dto_budget`**; another expanded seed has
already consumed space. The final D packet lacks the requested rule. No slicing
or budget tuning was added after inspecting this result.

All five real unanswerable questions return nonempty unsupported context in A,
B and D. No answerer ran: neither hallucinations nor successful abstentions were
measured. Expanded overlapping quotes also waste budget in some D packets.

## Artifacts and boundaries

- `/tmp/opencode/ablation-structure-readme-safe/`
- `/tmp/opencode/ablation-structure-four-docs-safe/`
- `/tmp/opencode/ablation-structure-mechanisms-safe/`
- `/tmp/opencode/ablation-structure-mechanisms-public/`
- `/tmp/opencode/ablation-structure-summary.json`
- Driver: `/tmp/opencode/ablation-ratio-replay.py`, with `ABLATION_ARMS=A,B,D_L`.

Raw candidates, lanes, assembly decisions, omissions and packets are retained;
case-review labels were created after execution. Self-authored, unblinded posthoc
development review; one repository, dependent topical panels, synthetic controls
kept separate. No independent holdout, quality acceptance or latency claim.

**Remaining T05:** HTML/RST converters and original/canonical provenance adapters;
API ownership beyond heading-scoped declarations, including ancestor declarations
needed by nested condition sections. CommonMark parsing does not certify what
every sentence says about its owner. Native project-only packet scope remains.

**Remaining T06:** replay externally saved pools/index snapshots, oversized atom
and budget-loss controls; current exact pairing is same-call plus controlled-root
rebuild, not a standalone saved-pool replayer.

Next minimal measurement: separate verified declaration/identity binding from
the soft two-body-match condition without disabling exact/reference checks.
Then measure bounded assembly's budget tradeoff on the same saved candidates.
Do not introduce hybrid to hide these admission/packing losses. Product removal
or activation is not justified by these results.
