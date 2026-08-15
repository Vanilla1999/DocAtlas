# Project-answer quality protocol v1

This provider-free protocol freezes realistic, neutral microrepositories and
executes the production path rather than evaluator-prepared candidates:

`temporary repository -> sync_project_docs -> production SQLite index -> production retrieval -> evidence selection -> public get_docs_context -> canonical bounded projection`

The public call contains only `question`, `project_path`, and `mode`. The
protocol does not pass `output_mode`, `delivery_strategy`, evaluator-authored
requirements, or pre-ranked candidates.

Run it with:

```bash
python -m eval.project_answer_quality_protocol --output /tmp/project-answer-quality.json
```

The gate checks document acquisition recall, indexed fact coverage, candidate
Recall@K, selected obligation coverage, projected answer coverage, citation
integrity, abstention correctness, contamination, and visible-token ceilings.
The Task 43 v1 protocol and its pending human review are intentionally
unchanged.
