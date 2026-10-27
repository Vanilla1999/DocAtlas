# VellumBuild security rules

Connectivity, namespace authorization, and artifact authenticity are distinct checks.

## Artifact verification

A runner must verify the signature of every artifact read from the shared cache.
A private network does not exempt the runner from signature verification.
An artifact with an invalid signature must not be executed or linked into a build.

## Signing-secret storage

The signing secret must be supplied by the runner's secret store.
It must not be placed in the project's `vellum.toml`, even if that file has restrictive filesystem permissions.

## Diagnostic logs

Do not place access credentials in diagnostic logs.
Diagnostic redaction does not determine which configuration source has precedence.

