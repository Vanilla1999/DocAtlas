from __future__ import annotations

from ipaddress import ip_address
from urllib.parse import urlparse


def is_remote_url(url: str) -> bool:
    return urlparse(url).scheme in {"http", "https"}


def url_security_error(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return f"unsupported URL scheme: {parsed.scheme}"
    host = parsed.hostname or ""
    if host in {"localhost", "localhost.localdomain"}:
        return "localhost URLs are not allowed"
    try:
        address = ip_address(host)
    except ValueError:
        return None
    if address.is_loopback or address.is_private or address.is_link_local or address.is_multicast:
        return "private network URLs are not allowed"
    return None


def host_allowed(url: str, allowed_domains: list[str]) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return any(host == domain or host.endswith(f".{domain}") for domain in allowed_domains)


def path_allowed(url: str, path_prefixes: list[str]) -> bool:
    if not path_prefixes:
        return True
    path = urlparse(url).path or "/"
    return any(path.startswith(prefix) for prefix in path_prefixes)
