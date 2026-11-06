# Pointer rollback

Rollback changes a published pointer while preserving the incident history.

## Rollback

Restore the previous snapshot pointer when publication verification fails. Preserve the failed publication record and its snapshot identifier for diagnosis. Do not delete the failed staging directory until the incident owner authorizes cleanup.

## Abandoned preview

An unpublished preview pointer may be removed without changing the public collection. Preview removal is not a rollback of a published pointer.
