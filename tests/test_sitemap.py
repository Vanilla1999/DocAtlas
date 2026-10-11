"""Tests for sitemap parsing."""

from __future__ import annotations

from unittest.mock import MagicMock

import gzip
import httpx
import pytest

from docmancer.connectors.fetchers.pipeline.sitemap import (
    _parse_urlset,
    _parse_xml_content,
    parse_sitemap,
)
import xml.etree.ElementTree as ET


STANDARD_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://example.com/docs/getting-started</loc>
        <lastmod>2024-01-15</lastmod>
        <priority>0.8</priority>
    </url>
    <url>
        <loc>https://example.com/docs/api-reference</loc>
        <lastmod>2024-02-20</lastmod>
        <priority>0.6</priority>
    </url>
</urlset>"""

NO_NAMESPACE_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset>
    <url>
        <loc>https://example.com/page1</loc>
    </url>
    <url>
        <loc>https://example.com/page2</loc>
    </url>
</urlset>"""

SITEMAP_INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap>
        <loc>https://example.com/sitemap-docs.xml</loc>
    </sitemap>
    <sitemap>
        <loc>https://example.com/sitemap-api.xml</loc>
    </sitemap>
</sitemapindex>"""

CHILD_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://example.com/docs/child-page</loc></url>
</urlset>"""





