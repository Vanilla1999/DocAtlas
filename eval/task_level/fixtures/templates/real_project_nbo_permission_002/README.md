# NBO Permission Module Snapshot

This benchmark fixture is a sanitized snapshot derived from the local `nbo` Flutter project.

Only the permission module files needed for the task are included. Private git remotes, generated build output, `.git` history, IDE files, and environment files are intentionally excluded.

## Task

Browser/scan preflight currently asks for Android `locationAlways` immediately after foreground location is granted. Keep `locationAlways` deferred: preflight may report it as still needed, but must not call `Permission.locationAlways.request()` during the first browser/scan permission check.

## Local constraints

- Follow `lib/modules/permission/ARCHITECTURE.md`.
- Add permission checks in `PermissionService`.
- Do not move permission logic into presentation providers.
- Keep `locationAlways` policy in `PermissionService`; presentation providers must only delegate.
- Do not hand-edit generated `*.g.dart` or `*.freezed.dart` files.
- Use pinned dependency versions from `pubspec.lock`, especially `permission_handler` version `11.4.0`.
