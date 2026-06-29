# Scan Flow

Scan flow must use the same permission contract as browser flow.

No scan-specific permission interpretation should exist outside the permission module. If scan behavior differs from browser behavior for the same permission result, the shared contract is the place to fix the interpretation.
