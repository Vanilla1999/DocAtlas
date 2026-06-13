"""Metric formulas for docmancer retrieval evals."""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median


def hit_at_k(relevance: list[bool | int | float], k: int) -> float:
    if k <= 0:
        return 0.0
    return 1.0 if any(float(v) > 0 for v in relevance[:k]) else 0.0


def mrr(relevance: list[bool | int | float]) -> float:
    for index, value in enumerate(relevance, start=1):
        if float(value) > 0:
            return 1.0 / index
    return 0.0


def latency_percentile_ms(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    if percentile <= 0:
        return min(values)
    if percentile >= 100:
        return max(values)
    ordered = sorted(float(v) for v in values)
    # Nearest-rank percentile keeps the MVP deterministic and easy to audit.
    rank = max(1, int(round((percentile / 100.0) * len(ordered))))
    return ordered[min(rank - 1, len(ordered) - 1)]


@dataclass
class MetricAccumulator:
    hit_ks: tuple[int, ...] = (1, 3, 5, 10)
    count: int = 0
    hit_sums: dict[int, float] = field(default_factory=dict)
    mrr_sum: float = 0.0
    latencies_ms: list[float] = field(default_factory=list)

    def add(self, relevance: list[bool | int | float], latency_ms: float) -> None:
        self.count += 1
        for k in self.hit_ks:
            self.hit_sums[k] = self.hit_sums.get(k, 0.0) + hit_at_k(relevance, k)
        self.mrr_sum += mrr(relevance)
        self.latencies_ms.append(float(latency_ms))

    def summary(self) -> dict:
        denominator = self.count or 1
        return {
            "queries": self.count,
            "hit_at": {str(k): self.hit_sums.get(k, 0.0) / denominator for k in self.hit_ks},
            "mrr": self.mrr_sum / denominator,
            "latency_ms": {
                "p50": median(self.latencies_ms) if self.latencies_ms else 0.0,
                "p95": latency_percentile_ms(self.latencies_ms, 95),
            },
        }
