from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from docmancer.connectors.fetchers.factory import detect_fetcher_provider
from docmancer.connectors.fetchers.github import GitHubFetcher


def _make_response(status_code: int, text: str = "", json_data=None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.raise_for_status = MagicMock()
    if json_data is not None:
        resp.json.return_value = json_data
    return resp






class TestFetch:
    pass

class TestSingleFileFetch:
    pass
