# Browser/Scan Preflight

Browser and scan entry points share one service-owned permission preflight before the user enters device-dependent flows.

The policy is intentionally flow-neutral: browser and scan use the same preflight set for a given platform version. Do not add a browser-only or scan-only branch unless a later ADR explicitly splits the flows.

Foreground/device-flow permissions may be checked before entry. The shared preflight covers camera and foreground location for both browser and scan flows.

Background location remains deferred. `Permission.locationAlways` must not be part of the initial browser/scan preflight batch and is requested later only by the explicit background-location follow-up flow.

Presentation callers should consume `PermissionService.requiredForPreflight(flow, sdkInt)` and should not duplicate permission rules in individual flow callers.
