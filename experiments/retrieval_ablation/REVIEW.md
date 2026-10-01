# Implementation review

Reviewed slice: T00–T04 internal diagnostics, not an alternate public retrieval
runtime. Implementation commit `d60a9c0d3eb279858c0ab41913eaf6ac7097f2f0`;
post-review corrections `00e83b1334c883cea8f6c2b3512cdd00ee92a1c9`.

Method: self-review by the implementing assistant, static diff inspection,
behavioral tests against the real SQLiteStore, and real-handler CI. This is not
an independent maintainer approval. Exact executions and limitations are recorded
in STAGE_REPORT.md and ABLATION_REPORT.md.

## Findings fixed

| Finding | Evidence and correction |
|---|---|
| Per-probe/AND–OR overexposure in the initial diagnostic prototype | Actual RED: 16 returned rows against total cap 4. Quotas now apply at each native SQL cursor, share one probe allocation, and count duplicates. This was a harness defect, not a claim that the unchanged product violates its own contract. |
| Freeze manifest symlink bypass | Actual RED: replacing `freeze.json` with a symlink was accepted. The manifest leaf and ancestors are now checked, as are source/input/output paths. |
| Forged quality/holdout metadata | Actual RED: `SUFFICIENT` and independent-holdout flags could be attached to a diagnostic freeze. Both now fail closed. |
| Runtime flags not part of the freeze identity | Actual REDs: changing offline, automatic-vectors or hash-seed flags was accepted. All three are now pinned; preflight also requires an explicit zero hash seed. |
| Missing-arm denominator | Actual RED: reviewing only A silently made planned runs equal one. The declared pair remains P/A; missing arms are listed and duplicate arm results are rejected. |

The SQLite connection observer delegates the original transaction exit behavior.
It does not close a connection earlier than production. Instrumentation is
process-local, restored after exceptions and never installed in a concurrent
server. Full-handler tests compare the complete DTO without deleting volatile
fields, plus actual SQL/parameters, search counts and index bytes.

One fixture initially used `obsolete`, which the real ingestion contract
normalizes to `active`. It was corrected to the supported `superseded` state;
production lifecycle policy was not weakened to make the test pass.

## Open blockers and limits

**P1 — Completed paired CI is red, with two newly observed failures.** On 5,078
common offline testcase IDs, base has 20 failures and head has 22; all 51 newly
added tests passed. The two existing tests newly failing on head require a
registered follow-up read but receive empty `read_next`. Their cause has not
been isolated, so they are not dismissed as flakes or attributed to a component
without evidence. Two old failures also show changed observable content. See
PAIRED_REGRESSIONS.md and retained raw JUnit. This branch is not merge-ready.

**P1 — No safe public packet adapter for A.** The diagnostic source checks are
not the entire qualification/authorization contract. Reference/API ownership,
combined-window validation and library-scope/version handling have not been
certified for an alternative packet. A deliberately returns no packet and no
answer/edit authority. Do not call T02 or the public-packet portion of T04 done.

**P1 — No OS-enforced private-gold isolation.** Explicit manifests and request
allowlists prevent accidental label ingestion, but the process is not a
filesystem sandbox and the unchanged P audit imports evaluation helper modules.
This is not suitable for a blinded independent quality evaluation. T03 is only
the freeze/staging portion.

**P2 — Uncapped raw recall / first-loss is not established.** The observer sees
individual SQL lists before custom ranking, but preserves original SQL caps.
Saturated lanes remain explicitly incomplete. There is no extra search to obtain
a conveniently expanded trace; no precise blame is assigned to a soft threshold.

**P2 — Scope and cost are deliberately narrow.** Fixtures use supported project
Markdown. A's pre-policy pass scans the active index before bounded exposure;
reported display bytes are not physical I/O or a complete memory measurement.
Its latency is not comparable to P as a production-performance result. Full
source scan construction is an experimental adapter, not a proposed default.

## Disposition

Keep this branch as a work-in-progress opt-in diagnostic contribution, not a
merge-ready change. The two new paired failures remain unresolved. No product rules should
be deleted, thresholds changed, or public retrieval activated on these results.
The full T00–T04 deliverable remains partial at the blockers above; T05–T12 are
outside this first slice. Semantic quality and non-inferiority remain unmeasured.
