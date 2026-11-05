"""Pruning of the merged candidate pool before joint selection.

``DOCATLAS_EXPERIMENT_POOL_PRUNE`` selects a mode. The lexical joint selector
uses ``body`` when the variable is unset (accepted by the blind gate in
STEP4_POOL_PRUNING_RU.md and STEP7_CONTEXT7_PATH_RU.md); the MiniLM section
selector stays ``off`` unless the variable asks otherwise. ``off`` restores
the unpruned pool everywhere. Results and limits of every mode are in
eval/blind_project_context/STEP4_POOL_PRUNING_RU.md.

The unit is a whole source section (path and heading path): the selector
groups adjacent rows of one section, so a partial section would change its
units. Three dictionary-free views score every section for every explicit
query, and each keeps the upper class of Otsu's (1979) two-class split of
its positive scores: no top-k, margin or tuned constant.

  heading     share of the query's character 4-gram information found in
              the section heading path (McNamee & Mayfield 2004); the
              information of a 4-gram is relative to the pool's sections.
  body_words  the best retrieval BM25 score of the section's rows
              (MaxP, Dai & Callan 2019).
  body_chars  the best share of the query's character 4-gram information
              found in one row text of the section (information relative
              to the pool's rows).

A section is kept by a view when one query's cut keeps it. Modes combine the
views; the pool order is kept and no row is edited. ``own_heading_or_body``
is ``heading_or_body`` with the heading view reading only the section's own
heading: the titles of its parent sections are shared by all its sibling
sections and so cannot tell them apart.

``prune_checked_pool`` is the one entry point: the joint selector and the
MiniLM section selector both call it before they see the pool, so the same
whole sections reach whichever selector the host configured (results in
eval/blind_project_context/STEP5_PRE_SELECTION_FILTER_RU.md).
"""
from __future__ import annotations

import math
import os
from collections import Counter

from docmancer.retrieval.lexical_terms import character_ngrams

MODES = ("off", "heading", "body", "heading_or_body", "vote", "own_heading_or_body")
ENVIRONMENT = "DOCATLAS_EXPERIMENT_POOL_PRUNE"


def otsu_upper(scores: list[float]) -> int:
    """Size of the upper class of Otsu's split of descending scores.

    Without any between-class variance (all scores equal) nothing separates
    the units, so all of them stay.
    """
    n = len(scores)
    if n <= 1:
        return n
    total, prefix, best, cut = sum(scores), 0.0, 0.0, n
    for i in range(1, n):
        prefix += scores[i - 1]
        upper, lower = prefix / i, (total - prefix) / (n - i)
        between = (i / n) * ((n - i) / n) * (upper - lower) ** 2
        if between > best:
            best, cut = between, i
    return cut


def _information(feature_sets: list[frozenset[str]]) -> tuple[dict[str, float], float]:
    n = len(feature_sets)
    frequency = Counter(term for features in feature_sets for term in features)
    return ({term: math.log1p((n - count + 0.5) / (count + 0.5)) for term, count in frequency.items()},
            math.log1p((n + 0.5) / 0.5))


def _share(query: frozenset[str], features: frozenset[str], information: dict[str, float],
           absent: float) -> float:
    total = sum(information.get(term, absent) for term in query) or 1.0
    return sum(information.get(term, absent) for term in query & features) / total


def _upper(scores: dict[int, float]) -> set[int]:
    items = sorted(((score, unit) for unit, score in scores.items() if score > 0),
                   key=lambda item: (-item[0], item[1]))
    return {unit for _, unit in items[:otsu_upper([score for score, _ in items])]}


def section_units(rows: list[dict]) -> list[int]:
    """Section number of every row, numbered by first appearance in the pool."""
    numbers: dict[tuple[str, str], int] = {}
    return [numbers.setdefault((str(row.get("path_or_url") or ""), str(row.get("section") or "")), len(numbers))
            for row in rows]


