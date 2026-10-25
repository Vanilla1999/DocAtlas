# Local coverage-aware section selection (experimental)

## Selected candidate and status

`facet-bundled-cover-v1` is the accuracy-first candidate from the recorded study,
not a new default. It retained 97/97 required witness groups on 53 documented
questions, but used 11.19% more model-visible context tokens than fixed5. No
compared candidate both preserved every control fact and reduced total context
tokens. See [measured results](coverage-selection-results.md).

PR #227 is stacked on the translated-query admission fix, PR #225. The source
selection implementation tested at `41f2072d450bf9692e8a81deb59a9d85c54d6eef`
is opt-in. Existing defaults and public schemas are unchanged.

```
DOCATLAS_CONTEXT_COMPRESSION=minilm-sections-v1
DOCATLAS_MINILM_MODEL_DIR=/absolute/provisioned/model
DOCATLAS_SECTION_SELECTION=facet-bundled-cover-v1
DOCATLAS_MCP_MODEL_VIEW=1
```

The last setting enables the compact model-facing representation used in the
comparison; a compatible client must retain its private reference ledger.

## What is replaced

The replacement acts after native source admission and before normal packet
projection. It does not acquire new sources or change question text, model
weights, authorization, snapshot/version/scope checks, or citation identity.

1. Keep the original full scoring question. Add exact clause/list views outside
   code, double quotes and bracketed expressions. These literal views are NOT a
   certified semantic decomposition. Contextual variants prepend the original
   first sentence/question to avoid losing the subject of a follow-up clause.
2. For the selected candidate, combine already-acquired sections of one native
   source identity when their concatenated scoring text is at most 512 MiniLM
   tokens. Long acquired sources remain sectioned. This does NOT read a whole
   file, fill gaps, follow links or import unacquired neighbors.
3. Score each unit for each view using the same pinned CPU MiniLM. Select a set
   retaining each view's best observed ranking score. Cost is a tie-breaker,
   not a calibrated semantic-coverage optimizer.
4. If every winner is a bounded source bundle, retain only those winners. If
   not, add the original B1 proposal as a conservative long-source reference.
   Thus the gap heuristic is NOT completely removed from the fallback path.
5. Deliver unchanged original rows. One selected bundle can contain many source
   sections; calling it one unit does not mean that their text costs one section.

## Safety and resource boundaries

All source rows, exact text and coordinates retain their original identities.
No generated summaries, new model assets or paid model calls enter selection.
The full negotiated machine packet remains bounded at 12,000 tokens. Removing
whole units for this budget explicitly sets `truncated` and `budget_limited`.
Ranking-target coverage and budget loss are recorded separately in private
observations. Neither ranking nor grouping certifies answer sufficiency.

The 8,192-forward-pass and 60-second scoring allowances are shared across all
views of one request, not reset for each view. There is an explicit 16-view
limit. Overlength contextual views fall back to the unchanged full question,
with recorded diagnostics; source text and the original question are not
silently token-sliced. Unsupported languages are not translated here.

## Compared policies retained for reproducibility

- `mmr-budget-v1`: frozen 0.7 normalized relevance / 0.3 lexical word-set Jaccard
  diversity, with the B1 proposal's estimated source-token allowance. This is a
  lexical comparator, not a reproduction of an embedding-based MMR paper.
- `facet-cover-v1`: literal-view winners only; loses required control facts.
- `facet-guarded-v1`: literal-view winners plus B1. It passed the no-lost-fact
  regression gate but left two N04 witness groups missing.
- `facet-cover-v2`, `facet-guarded-v2`: contextual-view variants; both showed
  control regressions. Subject preservation alone does not ensure good ranking.
- `facet-bundled-v1`: contextual views, short-source bundles and B1 union;
  complete documented coverage in this study, but higher cost than the selected
  `facet-bundled-cover-v1`.

These are explicit experimental choices, not recommendations to activate the
failed comparators. No score is a probability or entailment proof.

## Reproduction and measurement boundary

`eval/coverage_selection_integration.py` builds real prepared SQLite fixtures
and uses an installed wheel through public stdio MCP. Run its documented
`--suite` and `--policy` options inside the existing
`eval/minilm_sections.Dockerfile` image with `/opt/venv/bin/python -I`,
`--repo /repo --model /model`, and fresh absolute `--work` / `--out` paths.
Network is disabled during retrieval; use two CPUs and a hard 1-GB memory cap.

The nine-policy study makes 576 stdio search calls, 576 uncompressed public
handler acquisitions, and 72 language preflights. Immutable earlier arms are
reused only after checking exact revisions, all input hashes and both acquired
and actually scored source identities. Gold is read for post-delivery scoring,
not given to product selection or the answering model.

The comparison workflow is an archival development experiment. Its recorded
prior-run downloads expire after the CI artifact retention period (30 days).
After expiry, reproduce arms from the source revisions listed in the results,
using the integration driver, rather than interpreting a missing artifact as a
product failure or rerunning an unmatched comparison.

All 64 questions are KNOWN regression/development cases. No blind held-out
acceptance or statistical generalization claim was established. Actual compact
context tokens use o200k_base and exclude private metadata. Final answers and
full-dialogue provider usage are not source-coverage metrics.

A separate bounded answer-replay workflow and script are included. Its recorded
attempt stopped before any model request because `OPENAI_API_KEY` was not
available to the CI job. The configured model was not substituted, and its
availability was not tested. This replay, even when run with credentials, is
one-shot answering, not an autonomous client/history experiment.
