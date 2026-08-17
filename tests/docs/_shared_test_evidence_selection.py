from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from docmancer.docs.application.evidence_selection import (
    EvidenceRequirement,
    EvidenceRequirementSet,
    SelectionConfig,
    SupportDecision,
    aggregate_mixed_selection,
    build_requirements,
    docs_selection_config,
    library_docs_selection_config,
    project_docs_selection_config,
    patch_selection_config,
    select_evidence,
    validate_evidence_sufficiency,
)
from docmancer.docs.application.action_packet import build_action_packet


def _candidate(stable_id: str, text: str, **overrides):
    item = {
        "stable_chunk_id": stable_id,
        "parent_logical_id": overrides.pop("parent_logical_id", "parent:one"),
        "source": overrides.pop("source", f"docs/{stable_id}.md"),
        "display_text": text,
        "display_content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "authority": overrides.pop("authority", "official"),
        "docs_exactness": overrides.pop("docs_exactness", "exact"),
        "version": overrides.pop("version", "2.0"),
        "retrieval_rank": overrides.pop("retrieval_rank", 10),
        "score": overrides.pop("score", 0.5),
    }
    item.update(overrides)
    return item


def _ids(decision):
    return [item.stable_id for item in decision.selected_candidates]
