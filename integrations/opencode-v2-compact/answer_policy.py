"""Load fixed, opt-in answer-writing experiments without changing tool policy.

The default common prompt is returned unchanged. Candidates replace one known
answer-writing paragraph, never source text, trust boundaries or tool rules.
This module has no model/client calls and can also prepare answer-only studies.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

ANSWER_POLICIES = ("current", "rule-contract-v1", "evidence-led-v1")
HERE = Path(__file__).resolve().parent
SOURCE_TO_DRAFT_PARAGRAPH = (
    "Make one final pass through the supplied sources, comparing each question-relevant statement with your draft. "
    "Add any supported point the draft leaves out, and remove claims the sources do not support. "
    "Keep this check internal; return only the final answer."
)


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_common_prompt(policy: str = "current") -> tuple[str, dict]:
    """Return the selected common prompt and exact input provenance.

    A candidate is admitted only while the original paragraph boundary matches
    exactly once. The current policy does not replace or reinterpret that text.
    No caller-supplied prompt path or source/question-specific mapping is used.
    """
    if policy not in ANSWER_POLICIES:
        raise ValueError("answer_policy must be current, rule-contract-v1 or evidence-led-v1")
    common_path = HERE / "profile/common.txt"
    common_bytes = common_path.read_bytes()
    # Match the builder's original text read, including universal newlines on
    # checkouts that use CRLF. Input hashes still describe the actual bytes.
    base = common_path.read_text(encoding="utf-8").strip()
    inputs = {
        "answer_policy.py": _digest(Path(__file__).read_bytes()),
        "profile/common.txt": _digest(common_bytes),
    }
    provenance = {
        "answer_policy": policy,
        "answer_policy_base_prompt_sha256": _digest(base.encode("utf-8")),
        "answer_policy_prompt_sha256": None,
        "inputs": inputs,
    }
    if policy == "current":
        return base, provenance

    paragraphs = base.split("\n\n")
    if paragraphs.count(SOURCE_TO_DRAFT_PARAGRAPH) != 1:
        raise ValueError("Answer-writing instruction boundary changed; review the experimental answer policy")
    filename = "answer-rule-contract.txt" if policy == "rule-contract-v1" else "answer-evidence-led.txt"
    path = HERE / "profile" / filename
    candidate_bytes = path.read_bytes()
    candidate = path.read_text(encoding="utf-8").strip()
    if not candidate or "\n\n" in candidate:
        raise ValueError("An answer-policy candidate must contain exactly one nonempty paragraph")
    paragraphs[paragraphs.index(SOURCE_TO_DRAFT_PARAGRAPH)] = candidate
    inputs[str(path.relative_to(HERE))] = _digest(candidate_bytes)
    provenance["answer_policy_prompt_sha256"] = _digest(candidate.encode("utf-8"))
    return "\n\n".join(paragraphs), provenance
