"""Opt-in pool/unit ablations; no acquisition, scoring, splitting or source admission.

Control delegates to the existing pruner and leaves native unit construction
alone. These settings are separate from the existing paired Qwen policy: the
caller must opt into a *new* study and record ``settings.receipt()``. This
module intentionally neither activates that policy nor changes its guards.

Rows are existing checked windows, NOT guaranteed minimally semantically
complete units. Even a balanced code fence cannot prove condition/context
integrity. The optional structural guard suppresses all smaller alternatives
for a suspicious group; it is a conservative heuristic, not a coherence proof.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
import os
import re
from typing import Protocol, TypeVar

from .experimental_pool_pruning import prune_checked_pool, section_units, views

PRUNING_ENV = "DOCATLAS_EXPERIMENT_QWEN_STUDY_PRUNING"
UNITS_ENV = "DOCATLAS_EXPERIMENT_QWEN_STUDY_UNITS"
GUARD_ENV = "DOCATLAS_EXPERIMENT_QWEN_STUDY_UNIT_GUARD"
STUDY = "checked_pool_units_ablation_v1"


@dataclass(frozen=True)
class StudySettings:
    pruning: str = "control"
    units: str = "control"
    unit_guard: str = "off"

    def __post_init__(self) -> None:
        for name, value, choices in (
            (PRUNING_ENV, self.pruning, ("control", "off", "body_union")),
            (UNITS_ENV, self.units, ("control", "competing_rows")),
            (GUARD_ENV, self.unit_guard, ("off", "conservative")),
        ):
            if value not in choices:
                raise ValueError(f"{name} must be one of: {', '.join(choices)}")
        if self.units == "control" and self.unit_guard != "off":
            raise ValueError("unit guard requires competing_rows")

    @property
    def enabled(self) -> bool:
        return self.pruning != "control" or self.units != "control"

    def receipt(self) -> dict:
        return {"study": STUDY, "enabled": self.enabled,
                "pruning": self.pruning, "units": self.units,
                "unit_guard": self.unit_guard,
                "acquisition": "unchanged_checked_pool",
                "row_integrity": "preexisting_checked_rows_not_semantic_completeness_proof"}


def study_settings(environ: Mapping[str, str] | None = None) -> StudySettings:
    """Read per call; unset settings are the identical native control path."""
    env = os.environ if environ is None else environ
    return StudySettings(*(env.get(name, default).strip().lower() for name, default in (
        (PRUNING_ENV, "control"), (UNITS_ENV, "control"), (GUARD_ENV, "off"))))


def prune_study_pool(
    payload: dict, snapshot: dict, queries: dict[str, dict], *,
    settings: StudySettings, default_mode: str = "body",
    verified_locator_indices: Iterable[int] = (),
) -> tuple[dict, dict | None]:
    """Same API/result shape as prune_checked_pool; preserve original row objects.

    Call at the native prune site, AFTER checked acquisition and the unchanged
    whole-pool-fit shortcut. In body_union only, supply original pool indices
    whose locator was verified with the native _bound_locator_queries function.
    Never pass metadata/path matches as verified indices. Protect their whole
    pruning sections. Control deliberately delegates exactly, including existing
    environment overrides and fallback, without adding locator exceptions.
    """
    if settings.pruning == "control":
        return prune_checked_pool(payload, snapshot, queries, default_mode=default_mode)
    rows = payload.get("sources") or []
    receipt = {**settings.receipt(), "mode": settings.pruning,
               "candidate_rows": len(rows), "kept_rows": len(rows)}
    if settings.pruning == "off" or not rows or not queries:
        receipt["bypass"] = "lexical_prune_only" if settings.pruning == "off" else "nothing_to_score"
        return payload, receipt
    units = section_units(rows)
    protected = set(verified_locator_indices)
    if any(type(index) is not int or not 0 <= index < len(rows) for index in protected):
        raise ValueError("verified_locator_indices must index the original checked pool")
    matches = [(((snapshot.get(row.get("evidence_id")) or {}).get("source") or {})
                .get("retrieval_query_matches") or {}) for row in rows]
    lexical = {key: [float((match.get(key) or {}).get("lexical_score") or 0.0)
                     for match in matches] for key in queries}
    # Reuse the native per-query scoring/Otsu algorithm; only the set operator changes.
    kept = views(rows, lexical, queries)
    body_sections = kept["body_words"] | kept["body_chars"]
    chosen = body_sections | {units[index] for index in protected}
    indices = [index for index, unit in enumerate(units) if unit in chosen]
    receipt.update(candidate_sections=len(set(units)), kept_sections=len(chosen),
                   kept_rows=len(indices), verified_locator_rows=len(protected),
                   **{f"{name}_sections": len(value) for name, value in kept.items()})
    if not indices:
        # Match the native no-section fallback, including its pre-fallback counts.
        receipt["fallback"] = "no_section_kept"
        return payload, receipt
    if len(indices) == len(rows):
        return payload, receipt
    return {**payload, "sources": [rows[index] for index in indices]}, receipt


class UnitLike(Protocol):
    group: int
    indices: tuple[int, ...]


U = TypeVar("U", bound=UnitLike)
# Deliberately reject even balanced fences/lists: partial context is not proven.
_STRUCTURAL_CONTEXT = re.compile(r"(?m)^(?: {0,3}(?:`{3,}|~{3,}|[-+*]\s|\d+[.)]\s|>)| {4}|\t)")


def initial_study_units(
    whole: Sequence[U], rows: Sequence[dict], make_unit: Callable[[int, tuple[int, ...]], U], *,
    settings: StudySettings,
) -> tuple[list[U], dict]:
    """Seed native pending with whole groups AND existing rows before greedy fit.

    Keep native ``whole`` unchanged for group indexing/normalization. Apply the
    caller's usual features-or-locator eligibility to this returned sequence.
    Reuses native unit factory (cost, features, vectors and locator bindings).
    No text is cut or rebuilt. Group indices must come from native _groups.
    """
    candidates = list(whole)
    suppressed = 0
    seen = {item.indices for item in whole}
    if settings.units == "competing_rows":
        for item in whole:
            if len(item.indices) <= 1:
                continue
            if settings.unit_guard == "conservative" and any(
                _STRUCTURAL_CONTEXT.search(str(rows[index].get("snippet") or ""))
                for index in item.indices
            ):
                suppressed += 1
                continue
            for index in item.indices:
                if (index,) not in seen:
                    candidates.append(make_unit(item.group, (index,)))
                    seen.add((index,))
    return candidates, {**settings.receipt(), "whole_units": len(whole),
                        "initial_units": len(candidates), "suppressed_groups": suppressed}


def discard_overlapping_units(pending: dict[tuple[int, ...], U], selected: Iterable[int]) -> dict[tuple[int, ...], U]:
    """Competing mode only: after success remove alternatives sharing any row.

    Call after selected_set is updated. Never strip rows out of a whole unit to
    construct a new residual: other preexisting singleton alternatives remain.
    In competing mode DISABLE the native fit-failure singleton insertion;
    otherwise suppressed units reappear and rejected rows may be retried.
    Control must keep the existing fit-failure and pending lifecycle untouched.
    """
    occupied = set(selected)
    return {indices: item for indices, item in pending.items() if occupied.isdisjoint(indices)}
