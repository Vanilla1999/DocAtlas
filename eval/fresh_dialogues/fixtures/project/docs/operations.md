# Recovering a consumer after a crash

## Durable application commit

Apply an event's business effect and record its workspace-scoped event identifier in the same durable application transaction. The service does not make an arbitrary external business effect exactly once on the application's behalf.

## Acknowledgement order

Acknowledge an event only after that application transaction has committed. Acknowledging first can lose the business effect if the consumer then crashes.

## Checkpoint order

Advance the consumer checkpoint only after the server confirms the acknowledgement. A checkpoint records the last confirmed acknowledged sequence, not the last sequence merely read from the stream.

## Replay starting point

After a crash, reopen the same workspace stream from the sequence immediately after the durable checkpoint. Process replayed events in ascending sequence order before accepting a later sequence.

## Duplicate delivery

An event whose business effect committed before a crash but whose acknowledgement was not confirmed may be delivered again. Consult the durable workspace-scoped event-identifier record: skip an already committed business effect, then acknowledge the duplicate.

## Poison event

If an event cannot be processed, stop that consumer at the failing sequence and report it. Do not advance the checkpoint past the event, silently drop it or mark it acknowledged. Quarantining it requires a separate authorized operator action.

## Health signal

The recovery_ready metric becomes true only after the checkpoint has been read and the first replay page has been validated. It does not certify that every business effect is correct.
