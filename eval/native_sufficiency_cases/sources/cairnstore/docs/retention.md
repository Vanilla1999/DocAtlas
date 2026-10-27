# CairnStore retention policy

Retention deadlines and legal holds are independent controls.

## Legal holds

An active legal hold forbids object deletion even after the retention deadline has passed.
A compliance officer must record a release of the hold before deletion can be accepted.
The delete command has no flag that bypasses an active legal hold.

## Retention changes

Shortening a future retention deadline requires an administrator.
Changing a deadline does not release a legal hold.

## Export controls

Do not export encryption keys in a support bundle.
Support-bundle export controls do not change read consistency or synchronization scheduling.

