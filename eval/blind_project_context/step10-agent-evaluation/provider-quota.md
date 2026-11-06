# Step10 batched candidate: provider quota blocked answer evaluation

Historical record. A later single renewed-quota Terra run completed successfully;
see [renewed-results.md](renewed-results.md). The 429 evidence below is unchanged
and no longer describes current provider availability.

Run: `/tmp/opencode/terra-step10-batched`; product wheel **0651** (main-agent identifier).
All **16** receipts report `exit=1`, `censored=false`. Every trace contains
`provider.quota`, provider status **429**, error **`usage_limit_reached`**, and
message **“The usage limit has been reached”**. There are **no final answers**.
This is an operationally blocked evaluation, not a 0/16 answer-quality score.
The existing valid wheel **663e** quality result remains unchanged.

## Exact reset evidence

- Response body `resets_at`: **1794381828** or **1794381829**
  → **2026-11-11 07:23:48–49 UTC**.
- `X-Codex-Primary-Reset-At`: consistently **1794381829**
  → **2026-11-11 07:23:49 UTC**.
- Active limit `premium`; plan `prolite`; primary used **100%**;
  primary window **10080 minutes**. Preserve the one-second body/header difference.
- Exact per-session reset intervals, event timestamps, session IDs and trace
  SHA256 values are in [provider-quota.json](provider-quota.json). Original
  `error.response.body` strings remain in the identified traces.

## Work performed before quota

| Session | Completed model steps | Input | Cache read | Output | Completed source call |
|---|---:|---:|---:|---:|---|
| L0/T01-en | 3 | 5,377 | 2,944 | 99 | 154 rows; 48,944 o200k tokens; 57.374 s |
| L0/T01-ru | 3 | 8,320 | 0 | 98 | 157 rows; 49,532 o200k tokens; 109.957 s |
| Remaining 14 sessions | 0 recorded | 0 recorded | 0 recorded | 0 recorded | None |
| **Total recorded** | **6** | **13,697** | **2,944** | **197** | **2** |

Recorded input including cache: **16,641 tokens**. Cache write and reasoning
tokens are zero in the recorded completed steps. Session exports corroborate
these sums; they are not counted a second time. There were six tool calls overall.
No usage is reported for quota-rejected model requests; actual billed cost is
unknown. **Do not label all sixteen attempts zero-cost.** Source-result token
counts describe produced tool text, not additional proven provider input usage.

Both native `docatlas_get_docs_context` calls began before the first quota
response. Both completed `status=ok`, with `truncated=false` in the trace, before
their respective next model step failed. The Russian call completed after the
English session had already hit quota. Calls overlapped; their durations are not
additive wall time. Delivery of source text alone is not a measured answer.

## Command and review boundary

```sh
/tmp/opencode/step10-final-py313/bin/python eval/blind_project_context/run_gap_agent_study.py \
  --out /tmp/opencode/terra-step10-batched \
  --prepared-root /tmp/opencode/step8-corpora2 \
  --executable /tmp/opencode/step10-final-py313/bin/doc-atlas \
  --arm minimal-context \
  --model-dir /tmp/opencode/step10-mini-assets \
  --policy /tmp/opencode/step9-gap-resolution/eval/blind_project_context/step10-calibration/measurement/policy.json
```

This review only reads existing artifacts. No retries, quota workarounds,
provider switches, tuning, or production changes were performed. The main
agent's independent local v2 own-body-gate work is not assessed here.
