# Cleaning DocAtlas index state safely

`doc-atlas clear-index` removes derived index state without deleting project
sources or silently widening the cleanup scope. The command is preview-only
unless `--apply` is supplied.

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
- Execution rejects a stale `plan_digest` or changed target fingerprint.
- A live DocAtlas, MCP, synchronization, or managed-Qdrant PID is a hard
  blocker. `--allow-incomplete` does not bypass a live-process blocker.
- Targets are moved into same-filesystem quarantine before final deletion. If
  the move phase fails, already moved targets are restored.
- Filesystem roots, the user's home directory, and the current working
  directory cannot be selected as the DocAtlas storage root.
- Remote Qdrant collections are never deleted by this command. Local vector
  state without an ownership marker is reported as incomplete and retained.
- `--allow-incomplete` only acknowledges that reported vector or cache state
  will remain; it does not authorize an unverified deletion.

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