def views(rows: list[dict], lexical: dict[str, list[float]], queries: dict[str, dict], *,
          own_heading: bool = False) -> dict[str, set[int]]:
    """Section numbers kept by each view (union over explicit queries).

    With ``own_heading`` the heading view reads the last part of the heading
    path (the section's own heading) instead of the whole path.
    """
    units = section_units(rows)
    headings: dict[int, str] = {}
    for row, unit in zip(rows, units):
        heading = str(row.get("section") or "")
        headings.setdefault(unit, heading.rsplit(" > ", 1)[-1] if own_heading else heading)
    heading_features = {unit: frozenset(character_ngrams(text)) for unit, text in headings.items()}
    heading_info, heading_absent = _information(list(heading_features.values()))
    body_features = [frozenset(character_ngrams(str(row.get("snippet") or ""))) for row in rows]
    body_info, body_absent = _information(body_features)
    kept: dict[str, set[int]] = {"heading": set(), "body_words": set(), "body_chars": set()}
    for key, query in queries.items():
        grams = frozenset(character_ngrams(str(query.get("text") or "")))
        kept["heading"] |= _upper({unit: _share(grams, features, heading_info, heading_absent)
                                   for unit, features in heading_features.items()})
        words: dict[int, float] = {}
        chars: dict[int, float] = {}
        for index, unit in enumerate(units):
            score = float((lexical.get(key) or [0.0] * len(rows))[index] or 0.0)
            words[unit] = max(words.get(unit, 0.0), score)
            chars[unit] = max(chars.get(unit, 0.0), _share(grams, body_features[index], body_info, body_absent))
        kept["body_words"] |= _upper(words)
        kept["body_chars"] |= _upper(chars)
    return kept


def kept_sections(mode: str, kept: dict[str, set[int]]) -> set[int]:
    heading, words, chars = kept["heading"], kept["body_words"], kept["body_chars"]
    if mode == "heading":
        return heading
    if mode == "body":
        return words & chars
    if mode in ("heading_or_body", "own_heading_or_body"):
        return heading | (words & chars)
    if mode == "vote":
        return (heading & words) | (heading & chars) | (words & chars)
    raise ValueError(f"unknown pool pruning mode: {mode}")


def prune_rows(mode: str, rows: list[dict], lexical: dict[str, list[float]],
               queries: dict[str, dict]) -> tuple[list[int], dict]:
    """Indices of the rows to keep, in pool order, and a bounded receipt."""
    units = section_units(rows)
    kept = views(rows, lexical, queries, own_heading=mode == "own_heading_or_body")
    chosen = kept_sections(mode, kept)
    indices = [index for index, unit in enumerate(units) if unit in chosen]
    receipt = {"mode": mode, "candidate_rows": len(rows), "kept_rows": len(indices),
               "candidate_sections": len(set(units)), "kept_sections": len(chosen),
               **{f"{name}_sections": len(value) for name, value in kept.items()}}
    if not indices:
        receipt["fallback"] = "no_section_kept"
        return list(range(len(rows))), receipt
    return indices, receipt


def pool_prune_mode(default: str = MODES[0]) -> str:
    """The configured mode, else the caller's default; unknown is an error."""
    value = os.environ.get(ENVIRONMENT, default).strip().lower()
    if value not in MODES:
        raise ValueError(f"{ENVIRONMENT} must be one of: {', '.join(MODES)}")
    return value


def prune_checked_pool(payload: dict, snapshot: dict, queries: dict[str, dict], *,
                       default_mode: str = MODES[0]) -> tuple[dict, dict | None]:
    """Keep the chosen whole sections of a checked pool before any selector.

    ``queries`` are the authoritative explicit queries of the read. The
    retrieval BM25 score of every row comes from its bound snapshot entry.
    ``default_mode`` applies only when the environment does not name a mode.
    Returns the payload (a shallow copy with fewer rows, or the same object)
    and a receipt, or ``None`` when pruning is off or nothing can be scored.
    """
    rows = payload.get("sources") or []
    mode = pool_prune_mode(default_mode)
    if mode == "off" or not rows or not queries:
        return payload, None
    matches = [(((snapshot.get(row.get("evidence_id")) or {}).get("source") or {})
                .get("retrieval_query_matches") or {}) for row in rows]
    lexical = {key: [float((match.get(key) or {}).get("lexical_score") or 0.0) for match in matches]
               for key in queries}
    kept, receipt = prune_rows(mode, rows, lexical, queries)
    if len(kept) < len(rows):
        payload = {**payload, "sources": [rows[index] for index in kept]}
    return payload, receipt
