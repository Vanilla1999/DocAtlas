# Step 12: bounded live structural replay

This runner is a component integration diagnostic, not a fresh model test. It
reuses `probe_minimal_structure.py`'s passive return-hook and the ordinary real
public `prepare_docs` / `get_docs_context` path on isolated data. No scorer,
retrieval, storage, source authorization or validation is mocked or replaced.

The approved execution plan is
`v2plan/STEP12_LINKED_CONTEXT_CHECKPOINT_RU.md`. Before executing a single
prepare/query, the runner writes `execution-manifest.json` with source, policy,
gold, saved-output, runner and relevant product hashes, questions/case IDs,
guard inputs, counts and proof boundaries. Every invocation requires a new
result directory; a failed or incomplete attempt must be preserved.

## Bounded workload

| Group | Preparation | Context calls | Closure executions | Model calls |
|---|---:|---:|---:|---:|
| Four original Meridian questions | 1 | 4 | Up to 8 | 0 |
| Existing structural fixture plus explicit guard links | 1 | 1 | Up to 2 | 0 |

There are no resource calls. Missing live units produce **BLOCKED**, not a
synthetic substitution or a new lookup. The outer public calls run with
`DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT=0`, `DOCATLAS_CONTEXT_LINKS=off` and
compression off. Baseline/off and one-hop are executed inside the passive
callback while original same-call receipts are live.
The unchanged `EvidenceDocuments` builder performs the same full checked-source
preparation as the Qwen route, without invoking its scorer. Both closures must
leave structural/scoring inputs unchanged.

Meridian uses all six original project documents and the original excluded
module document. The four questions, source bytes, frozen threshold and real
Qwen scores are unchanged. Saved scores map to live units by path, raw-source
SHA256 and exact character span; old snapshot identities never grant access.
The off result must reproduce the saved source rows. Nineteen fact spans come
from the existing independently authored source/gold, not the selector. Fact
counts are measured, not fixed to a previous run's totals.

The guard copies the existing `DOCUMENTS`/`QUESTION` without changing those
constants. Its source-authored additions distinguish a direct link, an
ancestor-only link, a link-only navigation list, a linked body's second hop,
a missing anchor, a document-only target, and an excluded module target. A
literal HTML link to `condition&amp;amp;gate` must select the single-decoded
anchor, never the distinct double-decoded anchor; the correct and forbidden
source sentences are independent expected facts in the same public scenario. The
explicit `Selected` source section is a **component input, not model selection**.
Its required literal facts and forbidden source sentences are fixed in
`inputs.py`, independently of the production link parser.

The targeted post-review guard revision also links from `Selected` back to its
already delivered ancestor: the ancestor's other links must retain ancestor
origin. A raw HTML attribute containing backticks must remain a literal pending
reference, rather than silently changing the target through code masking.

Both groups check exact raw text/hash/spans, project scope, ordinary projection
validation, reconstructed packet size, source/database immutability, and denial
of expired structural provenance after the public call returns. The one-hop
variant must retain all baseline spans. Its full host-only trace is saved
separately; token measurements use the production compact closure summary.

## Run only after checkpoint approval

```bash
.venv/bin/python -m eval.blind_project_context.step12-linked-context.replay --out /ABSOLUTE/NEW/RESULT/DIRECTORY
```

An authorized guard-only recheck uses `--group guard`: one prepare, one context,
two closures and zero models/resources. It does not rerun the four Meridian
questions. The first run's runner/fixture source is retained in
`run-01/provenance` before these targeted revisions.

Results include unchanged ordinary `public_packet` separately from the
reconstructed `structural_replay` packets, exact counts, case metrics and
`PASS_STRUCTURAL_REPLAY_ONLY`, `BLOCKED`, or `FAIL`. A successful diagnostic
does not show a successful final public Qwen response, an installed MCP path,
source-cursor issuance for added rows, answer-model quality, or provider-token
savings. Those boundaries require separate tests; live Qwen is blocked in the
current CPU-only environment without pinned assets.
