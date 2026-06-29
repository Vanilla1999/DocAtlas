from __future__ import annotations

from dataclasses import dataclass



@dataclass(frozen=True)
class ContextUse:
    retrieved: set[str]
    viewed: set[str]
    used: set[str]
    patch_relevant: set[str]

    @property
    def recall(self) -> float | None:
        if not self.patch_relevant:
            return None
        return len(self.used & self.patch_relevant) / len(self.patch_relevant)

    @property
    def precision(self) -> float | None:
        if not self.used:
            return None
        return len(self.used & self.patch_relevant) / len(self.used)

    @property
    def utilization_rate(self) -> float | None:
        if not self.retrieved:
            return None
        return len(self.used) / len(self.retrieved)


def infer_used_context(patch_text: str, trajectory_text: str, gold_symbols: list[str]) -> set[str]:
    haystack = f"{patch_text}\n{trajectory_text}"
    return {symbol for symbol in gold_symbols if symbol and symbol in haystack}
