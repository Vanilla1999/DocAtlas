"""Conservative question-local boundaries, preserving original character offsets.

Sentence separation is not semantic authorization. Only explicit independent
requests receive separate probes; a trailing condition or anaphoric question
stays attached to the whole request until a supported compiler can bind it.
"""
from __future__ import annotations
import re

_PROTECTED = re.compile(
    r'(?P<tick>`+)(?:(?!(?P=tick)).)*(?P=tick)'
    r'|"[^"\n]*"|(?<!\w)\'[^\'\n]+\''
    r'|\[[^\]\n]*\]\([^\n]*?\)', re.S)
_HEAD = re.compile(
    r'^\s*(?:(?:also|additionally|separately|также|дополнительно|отдельно)\s+)?'
    r'(?:what|which|how|when\s+(?:do|does|is|are)|where|who|is|are|does|do|can|could|should|'
    r'list|name|show|tell|identify|describe|explain|что|какие|какой|какова|как|где|кто|'
    r'может\s+ли|можно\s+ли|перечисли|назови|покажи|определи|объясни)\b', re.I)
_DEPENDENT = re.compile(
    r'^\s*(?:(?:also|additionally|также)\s+)?(?:why\b|почему\b|what\s+about\b|'
    r'how\s+so\b|(?:what|how)\b.{0,24}\b(?:it|this|that|they|those|these)\b)', re.I)


def mask_protected(question: str) -> str:
    """Hide quotation/link separators, not their bytes or positions."""
    return _PROTECTED.sub(lambda m: 'x' * len(m[0]), question)


def independent_sentence_spans(question: str) -> tuple[tuple[int, int], ...]:
    """Return complete explicit request spans, or no independence certificate."""
    masked = mask_protected(question)
    boundaries = [0, *(m.end() for m in re.finditer(r'[!?]+\s+(?=\S)|\.\s+(?=[A-ZА-ЯЁ])', masked)), len(question)]
    spans = []
    for left, right in zip(boundaries, boundaries[1:]):
        while left < right and question[left].isspace():
            left += 1
        while right > left and question[right - 1].isspace():
            right -= 1
        if left < right:
            spans.append((left, right))
    if len(spans) < 2:
        return ()
    for left, right in spans:
        text = masked[left:right]
        if not _HEAD.match(text) or _DEPENDENT.match(text):
            return ()
    return tuple(spans)


from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ComposedPart:
    """Syntax/meaning proposal in the original question, never source proof."""
    start: int
    end: int
    relation: str
    focus: tuple[tuple[int, int], ...]
    constraints: tuple[tuple[int, int], ...] = ()
    alternatives: tuple[tuple[int, int], ...] = ()
    categories: tuple[tuple[int, int], ...] = ()
    requirement: str = 'scalar'
    expected_count: int | None = None
    prerequisite: int | None = None


_COUNT_WORDS = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6,
    'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12,
    'один': 1, 'два': 2, 'три': 3, 'четыре': 4, 'пять': 5, 'шесть': 6,
    'семь': 7, 'восемь': 8, 'девять': 9, 'десять': 10,
}
_CONDITION_CUE = re.compile(r'\b(?:when|if|unless|only|except|когда|если|только|кроме)\b', re.I)
_REQUEST_TAIL = re.compile(r'\b(?:and|or|и|или)\s+(?:also|identify|remove|delete|show|list|name|explain|how|what|which|покажи|удали|определи|назови|как|что|какой)\b', re.I)
_FORM = re.compile(
    r'(?:normal\s+def|ordinary\s+def|regular\s+def|обычн(?:ой|ая|ым)\s+def|'
    r'async\s+def|def|synchronous|asynchronous|синхронн(?:ой|ая|ым)|асинхронн(?:ой|ая|ым))', re.I)


def _trim_span(question: str, start: int, end: int, *, article: bool = False) -> tuple[int, int]:
    while start < end and question[start].isspace():
        start += 1
    while end > start and (question[end-1].isspace() or question[end-1] in ',.?!'):
        end -= 1
    if article:
        match = re.match(r'(?:the|a|an)\s+', question[start:end], re.I)
        if match:
            start += match.end()
    return start, end


