# Fairness Review: decisive_nbo_generated_policy_source_001

Source project: `/home/viadmin/StudioProjects/nbo`

Sanitized fixture: `eval/task_level/fixtures/templates/decisive_nbo_generated_policy_source_001/`

| hidden requirement | visible source | discoverability | decision |
|---|---|---|---|
| Add `blocksPreflight` behavior to the `PermissionInfo` source model | issue symptom, `docs/generated-source.md`, public tests | yes | keep |
| Edit `permission_info.dart`, not generated output | `README.md`, `docs/generated-source.md`, `lib/modules/permission/ARCHITECTURE.md`, public tests | yes | keep |
| Preflight-blocking set is camera, phone, foreground location, notification | `docs/generated-source.md`, public tests | yes | keep |
| Background location remains deferred, not preflight-blocking | `docs/generated-source.md`, public tests | yes | keep |
| Do not classify storage/media permissions as preflight-blocking | `docs/generated-source.md`, hidden tests derive from visible doc | yes | keep |
| Use pinned `permission_handler` 11.4.0 `Permission` enum names | `pubspec.lock`, `pubspec.yaml` | yes | keep |

No hidden requirement is oracle-only. Requirements are discoverable from issue text, visible project docs/source, public tests, or dependency lockfile. The issue text describes the user-visible policy symptom and does not prescribe the implementation path.
