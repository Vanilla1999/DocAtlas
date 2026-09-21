"""Current-span witnesses for the declared admission relations, without I/O.

An operator is a requested answer shape, not its expected truth/direction/value.
All arguments and applicability conditions must bind locally. No page-wide bag
of words, source-title authority, or answer strings participate in these proofs.
"""
from __future__ import annotations

import re
from .admission_grammar import ParsedMeaning, MeaningSlot, _WORDS, _FORMS, _STATES, ordered_list_spans
from .answer_units import extract_answer_units
from .technical_tokens import technical_term_pattern

_ARTICLE = r'(?:(?:a|an|the)\s+)?'
_FORM = '|'.join(re.escape(v) for v in sorted(_FORMS, key=len, reverse=True))
_STATE = '|'.join(re.escape(v) for v in sorted(_STATES, key=len, reverse=True))
_PREFIX_CONDITION = re.compile(
    rf'^(?:when|if|когда|если)\s+(?P<entity>.+?)\s+(?:is\s+)?(?P<state>{_STATE})\s*,\s*', re.I)


def _phrase(value: str) -> str:
    parts = []
    for token in re.findall(r'`[^`\n]+`|"[^"\n]+"|[^\s]+', value.strip()):
        literal = token.startswith(('`', '"')) and token[-1:] == token[:1]
        if literal:
            word = technical_term_pattern(token[1:-1], exact=True)
            parts.append(rf'(?:`|\")?{word}(?:`|\")?')
        else:
            base = _WORDS.get(token.casefold(), token.casefold())
            aliases = sorted({base, *(k for k, v in _WORDS.items() if v == base)})
            word = '(?:' + '|'.join(technical_term_pattern(a, exact=True) for a in aliases) + ')'
            parts.append(word)
    return r'\s+'.join(parts)


def _argument(slots: dict[str, MeaningSlot], role: str) -> str:
    return _ARTICLE + _phrase(slots[role].text)


def _source_clause(text: str, frame: ParsedMeaning) -> str | None:
    body = ' '.join(text.split()).strip().rstrip('.!?')
    body = re.sub(r'^\s*(?:[-*+]\s+|\d+[.)]\s+)', '', body)
    condition = _PREFIX_CONDITION.match(body)
    required = {s.role: s for s in frame.constraints}
    if required:
        if condition is None:
            return None
        entity = required.get('condition_subject')
        state = required.get('condition_state')
        if (entity is None or state is None
                or re.fullmatch(_phrase(entity.text), condition['entity'], re.I) is None
                or _STATES.get(condition['state'].casefold()) != state.canonical):
            return None
        body = body[condition.end():]
    elif condition:
        return None
    # A suffix condition, restriction or unrelated sentence cannot disappear
    # inside an argument/value capture. Quoted code is not natural-language scope.
    masked = re.sub(r'`[^`]+`|"[^"\n]+"', '', body)
    if re.search(r'\b(?:when|if|unless|except|provided|only|когда|если|только)\b', masked, re.I):
        return None
    return body


def _precedence(frame: ParsedMeaning, text: str) -> bool:
    s = {slot.role: slot for slot in frame.arguments}
    a, b = _argument(s, 'left'), _argument(s, 'right')
    predicate = r'(?:takes?\s+precedence\s+over|has\s+priority\s+over|overrides?|wins\s+over|имеет\s+приоритет\s+над)'
    return any(re.fullmatch(rf'{left}\s+{predicate}\s+{right}', text, re.I)
               for left, right in ((a, b), (b, a)))


def _temporal(frame: ParsedMeaning, text: str) -> bool:
    s = {slot.role: slot for slot in frame.arguments}
    subject, event = _argument(s, 'subject'), _argument(s, 'event')
    return bool(re.fullmatch(
        rf'{subject}\s+(?:runs?|executes?|выполняется|выполняются)\s+'
        rf'(?:before|after|до|после)\s+{event}', text, re.I)
        or re.fullmatch(rf'{event}\s+(?:precedes|follows)\s+{subject}', text, re.I))


