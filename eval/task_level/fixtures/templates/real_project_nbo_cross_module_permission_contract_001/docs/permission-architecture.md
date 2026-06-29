# Permission Architecture

`PermissionService` defines the canonical permission result interpretation for app entry flows.

Flow-specific gates must not duplicate permission policy. Browser and scan gates should consume the same shared contract from the permission module.

When permission results change shape, update the source model or shared service in the permission module. Do not patch browser-only or scan-only interpretation branches.
