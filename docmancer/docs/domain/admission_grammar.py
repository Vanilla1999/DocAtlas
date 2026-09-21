"""Declared, bounded RU/EN admission grammar, independent of source or eval data.

Full-surface matching is intentional. Unknown tails are not erased to manufacture
an interpretation; explicit literals keep both their spelling and source offsets.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re


@dataclass(frozen=True, slots=True)
class MeaningSlot:
    role: str
    start: int
    end: int
    text: str
    canonical: str


@dataclass(frozen=True, slots=True)
class ParsedMeaning:
    operator: str
    arguments: tuple[MeaningSlot, ...]
    constraints: tuple[MeaningSlot, ...] = ()

    @property
    def subject(self) -> str:
        for role in ('subject', 'left', 'attribute'):
            for slot in self.arguments:
                if slot.role == role:
                    return slot.text.strip('`"')
        return ''


# A frozen grammar vocabulary, not a library/answer dictionary. Unknown names
# are opaque and case-sensitive; only these ordinary role words are normalized.
_WORDS = {
    'таймаут': 'timeout', 'таймаута': 'timeout',
    'ключи': 'key', 'keys': 'key', 'переменные': 'variable', 'variables': 'variable',
    'protocols': 'protocol', 'протоколы': 'protocol',
    'способы': 'way', 'ways': 'way', 'methods': 'way', 'методы': 'way',
    'options': 'option', 'параметры': 'option',
    'functions': 'function', 'функция': 'function', 'функции': 'function',
    'handlers': 'handler', 'обработчик': 'handler',
    'прокси': 'proxy', 'всех': 'all', 'запросов': 'requests',
}
_FORMS = {
    'normal': 'sync', 'ordinary': 'sync', 'regular': 'sync', 'synchronous': 'sync',
    'def': 'sync', 'обычной': 'sync', 'обычным': 'sync', 'обычная': 'sync',
    'синхронной': 'sync', 'синхронным': 'sync', 'синхронная': 'sync',
    'asynchronous': 'async', 'async': 'async', 'async def': 'async',
    'асинхронной': 'async', 'асинхронным': 'async', 'асинхронная': 'async',
}
_ACTIONS = {
    'enable': 'enable', 'activate': 'enable', 'включают': 'enable', 'включения': 'enable',
    'disable': 'disable', 'deactivate': 'disable', 'выключают': 'disable', 'отключают': 'disable',
    'configure': 'configure', 'настраивают': 'configure',
    'control': 'control', 'управляют': 'control', 'set': 'set', 'задают': 'set',
    'for': 'list', 'для': 'list',
}
_STATES = {
    'enabled': 'enabled', 'disabled': 'disabled', 'not enabled': 'disabled',
    **{word: 'enabled' for word in ('включен', 'включена', 'включено', 'включены')},
    **{word: 'disabled' for word in ('выключен', 'выключена', 'выключено', 'выключены',
                                    'отключен', 'отключена', 'отключено', 'отключены', 'не включен')},
}
_QUOTE = re.compile(r'`[^`\n]+`|"[^"\n]+"')
_UNSUPPORTED = re.compile(
    r'\b(?:only|any|all|every|unless|except|provided|when|if|then|not|without|'
    r'только|любой|все|каждый|когда|если|кроме|не|без)\b|'
    r'\b(?:and|or|и|или)\s+(?:what|how|why|which|delete|remove|explain|identify|что|как|удал)', re.I)
_WRAPPER = re.compile(r'^\s*(?:(?:please|пожалуйста)[, ]+|(?:explain|объясни)\s+|'
                      r'(?:precisely|briefly|exactly|подробно)\s+)', re.I)
_STATE_WORDS = '|'.join(re.escape(v) for v in sorted(_STATES, key=len, reverse=True))
_CONDITION = re.compile(
    rf'(?:,?\s+)(?:when|if|когда|если)\s+(?P<condition_subject>.+?)\s+'
    rf'(?:is\s+)?(?P<condition_state>{_STATE_WORDS})\s*$', re.I)
_FORMS_PATTERN = '|'.join(re.escape(v) for v in sorted(_FORMS, key=len, reverse=True))


def canonical_phrase(value: str) -> str:
    """Normalize declared ordinary words only, preserving arbitrary literals."""
    pieces = []
    for token in re.findall(r'`[^`\n]+`|"[^"\n]+"|[^\s]+', value.strip()):
        if _QUOTE.fullmatch(token):
            pieces.append('literal:' + token[1:-1])
        else:
            key = token.casefold()
            # Names such as QueueHub/ΣClient are not translated or lowercased.
            pieces.append(_WORDS.get(key, key if token.islower() else token))
    return ' '.join(pieces)


def _safe_argument(value: str) -> bool:
    masked = _QUOTE.sub(lambda m: 'x' * len(m[0]), value)
    return bool(value.strip() and len(value) <= 160 and len(value.split()) <= 16
                and not _UNSUPPORTED.search(masked)
                and not re.search(r'[?!;\n]|\.\s', masked))


def _slot(role: str, question: str, start: int, end: int) -> MeaningSlot:
    while start < end and question[start].isspace():
        start += 1
    while end > start and question[end-1].isspace():
        end -= 1
    text = question[start:end]
    normalized = ' '.join(text.casefold().split())
    canonical = (_FORMS.get(normalized, canonical_phrase(text)) if role == 'form'
                 else _ACTIONS.get(normalized, normalized) if role == 'action'
                 else _STATES.get(normalized, normalized) if role == 'condition_state'
                 else canonical_phrase(text))
    return MeaningSlot(role, start, end, text, canonical)



_LIST_SEPARATOR = re.compile(r"\s*,\s*(?:(?:and|or|и|или)\s+)?|\s+(?:and|or|и|или)\s+", re.I)


def ordered_list_spans(text: str) -> tuple[tuple[int, int], ...]:
    """A bounded flat list; separators inside quoted identifiers stay literal."""
    masked = _QUOTE.sub(lambda m: 'x' * len(m[0]), text)
    spans, start = [], 0
    for delimiter in _LIST_SEPARATOR.finditer(masked):
        spans.append((start, delimiter.start()))
        start = delimiter.end()
    spans.append((start, len(text)))
    cleaned = []
    for start, end in spans:
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end-1].isspace():
            end -= 1
        value = text[start:end]
        # The explicitly requested universal domain is retained in its slot;
        # this exception does not erase quantifiers from other argument roles.
        scope = re.sub(r'^(?:all|всех)\s+', '', value, flags=re.I)
        if not _safe_argument(scope):
            return ()
        cleaned.append((start, end))
    if not 2 <= len(cleaned) <= 6:
        return ()
    if len({canonical_phrase(text[a:b]) for a, b in cleaned}) != len(cleaned):
        return ()
    return tuple(cleaned)


# Captures are typed slots, not whole rewritten questions. A fullmatch consumes
# the surface; omitted optional captures do not invent a subject, value or answer.
_PATTERNS = (
    ('default', r'(?:what|which)\s+(?:is\s+)?(?:the\s+)?(?:documented\s+)?default\s+'
                r'(?P<attribute>.+?)(?:\s+(?:of|for)\s+(?P<subject>.+?))?(?:\s+is)?'),
    ('default', r'what\s+is\s+(?P<subject>.+?)\s+default\s+(?P<attribute>.+)'),
    ('default', r'(?:какой|какова|каково)\s+(?P<attribute>.+?)\s+по\s+умолчанию(?:\s+у\s+(?P<subject>.+))?'),
    ('precedence', r'which\s+(?:takes\s+precedence|has\s+priority)\s*[:,]?\s+'
                   r'(?P<left>.+?)\s+or\s+(?P<right>.+)'),
    ('precedence', r'what\s+takes\s+precedence\s+between\s+(?P<left>.+?)\s+and\s+(?P<right>.+)'),
    ('precedence', r'что\s+(?:имеет\s+приоритет|приоритетнее)\s*[:,]?\s+'
                   r'(?P<left>.+?)\s+или\s+(?P<right>.+)'),
    ('temporal_order', r'when\s+(?:do|does)\s+(?P<subject>.+?)\s+(?:run|execute)\s+'
                      r'relative\s+to\s+(?P<event>.+)'),
    ('temporal_order', r'когда\s+(?:выполняется|выполняются|запускается)\s+(?P<subject>.+?)\s+'
                      r'относительно\s+(?P<event>.+)'),
    ('callable_form', rf'can\s+(?:a\s+|an\s+)?(?P<subject>.+?)(?:\s+for\s+(?P<owner>.+?))?\s+'
                     rf'be\s+(?P<form>{_FORMS_PATTERN})'),
    ('callable_form', rf'is\s+(?:a\s+|an\s+)?(?P<form>{_FORMS_PATTERN})\s+(?P<subject>.+?)'
                     rf'(?:\s+for\s+(?P<owner>.+?))?\s+allowed'),
    ('callable_form', rf'может\s+ли\s+(?P<subject>.+?)(?:\s+для\s+(?P<owner>.+?))?\s+'
                     rf'быть\s+(?P<form>{_FORMS_PATTERN})'),
    ('mapping', r'which\s+(?P<item_kind>variables|environment\s+variables)\s+'
                r'(?P<action>set|control|configure)\s+(?P<attribute>.+?)\s+for\s+(?P<targets>.+)'),
    ('mapping', r'какие\s+(?P<item_kind>переменные)\s+'
                r'(?P<action>задают|управляют|настраивают)\s+(?P<attribute>.+?)\s+для\s+(?P<targets>.+)'),
    ('enumeration', r'(?:which|what)\s+(?P<item_kind>ways|methods|options|variables|environment\s+variables)\s+'
                    r'(?P<action>enable|disable|activate|deactivate|configure|control)\s+(?P<subject>.+)'),
    ('enumeration', r'list\s+(?:the\s+)?(?P<item_kind>ways|methods|options|variables|environment\s+variables)\s+'
                    r'(?P<action>for)\s+(?P<subject>.+)'),
    ('enumeration', r'какие\s+(?P<item_kind>способы|методы|параметры|переменные)\s+'
                    r'(?P<action>включают|выключают|отключают|настраивают|управляют)\s+(?P<subject>.+)'),
    ('enumeration', r'перечисли\s+(?P<item_kind>способы|методы|параметры|переменные)\s+'
                    r'(?P<action>для)\s+(?P<subject>.+)'),
    ('mapping', r'(?:how\s+do|which)\s+(?P<left>.+?)\s+(?:map|correspond)\s+to\s+(?P<right>.+)'),
    ('mapping', r'как\s+(?P<left>.+?)\s+сопоставляются\s+с\s+(?P<right>.+)'),
    ('behavior', r'what\s+happens\s+to\s+(?P<subject>.+)'),
    ('behavior', r'что\s+происходит\s+с\s+(?P<subject>.+)'),
)
_COMPILED = tuple((op, re.compile(pattern, re.I)) for op, pattern in _PATTERNS)
NEW_RELATIONS = frozenset({'precedence', 'enumeration', 'mapping', 'temporal_order', 'callable_form'})


@lru_cache(maxsize=256)
def parse_admission_frame(question: str) -> ParsedMeaning | None:
    """Recognize only complete supported syntax and keep original coordinates."""
    start, end = 0, len(question)
    while start < end and question[start].isspace():
        start += 1
    while end > start and (question[end-1].isspace() or question[end-1] in '?! .'):
        end -= 1
    while wrapper := _WRAPPER.match(question[start:end]):
        start += wrapper.end()
    body = question[start:end]
    constraints = ()
    condition = _CONDITION.search(body)
    if condition:
        entity = condition['condition_subject']
        if not _safe_argument(entity):
            return None
        constraints = tuple(_slot(role, question, start+condition.start(role), start+condition.end(role))
                            for role in ('condition_subject', 'condition_state'))
        body = body[:condition.start()].rstrip()
    for operator, pattern in _COMPILED:
        match = pattern.fullmatch(body)
        if match is None or (operator == 'behavior' and not constraints):
            continue
        captures = [(role, value) for role, value in match.groupdict().items() if value is not None]
        if any(not _safe_argument(value) for role, value in captures if role != 'targets'):
            continue
        if operator == 'callable_form' and match['form'].casefold() in {
                'normal', 'ordinary', 'regular', 'обычной', 'обычным', 'обычная'}:
            if re.search(r"\b(?:handler|function|callback|callable|обработчик|функция)\b",
                         match['subject'], re.I) is None:
                continue  # 'normal temperature' does not mean a sync callable
        arguments = tuple(_slot(role, question, start+match.start(role), start+match.end(role))
                          for role, _ in captures if role != 'targets')
        if 'targets' in match.groupdict():
            target_ranges = ordered_list_spans(match['targets'])
            if not target_ranges:
                continue
            base = start + match.start('targets')
            arguments += tuple(_slot('target', question, base+a, base+b) for a, b in target_ranges)
        # A supported binary relation requires two distinct arguments. Direction
        # and answer truth are deliberately not stored in the question frame.
        sides = [s.canonical for s in arguments if s.role in {'left', 'right'}]
        if len(sides) == 2 and sides[0] == sides[1]:
            return None
        return ParsedMeaning(operator, arguments, constraints)
    return None
