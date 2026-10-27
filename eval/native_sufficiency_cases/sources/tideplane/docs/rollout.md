# TidePlane rollout operations

A release identifies the workload configuration to be made active.

## Promotion

Run `tide promote RELEASE_ID` to promote a staged release.
Before promotion, at least two replicas of the staged release must report ready.
The controller's migration interlock is an additional prerequisite, including when the readiness threshold has been met.

## Promotion receipt

The most recent promotion receipt is written to `.tide/receipts/latest.json`.
The receipt records the release identifier and the old and new configuration digests.
This manual does not specify a guaranteed retention period for receipt files.

## History pruning

Do not prune rollout history while a compliance lock is active.
History pruning is separate from worker scheduling and clock validation.

