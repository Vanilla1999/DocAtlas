For a stalled **RillPrint 4 queue already in maintenance mode**:

1. If any job is marked `held`, stop recovery and leave the queue paused. Do not purge or resume it.
2. Otherwise, export the job manifest before purging. Purge only when **both** the upstream feeder is stopped and the device buffer is empty.
3. After the purge, run `spool-verify` successfully before resuming the queue.

Uploading a diagnostic bundle is optional. Archived job receipts must remain unchanged throughout recovery. [Source: `docs/rillprint/recover-stalled-queue.md`, lines 1–9]

The supplied documentation does not specify how to recover a queue that is not already in maintenance mode.
