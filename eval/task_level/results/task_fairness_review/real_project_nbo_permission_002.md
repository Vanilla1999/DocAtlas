# Fairness Review: real_project_nbo_permission_002

Source project: `/home/viadmin/StudioProjects/nbo`

Sanitized fixture: `eval/task_level/fixtures/templates/real_project_nbo_permission_002/`

| hidden requirement | visible source | discoverability | decision |
|---|---|---|---|
| Do not request `Permission.locationAlways` during browser/scan preflight | issue text, `docs/permission-location.md`, public tests | yes | keep |
| Keep deferred-location policy in `PermissionService` | issue text, `README.md`, `lib/modules/permission/ARCHITECTURE.md` | yes | keep |
| Do not edit presentation providers | issue text, `README.md`, architecture doc | yes | keep |
| Do not edit generated files | `README.md`, architecture doc | yes | keep |
| Use pinned `permission_handler` 11.4.0 API and avoid media permissions | issue text, `pubspec.lock`, public docs expectation | yes | keep |

No hidden requirement is oracle-only. Requirements are discoverable from issue text, visible project docs/source, public tests, or dependency lockfile.
