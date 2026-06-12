# Verification Loop

## What already exists

Docmancer already provides the tools needed to verify documentation retrieval quality.

Existing behavior includes:

- project-doc inspection;
- project-doc ingestion;
- project-doc querying;
- project-context retrieval;
- stale-source reporting;
- trust-contract style selected/rejected/risky source reporting;
- async job status tools for docs prefetch/indexing flows.

This roadmap item is not about adding a new retrieval engine. It is about documenting a simple repeatable smoke-test loop.

## What still causes problems

After documentation changes, users may assume that agents will automatically retrieve the intended files. In practice, they need a quick way to confirm that discovery, indexing, and retrieval work as expected.

Without a verification loop:

- new docs may not be discovered;
- stale docs may remain in the index;
- expected files may not appear in context packs;
- agents may answer from incomplete context.

## What to improve

- Add a documented post-ingestion verification checklist.
- Suggest a small set of project-specific smoke-test questions after ingest/prefetch.
- Explain how to check whether expected files were cited.
- Explain what to change when expected sources are missing:
  - docs index links;
  - root documentation links;
  - discovery configuration;
  - docs manifest entries;
  - re-ingestion/refresh.
- Optionally add CLI/helper output that suggests test queries after ingestion.

## UX acceptance criteria

- Users know what to do immediately after changing docs or docs manifests.
- Documentation includes a short verification checklist.
- Troubleshooting docs explain why expected files may not be cited.
- Agents are instructed to recommend verification when docs were just added, refreshed, or reorganized.
