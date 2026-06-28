# Browser/Scan Preflight

Browser and scan entry points use the shared `PermissionService` policy before the user enters device-dependent flows.

Foreground/device-flow permissions may be checked before entry. The shared preflight currently covers camera and foreground location for both browser and scan flows.

Background location remains deferred. `Permission.locationAlways` must not be part of the initial browser/scan preflight batch and is requested later only by the explicit background-location flow.

Both browser and scan should use the same service-owned policy; do not duplicate permission rules in individual flow callers.
