# Project context quality protocol

## Claim boundaries

These are in-process self-host measurements through the existing public handler,
not installed MCP agent runs. No production aliases are added or fitted to these
questions. Repository docs were read to author factual expectations only.

Stage 3 freezes the five original user questions supplied verbatim in the
follow-up handoff, plus ten authored compound workflow questions and two
negatives. Original cases carry `provenance: original_user_verbatim`; their IDs
remain stable. The other ten positives and the separate paraphrases are authored
probes, not a historic manual transcript. All five were incorporated before the
first live run.

Stage 10 separates primary, question-only, and independent paraphrase reports.
The latter two are initially report-only, never release-gate evidence. Their
JSON verdict, failed checks, raw payloads, and numeric threshold errors remain
unchanged even when the CLI returns zero to allow report capture. Exceptions
still fail the process. The frozen lanes were subsequently executed; the latest
results are recorded in `IMPLEMENTATION_REPORT.md`.

## Frozen inventory

| Dataset / mode | Positives | Negatives | Policy |
| --- | ---: | ---: | --- |
| `cases.json` / legacy | 15 | 1 | Original alias-contract gate, unchanged |
| `cases.legacy.json` | 15 | 1 | Byte-identical immutable snapshot, not rewritten |
| `natural.json` / with lookups | 15 | 2 | Five verbatim originals + ten authored workflow cases |
| `natural.json` / question only | 15 | 2 | Report-only ablation of the same questions |
| `paraphrases.json` / with lookups | 5 | 1 | Separate bounded report-only dataset |

`protocol.lock.json` is untouched, including its original numeric thresholds
and archival red-baseline values. `lanes.lock.json` freezes new byte hashes,
ordered stable IDs, positive/negative counts, the original protocol hash, and
report-only policy before any new live run. A corpus or protocol byte change
fails loading. Shared paraphrase fact references require the natural fact bank
to pass its own hash check first.

Frozen numeric thresholds: contract pass rate **1.0**, false public tools **0**,
useful live results **13**, Top-1 fact-bearing results **12**, Top-3 relevant
results **15**, attributed original coverage **12**. The existing runner also
retains zero-tolerance false support/contamination and the **3 sources / 800
tokens** budget. No threshold is rescaled for the five-positive paraphrase set:
its absolute-count threshold errors are expected and remain reportable, not a
reason to lower the primary gate.

Every new positive has independent, all-required fact groups for the requested
components, including multiple selection components for the broad original.
Alternatives inside one group are OR; groups are AND. Paths bind visible factual
text, not just a document title or an expected top hit. Multiple maintained
documents may satisfy the same fact. Relevant/allowed paths are the union of
these factual alternatives; the first path is not privileged. Facts from
superseded sources are never new gold. The legacy expectation permitting
`docs/adr/0002-context-retrieval-vs-answer-proof.md` remains archival only.

Architecture, request flow, and evidence selection use `scope=all`; other
natural cases use `scope=project`. The independent evidence-selection paraphrase
also uses `all`. Both positive and negative scope and IDs reach the runner.

The original request-flow case requires the documented MCP input boundary,
`ProjectContextService` query-plan handoff, retrieval gateway's filtered chunks
and provenance, and final source-selection policy. It is not a sync/retry case.
Architecture binds application, domain, transport, and infrastructure duties.
Evidence selection requires domain qualification, application allocation,
mandatory local proof in certification lanes, and retrieval-only project reads.
The public-tools case independently requires all three identifiers with their
usage, not merely a server invocation or first-call/status pair.

Host lookups are natural English single-concept questions, not copied canonical
aliases. Every new positive requires two or three covered supplied lookups.
Explicit public IDs include the original, each supplied lookup, and the
legitimate `get_docs_context` anchor on `natural-request-flow`. Inventory checks
allow each ID in either covered or missing, disjointly. They do not require a
complete original answer. Claimed original coverage must still pass the existing
same-call attribution audit and aggregate frozen threshold.

Question-only omits the lookup argument, removes only `query-lookup-*` expected
IDs, and makes the per-case supplied-lookup minimum inapplicable (zero supplied
lookups). It preserves questions, scopes, original/anchor inventory, facts,
negative cases, and all numeric lock thresholds. It cannot alter primary input
objects or primary reports. No public MCP schema or new harness is introduced.

## Exact commands

Run from the repository root with the project's environment. These contract
commands are hermetic and do not index or retrieve documents:

`run_contract(legacy)` executes alias recognition, the query planner, and the
answer-requirement contract for RU/EN pairs. Natural/paraphrase contracts execute
`build_documentation_query_plan` for each question, checking the explicit public
query inventory and optional lookup semantics. They do not test alias intent
recognition, retrieval relevance, visible facts, or answer support. Reports label
these as `alias_and_query_plan_contract` versus
`query_plan_public_inventory_contract`, with `retrieval_executed=false`.

```bash
DOCATLAS_OFFLINE=1 .venv/bin/python -m eval.project_context_quality_protocol --lane legacy --output /tmp/opencode/project-context-legacy-contract.json
DOCATLAS_OFFLINE=1 .venv/bin/python -m eval.project_context_quality_protocol --lane natural --output /tmp/opencode/project-context-natural-contract.json
DOCATLAS_OFFLINE=1 .venv/bin/python -m eval.project_context_quality_protocol --lane paraphrases --output /tmp/opencode/project-context-paraphrases-contract.json
```

The lanes are executed independently with these commands:

```bash
DOCATLAS_OFFLINE=1 .venv/bin/python -m eval.project_context_quality_protocol --live --lane legacy --output /tmp/opencode/project-context-legacy-live.json
DOCATLAS_OFFLINE=1 .venv/bin/python -m eval.project_context_quality_protocol --live --lane natural --output /tmp/opencode/project-context-natural-live.json
DOCATLAS_OFFLINE=1 .venv/bin/python -m eval.project_context_quality_protocol --live --lane natural --question-only --output /tmp/opencode/project-context-question-only-live.json
DOCATLAS_OFFLINE=1 .venv/bin/python -m eval.project_context_quality_protocol --live --lane paraphrases --output /tmp/opencode/project-context-paraphrases-live.json
```

The default remains the legacy corpus for compatibility with existing CI and
callers. `--lane natural` is an explicit separate gate, not a replacement of
legacy expectations. CI's existing Project Docs report upload now uses
`if: always()` so a failed gate does not suppress its artifacts.

For a real installed coding agent, use the existing
`eval/agent_developer_v1/INSTALLED_MCP.md` and
`scripts/run_installed_mcp_agent_benchmark.py`. The main owner handles that run;
this work adds no harness and makes no installed-agent or public-package claim.
Do not run both harnesses and then merge their denominators or verdicts.

See `BASELINE.md` for historical evidence and `IMPLEMENTATION_REPORT.md` for
verification results, frozen hashes, and the diagnostic-manifest owner handoff.
