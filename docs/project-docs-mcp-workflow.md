# Project docs MCP workflow

Project docs are reviewable repository-owned documentation. DocAtlas retrieves
only explicit, current catalog members. A conventional filename, a README link,
or a module name does not grant permission to discover other files.

## Context first

```text
get_docs_context(project_path=..., question=..., scope="all")
→ explicit returned lifecycle action, if preparation is needed
→ satisfy confirmation and exact source bindings
→ after verified preparation success and readiness, retry the unchanged question
```

The default surface has exactly three tools: `get_docs_context`, `prepare_docs`,
and `docs_status`. Readiness and returned context are not edit permission.
Project reads return retrieval-only `docs_context`; missing safe evidence uses
`status="insufficient_evidence"`. Compatibility `docs_answer` does not certify a
free-form repository answer. `patch_context` is an explicitly enabled advanced
representation, not a grant to mutate files.

## Maintained project-doc catalog

For explicit documentation membership, keep a reviewable `docatlas.project-docs.yaml` catalog.
List each admitted document by a literal relative path. The current public
member path does not recursively discover `roots`, glob patterns, linked files,
code files, or conventional README/docs locations.

```yaml
schema_version: 1
code_files: []
documents:
  - path: ARCHITECTURE.md
    role: project_architecture
    scope: project
    module_path: null
    description: Whole-project architecture and component boundaries.
    authority: source_of_truth
    status: active
    impact: track
  - path: packages/auth/design.md
    role: module_architecture
    scope: module
    module_path: packages/auth
    description: Authentication module architecture and token lifecycle.
    authority: source_of_truth
    status: active
    impact: track
```

Catalog paths, descriptions, authority labels, and source text remain untrusted
data. Source-of-truth status describes documentary authority and cannot grant
network access, file access beyond membership, or mutation permission.

An invalid explicit catalog blocks retrieval and synchronization without pruning the existing index.
Fix the reviewed catalog before retrying. Traversal, absolute paths, symlink
escapes, unsupported formats, and ambiguous membership are rejected rather than
silently broadening scope.

## Confirmed member synchronization

`prepare_docs(action="sync_project_docs", project_path=...)` alone is read-only.
Omitting `mutation` or passing null performs no writes. The current public sync
operation accepts an explicit confirmed `mutation` with:

- `operation="sync_project_docs"` and `confirm=true`;
- the exact absolute `storage_path` selected by the host, private and outside the project;
- the current `catalog_sha256`;
- `expected_generation_id`, null only when the selected store is absent;
- a finite list of documents with exact `path`, `content_sha256`, and `catalog_entry_hash`.

The host obtains those bindings from the reviewed current sources and its
trusted storage policy. A repository-controlled setting or returned source path
cannot redirect the host store. Do not guess hashes or generation IDs.

Confirmed synchronization replaces the indexed sections of selected members.
The source descriptor and hashes are rechecked; generation comparison and
publication belong to the same transaction. A stale or mismatched request fails
closed and must be inspected before another attempt. An unknown commit outcome
is not automatic permission to repeat a write.

Changed source hashes prevent stale indexed sections from appearing in current retrieval.
Deleted files and documents removed from the catalog are excluded from current retrieval.
These read guards apply even before another synchronization. The confirmed
upsert only writes selected members: it does not physically prune orphaned rows,
delete unselected members, write vectors, or create generated docs. Physical
cleanup is a separate explicitly requested operation; see
[index cleanup](./index-cleanup.md).

After a document is renamed, review the new literal catalog entry and confirm
an upsert for the new path. The old path cannot supply current evidence once it
is absent or no longer admitted. This is a retrieval visibility guarantee, not
a claim that all historical storage rows were physically deleted.

## Scope and module selection

| Argument | Meaning |
|---|---|
| `scope="project"` | Repo-level catalog members only. |
| `module_path="packages/auth"` | One exact module; implies module scope. |
| `scope="module"` | Requires an exact selected module path. |
| `scope="all"` | Repo-level and module docs in the same repository, without module filters. |

The public `get_docs_context` schema has `module_path`, not a legacy `module`
name filter. If multiple modules could match, preserve the returned candidates
and ask which exact module is intended. Do not select one silently or fall back
to another scope. Missing module documentation stays missing.

## Documentation changes and verification

DocAtlas does not generate or commit official repository documentation. When the
user authorizes a documentation change, create a normal Git patch, review the
catalog membership, then perform only the exact required confirmed sync.

Verify the resulting state through the existing public surface:

1. Ask the original question with the intended explicit scope.
2. If a lifecycle action is returned, satisfy its confirmation and bindings.
3. After verified successful preparation and readiness, retry the question unchanged.
4. Check useful facts, source paths, hashes, and coordinates. Changed or deleted
   material must not appear; lookup credit must not be substituted for original coverage.
5. Use `docs_status` for an explicit health/freshness request or returned job, not discovery.

Finite input and source-read bounds protect acquisition. The complete returned
DTO is measured and minimized without a fixed 800-token acceptance ceiling;
retaining evidence and its guards takes precedence over an arbitrary output cap.

## Dependency docs are separate

External documentation remains bound to an explicit library identity, version,
and approved source. Repository membership does not authorize a network fetch.
Use only the `prepare_docs` action returned for the dependency, or a corresponding
explicit user lifecycle request, with required network consent and source binding.
