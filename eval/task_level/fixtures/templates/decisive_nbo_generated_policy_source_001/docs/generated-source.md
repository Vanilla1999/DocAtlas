# Generated Source Policy

The permission module uses Freezed/Riverpod generated files. Generated `*.freezed.dart` and `*.g.dart` files are artifacts and must not be hand-edited in benchmark tasks.

For `PermissionInfo` behavior, edit the source-of-truth file:

`lib/modules/permission/data/models/permission_info.dart`

## Permission review policy

The permission review UI distinguishes permissions that block browser/scan preflight from permissions that are shown as deferred follow-up work.

Required source helper:

- Add a `blocksPreflight` getter for `PermissionInfo`.
- It must return true for `Permission.camera`, `Permission.phone`, `Permission.location`, and `Permission.notification`.
- It must return false for `Permission.locationAlways`, because background location remains deferred until after foreground location is granted.
- It must not classify storage, bluetooth, photos, videos, or audio permissions as preflight-blocking.
- Keep the helper in the source model. Do not copy it into generated `*.freezed.dart` or `*.g.dart` artifacts.
