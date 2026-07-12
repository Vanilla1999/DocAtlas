# Task 32 — explicit project documentation catalog

Status: implementation in `feat/task32-explicit-project-doc-catalog`.

## Goal

Let the host coding model maintain a reviewable `docatlas.project-docs.yaml` file containing exact documentation paths, bounded descriptions, scope, module ownership, authority, lifecycle status, and maintenance policy. DocAtlas validates and consumes the catalog but never authors official project documentation itself.

## Acceptance criteria

- A valid catalog replaces filename/directory guessing for project-doc discovery.
- Auto-discovery remains available only when no catalog exists.
- Invalid, missing, duplicate, symlinked, and traversal entries fail closed with actionable warnings.
- Catalog metadata is retained in the project index and agent contract.
- `completed`, `superseded`, and `search_only` documents do not create normal docs-impact work.
- Projects without a catalog remain backward compatible.
