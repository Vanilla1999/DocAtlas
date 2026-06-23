# Live Benchmark Results

This directory contains generated artifacts from the live DocAtlas vs Context7 MCP benchmark (`eval/live_mcp_context7_benchmark.py`).

## Directory Structure

Each run produces a timestamped directory (`YYYYMMDD_HHMMSS/`):

```
eval/results/live/YYYYMMDD_HHMMSS/
├── summary.json                 # Aggregated metrics
├── report.md                    # Human-readable report
├── docatlas_zero_setup/         # Raw per-query outputs (when --save-raw)
│   └── <case_id>.json
├── docatlas_preindexed/         # Raw per-query outputs (--mode both or preindexed)
│   └── <case_id>.json
└── context7_zero_setup/         # Raw per-query outputs (when --save-raw)
    └── <case_id>.json
```

Raw output directories use `provider_id` (e.g. `docatlas_zero_setup`, `docatlas_preindexed`) to avoid collisions when both modes run in a single benchmark.

## Git Tracking

- **Timestamp folders are generated locally** and are **ignored by git** (see root `.gitignore`).
- `sample_report.md` is the **only committed example** — it serves as a format reference.
- Full raw outputs (per-query JSON payloads, MCP responses) must be stored locally or published as CI artifacts. They are never committed to the repository.

## Running

```bash
# Zero-setup (quick, 6 cases)
uv run python eval/live_mcp_context7_benchmark.py --mode zero-setup --quick --save-raw

# Preindexed (quick, 6 cases)
uv run python eval/live_mcp_context7_benchmark.py --mode preindexed --quick --save-raw

# Both modes (quick, isolates zero-setup from preindexed storage)
uv run python eval/live_mcp_context7_benchmark.py --mode both --quick --save-raw

# Full run (all suites, all cases)
uv run python eval/live_mcp_context7_benchmark.py --mode both --save-raw
```

## Storage Isolation

For every benchmark mode, each DocAtlas provider instance gets isolated runtime storage, including:
- `DOCMANCER_HOME` — isolated home directory for per-library indexes
- SQLite `db_path` — isolated database file
- `docs-indexes/` — per-library documentation indexes
- `extracted/` — extracted documentation files
- `registry/` — library registry cache and state

Runtime directories are generated per run with timestamp prefixes and are not reused between benchmark invocations:
```
/tmp/live-benchmark/<timestamp>/<mode>/<provider_id>/
  home/
    docs-indexes/
    extracted/
    registry/
  docmancer.db
```

Examples:
- `docatlas_zero_setup` — isolated temp storage (empty, no preindexed data)
- `docatlas_preindexed` — isolated temp storage (preindexed data populated independently)

This ensures that zero-setup results are not artificially inflated by preindexed data, and that each provider uses completely separate storage including per-library indexes.

## Notes

- These artifacts are **not committed** (see root `.gitignore`).
- `sample_report.md` is the exception — it's committed for reference.
- Context7 `quota_exceeded` is not considered a DocAtlas win.
- Provider mode naming: `live_direct_api` for DocAtlas, `live_mcp_stdio` for Context7.
