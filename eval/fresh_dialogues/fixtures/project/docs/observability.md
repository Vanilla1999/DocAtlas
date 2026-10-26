# Operational observations

## Audit retention

AuditTrail entries are retained for 21 days from ingestion. Entries are removed after that interval even if the corresponding workspace is paused.

## Audit exports

Operators with audit-read permission may export the retained entries. An export contains event timestamps, opaque actor identifiers, workspace identifiers and action outcomes; it does not include reusable tickets or signed download links.

## Metrics

queue_depth counts accepted tasks not yet assigned to a worker. in_flight counts tasks currently assigned but not completed. Neither metric includes uncommitted import chunks.

## Alert evaluation

The default queue_depth alert is evaluated every 20 seconds and requires three consecutive violating samples. It is an operational alert, not a contractual availability calculation.

## Diagnostic sampling

Tracing samples one in every sixteen successful requests. Permission denials and failed administrative actions are always recorded. Sampling must not remove AuditTrail records.
