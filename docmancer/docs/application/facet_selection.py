"""Experimental query-facet selection over already admitted original sections.

The local cross-encoder supplies relevance, never entailment or completeness.
Question excerpts are query probes, not a generated answer or a gold checklist.
No retrieval, remote model, source rewrite, or authority change occurs here.
"""
from __future__ import annotations

import hashlib
import re

POLICIES = frozenset({"facet-max-v1", "facet-envelope-v1", "facet-guarded-v1",
                      "facet-margin-envelope-v1", "facet-guarded-lexical-v1",
                      "facet-guarded-lexical-v2"})
MAX_PROBES = 16
SCORE_MARGIN = 1.0  # development heuristic in frozen-model logits, NOT calibrated probability
CAPSULE_TOKENS = 512  # maximum admitted source-text cost of one parent, not top-k


def question_probes(question: str) -> tuple[list[str], str | None]:
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
    for match in re.finditer(pattern, question, re.IGNORECASE):
        if not any(protected[match.start():match.end()]):
            cuts.append((match.start(), match.end()))
    pieces, start = [], 0
    for left, right in [*cuts, (len(question), len(question))]:
        text = question[start:left].strip()
        if text:
            pieces.append(text)
        start = right
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
    anchor = ""
    first = next((m for m in re.finditer(r"[:.!?]", question)
                  if not protected[m.start()]), None)
    if first and first.group() in ":." and first.start() < len(question) - 1:
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



# Lexical evidence bridging is a *positive-only* safety guard, not answer
# sufficiency, entailment, or a document-specific dictionary. It can only add
# already-admitted original sections; all previously protected facet winners
# retain priority under the full packet budget.
_LEXICAL_STOPWORDS = frozenset("""the a an and or if is are was were be been being to from
of on in at for with by as its it that this those these what which who whose
where when why how does do did may can could should would will shall all every
each same than then more less about before after during into out through
without also still there here our your their some not no yes explain describe
conditions happen happens including please report reports""".split())
_LEXICAL_MAX_SECTIONS = 64
_LEXICAL_MAX_PROBES = 16
_LEXICAL_MAX_MARGIN = 5.0  # exploratory cross-ranker guard, never a probability
_RULE_MARKER = re.compile(
    r"\b(?:must|require(?:s|d)?|only|never|cannot|not|without|before|after|"
    r"expires?|expire|bound|reuse|recheck|fails?|blocks?|invalidates?|"
    r"retains?|preserves?|allowed|may|resume|retry|renew|current)\b|(?<!\w)\d+(?!\w)",
    re.IGNORECASE,
)
_LEXICAL_SECONDARY_LIMIT = 2  # exact source sections, not whole parent bundles


def _lexical_words(value: str) -> frozenset[str]:
    result = set()
    for word in re.findall(r"[A-Za-z]+", value.casefold()):
        if len(word) < 3 or word in _LEXICAL_STOPWORDS:
            continue
        if word.endswith("ies") and len(word) >= 6:
            word = word[:-3] + "y"
        elif word.endswith("ing") and len(word) >= 7:
            word = word[:-3]
        elif word.endswith("ed") and len(word) >= 6:
            word = word[:-2]
        elif word.endswith("es") and len(word) >= 6:
            word = word[:-2]
        elif word.endswith("s") and not word.endswith("ss") and len(word) >= 5:
            word = word[:-1]
        if len(word) >= 5 and word.endswith("e"):
            word = word[:-1]
        if len(word) >= 3:
            result.add(word)
    return frozenset(result)


