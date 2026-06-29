# Permission - Architecture Guide

Runtime permission checks for Android: camera, storage, location, etc. Used before browser/scan flows.

## Scope

```text
permission/
├── data/
│   └── models/
│       ├── permission_info.dart              # Freezed model: type, name, isGranted
│       └── permission_info.freezed.dart
├── domain/
│   └── services/
│       ├── permission_service.dart           # Wraps permission_handler
│       └── permission_service.g.dart
├── navigation/
│   └── permission_route.dart                 # GoRoute: /permission_screen
├── presentation/
│   ├── permission_screen.dart                # Main screen: checks & requests permissions
│   ├── provider/
│   │   ├── permission_notifier.dart          # Manages permission check flow
│   │   ├── permission_notifier.g.dart
│   │   ├── permission_driver_notifier.dart   # Drives sequential permission requests
│   │   ├── permission_driver_notifier.g.dart
│   │   ├── permission_state.dart             # Freezed: loading / complete / error(neededPermissions)
│   │   └── permission_state.freezed.dart
│   └── widgets/
│       └── needed_permissions.dart           # Lists missing permissions to user
└── README.md
```

## Flow

```text
PermissionScreen.build()
  -> ref.watch(permissionNotifierProvider)
  -> PermissionNotifier checks PermissionService
  -> state = loading -> check or request -> complete or error

On error (missing permissions):
  -> PermissionDriverNotifier requests each missing permission sequentially
  -> NeededPermissions widget shows list
  -> on all granted -> navigate to next screen
```

## State

`PermissionState` is a Freezed union:

| Variant | Meaning |
|---------|---------|
| `loading` | Checking/requesting permissions |
| `complete` | All required permissions granted |
| `error` | Some permissions denied; `neededPermissions` list |

## Key Dependencies

| Dependency | Purpose |
|------------|---------|
| `permission_handler` | Android runtime permission API |
| `PermissionService` | Encapsulates `Permission.service` calls |
| `PermissionDriverNotifier` | Sequential request loop |

## Do NOT

- Add new permission checks without updating `PermissionService` and its test coverage.
- Navigate away from `PermissionScreen` without all required permissions granted.
- Hand-edit generated `*.g.dart` or `*.freezed.dart` files for provider/model changes.
