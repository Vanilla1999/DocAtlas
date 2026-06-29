# Generated Source Policy

The permission module uses Freezed/Riverpod generated files. Generated `*.freezed.dart` and `*.g.dart` files are artifacts and must not be hand-edited in benchmark tasks.

For `PermissionInfo` behavior, edit the source-of-truth file:

`lib/modules/permission/data/models/permission_info.dart`

Required helper:

- Add an `isCritical` getter for `PermissionInfo`.
- It must return true for `Permission.camera`, `Permission.phone`, `Permission.location`, and `Permission.locationAlways`.
- It must not classify storage, notification, bluetooth, photos, videos, or audio permissions as critical.
