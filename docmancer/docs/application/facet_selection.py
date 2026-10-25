"""Experimental query-facet selection over already admitted original sections.

The local cross-encoder supplies relevance, never entailment or completeness.
Question excerpts are query probes, not a generated answer or a gold checklist.
No retrieval, remote model, source rewrite, or authority change occurs here.
"""
from __future__ import annotations

import hashlib
import re

POLICIES = frozenset({"facet-max-v1", "facet-envelope-v1", "facet-guarded-v1"})
MAX_PROBES = 16
SCORE_MARGIN = 1.0  # development heuristic in frozen-model logits, NOT calibrated probability
CAPSULE_TOKENS = 512  # maximum admitted source-text cost of one parent, not top-k


def question_probes(question: str, *, contextual: bool = False) -> tuple[list[str], str | None]:
    """Keep the full query and expose literal clauses/enumerated query items.

    Quotes, inline code and brackets are protected from splitting. Excerpts
    remain unmodified; an optional leading topic sentence supplies antecedents.
    This deliberately does not claim to understand implicit requirements.
    An over-complex query keeps all admitted sections instead of dropping facets.
    """
    protected = [False] * len(question)
    quote = None
    stack = []
    for i, char in enumerate(question):
        if quote:
            protected[i] = True
            if char == quote and (i == 0 or question[i - 1] != "\\"):
                quote = None
            continue
        # Apostrophes inside words are not quotation delimiters.
        if char in '`"' or (char == "'" and not (i and question[i - 1].isalnum())):
            quote = char
            protected[i] = True
        elif char in "([{":
            stack.append(char)
            protected[i] = True
        elif char in ")]}":
            protected[i] = bool(stack)
            if stack:
                stack.pop()
        elif stack:
            protected[i] = True
    cuts = []
    pattern = r"[,:;?!\n]|\.(?=\s|$)|\b(?:and|or|и|или)\b"
    if contextual:
        # Do not split adjective/verb coordination such as "consistent and resumable".
        lead = r"how|when|what|which|where|why|whether|may|can|do|does|is|are|should|must|will|как|когда|что|где|почему"
        pattern = r"[,:;?!\n]|\.(?=\s|$)|\b(?:and|or|и|или)\b(?=\s+(?:" + lead + r")\b)"
    for match in re.finditer(pattern, question, re.IGNORECASE):
        if not any(protected[match.start():match.end()]):
            cuts.append((match.start(), match.end()))
    pieces, start = [], 0
    for left, right in [*cuts, (len(question), len(question))]:
        text = question[start:left].strip()
        if text:
            pieces.append(text)
        start = right
    # A split such as 'when and how often' must not produce the probe 'when'.
    interrogatives = {"when", "how", "what", "which", "where", "why", "whether",
                      "когда", "как", "что", "где", "почему"}
    merged = []
    pending = ""
    for piece in pieces:
        if piece.casefold() in interrogatives:
            pending = (pending + " " + piece).strip()
            continue
        merged.append((pending + " " + piece).strip() if pending else piece)
        pending = ""
    if pending:
        return [question], "incomplete_clause_keep_all"
    # Only an actual introductory sentence/colon is used as a topic anchor.
    anchor = ""
    first = next((m for m in re.finditer(r"[:.!?]", question)
                  if not protected[m.start()]), None)
    if first and first.group() in (":.!?" if contextual else ":.") and first.start() < len(question) - 1:
        anchor = question[:first.start()].strip()
    probes = [question]
    def normalized(text):
        return " ".join(text.casefold().strip(" .,:;?!\n").split())
    seen = {normalized(question)}
    for piece in merged:
        if not re.search(r"\w", piece) or piece == anchor:
            continue
        probe = f"{piece}. {anchor}" if anchor else piece
        if normalized(probe) not in seen:
            probes.append(probe)
            seen.add(normalized(probe))
    if len(probes) > MAX_PROBES:
        return [question], "probe_limit_keep_all"
    return probes, None


