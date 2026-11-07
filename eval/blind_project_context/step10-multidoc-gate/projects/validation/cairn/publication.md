# Restore publication

Publication changes the visitor-visible pointer for a production collection.

## Switch

Switch the collection pointer only after checksum reconciliation and custodian approval. Record both the previous and new snapshot identifiers. Apply the [rollback rule](rollback.md#rollback) if publication verification fails.

## Partial collections

If any required payload is missing, leave the previous pointer active even when all present payloads pass checksums. Custodian approval alone cannot authorize a partial collection.

## Preview pointer

An internal preview may point at an incomplete staged collection. Its address must remain separate from the visitor-visible collection pointer.
