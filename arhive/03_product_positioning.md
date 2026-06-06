# 03 — Product Positioning Plan

## Recommended positioning

> **Docmancer gives coding agents local, version-aware docs context.**

Primary category:

> **Local, version-aware docs runtime for coding agents.**

## Packaging decision

Use one brand and one binary, but two product layers:

| Layer | Narrative |
|---|---|
| Docmancer Docs | Main product: docs runtime, local ingest, versioned docs, MCP docs server |
| Docmancer Packs | Advanced product: version-pinned API action tools |

Docs-RAG and MCP docs server belong together. API packs are useful, but should not be first-screen narrative.

## Why this positioning

| Option | Verdict |
|---|---|
| Local docs-RAG | Good entry mode, too generic as umbrella |
| Local Context7 alternative | Useful comparison, weak primary brand |
| Agent docs runtime | Best primary positioning |
| MCP API tools platform | Secondary/advanced, wrong hero story |
| Project-aware dependency docs | Best wedge inside primary positioning |

## Top 3 wow use cases

### 1. Exact dependency docs from the repo

User asks agent a question in a real project. Docmancer resolves dependency version from lockfile/project metadata and returns docs for the used version.

Success metrics:

- exact/best-effort version resolution rate;
- useful answer without external WebFetch;
- median tool calls to answer.

### 2. Private docs to compact context pack

User indexes internal docs/local folder/docs site. Agent/CLI gets source-grounded answer with compact token footprint.

Success metrics:

- time to first grounded answer;
- citation/source coverage;
- token compression ratio.

### 3. Registered web docs feel local

User registers docs once. Later agent queries them without `docs_url` dance or WebFetch fallback.

Success metrics:

- registered-source success rate;
- fallback-to-WebFetch rate;
- success within ≤2 MCP calls.

## README / landing narrative

Hero:

```text
Docmancer gives coding agents local, version-aware docs context.
```

Value bullets:

- Index repo docs, docs sites, and internal docs into compact context packs.
- Resolve package docs by version and project metadata.
- Serve grounded docs locally via CLI or MCP, with source attribution.

Quickstart lanes:

1. Local Docs / CLI query.
2. Versioned MCP Docs.
3. Action Packs.

## 90-day product outcomes

| Outcome | Window | Exit gate |
|---|---|---|
| Lock the story | days 1–15 | README/landing explain one primary product |
| Kill `docs_url` trap | days 1–45 | registered docs query without manual URL |
| Productize project-aware versioning | days 20–65 | Flutter/Dart polished; npm/Python/Rust/Go prioritized by data |
| Ship quality gates | days 30–75 | eval baseline and CI soft gates |
| Fix activation | days 60–90 | 5-minute happy path and action-oriented doctor |

## What to cut/deprioritize

- Do not make Packs hero narrative.
- Do not chase MCP action platform category now.
- Do not build managed auth/catalog/OAuth/session platform.
- Do not expand provider breadth before happy path reliability.
- Do not expose Qdrant/retrieval internals in first-screen story.

## Product backlog implications

### Must

- Rewrite README/landing around Docs runtime.
- Split quickstarts.
- Use “local Context7” only as comparison/SEO, not primary identity.
- Track Weekly Grounded Docs Sessions.

### Should

- Highlight project-aware docs as wedge.
- Hide advanced retrieval knobs from onboarding.
- Move Packs into advanced docs section.

### Could

- Separate Packs microsite later.
- Add comparison page vs Context7 later.
