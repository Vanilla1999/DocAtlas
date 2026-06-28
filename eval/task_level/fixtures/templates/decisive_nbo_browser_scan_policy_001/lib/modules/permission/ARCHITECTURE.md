# Permission Module Architecture

## Ownership

`PermissionService` owns platform permission policy for browser/scan preflight.

Presentation providers delegate to the service and convert results into UI state. Do not encode platform permission policy in provider or UI layers.

## Browser/scan flow

```text
BrowserFlow / ScanFlow
  -> PermissionProvider.preflightFor(flow, sdkInt)
  -> PermissionService.requiredForPreflight(flow, sdkInt)
  -> UI receives the same service-owned permission policy for both flows
```

Browser and scan currently share a flow-neutral preflight contract. Platform-version checks belong in the shared service method, not in one caller.

## Deferred permissions

`Permission.locationAlways` represents background location. Background location remains deferred and must not be requested during the initial browser/scan preflight.

## Generated files

Generated `*.freezed.dart` and `*.g.dart` files are derived output. They are included in this fixture to preserve the project shape, but they are not source-of-truth and must not be hand-edited.
