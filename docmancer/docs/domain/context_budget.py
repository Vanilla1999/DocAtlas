"""Product-wide budget for model-visible project documentation context."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ContextBudget:
    max_sources: int = 3
    max_tokens: int = 800

    def __post_init__(self) -> None:
        if self.max_sources < 1 or self.max_tokens < 1:
            raise ValueError("context budget limits must be positive")

    def bounded_tokens(self, requested: int | None = None) -> int:
        if requested is None:
            return self.max_tokens
        return min(max(1, int(requested)), self.max_tokens)


PROJECT_CONTEXT_BUDGET = ContextBudget()


__all__ = ["ContextBudget", "PROJECT_CONTEXT_BUDGET"]
