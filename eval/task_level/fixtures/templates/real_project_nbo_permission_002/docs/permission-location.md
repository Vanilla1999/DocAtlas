# Location Permission Policy

The browser/scan preflight requests foreground-safe permissions only.

`Permission.locationAlways` is intentionally deferred because Android shows a separate background-location journey. The first `PermissionService.checkAndRequestPermissions()` call must not call `Permission.locationAlways.request()`.

Implementation rules:

- Keep the policy in `lib/modules/permission/domain/services/permission_service.dart`.
- Keep `Permission.locationAlways` out of the first batch request list.
- If foreground location is not granted or background location is still needed, return the existing `permissionLocationAlways` item in `permissionsToRequestAgain` so the UI can explain the deferred step.
- Do not encode this policy in presentation providers.
- Do not hand-edit generated `*.g.dart` or `*.freezed.dart` files.
