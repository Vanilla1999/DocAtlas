# Fairness Review: decisive_nbo_cross_module_gate_large_001

Source project: `/home/viadmin/StudioProjects/nbo`

Sanitized fixture: `eval/task_level/fixtures/templates/decisive_nbo_cross_module_gate_large_001/`

| hidden requirement | visible source | discoverability | decision |
|---|---|---|---|
| Partial/degraded immediate permission results must block browser entry even when offline fallback exists | issue symptom, `docs/permission-architecture.md`, `docs/browser-flow.md`, public browser test | yes | keep |
| `PermissionService.evaluateFlowEntry` owns the canonical entry decision | `README.md`, `docs/permission-architecture.md`, permission service source | yes | keep |
| Scan gate must delegate to the same entry contract, not a local camera/location subset | `docs/permission-architecture.md`, `docs/scan-flow.md`, scan gate source | yes | keep |
| Offline sync must also delegate and must not preserve browser fallback bypass behavior | `docs/offline-sync.md`, `README.md`, sync gate source | yes | keep |
| Background location remains a deferred review follow-up, not an immediate-entry blocker | `docs/permission-architecture.md`, service `evaluateReview` source | yes | keep |
| Review policy is descriptive and must not become an entry gate | `README.md`, review policy source | yes | keep |
| Generated files and dependency pins remain unchanged | `docs/generated-files.md`, `pubspec.yaml`, `pubspec.lock` | yes | keep |

No hidden requirement is oracle-only. The issue text describes the user-visible inconsistent gating symptom without prescribing the exact edit list. The larger fixture deliberately includes browser, scan, sync, review, permission-domain, docs, and lockfile context to avoid the previously rejected narrow one-flow cross-module task while keeping the solution discoverable from visible repository evidence.
