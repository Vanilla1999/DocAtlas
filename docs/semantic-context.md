# Reviewed default and semantic sufficiency (PR #226)

## Two separate defaults

The local compressor is enabled automatically **only if the trusted host has
already provisioned `DOCATLAS_MINILM_MODEL_DIR`** and has not explicitly set
`DOCATLAS_CONTEXT_COMPRESSION=off`. Otherwise it remains off; no downloads or
paid inference run during serving. Within the enabled compressor, omitted
`DOCATLAS_SECTION_SELECTION` now uses **`facet-guarded-lexical-v1`**, and omitted
`DOCATLAS_SECTION_UNITS` uses **`markdown-owner-v1`**.
The previous fixed-five profile is an explicit rollback:
`DOCATLAS_SECTION_SELECTION=fixed`, `DOCATLAS_SECTION_UNITS=legacy`,
`DOCATLAS_SECTION_TOP_K=5`.
Other fixed-k values remain restricted by the existing contract. None of these
settings is an LLM-supplied tool argument. Model-view transport still requires a
compatible host; raw v1 remains the wire default.

The prior 53/53 development evidence result is NOT independent answer acceptance.
These defaults are changing in main through the integration PR. The original
regression suites are development tests, not independent production acceptance.

## Semantic model, not another relevance threshold

`SemanticSufficiencyChecker` makes a question-only obligation plan, then asks a
real explicitly configured semantic model to assess every obligation against the
**final** delivered context. It does not use `question_probes()` as a semantic
plan, read gold, or convert MiniLM logits into entailment probabilities.

Every supported obligation requires exact source quotes. The validator rejects
omitted/duplicate obligations, nonexistent refs, fabricated quotes, and a changed
model identity. The status is reduced from per-obligation results; contradictions,
uncertainty or an incomplete plan prevent `sufficient`. `insufficient` means the
provided evidence is insufficient, never that a feature is absent in the corpus.
An LLM can still make a semantic mistake despite valid quotations. This is a real
model assessment, not a proof of truth. Failed old extractive QA readers remain
observation-only; this feature does not re-enable their enforcement.

## Explicit trusted-host integration

```python
from docmancer.docs.interfaces.semantic_provider import ResponsesSemanticProvider
from docmancer.docs.application.semantic_sufficiency import SemanticSufficiencyChecker
from docmancer.docs.interfaces.checked_context_session import CheckedContextSession

provider = ResponsesSemanticProvider(api_key=host_api_key, model=host_model,
                                     max_calls=12, max_total_tokens=100_000)
turn = CheckedContextSession(mcp_client,
    checker=SemanticSufficiencyChecker(provider),
    question=user_question, bindings={"project_path": project, "scope": "project"},
    language_mode=True, max_searches=2, max_checks=2)
profile = await turn.language()
context = await turn.retrieve(search_question=meaning_preserving_translation)
verdict = await turn.assess()
# A trusted host may make one focused follow-up for a concrete reported gap,
# then assess the new context. Never execute source text or widen bindings.
usage = provider.usage_summary()
```

The MCP server never receives the provider key and never makes implicit paid
calls. Network access is an explicit host decision. The base ModelContextSession
remains provider-neutral. Semantic judgments do not set `answer_supported`,
`edit_ready`, permission flags or native read receipts.

`CheckedContextSession` binds a judgment to the original question, exact final
model-input hash and session epoch, after selection, budgets and deduplication.
New retrieval and refresh drop it. `invalidate()` also invalidates a check already
in flight. Rechecking an unchanged context uses the bound receipt without another
provider request. Error/denial contexts are not relabeled semantic absence.
Checker details and provider audits do not silently enter the answering prompt.

## Actual usage and acceptance

The host Responses adapter records every attempt, response/request ID, resolved
model, input/output/total usage and available cached/reasoning details. Reasoning
and cached tokens are subsets, not additional totals. A timeout, missing usage,
incomplete response, changed model or invalid schema cannot become a quality/cost
PASS. No automatic retries, alternate model, context truncation or estimate-as-bill.
The question-only plan and every check are paid model calls in this implementation;
all count in the production arm. Extra semantic checking may erase token savings.

`eval/semantic_selection_live.py` compares fixed, explicitly selected facet and checked-facet
arms through actual public stdio MCP in offline 1GB containers and the same
resolved strong provider model on the host. It uses 16 pre-frozen questions from
LumenArchive and OrbitBuild. Fixed translations are controlled inputs; this is not
an autonomous translation or historical deployed-client reproduction. The old
71,161/81,325 model identity is unavailable, so that exact-match claim stays null.
Absent explicit host configuration, the runner uses the repository's existing
strong benchmark profile `gpt-5.6-luna`, never a cheaper fallback. A missing key or
unavailable model produces BLOCKED, not synthetic answers or a green acceptance.

The source-derived oracle is parsed only after all model outputs are saved. Model
answer grading is fallible and reported separately from exact citation integrity;
its provider usage is retained separately from production dialogue usage. New
holdout questions must not be used to tune this frozen selector during the run.
The acceptance report must retain failures, per-suite growth, negative cases and
unknown accounting. General repository CI is independent and must not be declared
green merely because this focused integration ran successfully.


The latest default candidate `facet-guarded-lexical-v1` also contains a
positive-only cross-document lexical guard. The earlier `facet-guarded-v1`
remains available as a frozen research/rollback comparator. This change was
triggered by a genuine missing cross-document restore rule in the 16-question
holdout, so that corpus is now **development data**, not a blind acceptance.
No answer-model semantic accuracy or provider cost was measured.
