# Time coordination

The gateway compares instrument time with the observatory reference before executing a schedule.

## Clock offset

If the absolute clock offset exceeds two seconds, pause schedule execution and notify the duty operator. Keep queued reservations unchanged. Resume only after two consecutive reference checks report an offset within two seconds.

## Missing reference

If the reference clock is unavailable, keep execution paused; a local clock reading alone cannot satisfy either recovery check.

## Simulation clock

The simulator advances time manually and never waits for reference checks. Its accelerated clock is isolated from the real instrument gateway.