def _capsules(sections, snapshot):
    """Nearest Markdown parent ranges; never fill holes in acquired evidence."""
    from docmancer.core.structured_chunking import parse_markdown_parents
    from .projection_tokenizer import projection_token_count

    parsed, members = {}, {}
    for index, section in enumerate(sections):
        identity = (section.key[0], *section.key[2:])
        primary = [r for r in section.rows if str(r.get("section") or "") == section.key[1]]
        if not primary:
            continue
        refs = [snapshot[r["evidence_id"]]["source"]["_reference_evidence"] for r in primary]
        raw = refs[0]["raw_document"]
        if identity not in parsed:
            parents = parse_markdown_parents(raw, str(identity))
            ancestors, stack = {}, []
            for n, parent in enumerate(parents):
                while stack and parents[stack[-1]].level >= parent.level:
                    stack.pop()
                ancestors[n] = stack[-1] if stack else n
                stack.append(n)
            parsed[identity] = parents, ancestors
        parents, ancestors = parsed[identity]
        spans = []
        for row, ref in zip(primary, refs):
            a = raw.find(row["snippet"], ref["char_start"], ref["char_end"])
            if a < 0:
                raise ValueError("facet capsule lost an admitted source binding")
            spans.append((a, a + len(row["snippet"])))
        owners = [n for n, p in enumerate(parents)
                  if all(p.char_start <= a < b <= p.char_end for a, b in spans)]
        if len(owners) != 1:
            continue
        parent = parents[ancestors[owners[0]]]
        key = identity, parent.char_start
        members.setdefault(key, []).append(index)
    result = {}
    for indices in members.values():
        rows = {r["evidence_id"]: r for i in indices for r in sections[i].rows}
        text = "\n\n".join(r["snippet"] for r in rows.values())
        cost = projection_token_count(text.encode())
        if cost <= CAPSULE_TOKENS:
            for index in indices:
                result[index] = tuple(indices)
    return result


def plan(engine, question, sections, global_scores, receipt, *, policy, snapshot, budget):
    """Select query-facet candidates, not a semantically certified answer set.

    MAX keeps exact best matches; ENVELOPE adds short-parent siblings.
    GUARDED keeps near-best alternatives and expands only predominantly selected
    short parents. Its margin and structural density are development heuristics.
    """
    guarded = policy == "facet-guarded-v1"
    probes, fallback = question_probes(question, contextual=guarded)
    matrix = [global_scores]
    if not fallback:
        for probe in probes[1:]:
            if len(engine.tokenizer.encode(probe, add_special_tokens=False).ids) > 128:
                fallback = "probe_query_limit_keep_all"
                break
            values, extra = engine.score(probe, sections, budget=budget)
            matrix.append(values)
            for field in ("forward_passes", "input_pair_tokens", "scoring_seconds"):
                receipt[field] += extra[field]
    rank = sorted(range(len(sections)), key=lambda i: (-global_scores[i], sections[i].key))
    wins = {i: [] for i in range(len(sections))}
    support = {i: [] for i in range(len(sections))}
    for p, scores in enumerate(matrix):
        maximum = max(scores)
        for i, score in enumerate(scores):
            if score == maximum:
                wins[i].append(p)
            if maximum - score <= (SCORE_MARGIN if guarded else 0.0):
                support[i].append(p)
    seeds = {i for i in support if support[i]}
    chosen = set(range(len(sections))) if fallback else set(seeds)
    expanded = {}
    if not fallback and policy in {"facet-envelope-v1", "facet-guarded-v1"}:
        capsules = _capsules(sections, snapshot)
        for index in sorted(seeds):
            neighbors = capsules.get(index, ())
            if guarded and 2 * len(set(neighbors) & seeds) < len(neighbors):
                continue  # short parent alone is not a reason to return unrelated siblings
            chosen.update(neighbors)
            expanded[index] = list(neighbors)
    # Facet witnesses first, then structural support, then omitted rows.
    # A budget cut is explicitly reported by the existing packet finalizer.
    ordered = sorted(chosen, key=lambda i: (not bool(support[i]), -len(support[i]),
                                          -global_scores[i], sections[i].key))
    ordered += [i for i in rank if i not in chosen]
    receipt["facet_selection"] = {
        "version": policy, "completeness": "unassessed",
        "score_margin": SCORE_MARGIN if guarded else 0.0,
        "margin_is_calibrated_probability": False,
        "probe_count": len(matrix), "planned_probe_count": len(probes),
        "fallback": fallback, "capsule_tokens": CAPSULE_TOKENS if policy in {"facet-envelope-v1", "facet-guarded-v1"} else None,
        "probes": [{"text": p, "sha256": hashlib.sha256(p.encode()).hexdigest()}
                   for p in probes[:len(matrix)]],
        "scores": matrix,
        "sections": [{"key_sha256": hashlib.sha256(str(s.key).encode()).hexdigest(),
                      "path": s.rows[0].get("path_or_url"), "section": s.key[1],
                      "winning_probes": wins[i], "retained_probes": support[i], "seed": i in seeds,
                      "selected": i in chosen, "capsule_members": expanded.get(i, [])}
                     for i, s in enumerate(sections)],
        "no_answer_judge": True, "paid_model_calls": 0,
    }
    receipt["adaptive_cutoff"] = {"reason": fallback or policy,
        "cutoff_rank": len(chosen), "gap_count": 0, "buffer": 0}
    return ordered, len(chosen)