def _callable(frame: ParsedMeaning, text: str) -> bool:
    s = {slot.role: slot for slot in frame.arguments}
    subject = _argument(s, 'subject')
    if 'owner' in s:
        subject += r'\s+(?:for|для)\s+' + _argument(s, 'owner')
    requested = s['form'].canonical
    # A negative statement about the requested form answers the question. A
    # different merely allowed form does not; a required opposite form does.
    for clause in text.split(';'):
        clause = clause.strip().rstrip('.!?')
        match = re.fullmatch(
            rf'{subject}\s+(?P<modal>can|may|must|cannot|must\s+not)\s+be\s+(?P<form>{_FORM})', clause, re.I)
        if match:
            form = _FORMS[match['form'].casefold()]
            if form == requested or match['modal'].casefold() == 'must':
                return True
        match = re.fullmatch(
            rf'{_ARTICLE}(?P<form>{_FORM})\s+{subject}\s+is\s+'
            rf'(?P<permission>(?:not\s+)?(?:allowed|permitted|required|supported))', clause, re.I)
        if match:
            form = _FORMS[match['form'].casefold()]
            if form == requested or match['permission'].casefold() == 'required':
                return True
    return False


def _behavior(frame: ParsedMeaning, text: str) -> bool:
    s = {slot.role: slot for slot in frame.arguments}
    return bool(re.fullmatch(_argument(s, 'subject') + r'\s+(?:has\s+no\s+effect|does\s+nothing|'
        r'is\s+ignored|stops|runs|remains\s+inactive)', text, re.I))


def _introduced_items(text: str):
    lines = text.splitlines(keepends=True)
    first = next((i for i, line in enumerate(lines) if re.match(r'^\s*(?:[-*+]\s+|\d+[.)]\s+)', line)), None)
    if first is None:
        return None
    intro = ' '.join(''.join(lines[:first]).split())
    if not intro or intro.startswith('#'):
        return None
    indent = len(lines[first]) - len(lines[first].lstrip())
    items = []
    offset = sum(map(len, lines[:first]))
    for line in lines[first:]:
        match = re.match(r'^(\s*)(?:[-*+]\s+|\d+[.)]\s+)(.+)', line)
        if match and len(match[1]) == indent:
            value = match[2].strip()
            if not (re.fullmatch(r'!?\[[^]]*\]\([^)]*\)|https?://\S+', value)
                    or re.fullmatch(r'(?:examples?|aliases)\s*:', value, re.I)):
                items.append((value, offset, offset + len(line.rstrip())))
        elif line.strip() and (not line[:1].isspace() or line.lstrip().startswith('#')):
            return None  # no borrowing a different section's list
        offset += len(line)
    return (intro, items) if items else None


def _enumeration(frame: ParsedMeaning, text: str) -> bool:
    parsed = _introduced_items(text)
    if parsed is None:
        return False
    intro, _ = parsed
    intro = _source_clause(intro, frame)
    if intro is None:
        return False
    slots = {s.role: s for s in frame.arguments}
    subject, items = _argument(slots, 'subject'), _argument(slots, 'item_kind')
    action = slots['action'].canonical
    inflections = {'enable': ('enable', 'enabled'), 'disable': ('disable', 'disabled'),
                   'configure': ('configure', 'configured'), 'control': ('control', 'controlled')}
    if action == 'list':
        return bool(re.fullmatch(rf'{items}\s+for\s+{subject}\s*:', intro, re.I))
    verb, participle = inflections[action]
    return bool(re.fullmatch(
        rf'{subject}\s+(?:can\s+be|may\s+be|is)\s+{participle}\s+'
        rf'(?:in|using|with)\s+(?:these|the\s+following)\s+{items}\s*:', intro, re.I)
        or re.fullmatch(rf'to\s+{verb}\s+{subject},?\s+use\s+(?:these|the\s+following)\s+{items}\s*:', intro, re.I))


def _mapping_list(frame: ParsedMeaning, text: str) -> bool:
    parsed = _introduced_items(text)
    if parsed is None:
        return False
    intro, items = parsed
    intro = _source_clause(intro, frame)
    s = {slot.role: slot for slot in frame.arguments}
    if intro is None or not re.fullmatch(
        rf'{_argument(s, "left")}\s+(?:map|correspond)\s+to\s+{_argument(s, "right")}\s+as\s+follows\s*:', intro, re.I):
        return False
    return any(re.fullmatch(r'\S(?:.*?\S)?\s+(?:->|→|maps\s+to)\s+\S(?:.*\S)?', value)
               for value, _, _ in items)



