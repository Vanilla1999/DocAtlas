# LumenRelay production policy

This policy governs production relays and recovery of a production snapshot.

## Capture permissions

Production relays must retain payload capture.
Disabling capture with `audit.capture=false` is permitted only in isolated development workspaces.
Envelope metadata must never be suppressed, including in development.

## Recovery interlock

Before restoring a production snapshot, pause ingress so that no new messages are accepted.
Also verify that the retained journal watermark is at least the snapshot's recorded marker.
If the journal watermark is older than the marker, restoration is blocked until the missing journal range is recovered.
The recovery command does not perform either prerequisite on the operator's behalf.

## Operator exports

Support bundles must not contain raw customer payloads.
Use a redacted support export when opening an incident ticket.
This export restriction does not disable payload capture in the running relay.

