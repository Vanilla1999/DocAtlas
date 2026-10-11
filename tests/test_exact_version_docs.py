"""Tests for exact-version documentation support."""

from __future__ import annotations

import pytest

from docmancer.docs.exact_version import (
    VersionedDocsResolution,
    resolve_fastapi_versioned_docs,
    resolve_click_versioned_docs,
    resolve_pydantic_versioned_docs,
    resolve_python_versioned_docs,
)
from docmancer.docs.resolver import canonical_library_id






            # The system should NOT silently use fallback_docs_url without marking it




        
        # Registry lookup by exact canonical_id should not cross-contaminate
        # (This is a design constraint verified by the ID generation)



