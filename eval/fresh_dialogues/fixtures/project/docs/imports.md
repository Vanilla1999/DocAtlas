# Staged imports

## Input format

An import contains UTF-8 newline-delimited JSON. Each line is one complete record; blank lines are ignored. A file with a byte-order mark is rejected before staging.

## Batch identity

Every staged import uses a batch identifier and a SHA-256 digest of the complete input. A repeated batch identifier is accepted only when its complete-input digest matches the first attempt; a different digest is a conflict and the existing batch is left unchanged.

## Interrupted upload

An interrupted upload may resume for nine minutes after the last accepted chunk. Resume using the same batch identifier and complete-input digest. After that interval, start a new batch rather than append to the expired one.

## Publication

Uploaded chunks are staging data and are never visible to queries or exports. Publication requires validation of the whole batch followed by an explicit commit. The committed manifest switches atomically; a partially uploaded or invalid batch cannot become partially visible.

## Abort

Aborting an uncommitted batch deletes its staging data and does not remove any records from an already committed manifest. Abort is not a substitute for deleting published records.