def _mapping_assignment(frame: ParsedMeaning, text: str) -> bool:
    """Two ordered local lists plus an explicit correspondence, not keyword sets."""
    slots = {s.role: s for s in frame.arguments}
    targets = [s for s in frame.arguments if s.role == 'target']
    action = slots['action'].canonical
    # Identifiers in this production are code literals, not an arbitrary prose
    # prefix that could hide a different subject or a restriction.
    match = re.fullmatch(
        rf'(?P<values>.+?)\s+{re.escape(action)}\s+{_argument(slots, "attribute")}\s+'
        rf'(?:to\s+be\s+used\s+)?for\s+(?P<targets>.+?)\s+respectively', text, re.I)
    if match is None:
        return False
    values = [match['values'][a:b] for a, b in ordered_list_spans(match['values'])]
    domains = [match['targets'][a:b] for a, b in ordered_list_spans(match['targets'])]
    if not (len(values) == len(domains) == len(targets)):
        return False
    if not all(re.fullmatch(r'`[^`\s]+`', value) for value in values):
        return False
    if len(set(values)) != len(values):
        return False
    # Question order is not an asserted mapping: the paired source order supplies
    # the answer. Every requested domain still has exactly one source domain.
    matches = [tuple(i for i, domain in enumerate(domains)
                     if re.fullmatch(_phrase(slot.text), domain.strip('`"'), re.I))
               for slot in targets]
    return all(len(indices) == 1 for indices in matches) and len({m[0] for m in matches}) == len(targets)


def _table_mapping(frame: ParsedMeaning, text: str, units) -> tuple[tuple[int, int], ...]:
    # A table header binds columns; an actual nonempty data row binds values.
    # No list-of-keys shortcut. Conditions outside the visible table are unknown.
    if frame.constraints:
        return ()
    s = {slot.role: slot for slot in frame.arguments}
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    row_starts = {u.char_start for u in units if u.kind == 'table_row'}
    for i in range(len(lines) - 2):
        if offsets[i] not in row_starts or offsets[i+2] not in row_starts:
            continue
        header = [c.strip() for c in lines[i].strip().strip('|').split('|')]
        sep = [c.strip() for c in lines[i+1].strip().strip('|').split('|')]
        if len(header) != 2 or len(sep) != 2 or not all(re.fullmatch(r':?-{3,}:?', c) for c in sep):
            continue
        if not (re.fullmatch(_phrase(s['left'].text), header[0], re.I)
                and re.fullmatch(_phrase(s['right'].text), header[1], re.I)):
            continue
        row = [c.strip() for c in lines[i+2].strip().strip('|').split('|')]
        if len(row) == 2 and all(row):
            return ((offsets[i], offsets[i+3]),)
    return ()


def relation_local_witness(frame: ParsedMeaning, text: str) -> tuple[bool | None, tuple[tuple[int, int], ...]]:
    """Find the smallest actually supported source unit for a parsed demand."""
    checks = {'precedence': _precedence, 'temporal_order': _temporal,
              'callable_form': _callable, 'behavior': _behavior}
    units = tuple(extract_answer_units(text, include_soft_wrapped_prose=True))
    assignment = frame.operator == 'mapping' and any(s.role == 'target' for s in frame.arguments)
    if frame.operator == 'mapping' and not assignment:
        table = _table_mapping(frame, text, units)
        if table:
            return True, table
    if frame.operator not in {*checks, 'enumeration', 'mapping'}:
        return None, ()
    matches = []
    for unit in units:
        if not unit.proposition or unit.char_start is None or unit.char_end is None:
            continue
        if assignment:
            clause = _source_clause(unit.text, frame) if unit.kind in {'sentence', 'paragraph_sentence', 'bullet'} else None
            matched = clause is not None and _mapping_assignment(frame, clause)
        elif frame.operator in {'enumeration', 'mapping'}:
            matched = (_enumeration if frame.operator == 'enumeration' else _mapping_list)(frame, unit.text)
        elif unit.kind in {'sentence', 'paragraph_sentence', 'bullet', 'key_value'}:
            clause = _source_clause(unit.text, frame)
            matched = clause is not None and checks[frame.operator](frame, clause)
        else:
            matched = False
        if matched:
            matches.append((unit.char_start, unit.char_end))
    if not matches:
        return False, ()
    return True, (min(matches, key=lambda span: (span[1]-span[0], span[0])),)
