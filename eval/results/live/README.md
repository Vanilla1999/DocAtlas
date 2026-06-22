# Live Benchmark Results

This directory contains generated artifacts from the live DocAtlas vs Context7 MCP benchmark (`eval/live_mcp_context7_benchmark.py`).

## Directory Structure

Each run produces a timestamped directory (`YYYYMMDD_HHMMSS/`):
- `summary.json` — aggregated metrics
- `report.md` — human-readable report
- `docatlas/` — raw per-query outputs (when `--save-raw`)
- `context7/` — raw per-query outputs (when `--save-raw`)

## Running

```bash
# Quick run (6 project-docs cases)
uv run python eval/live_mcp_context7_benchmark.py --mode zero-setup --quick --save-raw

# Full run
uv run python eval/live_mcp_context7_benchmark.py --mode both --save-raw

# Preindexed mode
uv run python eval/live_mcp_context7_benchmark.py --mode preindexed --save-raw
```

## Notes

- These artifacts are **not committed** (see root `.gitignore`).
- `sample_report.md` is the exception — it's committed for reference.
