"""Network policy checks for MCP HTTP executors."""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import TypeAlias
from urllib.parse import urljoin, urlparse

IPAddress: TypeAlias = ipaddress.IPv4Address | ipaddress.IPv6Address


class SecurityError(Exception):
    """Raised when a runtime network policy blocks a request target."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class HttpGrant:
    allowed_hosts: tuple[str, ...]
    allow_private_network: bool = False
    allow_http: bool = False
    max_response_bytes: int = 2_000_000


def grant_from_mapping(raw: dict | None) -> HttpGrant:
    raw = raw or {}
    return HttpGrant(
        allowed_hosts=tuple(raw.get("allowed_hosts") or ()),
        allow_private_network=bool(raw.get("allow_private_network", False)),
        allow_http=bool(raw.get("allow_http", False)),
        max_response_bytes=int(raw.get("max_response_bytes", 2_000_000)),
    )


def target_url(base_url: str, path: str = "") -> str:
    if not path:
        return base_url
    return base_url.rstrip("/") + path


def validate_http_target(url: str, grant: HttpGrant):
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"}:
        raise SecurityError("unsupported_scheme")
    if parsed.scheme == "http" and not grant.allow_http:
        raise SecurityError("plain_http_blocked")
    host = parsed.hostname
    if not host:
        raise SecurityError("missing_host")
    if not host_matches(host, grant.allowed_hosts):
        raise SecurityError("host_not_allowed")
    resolved = resolve_host(host)
    if not resolved:
        raise SecurityError("host_resolution_failed")
    for ip in resolved:
        if is_private_or_metadata_ip(ip) and not grant.allow_private_network:
            raise SecurityError("private_network_blocked")
    return parsed


def validate_redirect(location: str, previous_url: str, grant: HttpGrant):
    return validate_http_target(urljoin(previous_url, location), grant)


def host_matches(host: str, allowed_hosts: tuple[str, ...]) -> bool:
    host = host.rstrip(".").lower()
    for allowed in allowed_hosts:
        allowed = str(allowed).rstrip(".").lower()
        if not allowed:
            continue
        if allowed.startswith("*."):
            suffix = allowed[1:]
            if host.endswith(suffix) and host != allowed[2:]:
                return True
        elif host == allowed:
            return True
    return False


def resolve_host(host: str) -> list[IPAddress]:
    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return []
    out = []
    seen = set()
    for family, _type, _proto, _canonname, sockaddr in infos:
        raw = sockaddr[0]
        if raw in seen:
            continue
        seen.add(raw)
        out.append(ipaddress.ip_address(raw))
    return out


def is_private_or_metadata_ip(ip: IPAddress) -> bool:
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
        return True
    if isinstance(ip, ipaddress.IPv4Address) and ip == ipaddress.ip_address("169.254.169.254"):
        return True
    if isinstance(ip, ipaddress.IPv6Address) and ip == ipaddress.ip_address("fd00:ec2::254"):
        return True
    return False
