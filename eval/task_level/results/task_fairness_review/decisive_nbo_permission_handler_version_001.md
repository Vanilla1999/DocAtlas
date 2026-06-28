# Fairness Review: decisive_nbo_permission_handler_version_001

Source project: `/home/viadmin/StudioProjects/nbo`

Sanitized fixture: `eval/task_level/fixtures/templates/decisive_nbo_permission_handler_version_001/`

| hidden requirement | visible source | discoverability | decision |
|---|---|---|---|
| Map `PermissionStatus.permanentlyDenied` to app settings rather than retry | issue symptom, `docs/dependencies.md`, public tests | yes | keep |
| Map `PermissionStatus.provisional` to follow-up allowed state rather than app settings | issue symptom, `docs/dependencies.md`, public tests | yes | keep |
| Preserve pinned `permission_handler` 11.4.0 rather than changing dependency versions | `README.md`, `docs/dependencies.md`, `pubspec.yaml`, `pubspec.lock`, public tests | yes | keep |
| Keep raw dependency status classification in the domain mapper, not presentation providers | `README.md`, `lib/modules/permission/ARCHITECTURE.md`, visible source layout | yes | keep |
| Map `restricted` and `limited` according to the same visible pinned-version table | `docs/dependencies.md`, hidden tests derive from visible table | yes | keep |
| Avoid latest/wrong-version invented status symbols | `docs/dependencies.md`, `pubspec.lock` | yes | keep |

No hidden requirement is oracle-only. Requirements are discoverable from issue text, visible project docs/source, public tests, or dependency lockfile. The issue text describes the user-visible review-label symptom and does not prescribe the implementation path.