def _condition_spans(question: str, masked: str, *, end: int | None = None):
    limit = len(question) if end is None else end
    match = _CONDITION_CUE.search(masked[:limit])
    return ((_trim_span(question, match.start(), limit)),) if match else ()


def _plain_span(question: str, span: tuple[int, int]) -> bool:
    """Reject another request or scoping phrase inside a proposed operand."""
    a, b = span
    raw = question[a:b]
    masked = mask_protected(raw)
    return bool(raw and len(raw) <= 180 and not _CONDITION_CUE.search(masked)
                and not _REQUEST_TAIL.search(masked) and not re.search(r'[?!;\n]', masked))


def _set_part(question: str, masked: str) -> tuple[ComposedPart, ...]:
    head = re.match(r'^\s*(?:name|list|назови|перечисли)\s+', masked, re.I)
    if not head:
        return ()
    start = head.end()
    first = re.match(r'[\w]+', masked[start:])
    count = None
    if first:
        word = first[0].casefold()
        count = int(word) if word.isascii() and word.isdigit() else _COUNT_WORDS.get(word)
        if count is not None:
            if not 1 <= count <= 128:
                return ()
            start += first.end()
    kind = re.match(r'\s*(?:types?\b(?:\s+of\b)?|тип(?:а|ов|ы)\b|ways?\b|methods?\b|способы\b|методы\b)', masked[start:], re.I)
    if not kind:
        return ()
    start += kind.end()
    action = re.match(r'\s+(?:to\s+)?(?:enable|disable|configure|activate|включить|выключить|настроить)\b', masked[start:], re.I)
    if action:
        start += action.end()
    constraints = _condition_spans(question, masked)
    end = constraints[0][0] if constraints else len(question)
    text = masked[start:end]
    # The collection and the explanation request remain one set-valued need.
    explanation = re.search(r'\b(?:and|и)\s+(?:explain|объясни)\b', text, re.I)
    requirement = 'set'
    if explanation:
        suffix = text[explanation.end():].strip(' ,.!?')
        expected = (re.fullmatch(r'what\s+each\s+[\w -]+', suffix, re.I)
                    or re.fullmatch(r'what\s+(?:every|each)\s+[\w -]+\s+means', suffix, re.I)
                    or re.fullmatch(r'что\s+[\w -]+\s+каждый', suffix, re.I)
                    or re.fullmatch(r'(?:the\s+)?meaning\s+of\s+each', suffix, re.I))
        if not expected or _REQUEST_TAIL.search(suffix):
            return ()
        end = start + explanation.start()
        requirement = 'set_with_explanations'
    if _REQUEST_TAIL.search(masked[start:end]):
        return ()
    categories = ()
    included = re.search(r'\b(?:including|включая)\s+', masked[start:end], re.I)
    if included:
        if constraints:
            return ()  # per-category scope is not a global condition
        base = start + included.end()
        stop = _trim_span(question, base, end)[1]
        category_text = masked[base:stop]
        if re.search(r'\b(?:or|или)\b', category_text, re.I):
            return ()  # alternatives are not a conjunction of required categories
        offsets = [base]
        pieces = []
        for sep in re.finditer(r'\s*,\s*(?:(?:and|и)\s+)?|\s+(?:and|и)\s+', category_text, re.I):
            pieces.append(_trim_span(question, offsets[-1], base+sep.start()))
            offsets.append(base+sep.end())
        pieces.append(_trim_span(question, offsets[-1], stop))
        if not 1 <= len(pieces) <= 12 or not all(_plain_span(question, part) for part in pieces):
            return ()
        categories = tuple(pieces)
        end = start + included.start()
    # Namespace/context remains in the original need and hard identities; it is
    # not mistaken for the focal attribute which should be searched for.
    scope = re.search(r'\s+(?:in|в)\s+', masked[start:end], re.I)
    focus_end = start + scope.start() if scope else end
    focus = _trim_span(question, start, focus_end)
    if not _plain_span(question, focus):
        return ()
    return (ComposedPart(0, len(question), 'enumeration', (focus,), constraints,
                         categories=categories, requirement=requirement, expected_count=count),)


