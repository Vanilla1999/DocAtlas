# Collection restore

These rules govern production collections restored from immutable snapshots.

## Snapshot selection

Choose a snapshot with a signed manifest and a completed integrity scan. Record the snapshot identifier before copying any payload. If the most recent snapshot lacks either requirement, choose an older snapshot that satisfies both.

## Held collection

A collection under an investigation hold may be restored into isolated staging only. Do not publish it until the archive custodian explicitly releases the hold.

## Training archive

Disposable training archives may use unsigned snapshots and overwrite their staging directories. They cannot serve as a source for a production restore.
