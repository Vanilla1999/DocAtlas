# Native evidence sufficiency experiment

## Reviewed outcome, 2026-10-28

Do not promote the three experimental policies. Fresh installed-client CI runs
[40503271393](https://github.com/Vanilla1999/DocAtlas/actions/runs/40503271393)
and [40503271385](https://github.com/Vanilla1999/DocAtlas/actions/runs/40503271385)
completed on `840ddef6f18acf7f5dd0d1a78bfe9338996f73ae`.
The detailed [audit and errata](../reports/native-sufficiency-20261027/AUDIT_20261028_RU.md)
supersede the earlier interpretation of the local measurements.

On V40, v2 preserved 32/32 required witness groups; the rescues added no groups
and increased first-page tokens. On NS16, preserve delivered 36/36, v2 and
obligation 27/36, and constraint/combined 28/36 under the unchanged strict oracle.
However, two oracle groups overconstrain the required source combination:
the delivered retention rule already answers the legal-hold question, and the
delivered security rule already answers the restrictive-file-permission clause.
The apparent constraint rescue is therefore not a demonstrated new fact.
A separately disclosed post-hoc review of these two alternatives gives every
candidate, including v2, 29/36. Seven real content gaps remain. Gold was not
edited, and this review is not independent semantic acceptance or answer grading.

## Implemented alternatives

This experiment is stacked on PR #230 at
`40cfc413f8060b3d16fe962f6f9fe26bdfd27114`. The default remains
`guarded-cover-v2`; no semantic completeness certificate is introduced.

| Policy | Behavior |
|---|---|
| preserve | Existing page-filling control |
| guarded-cover-v2 | Unchanged native selector |
| guarded-obligation-v1 | Append acquired owners carrying still-uncovered literal query features, including a single feature |
| guarded-constraint-v1 | Append acquired owners with restriction language connected by a shared identifier or at least two query-topic features |
| guarded-combined-v1 | Apply both additive recoveries |

Here obligation means literal lexical features, not an inferred semantic plan.
All policies operate only on already admitted rows. They cannot recover missing
upstream documents, prove absence, certify answerability, or generate answers.
Empty v2 selections are not rescued by these policies. Whole acquired owners and
the v2 selected prefix retain original text and priority; signed continuation,
permissions and provenance remain unchanged. Additional owners can still exceed
the unchanged 3,000-token transport ceiling. Actual delivered spans, not selected
row counts, are the measurement boundary.

A provisioned MiniLM remains on the separate preserve-minilm path. These tests
exercise normal native installation without MiniLM assets, context compression
off. Existing unvalidated QA mechanisms are not enabled as evidence vetoes.
The selector hash remains
`81c0e094fb5377923bee595562846f0ef6aa576a23fb6d3708c3d06cc36b4abb`.

## Frozen evaluation contract

V40 sources, questions and gold are unchanged. NS16 adds 16 synthetic fictional
questions and 16 documents, 36 documented claims and four unsupported requested
claims, including distributed conditions, languages, versions and distractors.
It is a development/challenge corpus, not a population-level reliability claim.
No gold or case identifiers enter retrieval or selection. Do not retune the
selector against the revealed challenge answers.

Each corpus uses one mixed project, real SQLite, a non-editable installed wheel,
public stdio MCP and actual pinned OpenCode 2.1.2 at
`a517687fde98a7329ada3ae644a01a9fc6c4e99e`.
The harness independently compares visible source spans to the original files.
An empty witness list never counts as a verified unknown response. Missing
before native selection and admitted-but-not-delivered are distinct outcomes;
the latter requires trace inspection to distinguish selection from pagination.
Infrastructure PASS and candidate-quality PASS/FAIL remain separate.

Source text, coordinates and scope/version provenance, V40 signed pagination and
tamper rejection, and unchanged source/SQLite state are checked in installed CI.
Public content_sha256 is an upstream projection fingerprint, not necessarily the
hash of a displayed snippet; exact snippet bytes are checked separately.
First-reply o200k_base tokens include framing and signed cursor data. Small
run-to-run variation can affect what fits at a page boundary.
Recorded latency is sequential and affected by cold/warm execution order.

No answering model is used: answer_model_calls=0 and provider_usage=null.
Final-answer accuracy, correct unknowns, full dialogue cost and file-read counts
remain NOT_TESTED. A strong-model semantic gate and targeted upstream recovery
are not implemented by these three lexical ablations.

## Reproduction and audit trail

Use `.github/workflows/native-sufficiency.yml` for this experiment. The earlier
branch-specific copy in native-opencode.yml has been removed; that workflow is
restored to PR #230's original behavior. The dedicated experiment remains intact.
No duplicate expensive run is needed for the report-only/CI-routing correction.

```bash
python -I eval/native_sufficiency_integration.py \
  --repo /path/to/DocAtlas \
  --work /path/to/fresh-work \
  --out /path/to/fresh-results \
  --opencode /path/to/pinned-opencode
```

Use the isolated installed-wheel Python and Bun. Fresh CI does not pass
--replay-completed-v40. The recovery option was used only for the older local
run after a scorer-only hash assumption failed; it is not the basis of the
fresh CI results cited above.

Artifacts contain tested-source archives, PRODUCT_CHECKPOINT.json, every raw
MCP reply, per-policy metrics, OPENCODE.json, SUMMARY.json and SCORECARD.md.
The 28 October audit downloaded both immutable ZIPs, matched their published
SHA-256 digests, independently recounted 560 OpenCode first replies and rescored
all 160 NS16 outputs against unchanged source spans. V40 witness grades were
read from CI, not independently regraded during that offline audit.
Historical local scorecards are retained in reports/native-sufficiency-20261027.
