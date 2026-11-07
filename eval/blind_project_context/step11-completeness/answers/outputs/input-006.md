**Suspend outdoor observations when the wind interlock opens. Restart requires both the interlock to close and the duty operator to record restart approval. An explicitly classified indoor instrument may continue if its own safety interlocks remain closed.** (`weather.md`, lines 5–11)

### When wind should stop observations

The specified trigger is **the wind interlock opening**. The supplied excerpts do not give a numerical wind-speed threshold. Suspension affects execution, not reservation ownership, and reservation identifiers must be preserved. Transferring a reservation does not change its weather suspension. (`weather.md`, lines 3–7; `reservations.md`, lines 7–9)

### What is required to restart

Both weather recovery conditions must be met:

1. The wind interlock has closed.
2. The duty operator has **recorded** restart approval. (`weather.md`, lines 5–7)

A favourable forecast cannot authorize a restart: the forecast panel supports planning and is not an interlock signal. The planner may compute a plan while execution is suspended, but that plan cannot bypass weather interlocks or clock checks. The calendar likewise cannot authorize execution. (`weather.md`, lines 13–15; `architecture.md`, lines 5–7; `overview.md`, lines 5–7)

**Any independent clock pause must also be resolved.** The gateway checks instrument time against the observatory reference before execution. If the absolute offset exceeds two seconds, execution pauses, the duty operator must be notified, and queued reservations remain unchanged. Recovery from that pause requires **two consecutive reference checks reporting an offset within two seconds**. If the reference is unavailable, execution stays paused; a local clock reading alone cannot satisfy either recovery check. These are the clock-pause recovery conditions, not an additional two-check requirement stated for every wind suspension. (`clock.md`, lines 3–11)

### Whether an indoor instrument may continue

**Yes**, provided the instrument is **explicitly classified as indoor** and its own safety interlocks **remain closed**. A roof shown as closed on the calendar does **not** establish indoor classification. (`weather.md`, lines 9–11)
