# Processing architecture

The receiver, journal, exporter and dashboard communicate through durable identifiers.

## Journal design

The append-only journal permits sequential reads and checksum verification. Its file layout groups records by station, while the exporter groups output by civil day. These different groupings explain why a bundle can depend on several files.

## Recovery simulation

The simulator resumes immediately after an in-memory replay and discards records when a demonstration ends. It has no authenticated stations and cannot establish the live receiver recovery policy.
