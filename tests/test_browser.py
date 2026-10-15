"""Tests for optional Playwright browser fallback."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from docmancer.connectors.fetchers.pipeline.browser import BrowserRenderer, _check_playwright_available



