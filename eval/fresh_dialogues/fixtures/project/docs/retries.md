# HTTP retry policy

## HTTP 429

After HTTP 429, automatic retry is allowed only when Retry-After contains a non-negative integer number of seconds no greater than 90. Wait that many seconds before retrying.

If Retry-After is absent, malformed or greater than 90, stop automatic retry and report the response to the caller. There is no fallback delay.

## HTTP 502

After HTTP 502, automatic retry requires an Idempotency-Key that was already present on the first attempt. Use the identical key and request body for every retry.

At most two retries are permitted after HTTP 502: wait four seconds before the first retry and thirteen seconds before the second. Without the original Idempotency-Key, do not automatically retry.

## HTTP 403

HTTP 403 is a permission denial, not a transient failure. Never automatically retry it or obtain broader credentials on the caller's behalf. A separate authorized access change is required before a new attempt.

## Connection failures

If the connection closes before a response status is received, the client must query the request identifier before deciding to replay it. A network failure alone does not prove that the server rejected the operation.

## Retry accounting

Retry counters belong to one original request identifier. Reconnecting or changing a delay must not reset a counter. A new independent user operation receives a new request identifier.
