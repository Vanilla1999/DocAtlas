# Permission Architecture

`PermissionService` is the canonical owner of permission result interpretation for flow entry.

A flow-entry decision must consider the normalized `PermissionResult` contract:

- `PermissionDecision.allow` means all permissions required for immediate entry are available.
- `PermissionDecision.block` means at least one immediate-entry permission is missing or denied.
- `PermissionDecision.deferFollowUp` is reserved for permissions that are explicitly allowed after the user enters the flow. Background location is deferred follow-up; camera, foreground location, nearby device, and Android notification are not deferred for browser/scan entry.

Browser and scan flows both share the same immediate-entry contract. Browser may set `allowOfflineFallback` when it can queue work for later, but offline fallback still cannot bypass missing immediate-entry permissions. Offline sync must also delegate to the same permission service before accepting work created by either flow.

Flow-specific gates must not duplicate permission policy with checks such as direct `cameraGranted`, `locationGranted`, `nearbyGranted`, `notificationGranted`, `hasMissingImmediatePermission`, or `hasPartialImmediateGrant` branches. Keep those meanings in `PermissionService` so browser, scan, and sync remain consistent.

Generated `*.freezed.dart` and `*.g.dart` artifacts are generated output; edit source files only.
