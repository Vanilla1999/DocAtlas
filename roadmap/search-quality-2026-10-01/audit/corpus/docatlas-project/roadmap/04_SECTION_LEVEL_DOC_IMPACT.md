# Task 04 — improve docs impact from files to sections

## Audit status

Partial. Section metadata is written and the CLI reports section impact, but the stored index metadata is not consumed and CI does not derive changed symbols automatically. Task 20 owns the residual work.

## Problem

`doc-atlas docs-impact` maps changed files to maintained documents. It cannot yet say which heading or documented claim may be stale.

## Goal

Add deterministic section-level impact hints while remaining advisory and read-only.

## Required design

During project-doc indexing, record bounded metadata for each section:

- source document path;
- heading path;
- explicitly mentioned repository paths;
- explicitly mentioned symbols or configuration keys;
- content hash.

During `docs-impact`, compare changed paths and, when available, changed symbol names against this metadata.

## Output extension

Each impacted document may include:

```json
{
  "path": "docs/ARCHITECTURE.md",
  "sections": [
    {
      "heading_path": ["Authentication", "Token lifecycle"],
      "reason": "references_changed_path",
      "evidence": ["packages/auth/src/token_service.ts"]
    }
  ]
}
```

## Non-goals

- Do not rewrite the section.
- Do not claim semantic staleness without explicit evidence.
- Do not require embeddings.
- Do not block CI by default.

## Acceptance criteria

- Existing file-level output remains compatible.
- Explicit path/symbol references produce section hints.
- Unrelated headings are not reported.
- Unsupported cases fall back to the existing document-level review recommendation.
- Add precision and recall fixtures for Python, TypeScript, and Dart repositories.
