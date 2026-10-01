# Language-aware context experiment — draft

Base: `main` at `58c7f37c2a5ef686bcd6562abbade91ba94e347a`.
Branch: `experiment/language-aware-context`.

This is an isolated experiment, not product activation. No old task-44 commits
are imported. Retrieval runtime, the MCP surface, P0 and protocol v3 are unchanged.
Installed skill templates now include a final-evidence completeness check.
No MPNet/BGE inference is introduced.

## Current evidence

Read [FLOW_REPORT.md](FLOW_REPORT.md), [LIVE_PILOT_REPORT.md](LIVE_PILOT_REPORT.md),
[STRONG_MODEL_REPORT.md](STRONG_MODEL_REPORT.md), the
[skill smoke report](skill_smoke/README.md) and [STATUS.json](STATUS.json).
The known flow regression improves from 482 PASS / 1 FAIL to 483 PASS / 0 FAIL
with the explicit ordering hook. Weak Qwen showed no paired gain. The strong
planner has a one-question profile-specific signal, with rubric-sensitive
aggregate counts and no retained historical answer generations. The separate
four-question smoke retains actual answers and final packets but has no
skill-off control. Overall repository CI is not asserted green.

[DEVELOPMENT_REPORT.md](DEVELOPMENT_REPORT.md) and [CI_RESULTS.md](CI_RESULTS.md)
preserve historical viewed-task measurements, not independent acceptance data.

## Components

- [PLAN.md](PLAN.md) and [EXECUTOR_PROMPT.md](EXECUTOR_PROMPT.md): T0–T9 protocol.
- `reference_core.py`: profile binding, literal preservation and window proposals.
- `source_profile.py`: bounded, conservative prose extraction and RU/EN/unknown
  measurement. Not a universal detector, ACL resolver or production cache.
- `baseline_probe.py`: real main-branch handler, explicit hash-checked source set,
  exclusive report writes and deterministic trace-ID-set serialization.
- `ci_diagnostic.py`: actual Typer/HTTPX development calls and narrow canonical
  clause checks. Manual lookups are explicitly labelled; no generated answers.
- Registered experiment tests and diagnostic inventory shards.
- `skill_smoke_run.py`: source-hash-checked replay retaining complete raw traces;
  no automatic semantic grading or model inference.
- `protocol.proposed.json`: proposed parameters, NOT frozen evaluation data.

Historical simulated 11/11 and Grounded-like 6/7 are NOT evidence for this PR.
A must include the agent's existing lookups; A/C and B/D each reuse identical saved
queries. E compares a generic RU/EN prompt with the profile. E ran in the strong
pilot, not the weak pilot; neighbor assembly remains untested. Independent new
scopes/labels, frozen parameters and external judging remain acceptance work.

## Reproduce development diagnostics

From a full Git checkout; do not change the lock to force a pass:

```bash
uv sync --frozen --extra dev
DOCATLAS_OFFLINE=1 DOCATLAS_AUTO_VECTORS=0 .venv/bin/python -m pytest \
  tests/docs/test_language_aware_context_reference.py \
  tests/docs/test_language_aware_context_probe.py \
  tests/docs/test_language_ci_diagnostic.py \
  tests/docs/test_language_source_profile.py \
  tests/docs/test_language_trace_serialization.py -q
DOCATLAS_OFFLINE=1 DOCATLAS_AUTO_VECTORS=0 \
.venv/bin/python -m experiments.language_aware_context.ci_diagnostic \
  --output /tmp/docatlas-language-probe-UNIQUE
```

The output directory must not already exist. `EXECUTED` means the handler and
packet audit ran, not that the context is sufficient. Empty valid terminal
packets are misses. Import/runtime/audit errors are not quality measurements.
The GitHub workflow uploads revision-bound raw evidence even after failures.

For other development sources, use `baseline_probe --help`: the corpus requires
an explicit source manifest stored outside the source directory. Supplied lookups
are not live agent output. Library documents copied as project fixtures do not
test dependency-version resolution. Keep raw runs, credentials and private corpora
out of Git. Keep this PR draft until its actual acceptance gates are satisfied.
