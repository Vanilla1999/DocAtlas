# Direct DocAtlas questions sidecar

This report-only sidecar contains the 15 English questions from the direct-question quality investigation. It is intentionally separate from both frozen `eval/project_context_quality` and `eval/project_context_quality_v2`; their corpora, locks, thresholds, historical verdicts, and denominators are unchanged.

Each case is executed question-only through the existing self-host public handler with `scope="all"` and no `lookup_queries`. The sidecar reuses `scripts/run_project_docs_self_host_gate.py` and its `LiveCase.required_fact_groups` semantics: alternatives inside one fact group are OR, fact groups are AND, and a fact is credited only when the exact witness text is visible in a returned source with the expected path. Status, source/citation identity, three-source and 800-estimated-token bounds, and the project-read `docs_context` safety contract are checked separately.

`cases.json` records the baseline commit and Git blob SHA for every source used as an accepted witness. Tests recompute those Git blob identities from current bytes and verify every witness still exists before the live run. This sidecar is evaluator/test data only and is not part of the project documentation catalog or production retrieval index.

The direct lane does not claim to be an independent holdout: its questions and criteria are exposed development cases. It is also not an installed-agent result. The self-host runner uses the repository's normal temporary isolated state and FTS-only offline sync path; installed stdio MCP and host-agent checks remain separate claim boundaries.
