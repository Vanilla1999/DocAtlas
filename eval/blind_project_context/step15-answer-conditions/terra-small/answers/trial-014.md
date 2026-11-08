For a **RillPrint 4 queue already in maintenance mode**, the documented recovery procedure is:

1. If any job is marked `held`, stop recovery and leave the queue paused. **Do not purge or resume it.**
2. Before purging, export the job manifest. Purge only when the upstream feeder is stopped **and** the device buffer is empty.
3. After purging, run `spool-verify` successfully before resuming the queue.

Archived job receipts must remain unchanged throughout recovery. Uploading a diagnostic bundle is optional. The supplied procedure does not explain how to enter maintenance mode or provide purge commands. [Source: `docs/rillprint/recover-stalled-queue.md`, lines 1–9]
