# Snapshot exports

## Snapshot contents

An export reads the committed manifest that was current when the export request was accepted. Later commits are not added to that export. Uncommitted import chunks are never included.

## Creating an export

Creating an export requires an active session ticket and read permission for the requested workspace. The export does not grant permission to read any other workspace.

## Download lifetime

An export object is retained for six hours. Each signed download link is valid for twelve minutes. Download permission is checked again on every request, so revocation blocks a download immediately even when the object and link have not expired.

## Resuming a download

Resume with the same export identifier and a byte Range request. The returned snapshot identifier must match the original response. An expired signed link can be replaced only after a fresh authorization check; replacing the link does not refresh the six-hour object retention period.

## Empty results

A valid export can contain zero records. An empty export is not an authorization error and must still carry its snapshot identifier and checksum.
