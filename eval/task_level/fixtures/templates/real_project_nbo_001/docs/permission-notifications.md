# Permission Notifications Convention

NBO uses the Permission module as the single place for runtime permission checks before browser and scan flows.

For Android 13+ notification support:

- Declare the notification permission in `lib/modules/permission/domain/services/permission_service.dart`.
- Use `PermissionInfo` and add the permission to `permissionsToRequest` from `addPermissionsNotAw()`.
- Use the pinned `permission_handler` API available in `pubspec.lock`: `permission_handler` `11.4.0` exposes `Permission.notification`.
- Do not use unrelated Android media permission APIs such as `Permission.photos`, `Permission.videos`, or `Permission.audio` for this task.
- Keep `Permission.locationAlways` deferred from the first batch request.
- Do not edit generated Riverpod/Freezed files by hand.
