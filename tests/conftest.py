"""Test-wide defaults.

Vector retrieval is on by default for user installs, but the test suite
should never spawn the managed Qdrant binary or download FastEmbed models
into the developer's real ``~/.docmancer`` while running locally. Tests
that exercise the vector path opt in explicitly.
"""
from __future__ import annotations

import os

os.environ.setdefault("DOCMANCER_AUTO_VECTORS", "0")

# Unit tests must never reach the real hosted registry (docmancer.dev).
# Point the hosted fallback at an unroutable local port so an accidental
# network fetch fails fast instead of hanging on restricted networks.
# Tests that exercise the hosted path mock transports or delete this var.
os.environ.setdefault("DOCMANCER_REGISTRY_API_URL", "http://127.0.0.1:1")
