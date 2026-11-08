For a **RillPrint 4 queue already in maintenance mode**, the documented recovery procedure is:

1. If any job is marked `held`, **stop recovery and leave the queue paused**. Do not purge or resume it.
2. Before purging, export the job manifest.
3. Purge only when the upstream feeder is stopped **and** the device buffer is empty.
4. After the purge, run `spool-verify` successfully before resuming the queue.

Keep archived job receipts unchanged throughout recovery. Uploading a diagnostic bundle is optional.

The supplied documentation does not specify purge commands or how to recover a queue that is not already in maintenance mode.

Source: `docs/rillprint/recover-stalled-queue.md`, lines 1–9.
