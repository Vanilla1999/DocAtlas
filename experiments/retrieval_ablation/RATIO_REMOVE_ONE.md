# Real-P ratio-only remove-one — 2026-10-01

## Intervention

`P_MINUS_RATIO` invokes the same baseline handler as P. A process-local hook
compiles the existing `qualify_evidence` function after replacing exactly one
AST comparison, `ratio >= required_ratio`. The function body is otherwise intact:
source policy, reference preparation, substantive-text requirement, nonempty
matches, exact identifiers and typed admission still execute. It never changes
a returned rejection into a synthetic approved DTO/trace.

The comparison is bypassed only when `missing_parent_exact` is empty. The current
legacy gate traces missing parent identifiers without independently rejecting
them in its qualification expression. A guard test demonstrated that unconditional
ratio removal would broaden their admission. Those cases retain the original
comparison instead. This does not fix the pre-existing product behavior for
high-ratio candidates with missing parent identifiers; it prevents this experiment
from relaxing that path.

The hook refuses to run if the expected comparison is absent or duplicated. It
records source-function hash, qualification calls, executed ratio checks,
below-threshold checks and parent-exact-preserved checks. Imported aliases are
restored, including aliases loaded during the handler and after an exception.
Never install it in a concurrent/live MCP server. Product files are unchanged.

## Tests

- Real handler integration assertion: unsupported arm **RED**, then **GREEN**.
- Safety guard found the parent-exact exposure: **1 failed / 1 passed** before
  limiting the intervention; **2 passed** after the guard.
- Harness plus adjacent product suites: **156 passed**, including unchanged
  source/lifecycle qualification, exact/table, completion, contiguous-seed and
  ranking tests. OS isolation and full offline gate not rerun.

Existing local Python 3.13 environment; unchanged lock, offline, no auto vectors.
Evidence logs: `/tmp/opencode/ablation-ratio-{red,green,safety,safety-green,regressions}.log`.

## Replay protocol

Same 12 previously inspected public questions and README bytes, original-only.
P and P_MINUS_RATIO each run twice in new processes, alternating arm order.
Each run rebuilds fresh state at exactly the same owned temporary project path.
Only the fixture's temporary-directory provider is controlled; handler settings,
SQL, source identity, corpus and request are otherwise unchanged. This removes
cross-process temporary-root identity as a tie-order confound.

Public inputs and code hashes are checked before/after executions. No labels are
passed to workers. Ordinary processes, no OS namespace isolation. Same-author
development, not a holdout, model-answer evaluation or equivalence test.

Driver: `/tmp/opencode/ablation-ratio-replay.py`.
Artifacts: `/tmp/opencode/ablation-ratio-replay/`.

## Results: original 12-question panel

**48 planned / 48 executed / 48 audit-clean**. All 24 arm/case DTOs were exactly
identical in the second repeat. Both arms used 292 observed SQL searches across
the two repeats and at most 799 DTO tokens. Native lanes matched in all 24 pairs
after explicitly mapping generation UUIDs and fixture file creation mtimes;
original SQL, parameters, metadata and source text remain in the raw artifacts.
Every packet kept `answer_supported=false` and `edit_ready=false`.

Posthoc same-author review: **P 7/11, P_MINUS_RATIO 9/11** sufficient first packets,
**2 wins / 0 losses / 9 ties** on answerable cases. Repeats are not new questions.

- Case 6: removal recovers the four Python lockfiles and declared-intent caveat.
- Case 9: the Russian first-call question gains valid alternative evidence from
  the tools table's default-first-call description. An exact expected sentence
  is not required.
- Case 4: P already had the configuration paths; the standalone E_G loss did not
  transfer to P. Case 8's library-refresh fact still does not appear.
- Case 12: both arms return nonempty context without a documented retry default.

The hook actually executed: 1,430 below-threshold checks were bypassed and 104
parent-exact checks preserved the original comparison across the 24 candidate
runs. These are repeated qualification checks, not unique recovered facts.

## Results: four-document panel

Four existing public docs were staged together: `retrieval-boundaries.md`,
`source-continuation.md`, `change-aware-docs.md`, and `index-cleanup.md`.
16 new self-authored questions: 12 answerable (8 EN / 4 RU) and four EN
unanswerable. Original questions and source hashes saved before execution;
review labels created only after execution, outside worker inputs.

**64 planned / 64 executed / 64 audit-clean**. All 32 arm/case DTOs matched their
repeat exactly. Both arms made 448 observed SQL searches. Maximum DTO tokens:
P 796, P_MINUS_RATIO 800. No answer/edit authority granted.

30/32 native-lane pairs matched after the same UUID/mtime mapping. In case 2's
two repeats, the remaining difference was the order of two source-path parameters
in an identical SQL `IN (?, ?)` predicate: same allowed source set, ordered row
identities, native scores and text. This difference is explicitly retained in
`retrieval-pair-audit.json`, not silently removed as a query change.

| Panel | P sufficient | P_MINUS_RATIO sufficient | Paired wins/losses/ties |
|---|---:|---:|---:|
| Prior README, 11 answerable | 7 | 9 | 2 / 0 / 9 |
| Four docs, 12 answerable | 9 | 10 | 1 / 0 / 11 |

The new win is the Russian `docs_context` budget question: the candidate includes
both estimation methods and the 800-token/three-source limits. P omits the
calculation. Questions about reference expiry/restart and report status definitions
remain insufficient in both arms. The cleanup preview question accepts the
candidate's explicit reviewed-preview instructions and `--apply` command as
alternative evidence; it need not quote the exact preview-only sentence.

**Negative control:** P returned nonempty context on 3/4 new unanswerable questions;
P_MINUS_RATIO on 4/4. The added false admission is the cloud-backup question:
P is empty, the candidate returns unrelated continuation/expiry text with no
backup-service evidence. Some answerable packets also acquire unrelated sources
(case 9 adds continuation and cleanup prose). No answerer ran: these are context
quality problems, not measured hallucinations or abstentions.

New artifacts: `/tmp/opencode/ablation-ratio-four-docs/` and
`/tmp/opencode/ablation-ratio-four-docs-public/`. Same driver, configured with
`ABLATION_PUBLIC` and `ABLATION_OUTPUT`; no second retrieval runner introduced.

## Decision and limits

Across these panels: 28 questions, 23 answerable, five unanswerable, **112 physical
executions**. Descriptively 3 answerable wins / 0 losses / 20 ties, with one added
unanswerable false admission. Do not treat 112 runs as 112 independent questions.
The documents belong to one repository; topical panels are not independent
families or a holdout. Review is posthoc/unblinded and neither statistical
equivalence nor a general quality gain is established.

**Do not delete the ratio filter globally.** The real-P remove-one confirms both
its recall cost and part of its false-admission protection. The intervention is
the ratio test at every actual `qualify_evidence` call in the handler, not just
one early gate. Qualification affects downstream ordering and packing too;
the result does not isolate a particular call-site or prove the ranker useless.

Next minimal experiment: split the shared qualifier by measured call-site so
candidate admission and final coverage/certification can be compared separately
on saved inputs. Keep all exact/reference/source/authority gates and the negative
controls. No product patch, model download, full offline gate or activation.
