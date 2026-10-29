"""Offline adapters for the two unchanged independent oracle contracts.

Never imported by run.py. V40 uses its original union-of-line-span witnesses;
NEW20 uses its independent literal UTF-8 byte witnesses, without cleanup. There
are no graded relevance labels and no invented nDCG judgments.
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath

from common import DATASETS, PREFIXES, load, read, sha, source_intervals


def prepared_sources(documents: dict[str, str]) -> dict:
    result = {}
    for path, text in documents.items():
        offsets = [0]
        for line in text.splitlines(keepends=True):
            offsets.append(offsets[-1] + len(line))
        result[path] = {"content": text, "raw": text.encode("utf-8"),
                        "sha256": sha(text.encode("utf-8")), "line_offsets": offsets}
    return result


class Oracle:
    def __init__(self, repo: Path, name: str):
        self.name = name
        directory = repo / DATASETS[name][0]
        location = "gold_spans.json" if name == "v40" else "sealed/oracle.json"
        cases = read(directory / location)["cases"]
        self.cases = {case["id"]: case for case in cases}
        if len(self.cases) != DATASETS[name][1]:
            raise ValueError("oracle case identities/count changed")
        if name == "v40":
            self.helper = load("preminilm_historical_gold", directory / "evaluate.py")
        else:
            self.helper = load("preminilm_holdout_gold", repo / "eval/heuristic_removal/assess.py")

    def coverage(self, case: dict, rows: list[dict], documents: dict[str, str], root: str,
                 *, candidate: bool = False, generation: str | None = None) -> dict:
        intervals, errors = source_intervals(rows, documents, root, candidate=candidate,
                                             generation=generation)
        if errors:
            raise ValueError("source fidelity prevents gold scoring: " + repr(errors[:3]))
        prepared = {"root": root, "sources": prepared_sources(documents)}
        original = self.cases[case["id"]]
        if self.name == "v40":
            detail = self.helper._gold(case, original, prepared, intervals)
            facts = [{"id": c["claim_id"], "covered": c["covered"]}
                     for c in detail["claims"] if c["documented"]]
            unavailable = detail["unavailable_requested_claim_ids"]
        else:
            canonical, verified = [], []
            for index, row in enumerate(rows):
                value = (row.get("path") or row.get("source")) if candidate else row["path_or_url"]
                path = PurePosixPath(value)
                if path.is_absolute():
                    path = path.relative_to(PurePosixPath(root))
                canonical.append({"snippet": row["text"] if candidate else row["snippet"]})
                verified.append({"integrity_pass": True, "relative_path": path.as_posix(),
                                 "source_index": index})
            detail = self.helper.new_coverage(case, original, prepared, {"sources": canonical}, verified)
            facts = [{"id": f["id"], "covered": f["covered"]} for f in detail["facts"]]
            unavailable = detail["unavailable_obligations"]
        if detail["errors"]:
            raise ValueError("frozen independent witness invalid: " + repr(detail["errors"]))
        covered = [f["id"] for f in facts if f["covered"]]
        return {"documented_facts": len(facts), "covered_facts": len(covered),
                "covered_fact_ids": covered, "missing_fact_ids": [f["id"] for f in facts if not f["covered"]],
                "all_documented_facts_covered": bool(facts) and len(covered) == len(facts),
                "fact_coverage": len(covered) / len(facts) if facts else None,
                "unavailable_obligations": unavailable, "original_contract": detail}


def brief(coverage: dict) -> dict:
    return {key: value for key, value in coverage.items() if key != "original_contract"}


def retrieval_coverage(oracle: Oracle, case: dict, pool: list[dict], documents: dict[str, str],
                       root: str, generation: str) -> dict:
    """Gold coverage in the unchanged checked-pool order BEFORE MiniLM.

    First complete witness rank is a monotone prefix statistic, not a score
    inferred from MiniLM or FTS. Cache/binary search avoids quadratic rescoring.
    """
    cache = {}

    def score(size):
        size = min(size, len(pool))
        if size not in cache:
            cache[size] = oracle.coverage(case, pool[:size], documents, root,
                                          candidate=True, generation=generation)
        return cache[size]

    full = score(len(pool))
    prefixes = {str(k): {"available_rows": min(k, len(pool)), **brief(score(k))} for k in PREFIXES}
    first_ranks = {}
    for identity in full["covered_fact_ids"]:
        left, right = 1, len(pool)
        while left < right:
            middle = (left + right) // 2
            if identity in score(middle)["covered_fact_ids"]:
                right = middle
            else:
                left = middle + 1
        first_ranks[identity] = left
    first_ranks.update({identity: None for identity in full["missing_fact_ids"]})
    observed = [rank for rank in first_ranks.values() if rank is not None]
    return {"rank_measure": "checked_native_pool_order_before_minilm_not_raw_sql_order",
            "full_pool": full, "prefixes": prefixes, "first_complete_witness_rank": first_ranks,
            "first_supported_fact_rank": min(observed) if observed else None,
            "first_all_documented_facts_rank": max(observed) if (
                observed and full["all_documented_facts_covered"]) else None}
