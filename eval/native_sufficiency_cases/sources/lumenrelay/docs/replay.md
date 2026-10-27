# LumenRelay replay rules

A delivery failure and permission to retry are separate decisions.

## Non-idempotent messages

Do not retry a non-idempotent message unless it carries a valid reusable `replay.token`.
A transport timeout alone does not authorize another delivery attempt.
Token validity requires the unchanged message digest and destination defined in the configuration manual.
When the exception applies, the configured total-attempt limit still applies.

## Idempotent messages

An idempotent message may be retried after a transient transport failure, subject to the total-attempt limit.
A permanent authorization failure is not a transient transport failure.

## Operator notes

The replay queue records the reason for each retry.
Queue notes are diagnostic information and do not override the replay rules.

