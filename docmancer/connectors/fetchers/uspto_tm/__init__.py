"""USPTO trademark bulk-data connector.

Reads USPTO Trademark Case Files Data (XML, optionally inside a `.zip`),
streams `case-file` records via ``xml.etree.ElementTree.iterparse``,
validates each one against the ``CaseFile`` Pydantic schema, and emits
``docmancer.core.models.Document`` objects via the normalizer.

Usage:

    from docmancer.connectors.fetchers.uspto_tm import iter_uspto_documents

    for doc in iter_uspto_documents("apc18840407-20240102-xx.xml"):
        ...

This module ships parsers, schema, and normalizer only. The streaming
ingest hook lives in ``docmancer.agent.DocmancerAgent.ingest_records``.
"""
from __future__ import annotations

from .normalizer import case_file_to_document, iter_uspto_documents
from .parser import ParseStats, iter_case_files
from .schema import CaseFile, CaseFileOwner, GoodsAndServices

__all__ = [
    "CaseFile",
    "CaseFileOwner",
    "GoodsAndServices",
    "ParseStats",
    "case_file_to_document",
    "iter_case_files",
    "iter_uspto_documents",
]
