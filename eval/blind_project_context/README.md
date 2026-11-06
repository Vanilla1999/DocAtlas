# Blind project-context gate

Sealed blind questions about the project's own documentation, asked through
the real stdio MCP server (`get_docs_context` after `prepare_docs`), scored
against exact gold quotes. A change is accepted only if no slice
(dev/holdout x L0/L2 x RU/EN) delivers fewer gold facts or fewer fully
answered cases than the committed baseline. Full protocol, rules, limits and
disclosure (in Russian): [PROTOCOL_RU.md](PROTOCOL_RU.md).

| File | Role |
|---|---|
| `corpus.py`, `corpus-lock.json` | rebuild frozen L0 (19 docs) and L2 (489 docs) from git objects, sha256-checked |
| `topics.py` → `topics.json` | seeded draw of 24 leaf sections, 12 dev / 12 holdout |
| `questions.json` | 48 sealed cases (RU with `search_question`, EN without) |
| `FREEZE_MANIFEST.json` | sha256 seal of the five files above, committed before the gold |
| `oracle.json`, `audit.py` → `witness-audit.json` | 65 exact gold quotes and every verbatim occurrence in L0/L2 |
| `run.py`, `observed_server.py` | fresh isolated stdio servers, one per corpus shard; passive ceiling counters and candidate ranks of gold quotes |
| `score.py` | per case: facts delivered, where missed facts were lost, first fact row, question/answer word overlap, limits reached |
| `gate.py` | comparability checks, then "no slice worse" (exit 0 accept, 1 reject, 2 not comparable) |
| `baseline/` | committed score of the current tree (`score.json`, `report.md`, `holdout-details.md`) |

```bash
python eval/blind_project_context/run.py OUT --jobs 2
python eval/blind_project_context/score.py OUT
python eval/blind_project_context/gate.py eval/blind_project_context/baseline/score.json OUT/score.json
DOCATLAS_BLIND_EVAL=1 python -m pytest tests/test_blind_project_context_integration.py
```

Holdout cases are never used for tuning; `report.md` lists dev cases only.

## Continuation and delivery-size studies

```bash
# First-call facts remain the normal gate; cumulative portions are separate.
python eval/blind_project_context/run.py OUT --jobs 2 --portions 3 \
  --env BLIND_OBSERVER_SELECTION=1
python eval/blind_project_context/score.py OUT

# Measurement only; ordinary runtime remains at 12,000.
python eval/blind_project_context/run.py OUT --jobs 2 \
  --env DOCATLAS_EXPERIMENT_DELIVERY_MAX_TOKENS=18000
```

`--portions` follows only the server-issued next portion and snapshot token.
The scorer validates every returned source span, rejects repeated source
windows between portions, and re-scores the union of character intervals
after each cumulative portion. The ordinary `facts_found` and gate still
refer to the first answer. Cumulative results measure forced reading up to N
portions, not a model's ability to decide when more evidence is useful.

`BLIND_OBSERVER_SELECTION=1` adds first-portion checked-pool/pruning/final
selection observations. Gold quotes are used only by passive wrappers, never
by ranking. The passivity integration checks byte equality with and without
these observations over three portions. Missing trace rows remain explicitly
unobserved. A finalizer retraction is distinct from a pruning decision.

Use distinct `--work-root` paths for concurrent studies. Keep source and eval
trees frozen for each run, use dependencies from `uv.lock`, and do not compare
latency across runs sharing CPUs with other work. `score.py` records actual
o200k output tokens as well as bytes. Set `ORT_DISABLE_TELEMETRY=1` before
loading any third-party local-model runtime.
