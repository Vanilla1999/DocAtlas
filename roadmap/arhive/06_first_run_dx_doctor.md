# 06 — First-run DX, Doctor and Onboarding Plan

## Goal

Make first use goal-oriented:

> Setup should introduce users to outcomes — “I can query docs”, “my agent sees Docmancer”, “my MCP host is connected” — not to Qdrant, embeddings, drift, and config internals first.

## Principles

- First success before optimization.
- Separate lanes: CLI docs, agent, MCP docs, API packs.
- Local-first is explicit: no API key by default, but local downloads may happen.
- Every diagnostic issue ends with an exact next action.
- Severity is relative to active profile.

## Setup redesign

`docmancer setup` becomes a goal router.

Profiles:

- CLI docs;
- coding agent;
- MCP docs server;
- API packs later.

Retrieval profiles:

- `local-hybrid` — best quality, local models + managed vectors;
- `lexical-now` — fastest first success, no vector download;
- `cloud` — explicit opt-in only.

Final summary should show:

```text
Ready now
  CLI query ............. yes
  Local hybrid .......... preparing
  Coding agent .......... not installed
  MCP docs server ....... not configured

Next best command
  docmancer ingest ./docs
```

## Non-interactive setup

Support:

```bash
docmancer setup --yes
docmancer setup --profile agent --agent claude-code --yes
docmancer setup --offline --vectors off --yes
docmancer setup --project-local --yes
```

## Doctor redesign

`docmancer doctor` should answer:

> What prevents me from getting docs context in the selected mode?

Severity:

| Severity | Meaning |
|---|---|
| BLOCKER | Selected path cannot work |
| DEGRADED | Works with reduced quality/functionality |
| WARN | Not blocking now but important |
| INFO | Useful context |

Check groups:

- config;
- storage;
- sqlite;
- qdrant;
- embeddings;
- vectors;
- sources;
- extraction;
- agent;
- mcp-docs;
- cloud.

Every issue block includes:

- issue code;
- impact;
- fix command;
- expected result;
- restart required or not;
- auto-fix availability.

## List / inspect UX

`docmancer list` should show operational state:

```text
SOURCE     TYPE   STATUS   FRESHNESS   CONTENT       VECTORS   FAILURES   NEXT ACTION
pytest     web    degraded stale 31d   2410 sections drift     12         docmancer update pytest
```

Filters:

```bash
docmancer list --stale
docmancer list --failed
docmancer list --vectors=drift
docmancer list --format json
```

`docmancer inspect <source>` should show source card:

- identity;
- freshness;
- extraction;
- retrieval/vector state;
- fix commands.

Drill-downs:

```bash
docmancer inspect pytest --failed
docmancer inspect pytest --vectors
docmancer inspect pytest --extraction
docmancer inspect pytest --json
```

## README IA

```text
README
├─ What Docmancer is
├─ Choose your path
│  ├─ Index docs for CLI and coding agents
│  ├─ Run a docs MCP server
│  └─ Use version-pinned API packs
├─ Install
├─ Five-minute quickstarts
├─ Common commands
├─ Troubleshooting
├─ Advanced
└─ API packs
```

## Acceptance criteria

| Metric | Target |
|---|---:|
| Time-to-first-success local folder P50 | < 3 min |
| Time-to-first-success web docs P50 | < 5 min |
| Interactive setup completion | > 85% |
| Non-interactive setup reference env | > 95% |
| Doctor remediation coverage top failures | > 90% |
| Silent degraded query usage | 0% |

## MVP implementation plan

1. Add goal-first setup copy/flow.
2. Add explicit retrieval profiles.
3. Add setup final readiness summary.
4. Redesign doctor output around severity/impact/fix.
5. Add `doctor --json`, `--list-checks`, `--check` if missing.
6. Improve list output with status/freshness/vectors/failures.
7. Split README quickstarts.

## Non-goals for MVP

- TUI/dashboard.
- Full vector repair wizard.
- Per-agent deep diagnostics for every client.
- Background model prefetch UI.
