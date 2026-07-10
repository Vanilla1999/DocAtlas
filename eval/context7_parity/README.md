# Context7 parity evaluation

This is a reproducible evidence benchmark, not a marketing scorecard. It uses 150 identical version-pinned questions: 12 Python, 12 JavaScript/TypeScript, and 6 Dart/Flutter libraries, with five question types each.

Every dataset item fixes the requested version, allowed official corpus, expected source and section, expected symbols, and code-snippet requirement. Raw provider traces are local artifacts and must not be committed; summarized reports contain per-item verdicts and confidence intervals.

## Capture contract

Capture one JSON object per line. Required fields are `provider` (`docatlas` or `context7`), `case_id`, `first_tool`, `results`, `latency_ms`, and `phase` (`cold` or `warm`). Each result may contain `source`, `title`, `section`, `content`, and `snippet`. Optional trace fields measure `resolved_version`, `network_fetch_count`, `lifecycle_call_count`, and `unnecessary_lifecycle_call`. Omit `resolved_version` only when it is unavailable: the report marks that item as `unknown`, not as an exact-version match.

## Reproduce the DocAtlas scoring side

```bash
uv run python eval/context7_parity/run_docatlas.py \
  --traces /secure-local-captures/docatlas.jsonl \
  --output /tmp/docatlas-parity-report.json
```

Compare two complete captures only when they use the same committed dataset:

```bash
uv run python eval/context7_parity/parity_eval.py \
  --traces /secure-local-captures/docatlas.jsonl \
  --traces /secure-local-captures/context7.jsonl \
  --output /tmp/context7-parity-report.json
```

The scorer refuses to call a win or loss unless both providers cover all 150 identical items. It reports unsupported cases instead.
