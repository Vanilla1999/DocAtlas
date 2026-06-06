# 08.02 — Proposed MCP/CLI Surface

## `inspect_project_docs`

Purpose: показать агенту и пользователю, какие project-owned docs доступны, какие dependency manifests/lockfiles найдены, что уже indexed/stale, и какие next actions стоит выполнить.

Input:

```json
{
  "project_path": "."
}
```

Output shape:

```json
{
  "project_path": "/abs/path",
  "candidate_sources": [
    {"path": "README.md", "source_class": "project_file", "reason": "root_readme"},
    {"path": "wiki/Architecture.md", "source_class": "project_file", "reason": "architecture"}
  ],
  "dependency_sources": {
    "manifests_found": ["pubspec.yaml"],
    "lockfiles_found": ["pubspec.lock"],
    "exact_versions_available": true,
    "network_fetch_required": true
  },
  "indexed_sources": [],
  "stale_sources": [],
  "ignored_sources": [],
  "recommended_next_actions": [
    {"tool": "ingest_project_docs", "reason": "Project docs found but not indexed."},
    {"tool": "prefetch_project_docs", "reason": "Exact dependency versions found; network fetch may be useful."}
  ],
  "agent_guidance": "Call ingest_project_docs before answering repo-specific questions. Ask before network fetches."
}
```

## `ingest_project_docs`

Purpose: явно индексировать official project docs files, не весь repo.

Candidate defaults:

- `README.md`;
- `docs/**`;
- `wiki/**`;
- `ARCHITECTURE.md`;
- `docs/Architecture.md`;
- `adr/**` / `docs/adr/**`;
- `roadmap/**`;
- `CHANGELOG.md`;
- `CONTRIBUTING.md`.

Non-goals:

- auto-ingest source code by default;
- index `.git`, `node_modules`, `.venv`, build outputs;
- silently create docs files.

## `get_project_docs`

Purpose: Context7-style query, но по docs конкретного проекта.

Input:

```json
{
  "project_path": ".",
  "topic": "how docs registry identity works",
  "include_dependency_docs": false,
  "include_local_memory": false
}
```

Response requirements:

- compact context pack;
- source file path;
- heading path;
- source class: `project_file` / `local_memory` / `dependency_docs` / `public_docs`;
- freshness/stale warnings;
- next actions if docs are missing or stale;
- never suggest direct WebFetch for repo-owned docs before project docs inspect/ingest.

Missing docs response should be structured:

```json
{
  "answer_available": false,
  "reason": "project_docs_not_indexed",
  "next_actions": [
    {"tool": "inspect_project_docs", "reason": "Discover project docs candidates."},
    {"tool": "ingest_project_docs", "reason": "Index discovered project docs before querying."}
  ]
}
```

## Optional later: `write_project_doc`

Only if write flow is added:

```json
{
  "project_path": ".",
  "doc_type": "architecture",
  "path": "docs/Architecture.md",
  "mode": "propose_patch"
}
```

Rules:

- default mode must be `propose_patch`, not hidden DB mutation;
- generated docs must be files;
- response must show diff/summary;
- ingest after write should be explicit or clearly reported.
