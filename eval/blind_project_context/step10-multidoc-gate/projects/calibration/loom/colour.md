# Colour processing

These requirements apply to production derivatives of colour camera originals.

## Profile choice

Use the camera profile recorded in the capture manifest, not the worker's default profile. Embed the selected profile identifier in the derivative metadata. If the manifest profile is unavailable, quarantine the job instead of guessing a profile.

## Monochrome originals

For originals explicitly marked monochrome, skip colour conversion but retain the manifest's monochrome marker in derivative metadata. A filename containing the word grey is not sufficient to establish that status.

## Display preference

The preview screen lets an operator choose a temporary display profile. That choice affects only the screen and must not replace the capture manifest profile.
