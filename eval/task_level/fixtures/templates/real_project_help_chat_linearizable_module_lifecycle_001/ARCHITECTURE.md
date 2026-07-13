# Audited architecture overlay

This package is embedded in a host application and shares `GetIt.instance` with host-owned services. The module owns only the registrations it creates. Startup and auth redirect may call init concurrently; logout may call reset across the token-await boundary. Configuration must be installed before package services consume it, and a failed lifecycle operation must remain retryable.
