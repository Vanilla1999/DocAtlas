"""Conservative, annotation-driven assessment; never an answer authorization rule.

A witness set is an adjudicated minimal set of source spans, not a bag of words.
Unknown equivalences go to review. Corpus policy comes from a pinned external
source registry, not from model-generated claims. No runtime module imports this.
"""
from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

_POLICY_KEYS = ("project_group", "version", "scope", "authority", "lifecycle")
_TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)+\|?\s*$")


def normalize_markdown(text: str) -> str:
    """Ignore formatting backticks/table rulers/spacing, never polarity or case.

    Identifiers, underscores, numbers and sentence punctuation are preserved.
    This is a declared matching normalization, not semantic paraphrase inference.
    """
    lines = []
    for line in text.splitlines():
        if _TABLE_RULE.fullmatch(line):
            continue
        line = re.sub(r"`+([^`\n]+)`+", r"\1", line)
        if "|" in line:
            line = "|".join(part.strip() for part in line.strip().strip("|").split("|"))
        lines.append(line)
    return " ".join(" ".join(lines).split())


def _contains(snippet: str, text: str) -> bool:
    value = normalize_markdown(text)
    return bool(value) and re.search(r"(?<!\w)" + re.escape(value) + r"(?!\w)", normalize_markdown(snippet)) is not None


def _eligible_sources(case: Mapping, payload: Mapping, registry: Mapping) -> tuple[list, list, list]:
    accepted, rejected, review = [], [], []
    identities: set[str] = set()
    policy = {**case.get("policy", {}), "project_group": case["project_group"]}
    for raw in payload.get("sources") or []:
        source = dict(raw)
        identity = str(source.get("evidence_id") or "")
        if not identity or identity in identities:
            raise ValueError("missing or duplicate evidence identity")
        identities.add(identity)
        path = source.get("path_or_url")
        if case.get("allowed_paths") is not None and path not in case["allowed_paths"]:
            rejected.append({"evidence_id": identity, "reason": "explicit_path_restriction"})
            continue
        metadata = registry.get(path)
        if not isinstance(metadata, Mapping):
            review.append({"evidence_id": identity, "reason": "source_identity_unreviewed"})
            continue
        failure = None
        unknown = False
        for key in _POLICY_KEYS:
            required = policy.get(key)
            if required is None:
                continue
            actual = metadata.get(key)
            if actual is None:
                failure, unknown = f"policy_unobserved:{key}", True
                break
            allowed = required if isinstance(required, list) else [required]
            if actual not in allowed:
                failure = f"policy_mismatch:{key}"
                break
        if failure:
            (review if unknown else rejected).append({"evidence_id": identity, "reason": failure})
        else:
            accepted.append(source)
    return accepted, rejected, review


def _part_matches(part: Mapping, source: Mapping) -> bool:
    if part.get("paths") is not None and source.get("path_or_url") not in part["paths"]:
        return False
    if part.get("path") is not None and source.get("path_or_url") != part["path"]:
        return False
    # Optional exact occurrence constraints bind approved source spans, not a
    # coincidental repeated sentence elsewhere in an otherwise admissible file.
    for key in ("line_start", "line_end"):
        if key in part:
            start, end = source.get("line_start"), source.get("line_end")
            if not (type(start) is int and type(end) is int and start <= part[key] <= end):
                return False
    return _contains(str(source.get("snippet") or ""), str(part.get("text") or ""))


def _match_set(witness: Mapping, sources: list[dict]) -> tuple[bool, list[str]]:
    parts = witness.get("parts")
    if not isinstance(parts, list) or not parts or any(not p.get("text") for p in parts):
        raise ValueError("Each approved witness set requires nonempty complete span parts")
    groups = [sources]
    if witness.get("same_source"):
        groups = [[s for s in sources if s["path_or_url"] == path]
                  for path in dict.fromkeys(s["path_or_url"] for s in sources)]
    for group in groups:
        matches = [[s["evidence_id"] for s in group if _part_matches(part, s)] for part in parts]
        if all(matches):
            return True, list(dict.fromkeys(identity for ids in matches for identity in ids))
    return False, []


def _claim_status(claim: Mapping, sources: list[dict], unreviewed: list[dict]) -> dict:
    supported, contradicted = [], []
    for sets, output in ((claim.get("witness_sets", []), supported), (claim.get("contradiction_sets", []), contradicted)):
        for witness in sets:
            complete, evidence_ids = _match_set(witness, sources)
            if complete:
                output.append({"evidence_ids": evidence_ids, "parts": witness["parts"]})
    unknown = [s["evidence_id"] for s in unreviewed]
    for source in sources:
        # An explicitly reviewed irrelevant/partial span is not an unknown
        # paraphrase. Unknown remaining text is never silently scored as false.
        known = any(normalize_markdown(source.get("snippet", "")) == normalize_markdown(text)
                    for text in claim.get("known_insufficient", []))
        known = known or any(_part_matches(part, source)
            for w in [*claim.get("witness_sets", []), *claim.get("contradiction_sets", [])]
            for part in w["parts"])
        if not known:
            unknown.append(source["evidence_id"])
    if contradicted:
        status = "contradicted"
    elif supported:
        status = "supported"
    elif unknown:
        status = "needs_review"
    else:
        status = "missing"
    return {"status": status, "supporting_witnesses": supported, "contradicting_witnesses": contradicted,
            "unreviewed_evidence_ids": list(dict.fromkeys(unknown))}


def assess_context(case: Mapping[str, Any], payload: Mapping[str, Any], source_registry: Mapping[str, Any]) -> dict:
    """Evaluate only explicitly annotated claims against the actual visible text.

    Technical path/span/hash integrity is a separate result. Source registry and
    annotations must be frozen before comparative runtime experiments. A known
    supported fact cannot certify the absence of other, unreviewed contradictions;
    callers must retain the review queue even for sufficient recognized evidence.
    """
    required = case.get("required_claims")
    if not isinstance(required, list) or not required:
        raise ValueError("At least one required claim must be explicitly annotated")
    all_claims = [*required, *case.get("optional_claims", [])]
    ids = [claim.get("id") for claim in all_claims]
    if None in ids or len(ids) != len(set(ids)):
        raise ValueError("Claim identities must be nonempty and unique")
    sources, rejected, unknown = _eligible_sources(case, payload, source_registry)
    assessed = {claim["id"]: _claim_status(claim, sources, unknown) for claim in all_claims}
    claims = {claim["id"]: assessed[claim["id"]] for claim in required}
    statuses = {row["status"] for row in claims.values()}
    sufficiency = ("contradictory" if "contradicted" in statuses else
                   "sufficient" if statuses == {"supported"} else
                   "needs_review" if "needs_review" in statuses else "insufficient")
    review_queue = [{"case_id": case["id"], "claim_id": claim_id,
                     "evidence_ids": row["unreviewed_evidence_ids"], "reason": "unrecognized_alternative_or_relation"}
                    for claim_id, row in assessed.items() if row["unreviewed_evidence_ids"]]
    return {"case_id": case["id"], "context_sufficiency": sufficiency, "claims": claims,
            "optional_claims": {claim["id"]: assessed[claim["id"]] for claim in case.get("optional_claims", [])},
            "rejected_sources": rejected, "unreviewed_sources": unknown, "review_queue": review_queue,
            "required_supported": sum(row["status"] == "supported" for row in claims.values()),
            "required_count": len(claims), "citation_integrity": "separate_check_required"}
