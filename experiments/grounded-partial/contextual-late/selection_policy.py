"""Experimental, gold-blind retention policy. Not a production selector.

Only the runner can supply already-qualified source variants. The policy never
retrieves, rewrites a quote, changes admission, or decides answer sufficiency.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import re
from typing import Any, Callable

Item = dict[str, Any]
_SIGNATURE_INTENT = re.compile(r"\bsignatures?\b|\bсигнатур\w*", re.I)
_IDENTIFIER = r"[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*"
_STOP = frozenset("a an and are as at be by does for from how in is it of on or the this to was what when where which with would add adds adding used какая какой какие как для это что или при после одна одну к и в на у the signature signatures".split())


def signature_subjects(question: str) -> tuple[str, ...]:
    """Recognize explicit signature intent, never guess an API from evidence."""
    if not _SIGNATURE_INTENT.search(question):
        return ()
    direct = re.search(
        rf"(?:\bsignatures?\b|\bсигнатур\w*)\s+(?:(?:of|for|the|для|у)\s+)*`?({_IDENTIFIER})",
        question, re.I,
    )
    if direct and direct.group(1).casefold() not in _STOP:
        return (direct.group(1),)
    quoted = re.findall(rf"`({_IDENTIFIER})`", question)
    technical = [name for name in re.findall(_IDENTIFIER, question)
                 if re.search(r"[a-z][A-Z]|_|\.", name)]
    # Multiple unbound names are ambiguous. Do not infer the target from a hit.
    names = tuple(dict.fromkeys(quoted or technical))
    return names if len(names) == 1 else ()


def signature_features(question: str, text: str) -> frozenset[str]:
    found = set()
    for subject in signature_subjects(question):
        name = re.escape(subject)
        definition = rf"(?:^|\n)\s*(?:async\s+)?def\s+{name}\s*\([^)]{{0,800}}\)\s*(?:->[^:\n]+)?\s*:"
        labelled = rf"(?i:signature|сигнатура)\s*:\s*[`\"']?{name}\s*\([^\n)]{{0,800}}\)"
        if re.search(definition, text) or re.search(labelled, text):
            found.add("signature:" + subject)
    return frozenset(found)


def prefer_signature(candidates: list[Item], question: str) -> list[Item]:
    """Stable no-op except for a visible definition of the requested signature."""
    if not signature_subjects(question):
        return list(candidates)
    def score(candidate: Item) -> int:
        text = next((candidate.get(key) for key in ("snippet", "content", "display_text")
                     if isinstance(candidate.get(key), str)), "")
        return len(signature_features(question, text))
    return sorted(candidates, key=lambda c: -score(c))


def make_item(source: Item, origin: Item, *, rank: int, qualified: bool = True) -> Item | None:
    """Bind one literal quote to an unambiguous absolute character interval."""
    snippet = source.get("snippet")
    raw = next((origin.get(key) for key in ("code", "snippet", "content", "display_text")
                if isinstance(origin.get(key), str) and origin.get(key)), "")
    start = origin.get("char_start")
    if not isinstance(snippet, str) or not snippet or type(start) is not int:
        return None
    offset = raw.find(snippet)
    if offset < 0 or raw.find(snippet, offset + 1) >= 0:
        return None
    return {"source": deepcopy(source), "origin": deepcopy(origin), "rank": rank,
            "qualified": qualified, "start": start + offset,
            "end": start + offset + len(snippet)}


def _safe(item: Item, identity: str, authoritative: bool) -> bool:
    raw = item["origin"]
    return bool(
        item.get("qualified") is True
        and raw.get("source_class") == "project_doc"
        and raw.get("project_identity") == identity
        and not raw.get("stale")
        and raw.get("freshness", "current") == "current"
        and raw.get("index_freshness", "synchronized") == "synchronized"
        and not raw.get("risk_flags") and not raw.get("instruction_risk_flags")
        and (not authoritative or item["source"].get("authority") == "source_of_truth")
    )


def _path(item: Item) -> str:
    return str(item["source"].get("path_or_url") or item["origin"].get("path") or "")


def retains(before: list[Item], after: list[Item]) -> bool:
    return all(any(_path(old) == _path(new)
                   and new["start"] <= old["start"] < old["end"] <= new["end"]
                   and old["source"]["snippet"] in new["source"]["snippet"]
                   for new in after) for old in before)


def compatible(items: list[Item]) -> bool:
    for i, left in enumerate(items):
        for right in items[i + 1:]:
            if left["source"]["snippet"].strip() == right["source"]["snippet"].strip():
                return False
            if _path(left) == _path(right) and max(left["start"], right["start"]) < min(left["end"], right["end"]):
                return False
    return True


def _features(items: list[Item], question: str, lookup_texts: tuple[str, ...]) -> tuple[set[str], set[str]]:
    requested = {t.casefold() for t in re.findall(r"[\w-]+", " ".join((question, *lookup_texts)))
                 if len(t) >= 3 and t.casefold() not in _STOP}
    signatures, terms = set(), set()
    for item in items:
        text = item["source"]["snippet"]
        signatures.update(signature_features(question, text))
        terms.update(requested & {t.casefold() for t in re.findall(r"[\w-]+", text)})
    return signatures, terms


def retain_extend(
    baseline: list[Item], candidates: list[Item], *, question: str,
    lookup_texts: tuple[str, ...], tokens: Callable[[list[Item]], int],
    max_tokens: int = 800, max_sources: int = 3,
) -> list[Item]:
    """Up to three monotone extensions; empty admission is deliberately a no-op.

    Lexicographic utility: new signature facets, new requested lexical terms,
    original qualified-candidate rank, additional literal characters per added
    serialized DTO token, additional characters. This is a heuristic, not proof.
    """
    if not baseline:
        return []
    if not compatible(baseline):
        return deepcopy(baseline)
    if tokens(baseline) > max_tokens or len(baseline) > max_sources:
        raise ValueError("Baseline already violates the inherited budget")
    identities = {item["origin"].get("project_identity") for item in baseline}
    if len(identities) != 1 or not all(identities):
        return deepcopy(baseline)
    identity = next(iter(identities))
    authoritative = any(item["source"].get("authority") == "source_of_truth" for item in baseline)
    pool = [deepcopy(item) for item in candidates if _safe(item, identity, authoritative)]
    current = deepcopy(baseline)
    for _ in range(3):
        old_features = _features(current, question, lookup_texts)
        old_size = sum(len(item["source"]["snippet"]) for item in current)
        old_tokens = tokens(current)
        best, best_key = None, None
        for item in pool:
            text = item["source"]["snippet"]
            identity_text = f"{_path(item)}:{item['start']}:{item['end']}:{text}"
            item["source"]["evidence_id"] = "ev-" + hashlib.sha256(identity_text.encode()).hexdigest()[:16]
            trials = []
            if len(current) < max_sources:
                trials.append([*current, item])
            for index, old in enumerate(current):
                if retains([old], [item]) and len(text) > len(old["source"]["snippet"]):
                    trials.append([*current[:index], item, *current[index + 1:]])
            for trial in trials:
                if not compatible(trial) or not retains(current, trial):
                    continue
                count = tokens(trial)
                if count > max_tokens:
                    continue
                gain = sum(len(part["source"]["snippet"]) for part in trial) - old_size
                if gain <= 0:
                    continue
                new_features = _features(trial, question, lookup_texts)
                key = (len(new_features[0] - old_features[0]), len(new_features[1] - old_features[1]),
                       1 / (1 + item["rank"]), gain / max(1, count - old_tokens), gain)
                if best_key is None or key > best_key:
                    best, best_key = deepcopy(trial), key
        if best is None:
            break
        current = best
    assert retains(baseline, current)
    assert compatible(current) and len(current) <= max_sources and tokens(current) <= max_tokens
    return current
