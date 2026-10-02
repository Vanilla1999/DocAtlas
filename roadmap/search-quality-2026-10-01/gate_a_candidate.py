"""Review-only Gate A candidate; not imported by production retrieval.

No source approval, proof, query rewrites, route-specific relations or new models.
The lexical floor and pair requirement are inherited, not benchmark-tuned.
"""
from dataclasses import dataclass
import re

from docmancer.core.structured_chunking import _atom_spans
from docmancer.docs.domain.evidence_qualification import _substantive_markdown_line
from docmancer.docs.domain.query_terms import documentation_query_terms


@dataclass(frozen=True, slots=True)
class TopicDecision:
    state: str
    reason: str
    witness_span: tuple[int, int] | None = None


def _prose_sentences(text):
    # Soft wraps are presentation, not independent evidence. Explicit Markdown
    # hard breaks and paragraphs retain their boundaries; code is not flattened.
    lines = text.splitlines(keepends=True)
    parts, current = [], []
    for index, line in enumerate(lines):
        following = lines[index + 1].strip() if index + 1 < len(lines) else ''
        if re.fullmatch(r'[=-]{3,}', following):
            continue
        value = _substantive_markdown_line(line.rstrip('\r\n'))
        current.append(value.strip())
        if line.rstrip('\r\n').endswith(('  ', '\\')):
            parts.append(' '.join(current))
            current = []
    if current:
        parts.append(' '.join(current))
    return [s for part in parts for s in re.split(r'(?<=[.!?])\s+', part) if s.strip()]


def decide_topic(question: str, visible_text: str) -> TopicDecision:
    """Topic-only witness from actual visible prose, not the larger search hit.

    Exact/source/subject/conditions must be checked separately. Unsupported
    code/table/list-only windows are unknown, not automatically non-relevant.
    """
    if not question or not visible_text:
        return TopicDecision('unknown', 'missing_visible_input')
    terms = set(documentation_query_terms(question))
    words = re.findall(r'\w+(?:[.-]\w+)*', question.casefold())
    pairs = set(zip(words, words[1:]))
    substantive = False
    unsupported_structure = False
    for atom in _atom_spans(visible_text, 0, len(visible_text)):
        if atom.atom_type != 'prose':
            unsupported_structure |= atom.atom_type in {'code', 'table', 'list'}
            continue
        for sentence in _prose_sentences(visible_text[atom.start:atom.end]):
            if not sentence.strip():
                continue
            substantive = True
            tokens = re.findall(r'\w+(?:[.-]\w+)*', sentence.casefold())
            local = terms & set(tokens)
            # A source sentence consisting only of original content terms does
            # not supply a distinct read assertion. No new echo-word dictionary.
            content_terms = set(documentation_query_terms(sentence))
            if '?' in sentence or (content_terms and content_terms <= terms):
                continue
            if len(local) >= 3 and any(
                    a in local and b in local
                    for a, b in pairs & set(zip(tokens, tokens[1:]))):
                return TopicDecision('allowed', 'visible_local_topic_context', (atom.start, atom.end))
    if substantive or unsupported_structure:
        return TopicDecision('unknown', 'no_local_topic_witness')
    return TopicDecision('rejected', 'no_supported_prose_witness')


def packing_objective(windows, *, candidate_order, whole_dto_tokens):
    """Review-only objective for already source/applicability/topic-checked windows.

    Lexicographically maximize rank representation, then exact source coverage;
    minimize whole DTO cost. No BM25 sum, lexical utility or proof credits.
    Caller must enforce budget/source caps and use stable-ID ascending final ties.
    Coverage units are Unicode characters, explicitly not semantic completeness.
    """
    represented, coverage = [], []
    for candidate in candidate_order:
        spans = sorted((w['start'], w['end']) for w in windows if w['candidate_id'] == candidate)
        represented.append(int(bool(spans)))
        merged = []
        for start, end in spans:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        coverage.append(sum(b - a for a, b in merged))
    return tuple(represented), tuple(coverage), -whole_dto_tokens


