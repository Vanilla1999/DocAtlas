# Fairness Review: real_project_nbo_generated_source_001

Source project: `/home/viadmin/StudioProjects/nbo`

Sanitized fixture: `eval/task_level/fixtures/templates/real_project_nbo_generated_source_001/`

| hidden requirement | visible source | discoverability | decision |
|---|---|---|---|
| Add `isCritical` helper to source model | issue text, `docs/generated-source.md`, public tests | yes | keep |
| Edit `permission_info.dart`, not generated output | issue text, `README.md`, `docs/generated-source.md`, architecture doc | yes | keep |
| Critical set is camera, phone, location, locationAlways | issue text, `docs/generated-source.md`, public tests | yes | keep |
| Do not classify storage/media/notification as critical | `docs/generated-source.md`, hidden/public tests derive from visible doc | yes | keep |
| Use pinned `permission_handler` 11.4.0 Permission enum | issue text, `pubspec.lock` | yes | keep |

No hidden requirement is oracle-only. Requirements are discoverable from issue text, visible project docs/source, public tests, or dependency lockfile.
