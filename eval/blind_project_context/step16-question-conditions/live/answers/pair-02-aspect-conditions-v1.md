For a stalled RillPrint 4 queue, the documented procedure applies **only if the queue is already in maintenance mode**. First check for jobs marked `held`: if any are present, stop recovery, leave the queue paused, and do not purge or resume it. [Source](docs/rillprint/recover-stalled-queue.md#L3-L6)

Otherwise, the documented recovery is:

1. Export the job manifest before purging.
2. Purge only when **both** the upstream feeder is stopped and the device buffer is empty.
3. Run `spool-verify` successfully before resuming the queue.

Uploading a diagnostic bundle is optional. Archived job receipts must remain unchanged throughout recovery. [Source](docs/rillprint/recover-stalled-queue.md#L4-L9)

The supplied evidence does not say how to enter maintenance mode or give the purge and verification commands.
