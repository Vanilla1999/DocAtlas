# Fairness Review: real_project_nbo_distributed_permission_policy_001

Source project: `/home/viadmin/StudioProjects/nbo`

Snapshot scope: sanitized permission module docs/source excerpts plus minimal dependency manifest/lockfile. Private git remotes, `.git`, credentials, environment files, build output, generated runtime caches, and customer/private data are excluded.

## Hidden Requirements

| hidden requirement | visible source | discoverability | decision |
|---|---|---|---|
| PermissionService owns browser/scan preflight policy. | `lib/modules/permission/ARCHITECTURE.md`; `README.md` | yes | keep |
| Presentation provider must delegate and not encode platform policy. | `lib/modules/permission/ARCHITECTURE.md`; visible `permission_provider.dart` | yes | keep |
| Android 13+ notification permission is required for notification-dependent scan/browser flows. | `docs/permission-notifications.md`; public test | yes | keep |
| `Permission.locationAlways` remains deferred from preflight. | `docs/browser-scan-preflight.md`; `lib/modules/permission/ARCHITECTURE.md`; public test | yes | keep |
| Do not use media permissions as substitutes for notification permission. | `docs/permission-notifications.md`; `pubspec.lock` | yes | keep |
| Generated files must not be hand-edited. | `README.md`; `lib/modules/permission/ARCHITECTURE.md`; generated file headers | yes | keep |
| Dependency files remain pinned to `permission_handler` `11.4.0`. | `pubspec.yaml`; `pubspec.lock` | yes | keep |
| Browser and scan share the same service-owned policy. | `docs/browser-scan-preflight.md`; `lib/modules/permission/ARCHITECTURE.md` | yes | keep |

## Decision

Fixture is valid for screening. No hidden requirement is oracle-only or undiscoverable.
