"""Recheck published STEP4/7/8 aggregates without product or model calls.

This is arithmetic over public research receipts, not a semantic-candidate
replay and not an integration test. In particular, it cannot label any of the
24 newly acquired quote checks after selection.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re


STUDY = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def checked_pair(text: str, pattern: str, name: str) -> tuple[int, int]:
    match = re.search(pattern, text)
    if match is None:
        raise AssertionError(f"Cannot find previously published {name}")
    return int(match.group(1)), int(match.group(2))


def exact_mcnemar(gains: int, losses: int) -> float:
    discordant = gains + losses
    lower = min(gains, losses)
    return min(1.0, 2 * sum(math.comb(discordant, k) for k in range(lower + 1)) / (2**discordant))


def main() -> None:
    study4 = STUDY / "STEP4_POOL_PRUNING_RU.md"
    study7 = STUDY / "STEP7_CONTEXT7_PATH_RU.md"
    union_file = STUDY / "step8-evidence/models/minilm-union-with-baseline.json"
    mini_file = STUDY / "step8-evidence/models/minilm-summary.json"
    e5_file = STUDY / "step8-evidence/models/e5-summary.json"
    inputs = (study4, study7, union_file, mini_file, e5_file)

    step4, step7 = study4.read_text(encoding="utf-8"), study7.read_text(encoding="utf-8")
    union, mini, e5 = (read_json(path) for path in (union_file, mini_file, e5_file))

    after_pruning, before_pruning = checked_pair(
        step4, r"после отсева остаётся\s+(\d+)\s+из\s+(\d+)\s+фактов", "post-pruning counts"
    )
    dev_gains, dev_losses = checked_pair(
        step7, r"\+(\d+) и [−-](\d+) фактов по случаям", "E5 dev churn"
    )
    holdout_gains, holdout_losses = checked_pair(
        step7, r"holdout \+(\d+) и [−-](\d+) фактов по", "E5 holdout churn"
    )

    totals = union["totals"]
    lexical, dense, combined = (
        e5["totals"]["256"][key]
        for key in ("lexical_candidate_facts", "semantic_candidate_facts", "union_candidate_facts")
    )
    total, default, compact, offline_union = (
        totals[key] for key in ("facts_total", "default_facts", "minilm_facts", "union_facts")
    )
    assert (total, lexical, dense, combined) == (260, 236, 254, 260)
    assert (default, compact, offline_union) == (176, 149, 201)
    assert before_pruning == lexical and before_pruning >= after_pruning >= default
    assert (total - lexical, lexical - after_pruning, after_pruning - default) == (24, 31, 29)
    assert (dev_gains, dev_losses, holdout_gains, holdout_losses) == (13, 6, 9, 7)

    cases = totals["cases"]
    assert cases == mini["tokens_o200k"]["all"]["calls"] == 96
    default_tokens = round(union["default_mean_tokens"] * cases)
    mini_tokens = mini["tokens_o200k"]["all"]["total"]
    assert mini["facts_found"] == compact
    assert default_tokens == 824656 and mini_tokens == 143905

    gained, lost = dev_gains + holdout_gains, dev_losses + holdout_losses
    assert default + gained - lost == 185
    assert default + totals["gained_by_minilm"] == offline_union
    assert compact + totals["default_only"] == offline_union

    receipt = {
        "scope": "published aggregate arithmetic; no downstream E5 replay or client answers",
        "source_sha256": {str(path.relative_to(STUDY)): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in inputs},
        "facts": {"total_checks": total, "default_delivered": default,
                  "not_acquired": total - lexical,
                  "lost_in_pool_pruning": lexical - after_pruning,
                  "lost_after_pool_pruning": after_pruning - default},
        "e5_acquisition": {"lexical": lexical, "dense": dense, "union": combined},
        "dense_rerank": {"delivered": default + gained - lost, "gains": gained, "losses": lost,
                         "mcnemar_exact_unclustered_p": round(exact_mcnemar(gained, lost), 9)},
        "minilm": {"delivered": compact, "offline_union_delivered": offline_union,
                   "baseline_text_tokens_total": default_tokens,
                   "mini_text_tokens_total": mini_tokens,
                   "token_length_ratio": round(default_tokens / mini_tokens, 4),
                   "fact_density_ratio": round((compact / mini_tokens) / (default / default_tokens), 4),
                   "marginal_tokens_per_net_default_fact": round((default_tokens - mini_tokens) / (default - compact), 2),
                   "offline_union_extra_tokens_per_gained_fact": round(mini_tokens / totals["gained_by_minilm"], 2)},
        "limitations": [
            "McNemar p assumes 35 independent discordant checks, contradicted by shared topics/facts",
            "aggregates do not contain per-fact E5 ranking, checked source pool, or post-gate decisions",
            "offline two-output union is not an implemented production policy",
        ],
    }
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
