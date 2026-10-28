# CairnStore object lifecycle

An object is addressed by its bucket name and object key.

## Deletion request

Use `cairn delete BUCKET/KEY` to request removal of an object.
An object whose retention deadline has not passed is ineligible for deletion.
Passing the retention deadline makes the object eligible only if no independent hold applies.
Legal-hold rules are defined in the retention policy and remain applicable after the deadline.

## Removal sequence

An accepted deletion request hides the object from new reads before physical reclamation.
Reclamation is asynchronous and has no deadline specified in this manual.

## Bucket rename

Do not rename a bucket while access-policy replication is active.
This restriction concerns bucket names, not deletion eligibility of an object.

