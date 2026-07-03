from __future__ import annotations

from dataclasses import replace
from collections.abc import Callable
import json
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from docmancer.docs.models import DocsTarget
from docmancer.docs.resolver import normalize_version


DARTDOC_ENTITY_SUFFIXES = (
    "-class.html",
    "-library.html",
    "-mixin.html",
    "-enum.html",
    "-extension.html",
    "-typedef.html",
    "-constant.html",
    "-property.html",
    "-function.html",
)


def pub_dartdoc_root_url(package: str, version: str) -> str:
    return f"https://pub.dev/documentation/{package}/{version}/"


def pub_dartdoc_path_prefix(package: str, version: str) -> str:
    return f"/documentation/{package}/{version}/"


def is_pub_dartdoc_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() == "pub.dev" and parsed.path.startswith("/documentation/")


def is_pub_dartdoc_target(target: DocsTarget) -> bool:
    source_type = target.source_type or "api"
    if target.ecosystem != "pub" or source_type != "api":
        return False
    if target.seed_urls and not target.docs_url and not target.docs_url_template:
        return False
    if is_pub_dartdoc_url(target.docs_url) or is_pub_dartdoc_url(target.docs_url_template):
        return True
    return bool(target.version or target.docs_url_template)


def normalize_pub_dartdoc_target(target: DocsTarget) -> DocsTarget:
    version = normalize_version(target.version) or "latest"
    max_pages = 500 if target.max_pages == 200 else target.max_pages
    allowed_domains = list(target.allowed_domains)
    if not allowed_domains:
        allowed_domains = ["pub.dev"]
    path_prefixes = list(target.path_prefixes)
    prefix = pub_dartdoc_path_prefix(target.library, version)
    if not path_prefixes:
        path_prefixes = [prefix]
    docs_url = target.docs_url or pub_dartdoc_root_url(target.library, version)
    return replace(
        target,
        ecosystem="pub",
        version=version,
        source_type=target.source_type or "api",
        docs_url=docs_url,
        allowed_domains=allowed_domains,
        path_prefixes=path_prefixes,
        max_pages=max_pages,
        doc_format=target.doc_format or "dartdoc",
    )


def _is_library_page(path: str, prefix: str) -> bool:
    if not path.startswith(prefix):
        return False
    rest = path[len(prefix) :]
    return bool(rest) and rest.endswith("/") and "/" not in rest.strip("/")


def _is_entity_page(path: str) -> bool:
    lower = path.lower()
    return lower.endswith(DARTDOC_ENTITY_SUFFIXES) or (lower.endswith(".html") and not lower.endswith("index.html"))


def discover_pub_dartdoc_seed_urls(
    package: str,
    version: str,
    root_html: str,
    root_url: str,
    max_seed_urls: int = 50,
    fetch_url: Callable[[str], str | None] | None = None,
) -> list[str]:
    prefix = pub_dartdoc_path_prefix(package, version)
    entity_urls: list[str] = []
    library_urls: list[str] = []
    seen: set[str] = set()

    def add_url(value: str, *, prefer_library: bool = False, base_url: str = root_url) -> None:
        href = str(value or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            return
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.netloc.lower() != "pub.dev":
            return
        path = parsed.path
        if not path.startswith(prefix):
            return
        normalized = parsed._replace(fragment="", query="").geturl()
        if normalized in seen:
            return
        seen.add(normalized)
        if _is_entity_page(path):
            entity_urls.append(normalized)
        elif prefer_library or _is_library_page(path, prefix):
            library_urls.append(normalized)

    def add_html_links(html: str, *, prefer_library: bool = False, base_url: str = root_url) -> None:
        soup = BeautifulSoup(html or "", "html.parser")
        for link in soup.find_all("a", href=True):
            add_url(str(link.get("href") or ""), prefer_library=prefer_library, base_url=base_url)

    def add_json_links(payload: object) -> None:
        if isinstance(payload, dict):
            for key, value in payload.items():
                if key in {"href", "url", "link", "path"} and isinstance(value, str):
                    add_url(value, prefer_library=value.endswith("/"))
                else:
                    add_json_links(value)
        elif isinstance(payload, list):
            for item in payload:
                add_json_links(item)

    def fetch_and_parse(url: str) -> str | None:
        if fetch_url is None:
            return None
        try:
            return fetch_url(url)
        except Exception:
            return None

    add_html_links(root_html)

    if fetch_url is not None:
        json_candidates = [
            urljoin(root_url, "index.json"),
            urljoin(root_url, "categories.json"),
            urljoin(root_url, "sidebar.json"),
            *[url for url in list(library_urls) if url.endswith(".json")],
        ]
        for json_url in json_candidates:
            body = fetch_and_parse(json_url)
            if not body:
                continue
            try:
                add_json_links(json.loads(body))
            except json.JSONDecodeError:
                add_html_links(body)

        for library_url in list(library_urls):
            html = fetch_and_parse(library_url)
            if html:
                add_html_links(html, base_url=library_url)

        for library_url in list(library_urls):
            html = fetch_and_parse(library_url)
            if html:
                add_html_links(html, base_url=library_url)

    return [*entity_urls, *library_urls][:max(1, max_seed_urls)]
