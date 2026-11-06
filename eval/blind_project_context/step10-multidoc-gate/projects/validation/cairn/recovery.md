# Restore failure handling

This procedure applies to a production restore interrupted before publication.

## Recovery procedure

Execute every child section below in order. Merely restarting the worker leaves the recovery procedure incomplete.

### Preserve

Stop the worker and retain its restore journal. Record the failed snapshot identifier before changing staging files.

### Reconcile

Compare staged payload checksums with the signed snapshot manifest. Recopy mismatching payloads from the same snapshot; do not mix snapshots within one restore.

### Reopen

Resume the worker only after reconciliation completes. Keep the collection pointer on its previous published snapshot until publication approval is recorded.

## Sandbox reset

The training sandbox can erase its journal and start from any demonstration snapshot. That shortcut does not apply to production recovery.
