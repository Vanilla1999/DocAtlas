"""Tests for Crawl4AI fetcher and extraction adapter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from docmancer.connectors.fetchers.pipeline.crawl4ai_extraction import is_available


