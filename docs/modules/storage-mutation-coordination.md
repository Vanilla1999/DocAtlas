# Storage mutation coordination module

`StorageMutationCoordination` is the local concurrency contract that combines writer leases, an exclusive cleanup barrier, and short per-index mutation locks so refresh, publication, removal, and cleanup cannot corrupt shared index state.

## Responsibility

`docmancer/docs/infrastructure/storage_mutation_lock.py` coordinates writers and destructive index operations that share a DocAtlas storage root. Library refresh, project publication, remove/prune, and `clear-index` must not race in a way that resurrects stale state or deletes a database underneath an active writer.

## Contract

Long-running fetch/staging work uses a lightweight writer lease. Destructive cleanup enters an exclusive cleanup barrier, verifies that no writer lease is active, revalidates the cleanup plan, and only then moves targets into quarantine. Per-index mutation locks continue to protect short publication/write sections.

The barrier is deliberately not held across network fetches, so independent library refreshes can remain concurrent.

## Invariants

- cleanup does not start while a registered writer is active;
- a new writer does not enter an active cleanup barrier;
- `remove_library_docs` does not delete state while refresh is in flight;
- stale cleanup plans fail before destructive moves;
- local locking never grants ownership of remote Qdrant state.

## Tests

`tests/docs/test_storage_mutation_lock.py`, library refresh/publication tests, and clear-index tests protect this boundary.
