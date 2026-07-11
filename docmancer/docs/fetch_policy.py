"""Security policy for documentation fetch targets."""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Callable, Iterable, TypeAlias
from urllib.parse import urlparse, urlunparse

IPAddress: TypeAlias = ipaddress.IPv4Address | ipaddress.IPv6Address
Resolver: TypeAlias = Callable[[str], Iterable[IPAddress]]


class DocsFetchSecurityError(ValueError):
    """A safe, serializable reason why a documentation target was rejected."""

    def __init__(self, category: str, redacted_url: str):
        super().__init__(category)
        self.category = category
        self.redacted_url = redacted_url


@dataclass(frozen=True)
class ValidatedDocsTarget:
    url: str
    redacted_url: str
    scheme: str
    host: str
    port: int
    resolved_ips: tuple[str, ...]


@dataclass(frozen=True)
class DocsFetchPolicy:
    """Validate every documentation URL before dispatching a request."""

    resolver: Resolver | None = None
    allowed_hosts: tuple[str, ...] = ()
    path_prefixes: tuple[str, ...] = ()

    def allows_scope(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            host = parsed.hostname
            parsed.port
        except (TypeError, ValueError):
            return False
        if parsed.scheme not in {"http", "https"} or not host:
            return False
        normalized_host = host.rstrip(".").lower()
        return bool(
            (not self.allowed_hosts or _host_allowed(normalized_host, self.allowed_hosts))
            and (not self.path_prefixes or _path_allowed(parsed.path or "/", self.path_prefixes))
        )

    def validate_url(self, url: str) -> ValidatedDocsTarget:
        try:
            parsed = urlparse(url)
            host = parsed.hostname
            port = parsed.port
            username = parsed.username
            password = parsed.password
        except (TypeError, ValueError):
            raise DocsFetchSecurityError("invalid_url", "<invalid-url>") from None
        redacted = _redact_url(parsed)
        if parsed.scheme not in {"https", "http"}:
            raise DocsFetchSecurityError("unsupported_scheme", redacted)
        if username is not None or password is not None:
            raise DocsFetchSecurityError("userinfo_not_allowed", redacted)
        if not host:
            raise DocsFetchSecurityError("missing_host", redacted)
        normalized_host = host.rstrip(".").lower()
        if self.allowed_hosts and not _host_allowed(normalized_host, self.allowed_hosts):
            raise DocsFetchSecurityError("host_not_allowed", redacted)
        if self.path_prefixes and not _path_allowed(parsed.path or "/", self.path_prefixes):
            raise DocsFetchSecurityError("path_not_allowed", redacted)
        try:
            literal_ip = ipaddress.ip_address(normalized_host)
        except ValueError:
            literal_ip = None
        try:
            answers = (
                (literal_ip,)
                if literal_ip is not None
                else tuple((self.resolver or resolve_host)(normalized_host))
            )
        except (OSError, UnicodeError, ValueError):
            raise DocsFetchSecurityError("host_resolution_failed", redacted) from None
        if not answers:
            raise DocsFetchSecurityError("host_resolution_failed", redacted)
        for answer in answers:
            if _is_blocked_ip(answer):
                raise DocsFetchSecurityError("private_network_blocked", redacted)
        return ValidatedDocsTarget(
            url=url,
            redacted_url=redacted,
            scheme=parsed.scheme,
            host=normalized_host,
            port=port or (443 if parsed.scheme == "https" else 80),
            resolved_ips=tuple(sorted({str(answer) for answer in answers})),
        )


def resolve_host(host: str) -> tuple[IPAddress, ...]:
    try:
        return (ipaddress.ip_address(host),)
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError):
        return ()
    answers: dict[str, IPAddress] = {}
    for _family, _type, _proto, _canonname, sockaddr in infos:
        try:
            answer = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        answers[str(answer)] = answer
    return tuple(answers.values())


def _is_blocked_ip(address: IPAddress) -> bool:
    mapped = address.ipv4_mapped if isinstance(address, ipaddress.IPv6Address) else None
    candidate = mapped or address
    return bool(
        candidate.is_private
        or candidate.is_loopback
        or candidate.is_link_local
        or candidate.is_multicast
        or candidate.is_unspecified
        or candidate.is_reserved
    )


def _host_allowed(host: str, allowed_hosts: tuple[str, ...]) -> bool:
    for raw in allowed_hosts:
        allowed = raw.rstrip(".").lower()
        if host == allowed or (not allowed.startswith("*.") and host.endswith(f".{allowed}")):
            return True
        if allowed.startswith("*.") and host.endswith(allowed[1:]) and host != allowed[2:]:
            return True
    return False


def _path_allowed(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == prefix.rstrip("/") or path.startswith(prefix.rstrip("/") + "/") for prefix in prefixes)


def _redact_url(parsed) -> str:
    host = parsed.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    try:
        port = parsed.port
    except ValueError:
        return "<invalid-url>"
    if port is not None:
        host = f"{host}:{port}"
    return urlunparse((parsed.scheme, host, parsed.path, parsed.params, "", ""))


def redact_url(url: str) -> str:
    """Return a URL safe for public errors, progress events, and logs."""
    try:
        return _redact_url(urlparse(url))
    except (TypeError, ValueError):
        return "<invalid-url>"
