# Fairness Review: real_project_nbo_cross_module_permission_contract_001

Source project: `/home/viadmin/StudioProjects/nbo`

Snapshot scope: sanitized permission/browser/scan module docs/source excerpts plus minimal dependency manifest/lockfile. Private git remotes, `.git`, credentials, environment files, build output, generated runtime caches, and customer/private data are excluded.

## Hidden Requirements

| hidden requirement | visible source | discoverability | decision |
|---|---|---|---|
| Permission module owns canonical permission interpretation. | `docs/permission-architecture.md`; `lib/modules/permission/application/permission_service.dart` | yes | keep |
| Browser and scan flows must share the same permission contract. | `README.md`; `docs/browser-flow.md`; `docs/scan-flow.md` | yes | keep |
| Flow gates must not duplicate permission policy. | `docs/permission-architecture.md`; `docs/scan-flow.md` | yes | keep |
| Browser gate delegates to the shared permission contract. | visible `browser_permission_gate.dart`; `docs/browser-flow.md` | yes | keep |
| Scan gate delegates to the shared permission contract. | visible `scan_permission_gate.dart`; `docs/scan-flow.md`; public test | yes | keep |
| Generated files must not be hand-edited. | `docs/generated-files.md`; generated file headers | yes | keep |
| Dependency files must remain pinned and unchanged. | `pubspec.yaml`; `pubspec.lock` | yes | keep |

## Decision

Fixture is valid for screening. No hidden requirement is oracle-only or undiscoverable.
