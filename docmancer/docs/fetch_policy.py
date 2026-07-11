"""Security policy for documentation fetch targets."""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse


class DocsFetchSecurityError(ValueError):
    """A safe, serializable reason why a documentation target was rejected."""

    def __init__(self, category: str, redacted_url: str):
        super().__init__(category)
        self.category = category
        self.redacted_url = redacted_url


@dataclass(frozen=True)
class DocsFetchPolicy:
    """Validate documentation URLs before transport objects are constructed."""

    def validate_url(self, url: str) -> str:
        try:
            parsed = urlparse(url)
            username = parsed.username
            password = parsed.password
        except (TypeError, ValueError) as exc:
            raise DocsFetchSecurityError("invalid_url", "<invalid-url>") from exc
        redacted = urlunparse((parsed.scheme, parsed.hostname or "", parsed.path, parsed.params, "", parsed.fragment))
        if parsed.scheme not in {"https", "http"}:
            raise DocsFetchSecurityError("unsupported_scheme", redacted)
        if username is not None or password is not None:
            raise DocsFetchSecurityError("userinfo_not_allowed", redacted)
        return url
