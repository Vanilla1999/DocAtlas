# Archive architecture

Cairn separates immutable payload storage from mutable collection pointers.

## Object store

The object store uses content checksums to detect corruption. Replication improves availability but does not supply custodian approval. The catalogue maps stable object identifiers to snapshot manifests and supports historical lookup.

## Demonstration mode

The demonstration mode publishes whatever payloads are present and deletes the previous pointer. It is restricted to disposable examples and is not the archive publication policy.
