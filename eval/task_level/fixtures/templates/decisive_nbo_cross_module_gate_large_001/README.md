# NBO Permission Gate Contract Snapshot

This benchmark fixture is a sanitized real-project-derived snapshot from a Flutter/Dart permission subsystem. It is intentionally limited to permission, browser, scan, sync, and review excerpts.

Excluded: private git history, remotes, credentials, environment files, runtime/build output, dependency caches, IDE files, product-specific domain data, customer/user records, and raw trajectories.

## Fixture map

- `lib/modules/permission/application/permission_service.dart` owns the canonical flow-entry decision contract.
- `lib/modules/permission/domain/permission_result.dart` is the source result model used by all flow gates.
- `lib/modules/browser/application/browser_permission_gate.dart` controls browser entry.
- `lib/modules/scan/application/scan_permission_gate.dart` controls scanner entry.
- `lib/modules/sync/application/offline_sync_gate.dart` controls deferred offline handoff after either flow.
- `lib/modules/review/application/permission_review_policy.dart` renders copy/action hints after a block.
- `docs/permission-architecture.md`, `docs/browser-flow.md`, `docs/scan-flow.md`, and `docs/offline-sync.md` define the cross-module contract.

## Local constraints

- Browser, scan, and offline-sync gates must delegate entry decisions to the permission module.
- Flow modules may pass flow-specific options, but must not duplicate the meaning of partial/degraded permission results.
- Review policy may describe a decision, but must not become the entry gate.
- Generated files are not source-of-truth and must not be hand-edited.
