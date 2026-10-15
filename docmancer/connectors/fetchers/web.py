"""Secure finite whole-document and immutable-file fetcher."""

from __future__ import annotations

from ._web.shared import *  # noqa: F401,F403

from ._web.part01 import _WebFetcherPart01

from ._web.part02 import _WebFetcherPart02

class WebFetcher(_WebFetcherPart01, _WebFetcherPart02):

    """Generic documentation fetcher that works with any docs site.

    Implements the Fetcher protocol: ``def fetch(self, url: str) -> list[Document]``.

    Fetches only exact selected whole-document URLs or approved immutable
    GitHub manifest rows. No platform, sitemap, navigation or llms discovery.

    Args:
        timeout: HTTP request timeout in seconds.
        max_pages: Maximum number of pages to fetch.
        strategy: Legacy compatibility input; cannot expand finite selection.
        browser: Enable Playwright browser fallback for JS-heavy sites.
        respect_robots: Whether to respect robots.txt (default True).
        delay: Base delay between requests to same host (seconds).
        exact_urls: Required finite members; seed_urls is a compatibility input.
        robots_urls: Explicit protocol-control URLs within transport ceilings.
    """



__all__ = [name for name in globals() if not name.startswith("__") and not name.startswith("_WebFetcherPart")]

# Bind the public class into shard globals for static/class-name references.
from ._web import part01 as _impl_part01
_impl_part01.WebFetcher = WebFetcher
from ._web import part02 as _impl_part02
_impl_part02.WebFetcher = WebFetcher

# Install the generic shard compatibility bridge.
from docmancer._internal.shard_compat import install_class_shard_bridge as _install_class_shard_bridge
_install_class_shard_bridge(__name__, WebFetcher, ['docmancer.connectors.fetchers._web.shared', 'docmancer.connectors.fetchers._web.part01', 'docmancer.connectors.fetchers._web.part02'])
