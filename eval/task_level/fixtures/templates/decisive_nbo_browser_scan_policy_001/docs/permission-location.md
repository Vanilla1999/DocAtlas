# Location Permission Policy

Foreground location may be part of browser/scan preflight when a flow needs device position.

Background location is a follow-up permission. `Permission.locationAlways` represents background location and remains deferred from browser/scan preflight. It is requested only after the user enters the explicit background-location path.

A correct preflight patch may add platform-specific immediate blockers, but it must not move background location into the initial batch.
