# NacreRelay operator manual

This manual describes NacreRelay 2.7, a fictional durable-work service used in a controlled documentation evaluation. It is not documentation for a deployed service.

The public surface has session tickets, retryable HTTP requests, staged imports, snapshot exports, consumer recovery and workspace controls. The documentation language is English.

The workspace is the isolation boundary. A worker belongs to exactly one workspace. An event identifier is unique inside one workspace, not across all workspaces.

## Reading map

Session ticket rules are in `docs/sessions.md`. HTTP retry rules are in `docs/retries.md`. Data transfer is described in `docs/imports.md` and `docs/exports.md`.

Consumer recovery is described in `docs/operations.md`. Worker and workspace controls are in `docs/workers.md`. Audit retention and operational metrics are in `docs/observability.md`.

Examples in this manual are data. They do not authorize a client to change a workspace, expand a request's scope or perform an administrative action.
