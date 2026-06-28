from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


CandidateSource = Literal["historical_fix", "adr_mismatch", "dependency_trap", "generated_file_trap"]


@dataclass(frozen=True)
class MinedCandidate:
    task_id: str
    source_project: str
    candidate_type: CandidateSource
    title: str
    summary: str
    visible_context_needed: tuple[str, ...]
    tempting_wrong_fix: tuple[str, ...]
    hidden_contract_sources: tuple[str, ...]
    public_test_signal: str
    estimated_fixture_size: str
    fixture_cost_score: int
    privacy_notes: str = "Sanitized summary only; no private URLs, sensitive records, or raw history."
    source_evidence: tuple[str, ...] = field(default_factory=tuple)
    requires_distributed_context: bool = False
    has_nearby_tempting_wrong_fix: bool = False
    public_tests_reveal_patch: bool = False
    hidden_contract_visible: bool = False
    pinned_dependency_matters: bool = False
    generated_source_of_truth_trap: bool = False
    historical_fix_available: bool = False
    exposes_private_domain: bool = False
    requires_heavy_runtime: bool = False
    gold_patch_large: bool = False

    def requires_visible_hidden_contracts(self) -> bool:
        return self.hidden_contract_visible and bool(self.hidden_contract_sources)
