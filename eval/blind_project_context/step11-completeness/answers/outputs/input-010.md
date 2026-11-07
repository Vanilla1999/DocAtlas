The gateway must **pause schedule execution when the absolute clock offset exceeds two seconds** and resume only after **two consecutive reference checks** each report an offset within two seconds. Its comparison is between instrument time and the observatory reference, performed before executing a schedule. (`clock.md`, lines 1–8)

After excessive drift, it must:

- **Notify the duty operator.**
- **Keep queued reservations unchanged.**
- **Remain paused until both consecutive reference checks meet the recovery threshold.** (`clock.md`, lines 5–8)

**If the reference clock is unavailable, execution must stay paused.** A local clock reading alone cannot satisfy either recovery check. Recovery therefore requires the reference to become available and the two consecutive qualifying checks to be completed; the supplied excerpts do not specify an alternative recovery procedure while the reference remains unavailable. (`clock.md`, lines 5–12)

The gateway must not use the retired prototype’s recovery behavior: **clearing pending reservations or restarting on the first local clock sample is explicitly prohibited** for the current gateway. (`architecture.md`, lines 9–11)

The simulator’s behavior is a separate exception: it advances time manually and never waits for reference checks, but its accelerated clock is isolated from the real instrument gateway. That behavior does not change the gateway’s recovery requirements. (`clock.md`, lines 13–15)
