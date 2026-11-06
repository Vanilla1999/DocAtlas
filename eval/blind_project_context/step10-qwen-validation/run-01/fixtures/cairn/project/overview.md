# Cairn archive

Cairn restores research collections from immutable archive snapshots. Recovery procedures concern production collections; disposable training archives are separate.

## Components

A catalogue records object identifiers, a verifier checks stored payloads, and a restore worker reconstructs a collection in staging. Publication switches the collection pointer after review; it does not mutate the snapshot.

## Identity

Object identifiers remain stable across storage locations. A path in a staging directory is not a new object identity. Snapshot manifests bind identifiers to payload checksums.
