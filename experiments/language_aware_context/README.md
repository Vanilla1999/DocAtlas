# Language-aware context experiment — draft

Base: `main` at `58c7f37c2a5ef686bcd6562abbade91ba94e347a`.
Branch: `experiment/language-aware-context`.

This is an isolated experiment, not product activation. No old task-44 commits
are imported. Production code, the MCP surface, P0 and protocol v3 are unchanged.
No MPNet/BGE inference is introduced.

## Current evidence

Read [DEVELOPMENT_REPORT.md](DEVELOPMENT_REPORT.md), [CI_RESULTS.md](CI_RESULTS.md)
and [STATUS.json](STATUS.json). A full source archive is now available locally;
the native lexical handler ran both locally and in the frozen CI environment.
On five already reviewed questions, manually supplied lookups changed complete
packets from 2/5 to 4/5, with three gains **and one regression**. This is not A–E,
not independent data and not proof of language-profile or assembly improvement.
All 116 targeted tests passed locally and in diagnostic CI. Focused product tests
passed 106/106 in both local archive variants. The full local suite is blocked by
missing dependencies; overall repository CI is not asserted green.

## Components

- [PLAN.md](PLAN.md) and [EXECUTOR_PROMPT.md](EXECUTOR_PROMPT.md): T0–T9 protocol.
- `reference_core.py`: profile binding, literal preservation and window proposals.
- `source_profile.py`: bounded, conservative prose extraction and RU/EN/unknown
  measurement. Not a universal detector, ACL resolver or production cache.
- `baseline_probe.py`: real main-branch handler, explicit hash-checked source set,
  exclusive report writes and deterministic trace-ID-set serialization.
- `ci_diagnostic.py`: actual Typer/HTTPX development calls and narrow canonical
  clause checks. Manual lookups are explicitly labelled; no generated answers.
- Five registered test modules and diagnostic inventory shards.
- `protocol.proposed.json`: proposed parameters, NOT frozen evaluation data.

Historical simulated 11/11 and Grounded-like 6/7 are NOT evidence for this PR.
A must include the agent's existing lookups; A/C and B/D each reuse identical saved
queries. E compares a generic RU/EN prompt with the profile. These arms still need
real planner output, new scopes/labels, frozen parameters and blind judging.

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
