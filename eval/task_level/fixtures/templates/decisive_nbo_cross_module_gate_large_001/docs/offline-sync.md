# Offline Sync Permission Contract

Offline sync receives queued work created by browser and scan flows. It must reject work that was created from a permission state that would not pass flow entry.

Use `PermissionService.evaluateFlowEntry(result, allowOfflineFallback: false)` before accepting queued work. Do not copy browser-specific fallback logic into sync.

This keeps browser, scan, and sync aligned when permission semantics change.
