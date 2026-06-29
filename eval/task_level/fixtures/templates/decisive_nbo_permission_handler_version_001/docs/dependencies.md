# Dependency Notes

The fixture is pinned to `permission_handler` `11.4.0`, matching the sanitized source project lockfile.

## PermissionStatus contract used by permission review

`permission_handler` `11.4.0` exposes the `PermissionStatus` enum values used in this module:

| PermissionStatus value | Review action |
| --- | --- |
| `PermissionStatus.granted` | `PermissionReviewAction.allowed` |
| `PermissionStatus.denied` | `PermissionReviewAction.retryRequest` |
| `PermissionStatus.permanentlyDenied` | `PermissionReviewAction.openAppSettings` |
| `PermissionStatus.restricted` | `PermissionReviewAction.blockedBySystem` |
| `PermissionStatus.limited` | `PermissionReviewAction.allowedWithLimits` |
| `PermissionStatus.provisional` | `PermissionReviewAction.allowedWithFollowUp` |

Do not rely on latest-version examples that rename or add status symbols. Do not bump `permission_handler`; the app and generated platform bindings are verified against the lockfile version.

The presentation layer may choose icons or text for each `PermissionReviewAction`, but it must not re-map raw `PermissionStatus` values itself.
