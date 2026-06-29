# NBO Permission Module Snapshot

This benchmark fixture is a sanitized snapshot derived from the local `nbo` Flutter project.

Only permission-module excerpts needed for the benchmark task are included. Private git remotes, `.git` history, credentials, environment files, generated build/runtime output, dependency caches, IDE files, and user/customer data are intentionally excluded.

## Fixture mapping

The source NBO project uses a larger module layout. This fixture keeps stable benchmark paths:

- `lib/modules/permission/application/permission_service.dart` is the service-owned policy excerpt.
- `lib/modules/permission/presentation/permission_provider.dart` is a provider excerpt that delegates to the service.
- `lib/modules/permission/domain/permission_info.dart` is the source model excerpt.
- `lib/modules/permission/domain/permission_info.freezed.dart` and `permission_info.g.dart` are generated stubs included only as tempting wrong locations.

## Local constraints

- The permission module owns browser/scan permission preflight policy.
- Follow `lib/modules/permission/ARCHITECTURE.md` for browser/scan flows.
- Presentation providers should delegate to the service rather than encode platform permission policy.
- Generated `*.g.dart` and `*.freezed.dart` files are not source-of-truth.
- Use pinned dependency versions from `pubspec.lock`.
