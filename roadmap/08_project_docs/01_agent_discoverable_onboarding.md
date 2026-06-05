# 08.01 — Agent-Discoverable Onboarding

## Problem

Пользователь может знать только то, что Docmancer — “аналог Context7”. Если агент увидит только generic docs tools, он может использовать Docmancer как Context7-style lookup:

```text
get_library_docs("react")
```

И тогда пользователь не получит главные плюсы:

- project-owned docs;
- repo architecture;
- local wiki/ADR;
- exact dependency docs из lockfiles;
- source class / freshness / attribution;
- project-scoped answers.

Capability недостаточно. Нужен **agent affordance**: агент должен сам понять, что в repo надо сначала сделать project docs discovery.

## Desired default flow

Когда пользователь говорит:

```text
Use Docmancer in this repo.
```

или:

```text
Docmancer is like Context7, right?
```

агент должен выполнить или предложить следующий workflow:

```text
inspect_project_docs(project_path=".")
  -> show found project docs, manifests, lockfiles, indexed/stale state
  -> recommend ingest_project_docs for local files
  -> recommend dependency docs prefetch if exact lockfile versions exist
  -> ask permission for network fetches
  -> use get_project_docs before repo-specific implementation answers
```

## `inspect_project_docs` as entrypoint

`inspect_project_docs` должен быть безопасным read-only default entrypoint.

Tool description should say:

```text
Call this first when working inside a repository and the user asks to use Docmancer, asks about project architecture, asks how this repo works, or expects Context7-like docs help. This tool discovers local project docs and exact dependency metadata, then returns recommended next actions.
```

Important: это не просто list command. Это onboarding response для агента.

## Required inspect output

`inspect_project_docs` должен возвращать не только найденные файлы, но и actionable recommendations.

Example:

```json
{
  "project_detected": true,
  "project_path": "/abs/path",
  "project_type": ["dart", "flutter"],
  "project_docs": {
    "found": [
      {"path": "README.md", "source_class": "project_file", "reason": "root_readme"},
      {"path": "wiki/Architecture.md", "source_class": "project_file", "reason": "architecture"},
      {"path": "roadmap/08_next_wedge_project_docs.md", "source_class": "project_file", "reason": "roadmap"}
    ],
    "indexed": [],
    "stale": [],
    "ignored": []
  },
  "dependency_sources": {
    "manifests_found": ["pubspec.yaml"],
    "lockfiles_found": ["pubspec.lock"],
    "exact_versions_available": true,
    "network_fetch_required": true
  },
  "recommended_next_actions": [
    {
      "tool": "ingest_project_docs",
      "requires_confirmation": false,
      "reason": "Project docs found but not indexed."
    },
    {
      "tool": "prefetch_project_docs",
      "requires_confirmation": true,
      "reason": "Exact dependency versions found in pubspec.lock; fetching docs may use network."
    }
  ],
  "agent_guidance": "Before answering project-specific implementation questions, ingest project docs. Ask before network dependency docs fetches."
}
```

## Confirmation rules

Recommended default policy:

- `inspect_project_docs` — no confirmation required; read-only.
- `ingest_project_docs` for local files — usually ask briefly unless agent policy allows local indexing automatically.
- `prefetch_project_docs` / dependency docs fetch — ask confirmation because it may use network.
- `write_project_doc` — always propose patch; never silently mutate hidden DB.

## Fallback behavior

If `get_project_docs` is called before project docs are indexed, it should not fail generically.

It should return machine-readable remediation:

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

## README quickstart requirement

README should include a user-facing lane:

```text
I thought Docmancer was like Context7. What else should I do?
```

Answer should explain:

1. Context7-style public library lookup still exists.
2. In a repo, start with project docs discovery.
3. Docmancer can index local docs and exact dependency docs.
4. Agents should call `inspect_project_docs` first.

## Success criteria

- A user who only says “use Docmancer, it is like Context7” gets offered project docs indexing.
- The agent can infer the workflow from MCP tool descriptions and inspect result alone.
- Missing/stale project docs produce next actions, not dead ends.
- Network fetches are clearly distinguished from local indexing.
- Official docs remain repo files.
