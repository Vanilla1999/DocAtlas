"""Exact finite source selection, not host/path ceilings or URL equivalence."""
from __future__ import annotations

from time import monotonic
from urllib.parse import unquote, urlparse, urlsplit, urljoin

import httpx


def exact_url(url: str) -> str:
    if not isinstance(url, str) or not url or url != url.strip():
        raise ValueError("invalid_finite_member")
    try:
        parsed = urlparse(url)
        parsed.port
    except ValueError:
        raise ValueError("invalid_finite_member") from None
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or "#" in url or any(ord(char) <= 32 for char in url)):
        raise ValueError("invalid_finite_member")
    decoded = parsed.path
    for _ in range(4):
        value = unquote(decoded)
        if value == decoded:
            break
        decoded = value
    else:
        raise ValueError("invalid_finite_member")
    if "\\" in decoded or any(part in {".", ".."} for part in decoded.split("/")):
        raise ValueError("invalid_finite_member")
    # Preserve query order, values, trailing slashes and all meaningful parameters.
    split = urlsplit(url)
    member = split._replace(netloc=split.netloc.lower(), path=split.path or "/").geturl()
    # Empty delimiters, Unicode/IDNA, default ports and parser repairs are not
    # authorization aliases. Validate the actual HTTP serialization up front.
    if "?" in url and not split.query:
        raise ValueError("invalid_finite_member")
    try:
        serialized = str(httpx.URL(member))
    except (httpx.InvalidURL, ValueError):
        raise ValueError("invalid_finite_member") from None
    if serialized != member:
        raise ValueError("transport_unstable_finite_member")
    return member


def finite_members(urls: list[str] | tuple[str, ...] | None, max_pages: int) -> tuple[str, ...]:
    if not isinstance(urls, (list, tuple)) or not urls:
        raise ValueError("explicit_members_required")
    members = tuple(dict.fromkeys(exact_url(url) for url in urls))
    if not isinstance(max_pages, int) or isinstance(max_pages, bool) or max_pages <= 0 or len(members) > max_pages:
        raise ValueError("finite_members_exceed_max_pages")
    return members


def contains(members: tuple[str, ...], url: str) -> bool:
    try:
        return exact_url(url) in members
    except ValueError:
        return False


def selected_robots(urls: list[str]) -> list[str]:
    """Select only already-declared protocol control URLs; never synthesize one."""
    return [url for url in urls if urlparse(url).path == "/robots.txt" and not urlparse(url).query]


def validate_target_collections(value: dict) -> None:
    """Reject malformed declarations before adapters can coerce them to lists."""
    for field in ("seed_urls", "allowed_domains", "path_prefixes"):
        if field in value and not isinstance(value[field], (list, tuple)):
            raise ValueError("invalid_finite_target_collection")


def preflight_target_urls(
    urls, *, max_pages, allowed_domains, path_prefixes, source_manifest=None,
    cancellation_callback=None, deadline_at=None,
) -> tuple[str, ...]:
    """Snapshot and validate the complete target before any singleton dispatch.

    Local files retain the existing target validation contract. Immutable GitHub
    rows retain their separate blob-to-raw contract; neither lane grants discovery.
    """
    from docmancer.connectors.fetchers.pipeline.filtering import is_docs_url
    from docmancer.docs.fetch_policy import DocsFetchPolicy, DocsFetchSecurityError

    def check_operation():
        if cancellation_callback and cancellation_callback():
            raise RuntimeError("Documentation fetch cancelled.")
        if deadline_at is not None and monotonic() >= deadline_at:
            raise DocsFetchSecurityError("deadline_exceeded", "<selected-target>")

    check_operation()
    if not isinstance(urls, (list, tuple)) or not urls or any(
        not isinstance(url, str) or not url for url in urls
    ):
        raise ValueError("explicit_members_required")
    members = tuple(dict.fromkeys(
        exact_url(url) if urlparse(url).scheme in {"http", "https"} else url
        for url in urls
    ))
    if not isinstance(max_pages, int) or isinstance(max_pages, bool) or max_pages <= 0 or len(members) > max_pages:
        raise ValueError("finite_members_exceed_max_pages")
    remote = tuple(url for url in members if urlparse(url).scheme in {"http", "https"})
    if not remote:
        return members
    for values in (allowed_domains, path_prefixes):
        if not isinstance(values, (list, tuple)) or any(
            not isinstance(value, str) or not value or value != value.strip()
            for value in values
        ):
            raise ValueError("invalid_transport_ceiling")
    hosts, paths = tuple(allowed_domains), tuple(path_prefixes)
    if not hosts:
        raise ValueError("explicit_transport_hosts_required")
    for host in hosts:
        plain = host.removeprefix("*.")
        parsed = urlsplit(exact_url("https://" + plain + "/"))
        if parsed.netloc != plain.lower() or parsed.path != "/" or parsed.query:
            raise ValueError("invalid_transport_ceiling")
    for path in paths:
        if not path.startswith("/") or "?" in path or "#" in path:
            raise ValueError("invalid_transport_ceiling")
        exact_url("https://finite.invalid" + path)
    policy = DocsFetchPolicy(allowed_hosts=hosts, path_prefixes=paths, exact_urls=remote)
    controls = tuple(selected_robots(list(remote)))
    if not source_manifest:
        if any(urlparse(url).hostname in {"github.com", "raw.githubusercontent.com"} for url in remote):
            raise ValueError("github_source_manifest_required")
        if any(not is_docs_url(url, url) for url in remote):
            raise ValueError("finite_member_unsupported_format_or_endpoint")
        if any(not contains(controls, urljoin(url, "/robots.txt")) for url in remote):
            raise ValueError("explicit_robots_member_required")
    for url in remote:
        check_operation()
        policy.validate_url(url)
    if source_manifest:
        raws = finite_members([row["raw_url"] for row in source_manifest["documents"]], max_pages) if source_manifest["documents"] else ()
        raw_policy = DocsFetchPolicy(
            allowed_hosts=("raw.githubusercontent.com",), allow_subdomains=False,
            path_prefixes=tuple(urlparse(url).path for url in raws), exact_urls=raws,
        )
        for url in raws:
            check_operation()
            raw_policy.validate_url(url)
    check_operation()
    return members
