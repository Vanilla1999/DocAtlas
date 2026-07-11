"""Tests for provider routing in DocmancerAgent."""

from __future__ import annotations

from unittest.mock import patch

from docmancer.agent import DocmancerAgent
from docmancer.connectors.fetchers.web import WebFetcher


class TestAutoDetection:
    def test_untrusted_html_is_not_fetched_during_provider_selection(self):
        agent = DocmancerAgent(_lazy_init=True)

        with patch("httpx.Client") as client:
            fetcher = agent._get_fetcher(provider=None, url="https://example.com")

        client.assert_not_called()
        assert isinstance(fetcher, WebFetcher)

    def test_generic_returns_web_fetcher(self):
        agent = DocmancerAgent(_lazy_init=True)
        fetcher = agent._get_fetcher(provider=None, url="https://example.com")
        assert isinstance(fetcher, WebFetcher)

    def test_explicit_provider_overrides_auto(self):
        agent = DocmancerAgent(_lazy_init=True)
        fetcher = agent._get_fetcher(provider="web", url="https://example.com")
        assert isinstance(fetcher, WebFetcher)

    def test_explicit_gitbook_provider_uses_secure_web_boundary(self):
        agent = DocmancerAgent(_lazy_init=True)
        fetcher = agent._get_fetcher(provider="gitbook", url="https://example.com")
        assert isinstance(fetcher, WebFetcher)

    def test_explicit_mintlify_provider_uses_secure_web_boundary(self):
        agent = DocmancerAgent(_lazy_init=True)
        fetcher = agent._get_fetcher(provider="mintlify", url="https://example.com")
        assert isinstance(fetcher, WebFetcher)

    def test_github_auto_route_uses_secure_web_boundary(self):
        agent = DocmancerAgent(_lazy_init=True)
        fetcher = agent._get_fetcher(provider=None, url="https://github.com/acme/docs")
        assert isinstance(fetcher, WebFetcher)

    def test_explicit_crawl4ai_provider_uses_secure_web_boundary(self):
        agent = DocmancerAgent(_lazy_init=True)
        fetcher = agent._get_fetcher(provider="crawl4ai", url="https://example.com")
        assert isinstance(fetcher, WebFetcher)

    def test_unknown_remote_site_uses_web_without_preflight_request(self):
        agent = DocmancerAgent(_lazy_init=True)

        with patch("httpx.Client") as client:
            fetcher = agent._get_fetcher(provider=None, url="https://unreachable.com")

        client.assert_not_called()
        assert isinstance(fetcher, WebFetcher)
