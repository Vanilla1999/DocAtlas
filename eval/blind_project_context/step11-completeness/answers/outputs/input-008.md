If the **absolute clock offset exceeds two seconds**, the gateway must **pause schedule execution, notify the duty operator, and keep queued reservations unchanged**. The comparison is between instrument time and the observatory reference clock. (`clock.md`, lines 3–7)

Recovery must follow these rules:

1. **Require two consecutive reference checks with an offset within two seconds before resuming.** A single satisfactory check is insufficient. (`clock.md`, line 7)
2. **If the reference clock is unavailable, keep execution paused.** A local clock reading alone cannot satisfy either recovery check; recovery therefore requires reference checks to become possible again and meet the two-check requirement. (`clock.md`, lines 7–11)
3. **Do not use the retired prototype’s recovery behavior.** Clearing pending reservations or restarting on the first local clock sample is explicitly prohibited for the current gateway. (`architecture.md`, lines 9–11)
4. **Do not apply the simulator’s exception to the gateway.** The simulator advances time manually without waiting for reference checks, but its accelerated clock is isolated from the real instrument gateway. (`clock.md`, lines 13–15)

Planning may continue while execution is paused, but a computed plan cannot bypass a clock check or weather interlock. If outdoor observations are also suspended because the wind interlock opened, their restart additionally requires the interlock to close and the duty operator to record restart approval. (`architecture.md`, lines 5–7; `weather.md`, lines 5–7)

The supplied excerpts do not describe how to repair or restore an unavailable reference clock; they specify that execution must remain paused while it is unavailable. (`clock.md`, lines 9–11)
