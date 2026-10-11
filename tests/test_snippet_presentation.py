from __future__ import annotations

from docmancer.docs.domain.snippets import (
    build_snippet_presentation,
    clean_snippet_title,
    clean_surrounding_context,
    extract_snippet_candidates,
    infer_snippet_query_intent,
    normalize_code_for_dedupe,
)
from docmancer.docs.models import DocsChunk


def chunk(title, content, metadata=None, source="https://example.com/docs"):
    return DocsChunk(title=title, content=content, source=source, url=source, metadata=metadata or {})











































