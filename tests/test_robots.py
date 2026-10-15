"""Tests for robots.txt compliance."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx

from docmancer.connectors.fetchers.pipeline.robots import RobotsChecker


ROBOTS_BASIC = """User-agent: *
Disallow: /private/
Disallow: /admin/

Sitemap: https://example.com/sitemap.xml
Sitemap: https://example.com/sitemap-docs.xml
"""

ROBOTS_WITH_CRAWL_DELAY = """User-agent: *
Crawl-delay: 5
Disallow: /secret/
"""

ROBOTS_EMPTY = ""

ROBOTS_ALLOW_ALL = """User-agent: *
Allow: /
"""


def _make_client_with_robots(robots_text: str, status: int = 200) -> httpx.Client:
    mock_resp = MagicMock()
    mock_resp.status_code = status
    mock_resp.text = robots_text

    client = MagicMock(spec=httpx.Client)
    client.get.return_value = mock_resp
    return client

