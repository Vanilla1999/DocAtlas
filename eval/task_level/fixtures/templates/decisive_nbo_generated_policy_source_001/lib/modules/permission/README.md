### Introduction

Runtime permissions are declared in `permissionsToRequest` in the permission use case/service.

```dart
List<PermissionInfo> permissionsToRequest = <PermissionInfo>[
  PermissionInfo(
    name: LocaleKeys.permissionModule_camera.tr(),
    permission: Permission.camera,
  ),
  PermissionInfo(
    name: LocaleKeys.permissionModule_phone.tr(),
    permission: Permission.phone,
  ),
  PermissionInfo(
    name: LocaleKeys.permissionModule_location.tr(),
    permission: Permission.location,
  ),
  PermissionInfo(
    name: LocaleKeys.permissionModule_storage.tr(),
    permission: Permission.storage,
  ),
];
```
