from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def is_stale(last_refreshed_at: str | None, *, stale_after_days: int, now: datetime | None = None) -> bool:
    if not last_refreshed_at:
        return True
    try:
        refreshed = datetime.fromisoformat(last_refreshed_at)
    except ValueError:
        return True
    if refreshed.tzinfo is None:
        refreshed = refreshed.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return refreshed <= now - timedelta(days=stale_after_days)


def docs_policy(status: str, *, has_registered_source: bool) -> dict[str, Any]:
    if status == "ambiguous":
        return {"direct_webfetch": "forbidden", "reason_code": "registry_candidates_exist"}
    if has_registered_source:
        return {"direct_webfetch": "forbidden", "reason_code": "registered_source_exists"}
    return {"direct_webfetch": "discovery_only", "reason_code": "no_registered_source"}
