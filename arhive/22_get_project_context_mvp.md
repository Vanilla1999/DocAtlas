# 22 - `get_project_context` MVP

## Goal

Ship the first high-level tool that makes agents ask Docmancer first inside a repository.

Preferred MCP name:

```text
get_project_context
```

Preferred CLI command:

```bash
docmancer context "How should I implement this here?" --explain
```

Avoid names like `answer_from_project_docs` because `answer` implies Docmancer is an LLM answer generator. The product value is context resolution, not final answer synthesis.

## MVP scope

The first shipped slice should be intentionally small:

- one repository path;
- one natural-language question;
- project-owned docs from already discovered/indexed docs;
- one dependency ecosystem, preferably Dart/Flutter or Rust;
- one resolved dependency when explicitly mentioned or confidently inferred;
- compact merged output;
- Trust Contract;
- warnings and next actions;
- `--explain` text output.

This is enough to prove the wedge without solving every ecosystem or every docs host.

## Input

```json
{
  "project_path": "/path/to/repo",
  "question": "How should I add an autoDispose Riverpod provider in this repo?",
  "libraries": ["flutter_riverpod"],
  "tokens": 4000,
  "mode": "auto",
  "explain": true
}
```

Modes:

- `auto`: use project docs and dependency docs when relevant.
- `project-only`: only project-owned docs.
- `deps-only`: only dependency docs resolved from project metadata.
- `public-docs`: public docs only, still with trust labels.

## Internal flow

```text
get_project_context
  -> inspect_project_docs(project_path)
  -> if project docs are missing/stale, include next_actions
  -> query indexed project docs when available
  -> detect relevant dependency/dependencies
  -> resolve dependency version from lockfile/manifest when supported
  -> resolve docs source with confidence and rejection reasons
  -> query dependency docs
  -> merge project and dependency evidence
  -> return context_pack + trust_contract + explain data
```

## Output

The output should include:

- `answer_available`;
- `reason` when unavailable or partial;
- `context_pack`;
- `trust_contract`;
- `warnings`;
- `next_actions`;
- `metrics` such as token estimates and source counts.

Example partial response:

```json
{
  "answer_available": true,
  "reason": "project_and_dependency_context_available",
  "context_pack": [],
  "trust_contract": {
    "trusted_sources": [],
    "rejected_or_risky_sources": [],
    "warnings": [
      {
        "reason_code": "dependency_docs_not_indexed",
        "reason": "flutter_riverpod was resolved from pubspec.lock but docs are not indexed yet"
      }
    ],
    "next_actions": [
      {
        "tool": "prefetch_project_docs",
        "requires_confirmation": true,
        "arguments_patch": {"project_path": "/path/to/repo", "include_dart": true},
        "reason": "Fetch exact dependency docs for project-resolved Pub packages"
      }
    ]
  }
}
```

## Ranking and merge rules

For MVP, keep the merge deterministic and explainable:

1. Project docs with direct constraints outrank generic dependency docs.
2. Exact-version dependency docs outrank latest/default docs.
3. Stale project docs can be included, but must carry warnings.
4. Best-effort docs can be included, but never labeled exact.
5. Multiple sections from the same source should be capped when top-K would otherwise be redundant.

## CLI explain output

Example:

```text
Trusted context for: How should I add an autoDispose Riverpod provider in this repo?

Used:
  [project_doc] docs/architecture.md
    why: matched local state-management rule
    freshness: current

  [dependency_doc] flutter_riverpod 2.6.1
    why: resolved from pubspec.lock; exact Dartdoc URL
    docs_exactness: exact_version_url

Rejected / risky:
  [public_doc] latest flutter_riverpod docs
    reason: wrong_version_risk; project is pinned to 2.6.1

Next actions:
  none
```

## First PR sequence

1. Add response schema and tests for Trust Contract.
2. Implement `get_project_context` by composing existing project-doc and library-doc services.
3. Support project docs + one explicit dependency.
4. Add deterministic merge/ranking rules.
5. Add CLI `docmancer context ... --explain` or equivalent command wrapper.
6. Add one benchmark fixture where local project docs and exact dependency docs are required.

## Acceptance criteria

- A single tool call can return project docs and dependency docs in one context pack.
- The response includes selected sources and rejected/risky sources.
- Missing/stale/non-exact docs produce warnings and next actions.
- The first benchmark shows why Context7-only is insufficient for at least one repo-specific task.

## Non-goals

- Do not support all ecosystems in the first PR.
- Do not auto-fetch large public docs sites without explicit approval.
- Do not generate final code or natural-language answers.
