# VellumBuild runner setup

Runner configuration selects local and remote artifact locations.

## Shared cache connection

Set `cache.remote.url` to the shared-cache endpoint to enable remote cache access.
The runner also needs a credential scoped to the selected cache namespace.
A credential for a different namespace is rejected even if the endpoint is reachable.

## Local workspace

Each runner creates a temporary work directory for the build.
The work directory is removed after successful publication unless debugging retention is enabled.

## Cleanup

Remote cache cleanup may be initiated by an administrator.
This manual specifies neither an automatic artifact-count limit nor a maximum number of retained remote artifacts.

