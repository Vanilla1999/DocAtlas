# Fairness Review: decisive_nbo_browser_scan_policy_001

Candidate: `decisive_nbo_browser_scan_policy_001`  
Source project: sanitized NBO permission module  
Sanitized fixture: `eval/task_level/fixtures/templates/decisive_nbo_browser_scan_policy_001/`

## Visible requirement mapping

- Shared browser/scan preflight contract is visible in `docs/browser-scan-preflight.md` and `lib/modules/permission/ARCHITECTURE.md`.
- Android 13+ notification requirement and the correct pinned API are visible in `docs/permission-notifications.md` and `pubspec.lock`.
- Deferred background-location behavior is visible in `docs/permission-location.md` and `docs/browser-scan-preflight.md`.
- Service ownership and provider/generated-file boundaries are visible in `lib/modules/permission/ARCHITECTURE.md`.

## Hidden-test fairness

Hidden assertions check only requirements that are stated in visible source files: service-layer ownership, shared browser/scan behavior, Android version gating, no media-permission substitution, deferred `Permission.locationAlways`, unchanged providers/generated files, and unchanged lockfile pins.

The issue text intentionally avoids spelling out every hidden assertion but points to the same public, discoverable policy: shared preflight on newer Android devices, correct layer, deferred follow-up permissions, and pinned dependency behavior.

## Privacy and sanitization

The fixture contains no product identifiers, customer data, credentials, runtime logs, or private project history. Names are generic permission-module examples.

## Verdict

Fairness clean for strict-offline screening. Hidden requirements map to visible docs/source/lockfile and do not require network access or private knowledge.
