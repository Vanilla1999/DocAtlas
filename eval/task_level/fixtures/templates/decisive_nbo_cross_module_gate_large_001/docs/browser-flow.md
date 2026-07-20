# Browser Flow Permission Contract

The browser flow can work online or queue a small offline handoff. The gate receives `allowOfflineFallback` to describe that capability, but it must still ask `PermissionService.evaluateFlowEntry` for the entry decision.

Important contract points:

- Browser entry is allowed only for `PermissionDecision.allow`.
- `PermissionService.evaluateFlowEntry` owns entry decisions; `PermissionService.evaluateReview` owns review/follow-up handling, so the browser gate must not admit `PermissionDecision.deferFollowUp`.
- Offline fallback is not a substitute for camera, foreground location, nearby device, or notification permission.
- Browser code should not interpret partial permission booleans directly; it should delegate to the permission module and then translate the decision into UI state.
