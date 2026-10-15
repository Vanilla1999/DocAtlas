from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from docmancer.connectors.fetchers.gitbook import GitBookFetcher


def _make_response(status_code: int, text: str = "") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return resp


class TestGitBookFetcherLlmsFullTxt:
    pass


class TestGitBookFetcherLlmsTxt:
    def test_fetch_falls_back_to_llms_txt(self):
        """llms-full.txt returns 404, llms.txt returns bare URLs — 2 Documents."""
        index_content = (
            "https://docs.example.com/page1\n"
            "https://docs.example.com/page2\n"
        )
        page_content = "# Page content"

        responses = {
            "https://docs.example.com/llms-full.txt": _make_response(404),
            "https://docs.example.com/llms.txt": _make_response(200, index_content),
            "https://docs.example.com/page1": _make_response(200, page_content),
            "https://docs.example.com/page2": _make_response(200, page_content),
        }

        mock_client = MagicMock()
        mock_client.get.side_effect = lambda url: responses[url]
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("httpx.Client", return_value=mock_client):
            fetcher = GitBookFetcher()
            docs = fetcher.fetch("https://docs.example.com")

        assert len(docs) == 2
        sources = {d.source for d in docs}
        assert "https://docs.example.com/page1" in sources
        assert "https://docs.example.com/page2" in sources
        for doc in docs:
            assert doc.metadata["fetch_method"] == "llms.txt"

    def test_fetch_llms_txt_markdown_links(self):
        """llms.txt with markdown link format — 2 URLs parsed and fetched."""
        index_content = (
            "[Intro](https://docs.example.com/intro)\n"
            "[Guide](https://docs.example.com/guide)\n"
        )
        page_content = "# Content"

        responses = {
            "https://docs.example.com/llms-full.txt": _make_response(404),
            "https://docs.example.com/llms.txt": _make_response(200, index_content),
            "https://docs.example.com/intro": _make_response(200, page_content),
            "https://docs.example.com/guide": _make_response(200, page_content),
        }

        mock_client = MagicMock()
        mock_client.get.side_effect = lambda url: responses[url]
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("httpx.Client", return_value=mock_client):
            fetcher = GitBookFetcher()
            docs = fetcher.fetch("https://docs.example.com")

        assert len(docs) == 2
        sources = {d.source for d in docs}
        assert "https://docs.example.com/intro" in sources
        assert "https://docs.example.com/guide" in sources


class TestGitBookFetcherFailure:
    pass





class TestLlmsTxtHtmlHandling:
    def test_html_page_is_cleaned(self):
        """Pages returning full HTML should be cleaned via extract_main_content."""
        html_page = (
            '<!DOCTYPE html><html><head><title>Page</title>'
            '<style>:root { --color: red; }</style></head>'
            '<body><nav>Menu</nav>'
            '<article><p>Actual documentation content here.</p></article>'
            '<footer>Copyright</footer></body></html>'
        )
        responses = {
            "https://docs.example.com/llms-full.txt": _make_response(404),
            "https://docs.example.com/llms.txt": _make_response(
                200, "https://docs.example.com/page1\n"
            ),
            "https://docs.example.com/page1": _make_response(200, html_page),
        }

        mock_client = MagicMock()
        mock_client.get.side_effect = lambda url: responses[url]
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("httpx.Client", return_value=mock_client):
            fetcher = GitBookFetcher()
            docs = fetcher.fetch("https://docs.example.com")

        assert len(docs) == 1
        assert "Actual documentation content" in docs[0].content
        assert "--color" not in docs[0].content
        assert "Menu" not in docs[0].content
        assert "Copyright" not in docs[0].content
        assert docs[0].metadata["format"] == "html"

    def test_markdown_page_unchanged(self):
        """Pages returning markdown should be stored as-is."""
        md_content = "# Guide\n\nThis is a markdown page."
        responses = {
            "https://docs.example.com/llms-full.txt": _make_response(404),
            "https://docs.example.com/llms.txt": _make_response(
                200, "https://docs.example.com/page1\n"
            ),
            "https://docs.example.com/page1": _make_response(200, md_content),
        }

        mock_client = MagicMock()
        mock_client.get.side_effect = lambda url: responses[url]
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("httpx.Client", return_value=mock_client):
            fetcher = GitBookFetcher()
            docs = fetcher.fetch("https://docs.example.com")

        assert len(docs) == 1
        assert docs[0].content == md_content
        assert docs[0].metadata["format"] == "markdown"
