The documented procedure applies only to **RillPrint 4 queues already in maintenance mode**:

1. If any job is marked `held`, stop recovery and leave the queue paused. Do not purge or resume it.
2. Before any purge, export the job manifest.
3. Purge only when **both** the upstream feeder is stopped and the device buffer is empty.
4. After the purge, run `spool-verify` successfully before resuming the queue.

Uploading a diagnostic bundle is optional. Archived job receipts must remain unchanged throughout recovery. The supplied documentation does not specify the commands for exporting the manifest, purging, or resuming the queue.  
Source: `docs/rillprint/recover-stalled-queue.md`, lines 3–9.
