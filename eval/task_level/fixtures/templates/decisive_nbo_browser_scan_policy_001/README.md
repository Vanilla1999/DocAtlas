# Sanitized NBO Permission Fixture

This fixture is a sanitized slice of a Flutter permission module. It keeps source layout, docs, generated-file boundaries, and dependency pins while removing product-specific names.

Important local sources:

- `lib/modules/permission/ARCHITECTURE.md` explains that `PermissionService` owns browser/scan preflight policy.
- `docs/browser-scan-preflight.md` describes shared browser/scan preflight and deferred follow-up permissions.
- `docs/permission-notifications.md` documents the Android 13 notification runtime-permission rule.
- `docs/permission-location.md` documents why background location is not requested during preflight.
- `pubspec.lock` records the pinned `permission_handler` version.
