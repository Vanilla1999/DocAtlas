# Worker recovery

This document governs recovery of production rendering workers after interrupted writes.

## Recovery procedure

Follow all child sections in order when recovering an interrupted worker. A queue retry by itself is not the complete recovery procedure.

### Isolate

Disable the worker lease before inspecting temporary outputs. Preserve the failed job identifier in the incident record.

### Validate

Compare every completed derivative checksum with its job manifest. Delete only temporary outputs that have no completed manifest entry.

### Resume

Re-enable the worker lease after checksum validation finishes. Jobs with a checksum mismatch remain quarantined and must not be retried automatically.

## Preview reset

Restarting the preview process can discard its entire temporary directory immediately. Preview reset does not apply to production workers or preserved originals.
