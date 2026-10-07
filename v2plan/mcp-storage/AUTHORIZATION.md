# Storage continuation: approved boundaries

Common base: `cb29039e901824cbd4a9dc9b6cf427a0016fe19b`.
Prior safe-closed delivery report: `v2plan/mcp-delivery/FINAL_REPORT_RU.md`.

The user approved a separate storage/VFS design and implementation phase with
expanded ownership, isolated fixtures, no new dependencies, no live reinstall,
and no user-index mutation. Existing mutation denial stays in place until a
safe positive route has passed adversarial checks and independent review.

The user did **not** approve identity migration or a compatibility break; they
asked why migration is needed. The root-local identity change is ours. First
investigate compatibility without migration, aliasing, weakened scope filters,
unconstrained Git reads or index rebuilds. Do not treat that question as consent.

## Read-only design assignments

- A `/tmp/opencode/mcp-storage-a`: descriptor-bound SQLite main/sidecar storage,
  SQL atomicity, concurrency, crashes, platform support, minimal packaging.
- B `/tmp/opencode/mcp-storage-b`: preserve legitimate old index access without
  unapproved migration or inferred authorization; producer/consumer bindings.
- C `/tmp/opencode/mcp-storage-c`: real installed ready-index retrieval matrix,
  necessary >32 KB evidence feasibility under unchanged runtime guards; no
  mocked retrieval or fake padding. Fixture bootstrap is not preparation proof.
- R: independent review of concrete design before production implementation,
  then independent verification of the integrated result.

Each implementation needs a reviewed interface and exact non-overlapping file
allowlist. No nested agents. No edits to prior worktrees, historical gold,
thresholds, reports/evaluation suites, D1 catalog or other user work.
D1 remains exactly 10 documents, `code_files=()`; no corpus/scan expansion.

Merge, release publication, version selection, current installation/config/index
changes remain separately gated. Current stage does not imply release acceptance.

## Subsequent packing approval

The user approved reviewing token packing/admission for explicit
`context_format="patch_context"` on already found windows. This does not permit
expanding corpus, scan, candidate acquisition, source scope, network authority,
or I/O safety limits. Omitted/null docs mode remains separate and unchanged.
Source/hash/span bindings and partial evidence must survive. A naturally
reachable >32 KB result remains a test obligation, not permission to pad fixtures
or enlarge acquisition. Implementation requires the reviewed exact allowlist.

## Diagnostic implementation and pending native review

C's three-file ready-index diagnostic was approved and integrated as `f4db3e95`
(original `b81e942a`). It is fixture bootstrap evidence, not preparation proof.
Both transports delivered project/module evidence; library lineage and >32 KB
admission remain blocked. Full smoke and ready-index diagnostic both exit 1.

Neither the snapshot backend nor native persistence implementation is approved.
The native proposal is under independent R review; object-bound versus strict
external-alias semantics and crash recovery under hostile sidecar removal remain
unresolved. Existing unsafe persistence denial must not be removed on this basis.

## Explicitly approved isolated research spike

After R's concept review, the user selected the research spike. Coordinator
assigned A only these experimental paths, on disposable fixtures:

```text
experiments/mcp_storage_native/sqlite_fd_vfs.c
experiments/mcp_storage_native/worker.py
experiments/mcp_storage_native/README.md
experiments/mcp_storage_native/include/sqlite3.h
experiments/mcp_storage_native/include/sqlite3ext.h
tests/test_mcp_storage_native_spike.py
tests/diagnostic_labels.mcp_storage_native_spike.json
```

No production dispatch/store/agent/config/build/package integration is permitted
by this allowlist. Existing compiler use and temporary experimental artifacts
are allowed; no new dependency, runtime downloads, install or current-index use.
Header provenance and licensing must be recorded. Coverage, locking, recovery,
error and crash behavior must be reported with actual supported SQLite profiles.
Unknown operations deny; no unsafe fallback. Unsupported or uncertain outcomes
must not be mislabeled as no mutation.

This does not approve object-bound authorization in place of strict alias
guarantees, protected-namespace assumptions, or any threat-model weakening.
Persistence remains blocked; packaging and production integration need later
review and approval. B's found-window retention proposal is independently under
R review and has no implementation allowlist yet.

## Subsequent legacy-data decision

The user explicitly stated that the old database is unused and disposable, and
authorized clearing it if needed. Legacy-row preservation and identity migration
are no longer requirements. Prefer a fresh empty database rather than designing
compatibility aliases/migration. This supersedes the earlier unresolved legacy
compatibility decision, not the source/ownership/security contract.

No database has been cleared. Before any destructive operation, identify the
exact database and related files; this statement does not identify a pathname or
authorize broad storage-directory deletion. Live MCP/config replacement remains
separately gated. Fresh-database initialization needs a reviewed safe route;
discarding legacy data does not solve pathname/sidecar races or permit unsafe
persistence fallback.
