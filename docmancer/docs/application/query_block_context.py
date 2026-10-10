"""Bounded document-local context candidates, not independent answer proofs.

Use only authenticated snapshots of admitted sources. Rank canonical Markdown
blocks with the unchanged query vocabulary; no source reads or query rewriting.
Supplementary blocks get no coverage credit and never evict baseline quotes.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from itertools import islice
import math
import re

from docmancer.core.structured_chunking import parse_markdown_parents
from docmancer.docs.domain.query_terms import documentation_query_terms
from docmancer.docs.domain.query_reference_binding import prepare_reference_probe
from .joint_context_candidates import (
    MAX_PARENT_SECTIONS, _context_row, _verified_document, structural_spans,
)
from .joint_context_lineage import retained_seed_mapping
from .query_block_bridge import bridge_options
from .joint_context_selection import _finish
from .model_visible_projection import (
    _snapshot_entry,
    docs_context_budget_tokens, validate_model_visible_projection,
)

MAX_BLOCKS = 256
MAX_OPTIONS = 3
MAX_DOCUMENTS = 2  # prior optional scan work; never a returned-source cap
MAX_DRAFTS = 18  # two documents * three blocks * (supplement + two bridges)


def ranked_blocks(raw: str, document_id: str, question: str) -> list[tuple]:
    """Order exact source spans: explicit subject lead, then local BM25.

    Leaf headings entirely present in the question identify a structural subject,
    not a library-specific intent. Otherwise standard BM25 (k1=1.2, b=.75) ranks
    whole blocks with their leaf heading. A matched heading cannot make a code
    example or an arbitrary later paragraph the section's introductory rule.
    """
    terms = set(documentation_query_terms(question))
    if not terms:
        return []
    parents = parse_markdown_parents(raw, document_id)
    if len(parents) > MAX_PARENT_SECTIONS:
        return []
    blocks = []
    for parent in parents:
        first = True
        heading = set(documentation_query_terms(parent.title))
        subject = bool(parent.level > 1 and heading and heading <= terms)
        for start, end, kind in structural_spans(raw, parent.char_start, parent.char_end):
            if kind in {"heading", "whitespace"}:
                continue
            counts = Counter(re.findall(r"[A-Za-zА-Яа-яЁё0-9_.:/+-]+", (parent.title + "\n" + raw[start:end]).casefold()))
            lead = subject and first and kind == "prose"
            blocks.append((start, end, parent, counts, lead))
            first = False
            if len(blocks) > MAX_BLOCKS:
                # Do not silently turn a partial scan into a best-block claim.
                return []
    if not blocks:
        return []
    frequency = Counter(term for _, _, _, counts, _ in blocks for term in counts)
    average = sum(sum(counts.values()) for _, _, _, counts, _ in blocks) / len(blocks)
    result = []
    for start, end, parent, counts, lead in blocks:
        body_terms = set(re.findall(r"[A-Za-zА-Яа-яЁё0-9_.:/+-]+", raw[start:end].casefold()))
        if not (body_terms & terms):
            continue  # no metadata-only matches
        length = sum(counts.values())
        score = sum(
            math.log1p((len(blocks) - frequency[t] + .5) / (frequency[t] + .5))
            * counts[t] * 2.2 / (counts[t] + 1.2 * (.25 + .75 * length / max(average, 1)))
            for t in sorted(terms & counts.keys())
        )
        result.append(((int(lead), score), start, end, parent))
    return sorted(result, key=lambda row: (-row[0][0], -row[0][1], row[1]))


def select_query_block_context(payload: dict, snapshot: dict, retrieval: dict, *, max_tokens: int | None):
    """Add at most one relevant block, validating the entire draft packet.

    Checked/empty/host-lookup results are unchanged. Candidates are supplemental
    context, NOT newly certified query witnesses. Existing ranges, attribution
    and registered capabilities retain the pre-existing policy.
    """
    plan = retrieval.get("documentation_query_plan") or {}
    if (payload.get("kind") != "docs_context" or payload.get("support_status") != "retrieval_only"
        or any(payload.get(k) is not False for k in ("answer_supported", "answer_available", "edit_ready"))
        or (payload.get("context_quality") or {}).get("status") == "checked"
        or not payload.get("sources")
        or any(q.get("origin") == "host_lookup" for q in plan.get("queries", []) if isinstance(q, dict))):
        return payload, snapshot
    question = str(plan.get("original_question") or retrieval.get("question") or "")
    budget = max_tokens
    root = str(retrieval.get("_source_continuation_project_root") or "")
    candidates = []
    seen_documents = set()
    drafts = 0
    for seed in payload["sources"]:
        original = (snapshot.get(seed["evidence_id"]) or {}).get("source")
        if not isinstance(original, dict):
            continue
        raw = _verified_document(original, seed)
        if raw is None:
            continue
        ref = original["_reference_evidence"]
        key = (seed["project_identity"], seed["path_or_url"], ref["source"]["content_sha256"])
        if key in seen_documents:
            continue
        if len(seen_documents) >= MAX_DOCUMENTS:
            break
        seen_documents.add(key)
        ranked = ranked_blocks(raw, ref["source"]["document_id"], question)
        for rank, start, end, parent in ranked[:MAX_OPTIONS]:
            proposal = _context_row(original, seed, raw, parent, start, end, supplementary=True)
            if proposal is None:
                continue
            row, source = proposal
            # A supplement may not borrow an explicit semantic subject from a
            # different section. Use the existing occurrence/owner binder before
            # any adjacency coalescing can bring that unrelated heading along.
            required_subjects = {ref["mention"]["mention_id"] for ref in
                (original.get("_reference_root_plan") or {}).get("references", ())
                if ref.get("role") == "semantic_subject"}
            probe, reason = prepare_reference_probe({}, candidate=source, evidence_text=row["snippet"])
            bound_subjects = {ref["mention_id"] for ref in probe.get("reference_bindings", ())
                if ref.get("role") == "semantic_subject"}
            if reason is not None or not required_subjects <= bound_subjects:
                continue
            if any(s["path_or_url"] == row["path_or_url"] and row["snippet"] in s["snippet"]
                   for s in payload["sources"]):
                continue
            proposals = [(row, source, None)]
            for other in islice(payload["sources"], MAX_DOCUMENTS):
                old = (snapshot.get(other["evidence_id"]) or {}).get("source")
                if not isinstance(old, dict) or other["path_or_url"] != seed["path_or_url"]:
                    continue
                if _verified_document(old, other) != raw:
                    continue
                bridge = bridge_options(other, old, raw, start, end, retrieval)
                if bridge is not None:
                    proposals.append((*bridge, other["evidence_id"]))
            for row, source, replace_id in proposals:
                if drafts >= MAX_DRAFTS:
                    break
                drafts += 1
                draft, bindings = deepcopy(payload), deepcopy(snapshot)
                if replace_id is None:
                    draft["sources"].append(row)
                else:
                    draft["sources"] = [row if s["evidence_id"] == replace_id else s for s in draft["sources"]]
                bindings[row["evidence_id"]] = _snapshot_entry(source, row)
                finished = _finish(draft, bindings, retrieval, root, budget)
                if finished is None:
                    continue
                p, b, r = finished
                if (not retained_seed_mapping(payload, snapshot, p, b)
                    or validate_model_visible_projection(p, snapshot=b, max_tokens=budget)):
                    continue
                surviving = {s["evidence_id"]: s for s in p["sources"]}
                mapping = retained_seed_mapping(payload, snapshot, p, b)
                if any(old.get("source_uri") and not surviving[mapping[old["evidence_id"]]].get("source_uri")
                       for old in payload["sources"]):
                    continue  # a supplement must not spend an existing reader's budget
                candidates.append((rank, docs_context_budget_tokens(p), start, p, b, r))
    if not candidates:
        return payload, snapshot
    best = min(candidates, key=lambda c: (-c[0][0], -c[0][1], c[1], c[2]))
    _, cost, _, result, bindings, r = best
    retrieval.clear()
    retrieval.update(r)
    retrieval.setdefault("retrieval_diagnostics", {}).setdefault("docs_context_projection", {})["query_block_context"] = {
        "eligible_packets": len(candidates), "budget_tokens": cost,
        "qualification": "supplementary_context_only",
    }
    return result, bindings
