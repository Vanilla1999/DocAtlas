# Session tickets

## Lifetime

Each session ticket expires 47 seconds after issuance. The expiry clock is not paused while the ticket is idle.

## Renewal conditions

A ticket may be renewed at most three times. Renewal is allowed only before the current expiry and only by the worker named in the ticket.

Wait at least eight seconds after issuance or the previous successful renewal. Each successful renewal starts a new 47-second lifetime.

## Signed revocation

Receipt of a signed revocation invalidates the ticket immediately. The same ticket must not be renewed or retried. A replacement session requires a new authorization check.

## Ticket binding

A ticket is bound to its workspace and worker identifier. Copying the ticket into another workspace or using it as a different worker is rejected even when the ticket has not expired.

## Client clock

Clients may display the remaining lifetime using a monotonic clock. The server's timestamp decides whether a renewal arrived before expiry; a local timer is not proof that a ticket remains valid.
