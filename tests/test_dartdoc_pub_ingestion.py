"""Integration tests for Dart/Flutter pub.dev and official docs ingestion."""

from __future__ import annotations

import pytest
from unittest.mock import Mock, patch

from docmancer.docs.dart_official_docs import (
    resolve_dart_official_docs,
    get_seed_urls_for_package,
    has_official_docs,
    normalize_package_name,
)









class TestEndToEndDartIngestion:
    """End-to-end tests with mocked network calls."""
