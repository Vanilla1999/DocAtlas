# Frozen-CI reproduction of the development probe

GitHub Actions run **36701177026**, job **109840717597**, completed successfully
on **b54faee8780a6babac79a588d96861578079c7f2**. The checkout was clean. Python
3.12.14 used the unchanged project lock via `uv sync --frozen --extra dev`.

Downloaded artifact **11090200607** was verified against SHA-256
`9bd5ce49e9a8d6dfd6ba2f688f5bc0b065f2d62ebb5e2f3fe965f72c1774440f`.
Its source-head file and report revision agree. All 21 experiment/test/workflow
files in its source archive match the locally tested files. JUnit records
**116 passed, 0 failed, 0 skipped**. All **10 real-handler calls executed** and
passed the native canonical/budget audit. This is not a full-repository CI pass.

| Question | Original | Manual lookup | CI DTO tokens original / lookup |
|---|---|---|---|
| Typer mixed | ABSENT | COMPLETE | 286 / 463 |
| Typer RU | ABSENT | COMPLETE | 235 / 458 |
| Typer EN | COMPLETE | COMPLETE | 798 / 458 |
| HTTPX default timeout | ABSENT | COMPLETE | 754 / 717 |
| HTTPX disable Client timeouts | COMPLETE | ABSENT | 778 / 793 |

The **2/5 versus 4/5** outcome, including the HTTPX regression, reproduces the
local development observation in the frozen CI environment. Packet sizes differ;
they must not be copied from the local environment as CI measurements.
This repeats the same five reviewed questions, NOT ten new independent tasks.
The lookups remain manually supplied. No language profile, experimental assembly,
live planner, answer model, oracle or blind judge was used. H1/H2/H3 remain null.

Raw packets and traces are in the workflow artifact, not in Git. The artifact is
retained for seven days; preserve it locally for later diagnosis. See
[DEVELOPMENT_REPORT.md](DEVELOPMENT_REPORT.md) for the observed loss boundary,
prototype limitations and the locally blocked full offline suite.
