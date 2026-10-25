# Local coverage-aware section selection (experimental)

This study replaces the selection decision after native source admission. It
builds on the translated-query receipt fix in PR #225. It does not change source
acquisition, authorization, question text, model weights, the public MCP schema,
or default behavior. Never treat its ranking signals as semantic sufficiency.

Enable the existing local MiniLM compression and explicitly select one policy:

```
DOCATLAS_CONTEXT_COMPRESSION=minilm-sections-v1
DOCATLAS_MINILM_MODEL_DIR=/absolute/provisioned/model
DOCATLAS_SECTION_SELECTION=facet-guarded-v1
```

Policies compared, with no fixed section count:

- `mmr-budget-v1`: marginal relevance with lexical word-set Jaccard diversity,
  frozen relevance weight 0.7. Its estimated source-token allowance equals the
  same request's B1 proposal. This is a low-cost comparator, not semantic MMR.
- `facet-cover-v1`: full question plus literal clause/list slices outside code,
  quotes and brackets; choose a small set retaining the best observed MiniLM
  ranking score for each probe. Cost breaks equal-ranking choices. A literal
  probe is not a verified semantic requirement; top rank is not entailment.
- `facet-guarded-v1`: probe winners plus the full B1 proposal, removing only
  identical selected section IDs. This is a conservative comparison candidate,
  not a claim that a score gap certifies completeness. It may cost more tokens.

All policies preserve whole admitted source rows, exact spans and source
identity. No new reads, generated summaries or paid model calls occur. The full
negotiated machine packet is still bounded at 12,000 tokens. Budget-induced
removal is explicit (`truncated`, `budget_limited`) and recorded separately from
ranking decisions. No `answer_supported` or edit authority is granted.

The 8,192-forward-pass and 60-second MiniLM bounds apply across the entire probe
set, not per probe. There is an explicit 16-probe limit, no silent probe or query
truncation. Unsupported-language clauses are not translated by this selector.
Diagnostics remain private and record per-probe scores only when the existing
observer is enabled.

## Evaluation

`eval/coverage_selection_integration.py` reuses real SQLite fixtures and the
independent V40 source-span oracle. Each arm runs a non-editable installed wheel
through public stdio MCP under an offline, two-CPU, hard-1-GB container. The V40,
New16 and fresh N01-N08 input bytes and gold remain unchanged. These are all
KNOWN regression suites, not a newly blind holdout. The new comparison uses one
search per question; the old scripted follow-up/history totals are not directly
comparable.

Five policies x 64 questions = 320 actual stdio searches and 320 uncompressed
public baseline acquisitions. Candidate fingerprints must match across policies.
Gold is assessed after delivery, never passed to retrieval, ranking or prompts.

Acceptance checks every required fact against both fixed5 and B1, not just the
average number of facts. Accuracy dominates token count. Failed comparators are
retained in the report. Context tokens use o200k_base and exclude private metadata.
Provider usage is null and final strong-model answer quality is not tested by
this workflow. Passing these source checks does not establish those properties.

No default promotion is performed automatically. Final results belong in the
PR report with the tested commit and actual CI artifact references.