def _lexical_cross_source_guard(probes, sections, matrix, already_selected, capsules, *, variant='v1'):
    """Choose <=one missing native document from a matching query obligation.

    Require both lexical evidence and an independent, bounded MiniLM near-match.
    This prevents one exceptionally ranked document's unrelated sibling capsule
    from crowding out an entirely different document needed by the question.
    No new source is read. Subword heuristics cannot certify sufficiency.
    """
    if (len(sections) > _LEXICAL_MAX_SECTIONS or len(probes) > _LEXICAL_MAX_PROBES
            or not matrix or not sections):
        return set(), {"status": "skipped_complexity_limit"}
    present = {(sections[i].key[0], *sections[i].key[2:]) for i in already_selected}
    corpus_terms = [
        _lexical_words(str(section.key[1]) + "\n" + section.text[:16_384])
        for section in sections
    ]
    best = None
    for p, (view, scores) in enumerate(zip(probes, matrix)):
        query_terms = _lexical_words(view)
        if len(query_terms) < 3:
            continue
        ceiling = max(scores)
        for i, section in enumerate(sections):
            if i in already_selected or (section.key[0], *section.key[2:]) in present:
                continue
            if variant == 'v2' and not _RULE_MARKER.search(section.text):
                # A topic/navigation summary without an explicit operational
                # condition is not enough to pull in an extra source.
                continue
            overlap = query_terms.intersection(corpus_terms[i])
            count = len(overlap)
            if count < 3 or count / len(query_terms) < 0.27:
                continue
            margin = ceiling - scores[i]
            if margin > _LEXICAL_MAX_MARGIN:
                continue
            # Keep language-only overlap secondary to the actual locally
            # measured relevance. At most one new source-document is admitted.
            order = (count, count / len(query_terms), -margin, scores[i], -i)
            if best is None or order > best[0]:
                best = (order, p, i, sorted(overlap))
    if best is None:
        return set(), {"status": "no_safe_cross_source_candidate"}
    _, probe_index, index, overlapping = best
    if variant == 'v2':
        # Keep at most two independently scored substantive original groups,
        # rather than a whole short parent which may include unrelated rules.
        # The query view that justified the bridge also ranks its companion.
        scores = matrix[probe_index]
        identity = (sections[index].key[0], *sections[index].key[2:])
        qwords = _lexical_words(probes[probe_index])
        alternatives = [j for j, section in enumerate(sections)
                        if j not in already_selected
                        and (section.key[0], *section.key[2:]) == identity
                        and _RULE_MARKER.search(section.text)
                        and len(qwords.intersection(corpus_terms[j])) >= 2]
        alternatives.sort(key=lambda j: (-scores[j], sections[j].key))
        added = {index, *alternatives[:_LEXICAL_SECONDARY_LIMIT]}
        # The seed is selected independently, and only one companion is
        # required to protect common two-rule dependencies.
        if len(added) > _LEXICAL_SECONDARY_LIMIT:
            added = set([index] + [j for j in alternatives if j != index][:_LEXICAL_SECONDARY_LIMIT - 1])
    else:
        added = set(capsules.get(index, (index,)))
        # Some document sections are not short-owner grouped; keep the seed.
        added.add(index)
    return added, {
        "status": "bounded_source_sections_added" if variant == "v2" else "one_already_admitted_source_added",
        "probe_index": probe_index,
        "path": sections[index].rows[0].get("path_or_url"),
        "seed_section": sections[index].key[1],
        "matched_stems": overlapping,
        "proposed_groups": sorted(added), "guard_variant": variant,
        "semantic_sufficiency_certified": False,
    }



def plan(engine, question, sections, global_scores, receipt, *, policy, snapshot, budget):
    """Select query-facet candidates, not a semantically certified answer set.

    MAX keeps exact best matches; ENVELOPE adds short-parent siblings.
    MARGIN-ENVELOPE gives every probe a raw-score band (often too expensive).
    GUARDED revision 2 limits that band to the full original scoring question;
    fragment probes supply only their best matches, avoiding flat-score floods.
    """
    guarded = policy in {"facet-guarded-v1", "facet-guarded-lexical-v1", "facet-guarded-lexical-v2"}
    margin = policy in {"facet-guarded-v1", "facet-guarded-lexical-v1", "facet-guarded-lexical-v2", "facet-margin-envelope-v1"}
    probes, fallback = question_probes(question)
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
        band = SCORE_MARGIN if margin and (not guarded or p == 0) else 0.0
        for i, score in enumerate(scores):
            if score == maximum:
                wins[i].append(p)
            if maximum - score <= band:
                support[i].append(p)
    seeds = {i for i in support if support[i]}
    chosen = set(range(len(sections))) if fallback else set(seeds)
    expanded = {}
    envelopes = {"facet-envelope-v1", "facet-guarded-v1", "facet-guarded-lexical-v1", "facet-guarded-lexical-v2", "facet-margin-envelope-v1"}
    if not fallback and policy in envelopes:
        capsules = _capsules(sections, snapshot)
        for index in sorted(seeds):
            neighbors = capsules.get(index, ())
            chosen.update(neighbors)
            expanded[index] = list(neighbors)
    lexical_added, lexical_receipt = set(), {"status": "not_requested"}
    if policy in {"facet-guarded-lexical-v1", "facet-guarded-lexical-v2"} and not fallback:
        lexical_added, lexical_receipt = _lexical_cross_source_guard(
            probes[:len(matrix)], sections, matrix, chosen, capsules,
            variant="v2" if policy == "facet-guarded-lexical-v2" else "v1")
        chosen.update(lexical_added)
    # Facet winners first. The independent lexical bridge is secondary; a
    # complete-packet budget cut can remove it before any original facet seed.
    # Facet witnesses first, then structural support, then omitted rows.
    # A budget cut is explicitly reported by the existing packet finalizer.
    ordered = sorted(chosen, key=lambda i: (not bool(support[i]), -len(support[i]),
                                          -global_scores[i], sections[i].key))
    ordered += [i for i in rank if i not in chosen]
    receipt["facet_selection"] = {
        "version": policy, "completeness": "unassessed",
        "strategy_revision": (
            "lexical-cross-source-v2" if policy == "facet-guarded-lexical-v2"
            else "lexical-cross-source-v1" if policy == "facet-guarded-lexical-v1"
            else "global-margin-envelope-v2" if guarded else policy),
        "margin_scope": "full_question_only" if guarded else "all_probes",
        "score_margin": SCORE_MARGIN if margin else 0.0,
        "margin_is_calibrated_probability": False,
        "probe_count": len(matrix), "planned_probe_count": len(probes),
        "fallback": fallback, "capsule_tokens": CAPSULE_TOKENS if policy in envelopes else None,
        "cross_source_lexical_guard": lexical_receipt,
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
