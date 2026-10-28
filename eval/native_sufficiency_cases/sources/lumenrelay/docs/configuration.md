# LumenRelay configuration

LumenRelay is a message relay. These settings apply to the fictional challenge installation described in this manual.

## Payload capture

Set `audit.capture=false` to stop recording message payloads.
Envelope metadata, including the message identifier and delivery result, is still written when payload capture is disabled.
The environment restrictions in the production policy also apply to this setting.

## Delivery attempts

`delivery.retry.max=3` permits at most three total delivery attempts, including the first attempt.
The limit does not grant permission to replay a message; replay eligibility is defined separately.

## Replay identity

A `replay.token` is bound to both the original message digest and the destination identifier.
The token cannot authorize a different payload or a different destination.

## Local spool

The relay flushes its local spool every 30 seconds while it is idle.
This timing describes an idle flush, not a delivery deadline or a storage-reduction guarantee.
A spool segment is closed after it reaches eight mebibytes.

