"""Shared, inference-free guards for paired-Qwen selection and its preflight.

Existing selector checks are shared instead of duplicated. Conflicting opt-ins
fail before routing to a different scorer; CLI preflight cannot establish
whether a future request will own a native context-read scope.
"""
from __future__ import annotations

import os

from .experimental_pool_pruning import pool_prune_mode
from .experimental_qwen_ablation import load_settings as qwen_study_settings
from .experimental_qwen_checked_pool import enabled as paired_qwen_enabled, cache_directory
from .experimental_qwen_pool_units import (
    study_settings as qwen_pool_settings, PRUNING_ENV, UNITS_ENV, GUARD_ENV,
)


JOINT_POOL_PRUNE_DEFAULT = "body"
JOINT_EXPERIMENT_CHOICES = {
    "DOCATLAS_EXPERIMENT_JOINT_TERMS": ("word", "char4"),
    "DOCATLAS_EXPERIMENT_JOINT_PRIORITY": ("cost_sqrt", "gain"),
    "DOCATLAS_EXPERIMENT_JOINT_FUSION": ("mean", "max_shared_scale"),
    "DOCATLAS_EXPERIMENT_JOINT_CUT": ("off", "otsu_mean", "otsu_union"),
}


class PairedQwenProfileError(ValueError):
    """A configuration conflict that the public MCP envelope can name."""

    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__(reason_code)


def joint_experiment(name: str) -> str:
    choices = JOINT_EXPERIMENT_CHOICES[name]
    value = os.environ.get(name, choices[0]).strip().lower()
    if value not in choices:
        raise ValueError(f"{name} must be one of: {', '.join(choices)}")
    return value


def study_options():
    """Explicit independent study; never silently alter the original paired arm."""
    selection, pool = qwen_study_settings(), qwen_pool_settings()
    if any(name in os.environ for name in (PRUNING_ENV, UNITS_ENV, GUARD_ENV)) and selection.mode is None:
        raise ValueError("qwen_pool_options_require_explicit_study")
    if pool.enabled and selection.mode != "control":
        raise ValueError("qwen_study_change_one_mechanism_at_a_time")
    if pool.pruning != "control" and pool.units != "control":
        raise ValueError("qwen_study_pruning_and_units_are_separate_arms")
    if pool.units == "competing_rows" and pool.unit_guard != "conservative":
        raise ValueError("qwen_study_competing_rows_requires_conservative_guard")
    return selection, pool


def validate_paired_context_mode(minimal: bool | None = None) -> None:
    # Refuse the incompatible opt-ins before minimal_context_enabled() asks
    # for model assets which cannot make the combination valid.
    if minimal is None:
        minimal = os.environ.get("DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT") == "1"
    if paired_qwen_enabled() and minimal:
        raise PairedQwenProfileError("paired_qwen_requires_default_native_acquisition_not_minimal_complete_scope")


def validate_paired_compression(active: bool) -> None:
    if paired_qwen_enabled() and active:
        raise PairedQwenProfileError("paired_qwen_requires_compression_off")


def validated_minimal_context_enabled() -> bool:
    from docmancer.docs.domain.minimal_context_config import minimal_context_enabled

    validate_paired_context_mode()
    return minimal_context_enabled()


def validated_section_compression_enabled() -> bool:
    from .section_compression import enabled

    active = enabled()
    validate_paired_compression(active)
    return active


def validate_paired_context_budget(cap: int | None) -> None:
    if paired_qwen_enabled() and cap is None:
        raise ValueError("paired_qwen_requires_native_context_token_budget")


def validate_paired_native_settings(settings: tuple[str, str, str, str]) -> None:
    if paired_qwen_enabled() and (
        settings != ("word", "cost_sqrt", "mean", "off")
        or pool_prune_mode(JOINT_POOL_PRUNE_DEFAULT) != JOINT_POOL_PRUNE_DEFAULT
        or os.environ.get("DOCATLAS_EXPERIMENT_JOINT_RELEVANCE", "off") != "off"
    ):
        raise ValueError("paired_qwen_requires_default_pruning_eligibility_mmr_and_cost_settings")


def configured_profile() -> dict:
    """Check the current process's configuration without opening a request scope."""
    from docmancer.docs.domain.original_body_discovery import configured_context_max_tokens

    selection, pool = study_options()
    validated_minimal_context_enabled()
    compression_active = validated_section_compression_enabled()
    cap = configured_context_max_tokens()
    validate_paired_context_budget(cap)
    settings = tuple(joint_experiment(name) for name in JOINT_EXPERIMENT_CHOICES)
    validate_paired_native_settings(settings)
    cache_path = os.environ.get("DOCATLAS_EXPERIMENT_PAIRED_CACHE")
    if paired_qwen_enabled() and cache_path:
        cache_directory(cache_path)
    return {
        "selection_mode": selection.mode,
        "pruning": pool.pruning,
        "units": pool.units,
        "unit_guard": pool.unit_guard,
        "section_compression_active": compression_active,
        "native_budget": cap,
        "request_binding": "not_checked",
    }
