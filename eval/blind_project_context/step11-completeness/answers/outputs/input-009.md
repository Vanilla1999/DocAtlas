When the **absolute clock offset exceeds two seconds**, the gateway must **pause schedule execution, notify the duty operator, and keep queued reservations unchanged**. The gateway checks this offset by comparing instrument time with the observatory reference before executing a schedule. (`clock.md`, lines 3–7)

Recovery must follow these rules:

- **Require two consecutive successful reference checks.** Execution may resume only after both checks report an offset within two seconds. A single successful check is insufficient. (`clock.md`, line 7)
- **Remain paused if the reference clock is unavailable.** A local clock reading alone cannot satisfy either recovery check, so reference unavailability does not permit a local-clock restart. Recovery still requires the two consecutive reference checks. (`clock.md`, lines 7–11)
- **Do not use the retired prototype’s recovery behavior.** Clearing pending reservations after drift or restarting on the first local clock sample is explicitly prohibited for the current gateway. (`architecture.md`, lines 9–11)

Planning may continue while execution is suspended, but a computed plan cannot bypass a clock check or weather interlock. The simulator’s manually advanced clock is isolated from the real gateway; its exemption from waiting for reference checks does not provide a gateway recovery exception. (`architecture.md`, lines 5–7; `clock.md`, lines 13–15)

The supplied excerpts do not specify how to correct the clock, how frequently to repeat reference checks, or any alternative recovery procedure while the reference remains unavailable.
