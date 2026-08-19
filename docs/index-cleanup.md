# Cleaning DocAtlas index state safely

`doc-atlas clear-index` removes derived index state while preserving project
sources, `docmancer.yaml`, configuration, and unrelated files; it never
silently widens the cleanup scope. The command is preview-only
unless `--apply` is supplied.

`clear-index` supports exactly two scopes: `project-local` and `global`.
Quarantine is the same-filesystem staging area used before final deletion so
moved targets can be restored if the move phase fails. In `clear-index`,
`--allow-incomplete` acknowledges that reported unverified vector or cache
state will remain; it never bypasses live-process blockers or authorizes remote
deletion. `clear-index` deletes only derived SQLite, extracted-document, cache,
and verified local vector state. `clear-index` preserves project sources,
`docmancer.yaml`, configuration, and unrelated files.

## Clear one project-local index

A project-local cleanup requires a project whose `docmancer.yaml` resolves to
that project's `.docmancer` directory:

```bash
doc-atlas clear-index \
  --scope project-local \
  --project-path /absolute/path/to/project \
  --format json
```

The preview reports a deterministic `plan_digest`, every recognized target,
and any incomplete or blocking condition. Review the preview, stop the Docs MCP
server and synchronization workers that use the same storage, then apply the
same plan:

```bash
doc-atlas clear-index \
  --scope project-local \
  --project-path /absolute/path/to/project \
  --plan-digest <digest-from-preview> \
  --apply \
  --format json
```

The project-local plan may include:

- the configured SQLite database and its `-wal`, `-shm`, and `-journal`
  sidecars;
- the configured extracted-document directory;
- project-owned docs, library, embedding, and sqlite-vec cache directories
  below the resolved project storage root;
- a local managed-Qdrant directory only when its ownership marker identifies it
  as DocAtlas-managed state.

Project sources and `docmancer.yaml` are not cleanup targets. A later
`prepare_docs(action="sync_project_docs")` can rebuild the index from the
reviewable repository files.

`project-local` is intentionally limited to a dedicated project-local
`.docmancer` root. It refuses projects that resolve to the shared/global index;
DocAtlas does not delete one project's rows from a shared database by guessing
ownership. Use `--scope global` to reset that shared local index, or give each
project an explicit project-local `docmancer.yaml` when independent cleanup is
required.

## Clear all local indexes while preserving configuration

Use the global index scope when the goal is to remove derived indexes under the
resolved DocAtlas home while preserving configuration and unrelated files:

```bash
doc-atlas clear-index --scope global --format json
```

Apply the reviewed plan with its digest:

```bash
doc-atlas clear-index \
  --scope global \
  --plan-digest <digest-from-preview> \
  --apply \
  --format json
```

This is intentionally different from `doc-atlas clear`, which remains the
broader destructive reset command and may remove configuration and model
caches.

## Safety rules

- Preview does not create a missing storage home or an empty database.
- If the preview plan is stale, execution refuses to apply it before any destructive move; a stale `plan_digest` or changed target fingerprint cannot be applied.
- `clear-index` refuses to apply a cleanup plan while a live DocAtlas, MCP, synchronization, or managed-Qdrant process holds the index; a recorded live PID is a hard blocker. `--allow-incomplete` does not bypass this live-process blocker.
- Targets are moved into same-filesystem quarantine before final deletion. If
  the move phase fails, already moved targets are restored.
- Filesystem roots, the user's home directory, and the current working
  directory cannot be selected as the DocAtlas storage root.
- `clear-index` never deletes remote Qdrant collections. Local vector state
  without an ownership marker is reported as incomplete and retained.
- `--allow-incomplete` only acknowledges that reported vector or cache state
  will remain; it never bypasses live-process blockers or authorizes unverified
  or remote deletion.

### Coordination with index writers

Storage mutation coordination is fail-closed: a project sync or library refresh registers a writer lease, while `clear-index` takes the cleanup barrier and refuses cleanup while any live writer lease exists.

The short per-database mutation lock is used only around publication/removal, so independent fetch/staging work is not serialized for its full duration. `remove_library_docs` refuses removal while a library-refresh writer lease is active; after the barrier is clear it takes the per-index mutation lock before deleting SQLite/extracted state. Writer leases from dead processes are cleaned during the barrier check; an unreadable lease remains a blocker rather than being ignored.

For an MCP client, the same operation remains available through the existing
three-tool surface:

```text
prepare_docs(
  action="clear_index",
  scope="project-local",
  project_path="/absolute/path/to/project",
)
```

The first response requires confirmation and returns the bound `plan_digest`.
The confirmed call must send that digest back so a changed preview cannot be
applied accidentally.
