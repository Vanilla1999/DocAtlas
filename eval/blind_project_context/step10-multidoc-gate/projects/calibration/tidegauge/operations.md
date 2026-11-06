# Station operations

These procedures apply only to authenticated live station feeds in the active harbour.

For orientation, the operator console links to the dashboard's [display settings](dashboard.md#display).

## Replay

To replay an interrupted feed, pause the receiver and obtain a journal checkpoint before requesting the missing interval. Preserve the original observation identifiers during replay. Resume the receiver only after the exporter acknowledges the checkpoint. See the [retention rule](storage.md#retention) before removing journal files.

## Disconnected station

If a station is still disconnected, do not resume its receiver after replay; leave it paused until a fresh authenticated heartbeat arrives. This exception applies even when the exporter acknowledged the checkpoint.

## Survey imports

Survey imports assign new identifiers and may start without a station heartbeat. They are scheduled offline and do not repair a live feed. Reusing this process for a station would create duplicate observations.