def compositional_parts(question: str) -> tuple[ComposedPart, ...]:
    """Compose small operator/operand productions; unrecognized surfaces stay unknown.

    This does not translate source evidence, infer an answer, or authorize a
    rewrite. Every operand, alternative and constraint points to input bytes.
    """
    if len(question) > 8192:
        return ()
    masked = mask_protected(question)
    why = re.search(r'\b(?:and|и)\s+(?P<why>why|почему)[?! .]*$', masked, re.I)
    if (why and re.match(r'^\s*(?:how\s+(?:does|do)|как)\s+\S', masked, re.I)
            and not _REQUEST_TAIL.search(masked[:why.start()])):
        stop = _trim_span(question, 0, why.start())[1]
        constraints = _condition_spans(question, masked, end=stop)
        focus_end = constraints[0][0] if constraints else stop
        focus = _trim_span(question, 0, focus_end)
        return (ComposedPart(0, stop, 'mechanism', (focus,), constraints),
                ComposedPart(why.start('why'), len(question), 'reason', (focus,), constraints, prerequisite=0))
    collection = _set_part(question, masked)
    if collection:
        return collection
    # An alternative names candidate answer forms. Its negative connective is
    # not a requirement that the source agree with a negative proposition.
    alternative = re.search(r'\b(?:rather\s+than|instead\s+of|а\s+не)\s+', masked, re.I)
    modal = re.match(r'^\s*(?:can|could|may|может\s+ли|можно\s+ли)\s+', masked, re.I)
    if alternative and modal:
        constraints = _condition_spans(question, masked)
        end = constraints[0][0] if constraints else len(question)
        if alternative.end() >= end:
            return ()
        second_span = _trim_span(question, alternative.end(), end)
        second = _FORM.fullmatch(question[second_span[0]:second_span[1]])
        first_matches = tuple(_FORM.finditer(masked[:alternative.start()]))
        if second and first_matches:
            first = first_matches[-1]
            if not masked[first.end():alternative.start()].strip(' ,'):
                before = re.search(r'\b(?:be|быть)\s*$', masked[:first.start()], re.I)
                if before and re.search(r'\b(?:function|handler|callback|callable|функция|обработчик)\b', masked[modal.end():before.start()], re.I):
                    focus = _trim_span(question, modal.end(), before.start(), article=True)
                    if not _REQUEST_TAIL.search(masked[modal.end():before.start()]):
                        return (ComposedPart(0, len(question), 'callable_form', (focus,), constraints,
                                              (first.span(), second_span)),)
    # The conflicting sources are distinct operands, not a definition of the
    # last capitalized token. Keep the entire conflict as applicability scope.
    win = re.match(r'^\s*which\s+(?P<property>.+?)\s+wins\b|^\s*что\s+имеет\s+приоритет\b', masked, re.I)
    if win:
        condition = re.search(r'\b(?:when|когда)\s+', masked[win.end():], re.I)
        if condition:
            base = win.end() + condition.end()
            predicate = re.search(r'\s+(?:define|set|задают)\s+(?:different|разные)\s+[\w -]+[?.!]*\s*$', masked[base:], re.I)
            if predicate:
                sides = masked[base:base+predicate.start()]
                separators = tuple(re.finditer(r'\s+(?:and|и)\s+', sides, re.I))
                if len(separators) == 1:
                    cut = separators[0]
                    left = _trim_span(question, base, base+cut.start(), article=True)
                    right = _trim_span(question, base+cut.end(), base+predicate.start(), article=True)
                    condition_start = win.end() + condition.start()
                    if all(_plain_span(question, x) for x in (left, right)) and not _CONDITION_CUE.search(masked[base+predicate.start():]):
                        focus = (win.span('property'),) if win.groupdict().get('property') else (left, right)
                        if not all(_plain_span(question, x) for x in focus):
                            return ()
                        return (ComposedPart(0, len(question), 'precedence', focus,
                            (_trim_span(question, condition_start, len(question)),), (left, right)),)
    return ()
