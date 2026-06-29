from __future__ import annotations

AUDIT_EVENTS: list[str] = []


def record_audit(event: str) -> None:
    AUDIT_EVENTS.append(event)


def clear_audit() -> None:
    AUDIT_EVENTS.clear()
