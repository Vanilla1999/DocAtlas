# VellumBuild command-line behavior

A build evaluates a target and produces one or more artifacts.

## Fresh execution

`vellum build --fresh TARGET` skips cache reads for that build.
A successful build with `--fresh` still publishes its new artifacts to the configured cache.
Use this mode when existing artifacts must not be reused but the new result should remain reusable.

## No-cache execution

`vellum build --no-cache TARGET` disables both cache reads and cache writes for that build.
It does not publish the new result to the shared cache.

## Reporting

`--report-json` writes a machine-readable build report.
Do not treat a report file as an artifact-signature verification result.

