If the absolute clock offset **exceeds two seconds**, the gateway must:

- Pause schedule execution and notify the duty operator.
- Keep queued reservations unchanged.
- Resume only after **two consecutive checks against the observatory reference clock** each report an offset within two seconds.

If the reference clock is unavailable, execution must remain paused. A local clock reading alone cannot satisfy either recovery check. [Time coordination: Clock offset and Missing reference](https://raw.githubusercontent.com/Vanilla1999/DocAtlas/e62fa9e357bd22731cddabe930532a4a2faecc18/eval/blind_project_context/step14-host-language-live/frozen-corpus/clock.md)

The retired prototype’s recovery behavior—clearing pending reservations and restarting on the first local clock sample—must not be used for the current gateway. The planner may compute a plan while execution is suspended, but that plan does not bypass the clock check or a weather interlock. [Scheduler architecture: Planner and Prototype recovery](https://raw.githubusercontent.com/Vanilla1999/DocAtlas/e62fa9e357bd22731cddabe930532a4a2faecc18/eval/blind_project_context/step14-host-language-live/frozen-corpus/architecture.md)