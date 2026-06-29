# Fairness Review: real_project_nbo_001

Source project: `/home/viadmin/StudioProjects/nbo`

Snapshot scope: permission module docs/source excerpts plus sanitized dependency manifest/lockfile. Private git remotes, `.git`, build output, generated caches, and environment files are excluded.

## Hidden Requirements

| requirement | why it matters | visible source | discoverability | decision |
|---|---|---|---|---|
| Add Android 13+ notification permission with `Permission.notification`. | This is the behavior requested by the issue and the pinned `permission_handler` API supports this symbol. | Issue text; `docs/permission-notifications.md`; `pubspec.lock`; `lib/modules/permission/domain/services/permission_service.dart` | yes | keep |
| Implement the change in `PermissionService`, not presentation providers. | The module architecture states permission checks are encapsulated in the domain service and providers delegate to it. | `lib/modules/permission/ARCHITECTURE.md`; `README.md`; visible `permission_notifier.dart` | yes | keep |
| Do not hand-edit generated `*.g.dart` or `*.freezed.dart` files. | Generated Riverpod/Freezed files are part of the documented module structure and should not be manually patched for this service-only change. | `lib/modules/permission/ARCHITECTURE.md`; issue text | yes | keep |
| Use pinned `permission_handler` `11.4.0`; do not use unrelated media permission APIs. | Latest or generic Android permission advice can suggest media permissions, but this task is notification-specific and the lockfile is explicit. | `pubspec.lock`; `docs/permission-notifications.md`; issue text | yes | keep |
| Keep `Permission.locationAlways` out of the first batch request. | Existing permission flow defers background location until foreground location is granted. | `docs/permission-notifications.md`; visible `permission_service.dart`; public test | yes | keep |

## Decision

Fixture is valid. No hidden requirement is oracle-only or undiscoverable.