def decide_fact_or_topic(question: str, visible_text: str) -> TopicDecision:
    """Recompute existing typed witness; do not deserialize an approval flag.

    This is still review-only relevance, not source/applicability validation.
    Known typed demand with absent evidence cannot be repaired by topical words.
    """
    from docmancer.docs.domain.admission_grammar import parse_admission_frame, NEW_RELATIONS
    from docmancer.docs.domain.admission_relations import relation_local_witness
    from docmancer.docs.domain.admission_local_binding import default_local_witness
    from docmancer.docs.domain.need_composition import independent_sentence_spans
    from docmancer.docs.domain.question_retrieval_needs import retrieval_needs

    absent = False
    # Existing independent original spans only. The public retrieval question
    # stays untouched; a known part does not certify an unresolved sibling.
    for start, end in independent_sentence_spans(question) or ((0, len(question)),):
        text = question[start:end]
        frame = parse_admission_frame(text)
        proofs = []
        if frame is not None and frame.operator in NEW_RELATIONS:
            proofs.append(relation_local_witness(frame, visible_text))
        else:
            for need in retrieval_needs(text):
                if need.relation == 'default':
                    # Keep the FULL independent text, including conditions and
                    # unknown suffixes, as required by the retained primitive.
                    proofs.append(default_local_witness(
                        {'text': text, 'need_subject': need.subject, 'need_relation': 'default'}, visible_text))
        for matched, spans in proofs:
            if matched is True:
                if not spans or any(type(a) is not int or type(b) is not int
                        or not 0 <= a < b <= len(visible_text)
                        or '?' in visible_text[a:b] for a, b in spans):
                    return TopicDecision('unknown', 'invalid_or_question_fact_witness')
                return TopicDecision('allowed', 'recomputed_local_fact_context',
                                     (min(a for a, _ in spans), max(b for _, b in spans)))
            absent |= matched is False
    if absent:
        return TopicDecision('unknown', 'typed_witness_absent')
    return decide_topic(question, visible_text)


def decide_structural_window(question: str, raw: str, start: int, end: int) -> TopicDecision:
    """Review-only intact atom constraint; not arbitrary semantic completeness.

    Never fetch or enlarge the authorized window to repair a missing dependency.
    All touched atoms must remain visible. Standalone unsupported code is unknown.
    """
    from docmancer.core.structured_chunking import parse_markdown_parents
    from docmancer.docs.domain.context_blocks import source_block_alternatives
    if (type(start) is not int or type(end) is not int
            or not 0 <= start < end <= len(raw)):
        return TopicDecision('rejected', 'invalid_window_span')
    parents = [p for p in parse_markdown_parents(raw, 'review-only-source')
               if p.char_start < end and start < p.char_end]
    if len(parents) != 1:
        return TopicDecision('unknown', 'mixed_owning_sections')
    for atom in _atom_spans(raw, parents[0].char_start, parents[0].char_end):
        left, right = atom.start, atom.end
        while left < right and raw[left].isspace():
            left += 1
        while right > left and raw[right - 1] in '\r\n':
            right -= 1
        if left < end and start < right and not start <= left < right <= end:
            return TopicDecision('unknown', 'clipped_source_atom')
    window = raw[start:end]
    if source_block_alternatives(window).limitations:
        return TopicDecision('unknown', 'unverified_structure')
    decision = decide_fact_or_topic(question, window)
    if decision.witness_span is not None:
        a, b = decision.witness_span
        return TopicDecision(decision.state, decision.reason, (start + a, start + b))
    return decision


@dataclass(frozen=True, slots=True)
class SolverResult:
    status: str
    windows: tuple
    visits: int
    whole_dto_tokens: int | None


def solve_packets(windows, *, candidate_order, packet_cost, max_tokens=800,
                  max_visits=4096) -> SolverResult:
    """Bounded exact comparison over packets of at most three source rows.

    On work exhaustion return NO packet, not a heuristic best-so-far winner.
    packet_cost must use the real DTO counter in public-boundary integration.
    Input windows are proposals, never permission; final binding rechecks remain.
    """
    from itertools import combinations
    if type(max_visits) is not int or not 1 <= max_visits <= 4096:
        raise ValueError('max_visits must be within 1..4096')
    if type(max_tokens) is not int or not 0 <= max_tokens <= 800:
        raise ValueError('max_tokens must be within 0..800')
    if len(windows) > 4096 or len(candidate_order) > 20 or len(set(candidate_order)) != len(candidate_order):
        raise ValueError('inventory work bound or duplicate candidate order')
    def key(window):
        return window['source'], window['candidate_id'], window['start'], window['end']
    for window in windows:
        if (window['candidate_id'] not in candidate_order
                or not isinstance(window['source'], str) or not window['source']
                or type(window['start']) is not int or type(window['end']) is not int
                or not 0 <= window['start'] < window['end']):
            raise ValueError('invalid proposal inventory')
    ordered = sorted(windows, key=key)
    if len({key(w) for w in ordered}) != len(ordered):
        raise ValueError('duplicate source span proposal')
    best, best_score, best_key, best_cost, visits = (), None, None, None, 0
    for size in range(min(3, len(ordered)) + 1):
        for packet in combinations(ordered, size):
            if visits == max_visits:
                return SolverResult('work_limited', (), visits, None)
            visits += 1
            sources = [w['source'] for w in packet]
            if any(sources.count(source) > 2 for source in set(sources)):
                continue
            cost = packet_cost(packet)
            if type(cost) is not int or cost < 0:
                raise ValueError('invalid DTO cost')
            if cost > max_tokens:
                continue
            score = packing_objective(packet, candidate_order=candidate_order, whole_dto_tokens=cost)
            stable_key = tuple(key(w) for w in packet)
            if best_score is None or score > best_score or (score == best_score and stable_key < best_key):
                best, best_score, best_key, best_cost = packet, score, stable_key, cost
    return SolverResult('optimal_in_inventory', tuple(best), visits, best_cost)
