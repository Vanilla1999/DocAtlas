# NBO Cross-Module Permission Snapshot

This benchmark fixture is a sanitized real-project-derived snapshot from the local `nbo` Flutter project.

Only permission, browser, and scan excerpts needed for this benchmark task are included. Private git remotes, `.git` history, credentials, environment files, generated runtime/build output, dependency caches, IDE files, and customer/private data are intentionally excluded.

## Fixture mapping

- `lib/modules/permission/application/permission_service.dart` owns the shared permission contract excerpt.
- `lib/modules/browser/application/browser_permission_gate.dart` and `lib/modules/scan/application/scan_permission_gate.dart` are flow gates that consume the permission contract.
- `lib/modules/permission/domain/permission_result.dart` is the source permission result model.
- `lib/modules/permission/domain/permission_result.freezed.dart` is generated output retained only to preserve project shape.

## Local constraints

- Browser and scan flows must use the shared permission contract.
- Permission interpretation belongs to the permission module, not individual flow modules.
- Flow gates should not duplicate permission policy.
- Generated files are not source-of-truth.
