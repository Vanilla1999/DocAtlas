"""Product-wide budget for model-visible project documentation context."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ContextBudget:
    max_sources: int | None = None
    max_tokens: int | None = None

    def __post_init__(self) -> None:
        if ((self.max_sources is not None and self.max_sources < 1)
            or (self.max_tokens is not None and self.max_tokens < 1)):
            raise ValueError("context budget limits must be positive")

    def bounded_tokens(self, requested: int | None = None) -> int | None:
        if requested is None:
            return self.max_tokens
        requested = max(1, int(requested))
        return requested if self.max_tokens is None else min(requested, self.max_tokens)


PROJECT_CONTEXT_BUDGET = ContextBudget()


__all__ = ["ContextBudget", "PROJECT_CONTEXT_BUDGET"]
