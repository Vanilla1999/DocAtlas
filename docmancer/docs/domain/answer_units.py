"""Bounded answer-unit extraction and typed local proof checks."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Any, Iterable, Mapping

from docmancer.docs.domain.project_answer_contract import ProofObligation
from docmancer.docs.domain.question_plan_proof import (
    behavior_proof as planned_behavior_proof,
    relation_proof as planned_relation_proof,
    usage_proof as planned_usage_proof,
    workflow_proof as planned_workflow_proof,
)
from docmancer.docs.domain.technical_terms import (
    TechnicalTerm,
    canonical_technical_term,
    coerce_technical_term,
    controlled_noun_forms,
    technical_term_present,
    technical_term_spans,
    term_sequence_present,
    term_sequence_spans,
)


ANSWER_UNIT_SCHEMA = "answer-unit-v2"
MAX_ANSWER_UNITS = 64
MAX_ANSWER_UNIT_CHARS = 1_500

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_BULLET_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)(\S.*)$")
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$")
_KEY_VALUE_RE = re.compile(
    r"^\s*(?:[-*+]\s+)?[`\"']?([A-Za-zА-Яа-яЁё_][\w .:/-]{0,80})[`\"']?\s*[:=]\s*(\S.{0,1000})$"
)
_CODE_DECL_RE = re.compile(
    r"^\s*(?:class|def|async\s+def|function|interface|enum|type|const|let|var|final|"
    r"public|private|protected|static|fun|data\s+class|struct|trait|impl|fn|package|module|"
    r"[A-Za-z_][A-Za-z0-9_]*\s*=)\b.*$",
    re.I,
)
# Do not split dotted identifiers or versions (``mcp.server``, ``3.11``).
# A sentence boundary is punctuation followed by whitespace/end, not every dot.
_SENTENCE_RE = re.compile(r".+?(?:[.!?](?=\s|$)|$)")
_PARAGRAPH_SENTENCE_RE = re.compile(r".+?(?:[.!?](?=\s|$)|$)", re.S)
_IDENTIFIER_RE = re.compile(r"`([^`\n]{2,120})`|\b([A-Za-z_][A-Za-z0-9_.:-]{2,})\b")
_VERSION_VALUE_RE = re.compile(
    r"(?<!\w)(?:[~^<>=!]{0,2}\s*)?v?\d+(?:\.\d+){1,3}(?:[-+][0-9A-Za-z.-]+)?(?:\s*(?:\+|or\s+newer))?(?!\w)",
    re.I,
)
_DURATION_RE = re.compile(
    r"(?<!\w)\d+(?:\.\d+)?\s*(?:ms|msec|milliseconds?|s|sec|seconds?|m|min|minutes?|h|hours?|мс|сек(?:унд[а-я]*)?|мин(?:ут[а-я]*)?|час(?:а|ов)?)\b",
    re.I,
)
_STATUS_VALUE_RE = re.compile(
    r"\b(?:accepted|completed|done|active|in\s+progress|blocked|failed|cancelled|canceled|"
    r"ready|partial|inconclusive|superseded|deprecated|принят[а-я]*|завершен[а-я]*|готов[а-я]*|"
    r"активн[а-я]*|в\s+работе|заблокирован[а-я]*|отменен[а-я]*|неубедител[а-я]*)\b",
    re.I,
)
_COPULA_RE = re.compile(
    r"\b(?:is|are|means|refers\s+to|provides?|represents?|defines?|serves?\s+as|"
    r"это|является|представляет|означает|служит|предоставляет)\b",
    re.I,
)
_BEHAVIOR_RE = re.compile(
    r"\b(?:returns?|reports?|shows?|reads?|writes?|loads?|indexes?|retrieves?|selects?|"
    r"validates?|handles?|processes?|dispatches?|routes?|creates?|updates?|deletes?|use(?:s|d)?|exposes?|"
    r"invokes?|supplies?|calls?|replaces?|preserves?|keeps?|sets?|configures?|requires?|governs?|"
    r"возвращает|показывает|сообщает|читает|записывает|индексирует|извлекает|выбирает|"
    r"проверяет|обрабатывает|маршрутизирует|создает|обновляет|удаляет)\b",
    re.I,
)
_USAGE_RE = re.compile(
    r"\b(?:use[sd]?|using|should\s+be\s+used|when|recommended|reserved\s+for|"
    r"использ(?:овать|уется|ован)|применя(?:ть|ется)|когда|рекомендуется)\b",
    re.I,
)
_SEQUENCE_RE = re.compile(
    r"\b(?:first|then|next|after|before|finally|step\s*\d+|->|→|"
    r"сначала|затем|далее|после|перед|наконец|шаг\s*\d+)\b",
    re.I,
)
_CONTRAST_RE = re.compile(
    r"\b(?:whereas|while|unlike|instead\s+of|but|compared\s+with|versus|vs\.?|"
    r"тогда\s+как|в\s+отличие|вместо|но|по\s+сравнению)\b",
    re.I,
)
_TOOL_WORD_RE = re.compile(r"\b(?:tools?|commands?|methods?|инструмент(?:ы|ов|а)?|команд(?:ы|а|ах)?)\b", re.I)
_TOOL_INVENTORY_ANCHOR_RE = re.compile(
    r"\b(?:public\s+)?(?:tools|commands|methods|инструмент(?:ы|ов)|команд(?:ы|ах))\b"
    r"|\b(?:three|3)[- ]tool(?:[- ]\w+){0,5}\s+surface\b",
    re.I,
)
_EXPLICIT_COUNT_RE = re.compile(
    r"\b(?:exactly\s+)?(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"один|одна|два|две|три|четыре|пять|шесть|семь|восемь|девять|десять)\b",
    re.I,
)
_NEGATION_RE = re.compile(
    r"\b(?:does|do|did|is|are|was|were|should|must|can|could|would|will)\s+not\b"
    r"|\b(?:never|cannot|can't|mustn't|shouldn't)\b"
    r"|\b(?:не\s+следует|не\s+нужно|нельзя|никогда\s+не)\b",
    re.I,
)
_ACTION_RE = re.compile(
    r"(?<![\w-])(?:runs?|follows?|retries?|prepares?|calls?|validates?|dispatches?|routes?|processes?|loads?|reads?|writes?|"
    r"syncs?|synchronizes?|indexes?|reindexes?|discovers?|removes?|publishes?|activates?|creates?|updates?|deletes?|"
    r"preserves?|keeps?|retains?|overrides?|acknowledges?|"
    r"запустить|выполнить|повторить|подготовить|вызвать|проверить|обработать|"
    r"синхронизировать|индексировать|удалить|опубликовать)(?![\w-])",
    re.I,
)
_PURPOSE_RE = re.compile(
    r"\b(?:is\s+used\s+for|used\s+for|serves?\s+as|controls?|overrides?|"
    r"acknowledges?|allows?|enables?|selects?|specifies?|configures?|sets?|"
    r"предназначен[а-я]*\s+для|используется\s+для|переопределяет|управляет|разрешает)\b",
    re.I,
)
_PURPOSE_COPULA_RE = re.compile(
    r"\b(?:is|are|means|represents?|defines?)\b(?!\s+not\b)"
    r"(?=[^.;!?\n]{0,180}\b(?:staging\s+area|mechanism|facility|purpose|"
    r"used\s+(?:for|to|before)|responsible\s+for|so\s+that|so\b))",
    re.I,
)
_DELETE_PREDICATE_RE = re.compile(
    r"(?<![\w-])(?:deletes?|removes?|clears?|purges?|drops?|удаляет|очищает)(?![\w-])",
    re.I,
)
_PRESERVE_PREDICATE_RE = re.compile(
    r"(?<![\w-])(?:preserves?|keeps?|retains?|leaves?\s+intact|сохраняет|оставляет)(?![\w-])",
    re.I,
)
_NEGATED_DELETE_RE = re.compile(
    r"\b(?:without|not|never|does\s+not|do\s+not|will\s+not)\s+"
    r"(?:silently\s+)?(?:deleting|removing|clearing|purging|delete|remove|clear|purge)\b",
    re.I,
)
_ARCH_COMPONENT_RE = re.compile(
    r"\b(?:server|handler|router|service|transport|registry|adapter|layer|module|"
    r"ui|application|domain|infrastructure)\b",
    re.I,
)
_ARCH_RELATION_RE = re.compile(
    r"\b(?:routes?|dispatch(?:es)?|coordinates?|connects?|composes?|through|consists?|"
    r"состоит|связывает|маршрутизирует)\b|->|→",
    re.I,
)


def _normal(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold().replace("ё", "е").replace("_", " ")).strip()


def _bounded_text(text: str) -> str:
    return text.strip()[:MAX_ANSWER_UNIT_CHARS]


@dataclass(frozen=True, slots=True)
class AnswerUnit:
    unit_id: str
    kind: str
    text: str
    char_start: int | None
    char_end: int | None
    content_sha256: str
    proposition: bool
    source_field: str | None = None

    def __post_init__(self) -> None:
        if not self.unit_id or not self.text:
            raise ValueError("invalid answer unit")
        if self.source_field is not None:
            if self.char_start is not None or self.char_end is not None:
                raise ValueError("source-field answer units do not use content offsets")
        elif (
            self.char_start is None or self.char_end is None
            or self.char_start < 0 or self.char_end <= self.char_start
        ):
            raise ValueError("invalid answer unit offsets")
        if len(self.text) > MAX_ANSWER_UNIT_CHARS:
            raise ValueError("answer unit exceeds bound")
        expected = hashlib.sha256(self.text.encode("utf-8")).hexdigest()
        if expected != self.content_sha256:
            raise ValueError("answer unit hash mismatch")


def materialize_answer_units(
    source_text: str,
    units: Iterable[AnswerUnit],
    *,
    max_gap_chars: int = 400,
) -> str:
    """Render the exact bounded material represented by assigned answer units.

    Nearby content units are expanded to their contiguous source span.  This
    preserves short connective sentences between two assigned propositions and
    keeps selection-time token fitting identical to final projection.  Distant
    units remain separate so an assignment cannot expose an unrelated middle of
    the chunk.  Source-field witnesses are appended independently because they
    have no content offsets.
    """

    source = str(source_text or "")
    unique: dict[str, AnswerUnit] = {}
    for unit in units:
        unique.setdefault(unit.unit_id, unit)
    ordered = sorted(
        unique.values(),
        key=lambda item: (
            item.char_start if item.char_start is not None else 10**9,
            item.char_end if item.char_end is not None else 10**9,
            item.unit_id,
        ),
    )
    content_units = [
        item for item in ordered
        if item.char_start is not None and item.char_end is not None
    ]
    parts: list[str] = []
    if content_units:
        cluster: list[AnswerUnit] = []
        for unit in content_units:
            if not cluster:
                cluster = [unit]
                continue
            cluster_start = min(item.char_start or 0 for item in cluster)
            cluster_end = max(item.char_end or cluster_start for item in cluster)
            unit_start = unit.char_start if unit.char_start is not None else cluster_end
            unit_end = unit.char_end if unit.char_end is not None else unit_start
            combined_end = max(cluster_end, unit_end)
            if (
                unit_start - cluster_end <= max_gap_chars
                and combined_end - cluster_start <= MAX_ANSWER_UNIT_CHARS
            ):
                cluster.append(unit)
                continue
            start = min(item.char_start or 0 for item in cluster)
            end = max(item.char_end or start for item in cluster)
            material = source[start:end].strip() or "\n\n".join(item.text for item in cluster)
            if material:
                parts.append(material)
            cluster = [unit]
        if cluster:
            start = min(item.char_start or 0 for item in cluster)
            end = max(item.char_end or start for item in cluster)
            material = source[start:end].strip() or "\n\n".join(item.text for item in cluster)
            if material:
                parts.append(material)

    seen_parts = {part.strip() for part in parts}
    for unit in ordered:
        if unit.source_field is None:
            continue
        value = unit.text.strip()
        if value and value not in seen_parts:
            parts.append(value)
            seen_parts.add(value)
    return "\n\n".join(part for part in parts if part.strip())


@dataclass(frozen=True, slots=True)
class LocalProof:
    valid: bool
    subject_score: int = 0
    relation_score: int = 0
    value_score: int = 0
    completeness_score: int = 0
    reason: str = ""


def _make_unit(kind: str, raw: str, start: int, end: int, *, proposition: bool) -> AnswerUnit | None:
    left_trim = len(raw) - len(raw.lstrip())
    right_trim = len(raw) - len(raw.rstrip())
    text = _bounded_text(raw)
    if not text:
        return None
    start += left_trim
    end -= right_trim
    if len(text) != end - start:
        end = start + len(text)
    identity = hashlib.sha256(f"{kind}\0{start}\0{end}\0{text}".encode("utf-8")).hexdigest()
    return AnswerUnit(
        unit_id=f"unit-{identity[:20]}", kind=kind, text=text,
        char_start=start, char_end=end,
        content_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        proposition=proposition,
    )


def _make_source_field_unit(name: str, value: Any) -> AnswerUnit | None:
    text = _bounded_text(str(value or ""))
    if not text:
        return None
    identity = hashlib.sha256(f"source_field\0{name}\0{text}".encode("utf-8")).hexdigest()
    return AnswerUnit(
        unit_id=f"unit-{identity[:20]}",
        kind="source_field",
        text=text,
        char_start=None,
        char_end=None,
        content_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        proposition=True,
        source_field=name,
    )


def extract_answer_units(
    text: str,
    *,
    source_fields: Mapping[str, Any] | None = None,
    include_soft_wrapped_prose: bool = False,
) -> tuple[AnswerUnit, ...]:
    """Extract deterministic local propositions without merging unrelated chunks.

    The default path preserves the v2 line-oriented unit surface.  New v3
    obligations may opt into exact paragraph sentences and continued Markdown
    bullets when source prose is hard-wrapped.  This keeps frozen v1/v2
    selection traces stable while allowing a predicate or object to cross one
    physical line boundary without becoming an incomplete witness.
    """

    source = str(text or "")
    if not source.strip():
        return ()
    units: list[AnswerUnit] = []
    lines = list(re.finditer(r".*(?:\n|$)", source))
    heading_positions: list[tuple[int, int, str]] = []
    in_fence = False
    fence_start = 0
    fence_lines: list[tuple[int, int, str]] = []

    def add(kind: str, raw: str, start: int, end: int, proposition: bool = True) -> None:
        unit = _make_unit(kind, raw, start, end, proposition=proposition)
        if unit is not None:
            units.append(unit)

    consumed_until = -1
    for line_index, line_match in enumerate(lines):
        raw_line = line_match.group(0)
        line = raw_line.rstrip("\n")
        start = line_match.start()
        end = start + len(line)
        if start < consumed_until:
            continue
        if not line and line_match.end() == len(source):
            continue
        if line.strip().startswith("```"):
            if not in_fence:
                in_fence = True
                fence_start = start
                fence_lines = []
            else:
                for code_start, code_end, code_line in fence_lines:
                    if _CODE_DECL_RE.match(code_line) or _KEY_VALUE_RE.match(code_line):
                        add("code_declaration", code_line, code_start, code_end)
                if fence_lines and not any(_CODE_DECL_RE.match(value[2]) for value in fence_lines):
                    raw_block = source[fence_start:line_match.end()]
                    if len(raw_block.strip()) <= MAX_ANSWER_UNIT_CHARS:
                        # Preserve source-relative offsets.  Passing a stripped
                        # block with the untrimmed start used to shorten the
                        # span and could make a selected code-block witness
                        # impossible to re-materialize exactly.
                        add("code_block", raw_block, fence_start, line_match.end())
                in_fence = False
            continue
        if in_fence:
            fence_lines.append((start, end, line))
            continue
        heading = _HEADING_RE.match(line)
        if heading:
            heading_positions.append((start, end, heading.group(2).strip()))
            continue
        bullet = _BULLET_RE.match(line)
        if bullet:
            block_end = end
            if include_soft_wrapped_prose:
                for following in lines[line_index + 1:]:
                    continuation = following.group(0).rstrip("\n")
                    continuation_start = following.start()
                    continuation_end = continuation_start + len(continuation)
                    if not continuation.strip() or not re.match(r"^[ \t]{2,}\S", continuation):
                        break
                    if (
                        continuation.strip().startswith("```")
                        or _HEADING_RE.match(continuation)
                        or _BULLET_RE.match(continuation)
                    ):
                        break
                    block_end = continuation_end
                consumed_until = block_end
            block = source[start:block_end]
            add(
                "bullet", block, start, block_end,
                proposition=bool(
                    _COPULA_RE.search(block) or _BEHAVIOR_RE.search(block)
                    or _KEY_VALUE_RE.match(bullet.group(1))
                    or len(block.split()) >= 2
                ),
            )
            continue
        if "|" in line and not _TABLE_SEPARATOR_RE.match(line) and len([part for part in line.split("|") if part.strip()]) >= 2:
            add("table_row", line, start, end, proposition=True)
            continue
        if _KEY_VALUE_RE.match(line):
            add("key_value", line, start, end, proposition=True)
            continue
        if _CODE_DECL_RE.match(line):
            add("code_declaration", line, start, end, proposition=True)
            continue
        next_line = (
            lines[line_index + 1].group(0).rstrip("\n")
            if line_index + 1 < len(lines) else ""
        )
        next_is_plain_prose = bool(
            next_line.strip()
            and not next_line.strip().startswith("```")
            and not _HEADING_RE.match(next_line)
            and not _BULLET_RE.match(next_line)
            and not _TABLE_SEPARATOR_RE.match(next_line)
            and not ("|" in next_line and len([part for part in next_line.split("|") if part.strip()]) >= 2)
            and not _KEY_VALUE_RE.match(next_line)
            and not _CODE_DECL_RE.match(next_line)
        )
        soft_wrapped_line = bool(
            include_soft_wrapped_prose
            and next_is_plain_prose
            and not re.search(r"[.!?]\s*$", line)
        )
        for sentence in _SENTENCE_RE.finditer(line):
            sentence_text = sentence.group(0).strip()
            if not sentence_text:
                continue
            sentence_start = start + sentence.start() + (len(sentence.group(0)) - len(sentence.group(0).lstrip()))
            add(
                "sentence", sentence_text, sentence_start, sentence_start + len(sentence_text),
                proposition=bool(
                    not soft_wrapped_line
                    and (
                        _COPULA_RE.search(sentence_text) or _BEHAVIOR_RE.search(sentence_text)
                        or _STATUS_VALUE_RE.search(sentence_text) or _VERSION_VALUE_RE.search(sentence_text)
                        or _DURATION_RE.search(sentence_text) or len(sentence_text.split()) >= 4
                    )
                ),
            )

    if include_soft_wrapped_prose:
        paragraph_lines: list[tuple[int, int, str]] = []
        paragraph_in_fence = False
        paragraph_sentence_count = 0

        def flush_paragraph() -> None:
            nonlocal paragraph_lines, paragraph_sentence_count
            if not paragraph_lines or paragraph_sentence_count >= 16:
                paragraph_lines = []
                return
            paragraph_start = paragraph_lines[0][0]
            paragraph_end = paragraph_lines[-1][1]
            paragraph = source[paragraph_start:paragraph_end]
            if "\n" not in paragraph or len(paragraph) > MAX_ANSWER_UNIT_CHARS:
                paragraph_lines = []
                return
            for sentence in _PARAGRAPH_SENTENCE_RE.finditer(paragraph):
                raw = sentence.group(0)
                stripped = raw.strip()
                if not stripped:
                    continue
                left_trim = len(raw) - len(raw.lstrip())
                sentence_start = paragraph_start + sentence.start() + left_trim
                add(
                    "paragraph_sentence", stripped,
                    sentence_start, sentence_start + len(stripped),
                    proposition=bool(
                        _COPULA_RE.search(stripped) or _BEHAVIOR_RE.search(stripped)
                        or _STATUS_VALUE_RE.search(stripped) or _VERSION_VALUE_RE.search(stripped)
                        or _DURATION_RE.search(stripped) or len(stripped.split()) >= 4
                    ),
                )
                paragraph_sentence_count += 1
                if paragraph_sentence_count >= 16:
                    break
            paragraph_lines = []

        for line_match in lines:
            raw_line = line_match.group(0)
            line = raw_line.rstrip("\n")
            start = line_match.start()
            end = start + len(line)
            if line.strip().startswith("```"):
                flush_paragraph()
                paragraph_in_fence = not paragraph_in_fence
                continue
            if paragraph_in_fence:
                continue
            structural = bool(
                not line.strip()
                or _HEADING_RE.match(line)
                or _BULLET_RE.match(line)
                or _TABLE_SEPARATOR_RE.match(line)
                or ("|" in line and len([part for part in line.split("|") if part.strip()]) >= 2)
                or _KEY_VALUE_RE.match(line)
                or _CODE_DECL_RE.match(line)
            )
            if structural:
                flush_paragraph()
                continue
            paragraph_lines.append((start, end, line))
        flush_paragraph()

    # A heading supplies context only when followed by an actual bounded block.
    for heading_start, heading_end, _heading in heading_positions:
        next_heading = min(
            (start for start, _end, _value in heading_positions if start > heading_start),
            default=len(source),
        )
        region = source[heading_end:next_heading]
        content_match = re.search(r"\S", region)
        if content_match is None:
            continue
        content_start = content_match.start()
        content_region = region[content_start:]
        paragraph_break = re.search(r"\n\s*\n", content_region)
        content_end = content_start + paragraph_break.start() if paragraph_break is not None else len(region)
        block_end = min(next_heading, heading_end + content_end)
        candidate = source[heading_start:block_end].rstrip()
        heading_text = source[heading_start:heading_end].strip()
        body_text = source[heading_end:block_end].strip()
        if not body_text or candidate.strip() == heading_text:
            continue
        if len(candidate) <= MAX_ANSWER_UNIT_CHARS:
            add("heading_context", candidate, heading_start, block_end, proposition=True)

    positional = sorted(
        (unit for unit in units if unit.char_start is not None and unit.char_end is not None),
        key=lambda item: (item.char_start, item.char_end, item.kind, item.unit_id),
    )
    runs: list[list[AnswerUnit]] = []
    current: list[AnswerUnit] = []
    for unit in positional:
        if unit.kind == "heading_context":
            continue
        if not current:
            current = [unit]
            continue
        previous = current[-1]
        gap = source[previous.char_end:unit.char_start]
        if (
            len(current) < 6
            and not gap.strip()
            and unit.char_end - current[0].char_start <= MAX_ANSWER_UNIT_CHARS
        ):
            current.append(unit)
        else:
            if len(current) >= 2:
                runs.append(current)
            current = [unit]
    if len(current) >= 2:
        runs.append(current)

    if include_soft_wrapped_prose:
        group_count = 0
        for run in runs[:12]:
            max_width = min(6, len(run))
            for width in range(2, max_width + 1):
                for offset in range(0, len(run) - width + 1):
                    window = run[offset:offset + width]
                    start = window[0].char_start
                    end = window[-1].char_end
                    if start is None or end is None:
                        continue
                    material = source[start:end]
                    bullet_count = sum(item.kind == "bullet" for item in window)
                    if bullet_count >= 2 or _SEQUENCE_RE.search(material) or len(_ACTION_RE.findall(material)) >= 2:
                        add("unit_group", material, start, end, proposition=True)
                        group_count += 1
                        if group_count >= 24:
                            break
                if group_count >= 24:
                    break
            if group_count >= 24:
                break
    else:
        for run in runs[:12]:
            start = run[0].char_start
            end = run[-1].char_end
            if start is None or end is None:
                continue
            material = source[start:end]
            bullet_count = sum(item.kind == "bullet" for item in run)
            if bullet_count >= 2 or _SEQUENCE_RE.search(material) or len(_ACTION_RE.findall(material)) >= 2:
                add("unit_group", material, start, end, proposition=True)

    for field_name, value in sorted((source_fields or {}).items()):
        unit = _make_source_field_unit(str(field_name), value)
        if unit is not None:
            units.append(unit)

    by_key: dict[tuple[str, int | None, int | None, str | None], AnswerUnit] = {}
    for unit in units:
        by_key.setdefault((unit.content_sha256, unit.char_start, unit.char_end, unit.source_field), unit)
    ordered = sorted(by_key.values(), key=lambda item: (
        item.char_start if item.char_start is not None else 10**9,
        item.char_end if item.char_end is not None else 10**9,
        item.kind, item.source_field or "", item.unit_id,
    ))
    return tuple(ordered[:MAX_ANSWER_UNITS])

def _obligation_technical_term(obligation: ProofObligation) -> TechnicalTerm | None:
    if obligation.subject_kind is None:
        return None
    base = coerce_technical_term(obligation.subject, obligation.subject_kind)
    aliases = obligation.subject_aliases or base.aliases
    return TechnicalTerm(
        raw=base.raw,
        canonical=canonical_technical_term(base.raw, base.kind),
        kind=base.kind,
        aliases=aliases,
    )


def _contains_term(term: str | None, text: str) -> bool:
    wanted = str(term or "").strip()
    return bool(wanted) and term_sequence_present(wanted, text)


def _subject_spans(
    obligation: ProofObligation,
    text: str,
) -> tuple[tuple[int, int], ...]:
    """Return exact alias-aware subject spans inside one visible unit."""

    technical = _obligation_technical_term(obligation)
    if technical is not None:
        return technical_term_spans(technical, text, require_kind_shape=True)
    spans: list[tuple[int, int]] = []
    for alias in obligation.subject_aliases or (obligation.subject,):
        spans.extend(term_sequence_spans(alias, text))
    return tuple(dict.fromkeys(spans))


def _subject_present(obligation: ProofObligation, text: str) -> bool:
    return bool(_subject_spans(obligation, text))


def _bounded_clauses(text: str) -> tuple[tuple[int, int, str], ...]:
    """Split one answer unit into bounded relation-local clauses.

    The split is intentionally conservative: sentence terminators, semicolons,
    and physical line boundaries end a clause.  Dotted identifiers and versions
    remain intact because a period is a boundary only before whitespace/end.
    """

    source = str(text or "")
    if not source:
        return ()
    clauses: list[tuple[int, int, str]] = []
    start = 0
    for boundary in re.finditer(r"(?:[.!?](?=\s|$)|;|\n)", source):
        end = boundary.end()
        raw = source[start:end]
        left = len(raw) - len(raw.lstrip())
        right = len(raw) - len(raw.rstrip())
        clause_start = start + left
        clause_end = end - right
        if clause_end > clause_start:
            clauses.append((clause_start, clause_end, source[clause_start:clause_end]))
        start = end
    raw = source[start:]
    left = len(raw) - len(raw.lstrip())
    right = len(raw) - len(raw.rstrip())
    clause_start = start + left
    clause_end = len(source) - right
    if clause_end > clause_start:
        clauses.append((clause_start, clause_end, source[clause_start:clause_end]))
    return tuple(clauses)


def _word_distance(
    left: tuple[int, int],
    right: tuple[int, int],
    text: str,
) -> int:
    if left[1] <= right[0]:
        between = text[left[1]:right[0]]
    elif right[1] <= left[0]:
        between = text[right[1]:left[0]]
    else:
        return 0
    return len(re.findall(r"[A-Za-zА-Яа-яЁё0-9_~-]+", between))


def _purpose_clause(
    obligation: ProofObligation,
    text: str,
    *,
    max_words: int = 14,
) -> tuple[str, int] | None:
    """Return the strongest clause that locally binds subject and purpose.

    A direct ``subject -> predicate`` proposition is preferred to a reverse
    imperative/example (``set ... with SUBJECT``).  Both remain valid, but the
    direct form is the better model-visible answer when both are available.
    """

    matches: list[tuple[int, str]] = []
    for _start, _end, clause in _bounded_clauses(text):
        subject_spans = _subject_spans(obligation, clause)
        if not subject_spans:
            continue
        predicate_spans = [
            match.span()
            for pattern in (_PURPOSE_RE, _PURPOSE_COPULA_RE)
            for match in pattern.finditer(clause)
            if _positive_relation_match(match, clause)
        ]
        for subject in subject_spans:
            for predicate in predicate_spans:
                if subject[0] < predicate[1] and predicate[0] < subject[1]:
                    continue
                if _word_distance(subject, predicate, clause) > max_words:
                    continue
                matches.append((4 if subject[0] < predicate[0] else 3, clause))
    if not matches:
        return None
    score, clause = max(matches, key=lambda item: (item[0], len(item[1])))
    return clause, score


def _context_score(context: str | None, text: str, source_text: str) -> int:
    if not context:
        return 1

    # Context matching is token based and intentionally uses only a tiny,
    # domain-neutral derivational map.  This makes ``clear-index`` compatible
    # with the source path ``index-cleanup.md`` without introducing a global
    # stemmer that could corrupt API/config identities.
    canonical = {
        "cleanup": "clear",
        "cleaning": "clear",
        "clearing": "clear",
        "indexes": "index",
        "indices": "index",
        "indexing": "index",
    }

    def tokens(value: str) -> set[str]:
        return {
            canonical.get(token.casefold(), token.casefold())
            for token in re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", value)
            if len(token) > 2
        }

    wanted = tokens(context)
    if not wanted:
        return 1
    haystack = tokens(f"{text}\n{source_text}")
    return 3 if wanted.issubset(haystack) else 0


def _predicate_has_object(match: re.Match[str], text: str) -> bool:
    tail = text[match.end():]
    clause = re.split(r"[.;!?\n]", tail, maxsplit=1)[0]
    return len(re.findall(r"[A-Za-zА-Яа-яЁё0-9_~-]+", clause)) >= 1


def _positive_relation_match(match: re.Match[str], text: str) -> bool:
    prefix = text[max(0, match.start() - 30):match.start()]
    if re.search(
        r"\b(?:without|not|never|does\s+not|do\s+not|will\s+not)\s+(?:\w+\s+){0,2}$",
        prefix,
        re.I,
    ):
        return False
    return _predicate_has_object(match, text)


def _positive_relation(pattern: re.Pattern[str], text: str) -> bool:
    return any(_positive_relation_match(match, text) for match in pattern.finditer(text))


def _effect_relation_valid(
    obligation: ProofObligation,
    text: str,
    *,
    max_words: int = 16,
) -> bool:
    """Require the requested effect and command subject in the same clause."""

    relation = obligation.relation
    for _start, _end, clause in _bounded_clauses(text):
        subjects = _subject_spans(obligation, clause)
        if not subjects:
            continue
        if relation == "delete":
            matches = [
                match for match in _DELETE_PREDICATE_RE.finditer(clause)
                if _positive_relation_match(match, clause)
            ]
        elif relation == "preserve":
            matches = [
                match for match in _PRESERVE_PREDICATE_RE.finditer(clause)
                if _positive_relation_match(match, clause)
            ]
            matches.extend(
                match for match in _NEGATED_DELETE_RE.finditer(clause)
                if _predicate_has_object(match, clause)
            )
        else:
            return False
        if any(
            _word_distance(subject, match.span(), clause) <= max_words
            for subject in subjects
            for match in matches
        ):
            return True
    return False


def _attribute_aliases(attribute: str | None) -> tuple[str, ...]:
    normalized = _normal(attribute)
    aliases = {
        "python version": ("python version", "requires-python", "python_requires", "python requirement", "python"),
        "version": ("version", "requires", "runtime"),
        "timeout": ("timeout", "time-out", "deadline", "request timeout", "timeout_seconds", "timeout_ms", "время ожидания", "тайм-аут"),
        "status": ("status", "state", "статус", "состояние"),
        "public tools": ("public tools", "tools", "commands", "methods", "инструменты", "команды"),
        "scope": ("scope", "scopes", "область", "области"),
        "marker": ("marker", "markers", "test marker", "test markers"),
        "source": ("source", "sources", "source type", "source types"),
    }
    return aliases.get(normalized, (attribute,) if attribute else ())


def _attribute_present(attribute: str | None, text: str) -> bool:
    return any(_contains_term(alias, text) for alias in _attribute_aliases(attribute))


_NUMBER_WORD_VALUES = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "один": 1, "одна": 1, "два": 2, "две": 2, "три": 3, "четыре": 4,
    "пять": 5, "шесть": 6, "семь": 7, "восемь": 8, "девять": 9, "десять": 10,
}


def _inventory_anchor(text: str, item_kind: str | None = None) -> re.Match[str] | None:
    if not item_kind or item_kind == "public_tool":
        return _TOOL_INVENTORY_ANCHOR_RE.search(text)
    forms = controlled_noun_forms(item_kind)
    if not forms:
        return None
    variants = set(forms)
    singular = forms[-1]
    if re.fullmatch(r"[a-z][a-z0-9_-]{2,}", singular) and not singular.endswith("s"):
        variants.add(singular + "s")
    if singular == "scope":
        variants.update(("scope", "scopes", "область", "области"))
    elif singular == "mode":
        variants.update(("mode", "modes", "режим", "режимы"))
    elif singular == "option":
        variants.update(("option", "options", "опция", "опции"))
    pattern = re.compile(
        r"(?<![A-Za-zА-Яа-яЁё0-9_-])(?:"
        + "|".join(re.escape(value) for value in sorted(variants, key=lambda value: (-len(value), value)))
        + r")(?![A-Za-zА-Яа-яЁё0-9_-])",
        re.I,
    )
    return pattern.search(text)


def _inventory_facts(
    text: str,
    *,
    item_kind: str | None = None,
) -> tuple[int | None, tuple[str, ...], bool]:
    anchor = _inventory_anchor(text, item_kind)
    if anchor is None:
        return None, (), False
    window = text[max(0, anchor.start() - 40):anchor.end() + 700]
    explicit_count: int | None = None
    count_match = _EXPLICIT_COUNT_RE.search(window)
    if count_match:
        raw = count_match.group(1).casefold()
        explicit_count = int(raw) if raw.isdigit() else _NUMBER_WORD_VALUES.get(raw)
    names: list[str] = []
    tail = window[window.casefold().find(anchor.group(0).casefold()) + len(anchor.group(0)):]
    # Closed inventories are introduced by punctuation/copula and contain
    # code-shaped or quoted names.  Ordinary identifiers elsewhere in a
    # branding sentence are deliberately ignored.
    introduced = re.search(r"(?:\b(?:are|include|consist\s+of|namely)\b|[:=-])\s*(.+)$", tail, re.I | re.S)
    if introduced:
        material = introduced.group(1).split("\n\n", 1)[0]
        for match in re.finditer(r"`([^`\n]{2,120})`", material):
            candidate = match.group(1).strip().rstrip("()")
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.:-]{1,119}", candidate):
                names.append(_normal(candidate))
        for part in re.split(r"\s*[,;]\s*|\s+(?:and|or|и|или)\s+", material):
            candidate = re.sub(r"^(?:and|or|и|или)\s+", "", part.strip(), flags=re.I)
            candidate = candidate.strip(" `.'\"()[]")
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.:-]{1,80}", candidate) and (
                "_" in candidate or "." in candidate or ":" in candidate or candidate.islower()
            ):
                names.append(_normal(candidate))
    # Generic closed inventories may be documented as Markdown tables or a
    # parenthesized/backticked list.  Keep public-tool parsing strict, but let
    # already-typed item kinds use those reviewable structures.
    if item_kind and item_kind != "public_tool" and len(names) < 2:
        lines = text.splitlines()
        anchor_line = next((idx for idx, line in enumerate(lines) if _inventory_anchor(line, item_kind)), None)
        if anchor_line is not None and "|" in lines[anchor_line]:
            for line in lines[anchor_line + 1:]:
                if not line.strip():
                    break
                if re.match(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+", line):
                    continue
                cells = [cell.strip(" `") for cell in line.strip().strip("|").split("|")]
                if cells and cells[0] and len(cells[0]) <= 120:
                    names.append(_normal(cells[0]))
        if len(names) < 2:
            for match in re.finditer(r"`([^`\n]{1,80})`", window):
                candidate = match.group(1).strip()
                if candidate and len(candidate.split()) <= 4:
                    names.append(_normal(candidate))
    unique = tuple(dict.fromkeys(value for value in names if value))
    return explicit_count, unique, True


def _subject_token_overlap(subject: str, text: str) -> int:
    ignored = {"docatlas", "the", "a", "an", "execution", "document", "docs"}
    wanted = [token for token in re.findall(r"[a-z0-9_]+", _normal(subject)) if token not in ignored and len(token) > 2]
    haystack = _normal(text)
    return sum(1 for token in set(wanted) if token in haystack)


def _value_score(value_kind: str, text: str, *, cardinality: int | None = None) -> int:
    if value_kind == "version_range":
        return 3 if _VERSION_VALUE_RE.search(text) else 0
    if value_kind == "duration":
        return 3 if _DURATION_RE.search(text) else 0
    if value_kind == "status":
        return 3 if _STATUS_VALUE_RE.search(text) else 0
    if value_kind == "number":
        return 2 if re.search(r"(?<!\w)\d+(?:\.\d+)?(?!\w)", text) else 0
    if value_kind == "boolean":
        return 2 if re.search(r"\b(?:true|false|yes|no|enabled|disabled|да|нет|включен|выключен)\b", text, re.I) else 0
    if value_kind == "path":
        return 2 if re.search(r"(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+", text) else 0
    if value_kind in {"code", "call_expression"}:
        return 2 if (
            re.search(r"`[^`]+`|\b[A-Za-z_]\w*(?:(?:::|\.)[A-Za-z_]\w*)+", text)
            or _CODE_DECL_RE.match(text)
            or re.search(r"\b(?:const|let|var|final)\s+[A-Za-z_]\w*\s*=", text, re.I)
        ) else 0
    if value_kind == "identifier_list":
        _count, identifiers, anchored = _inventory_facts(text)
        if not anchored:
            return 0
        count = len(identifiers)
        if cardinality is not None:
            return 3 if count == cardinality else 0
        return 3 if count >= 2 else 0
    # text values need a predicate/content beyond a bare identity.
    return 1 if len(re.findall(r"\w+", text, re.UNICODE)) >= 3 else 0


def _subject_before_pattern(subject: str, pattern: re.Pattern[str], text: str, *, words: int = 8) -> bool:
    subject_pattern = re.escape(_normal(subject)).replace(r"\ ", r"[\s_]+")
    normalized = _normal(text)
    return re.search(
        rf"(?<!\w){subject_pattern}(?!\w)(?:\W+\w+){{0,{words}}}?\W+{pattern.pattern}",
        normalized,
        pattern.flags,
    ) is not None


def _special_relation_valid(relation: str | None, text: str) -> bool:
    normalized = _normal(text)
    if relation == "recall_mechanism":
        return bool(
            re.search(r"\bexact(?:[- ]term| match| query)?\b", normalized)
            and re.search(r"\b(?:recall|retrieve|retrieval|lookup|match)\b", normalized)
        )
    if relation == "authority_invariant":
        return bool(
            re.search(r"\b(?:authority|scope)\b", normalized)
            and re.search(
                r"\b(?:unchanged|preserv(?:e|es|ed)|without\s+(?:widening|expanding|broadening)|"
                r"does\s+not\s+(?:widen|expand|broaden))\b",
                normalized,
            )
        )
    if relation == "request_handling":
        return bool(
            re.search(r"\brequest\b|\bзапрос", normalized)
            and re.search(r"\b(?:handles?|process(?:es|ing)?|dispatch(?:es|ing)?|routes?|validates?|forwards?)\b|\b(?:обрабатывает|маршрутизирует|проверяет)", normalized)
            and re.search(r"\b(?:handler|router|server|tool|transport|service|registry)\b", normalized)
        )
    if relation == "architecture":
        return len(set(_ARCH_COMPONENT_RE.findall(normalized))) >= 2 and bool(_ARCH_RELATION_RE.search(normalized))
    if relation == "responsiveness":
        return bool(
            re.search(r"\b(?:non[- ]blocking|asynchronous|async|does\s+not\s+block)\b", normalized)
            and re.search(r"\b(?:worker|background|event\s+loop|queue|thread|task)\b", normalized)
        )
    return False


def local_proof_for_obligation(
    obligation: ProofObligation,
    unit: AnswerUnit,
    *,
    source: Mapping[str, Any] | None = None,
) -> LocalProof:
    """Validate one obligation against exactly one model-visible answer unit."""

    text = unit.text
    source = source or {}
    source_text = "\n".join(str(source.get(key) or "") for key in (
        "path", "source", "title", "heading_path", "project_identity", "module_id",
    ))
    authority = str(source.get("authority") or source.get("project_doc_authority") or "").casefold()
    lifecycle = str(
        source.get("lifecycle_status") or source.get("project_doc_lifecycle_status") or "active"
    ).casefold()
    if obligation.lifecycle_intent == "current" and lifecycle not in {"", "active", "current"}:
        return LocalProof(False, reason="historical_source_for_current_obligation")
    if obligation.lifecycle_intent == "historical" and lifecycle in {"", "active", "current"}:
        # Historical queries may still cite an active status table, but it cannot
        # be the sole witness for a completed/historical fact.
        return LocalProof(False, reason="current_source_for_historical_obligation")

    subject_local = _subject_present(obligation, text)
    authoritative_identity = (
        authority in {"canonical", "source_of_truth", "official", "project_owned", "project_rule", "primary"}
        and _subject_present(obligation, source_text)
    )
    # Synthetic parser fallbacks (``project``, ``request``, ``workflow`` and
    # similar placeholders) are never proof by themselves.  A very small set
    # of legacy semantic subjects is different: v1-v3 intentionally models
    # relations such as MCP architecture/request handling as a typed facet and
    # allows the locally visible component nouns (server/handler/transport) to
    # carry the subject identity.  Keep that frozen compatibility without
    # reopening the generic-subject false-positive path.
    legacy_semantic_subject = (
        _normal(obligation.subject) in {"mcp server", "exact-term retrieval", "authority scope"}
        and obligation.kind == "relation"
        and obligation.relation in {
            "recall_mechanism", "authority_invariant", "request_handling",
            "architecture", "responsiveness",
        }
    )
    subject_score = (
        3 if subject_local else
        2 if authoritative_identity else
        1 if legacy_semantic_subject and unit.proposition else
        0
    )

    if obligation.kind == "purpose":
        context = _context_score(obligation.context, text, source_text)
        purpose = _purpose_clause(obligation, text)
        bound_clause = purpose[0] if purpose is not None else None
        relation = purpose[1] if purpose is not None else 0
        value = _value_score("text", bound_clause or "")
        valid = subject_local and context > 0 and relation > 0 and value > 0 and unit.proposition
        return LocalProof(
            valid, subject_score, relation + context, value,
            subject_score + relation + context + value,
            "purpose" if valid else "purpose_subject_context_or_predicate_missing",
        )

    if obligation.kind == "effect":
        relation_valid = _effect_relation_valid(obligation, text)
        relation = 3 if relation_valid else 0
        value = 2 if relation_valid else 0
        valid = subject_score > 0 and relation > 0 and unit.proposition
        return LocalProof(
            valid, subject_score, relation, value,
            subject_score + relation + value,
            f"effect_{obligation.relation}" if valid else f"effect_{obligation.relation}_not_locally_bound",
        )

    if obligation.kind == "definition":
        relation = 3 if _COPULA_RE.search(text) else 0
        value = _value_score("text", text)
        valid = subject_score > 0 and relation > 0 and value > 0 and unit.proposition
        return LocalProof(valid, subject_score, relation, value, subject_score + relation + value, "definition" if valid else "definition_incomplete")

    if obligation.kind == "attribute":
        attribute = 3 if _attribute_present(obligation.attribute, text) else 0
        value = _value_score(obligation.value_kind, text)
        local_binding = bool(attribute and value and (subject_local or authoritative_identity))
        return LocalProof(local_binding, subject_score, attribute, value, subject_score + attribute + value, "attribute" if local_binding else "attribute_value_not_locally_bound")

    if obligation.kind == "inventory":
        explicit_count, names, anchored = _inventory_facts(
            text, item_kind=obligation.item_kind,
        )
        attribute_bound = anchored and (
            obligation.item_kind == "public_tool"
            or _attribute_present(obligation.attribute, text)
        )
        attribute = 3 if attribute_bound else 0
        names_valid = len(names) >= 2 and (
            obligation.cardinality is None or len(names) == obligation.cardinality
        )
        derived_count = explicit_count if explicit_count is not None else (len(names) if names_valid else None)
        count_valid = derived_count is not None and (
            obligation.cardinality is None or derived_count == obligation.cardinality
        )
        mode = obligation.response_mode
        value = (
            3 if mode == "count" and count_valid else
            3 if mode == "names" and names_valid else
            3 if mode == "count_and_names" and count_valid and names_valid else 0
        )
        inventory_subject_score = subject_score
        if inventory_subject_score == 0 and obligation.item_kind == "public_tool" and anchored:
            # ``Docs MCP`` is a domain label rather than text that every
            # canonical inventory sentence must repeat.  A closed public-tool
            # inventory is itself sufficient subject binding; this exception is
            # intentionally limited to the frozen public-tool contract.
            inventory_subject_score = 1
        valid = inventory_subject_score >= 1 and attribute > 0 and value > 0
        reason = "inventory" if valid else "inventory_not_closed_or_not_locally_bound"
        return LocalProof(valid, inventory_subject_score, attribute, value, inventory_subject_score + attribute + value, reason)

    if obligation.kind == "command":
        expected = obligation.expected_value or obligation.subject
        expected_present = _contains_term(expected, text)
        normalized = _normal(text)
        action_binding = bool(
            re.search(rf"\baction\s*=\s*[\"']{re.escape(expected)}[\"']", text, re.I)
            or re.search(rf"\b[A-Za-z_][A-Za-z0-9_]*\s*\([^)]*{re.escape(expected)}", text, re.I | re.S)
            or ("doc-atlas" in normalized and expected.replace("_", " ") in normalized)
        )
        call_shape = bool(re.search(r"\b[A-Za-z_][A-Za-z0-9_]*\s*\(", text) or "doc-atlas" in normalized)
        relation = 3 if expected_present and action_binding and call_shape else 0
        valid = relation > 0 and unit.proposition and unit.source_field is None
        return LocalProof(valid, 3 if expected_present else 0, relation, 3 if call_shape else 0, relation + (3 if expected_present else 0) + (3 if call_shape else 0), "command" if valid else "command_operation_not_locally_bound")

    if obligation.kind == "location":
        if unit.source_field not in {"path_or_url", "path", "source_path"}:
            return LocalProof(False, reason="location_requires_source_field")
        source_identity_text = source_text + "\n" + text
        overlap = _subject_token_overlap(obligation.subject, source_identity_text)
        value = _value_score("path", text)
        valid = overlap > 0 and value > 0
        return LocalProof(valid, min(3, overlap + 1), 3 if overlap else 0, value, overlap + value + 3, "location" if valid else "location_subject_not_bound_to_source")

    if obligation.kind == "status":
        attribute = 2 if _attribute_present("status", text) else 1 if _STATUS_VALUE_RE.search(text) else 0
        value = _value_score("status", text)
        valid = subject_score > 0 and attribute > 0 and value > 0
        return LocalProof(valid, subject_score, attribute, value, subject_score + attribute + value, "status" if valid else "status_subject_not_locally_bound")

    if obligation.kind == "comparison":
        target = 3 if _contains_term(obligation.target, text) else 0
        relation = 3 if _CONTRAST_RE.search(text) else 0
        # Two clauses can establish contrast even without an explicit marker.
        if relation == 0 and subject_score and target and len(re.findall(r"\b(?:returns?|schedules?|creates?|blocks?|awaits?)\b", text, re.I)) >= 2:
            relation = 2
        valid = subject_score > 0 and target > 0 and relation > 0 and unit.proposition
        return LocalProof(valid, subject_score, relation, target, subject_score + relation + target, "comparison" if valid else "comparison_relation_missing")

    if obligation.kind == "behavior":
        planned = planned_behavior_proof(obligation, text, source=source)
        if planned is not None:
            effective_subject_score = max(subject_score, planned.subject_score)
            valid = planned.valid and effective_subject_score > 0
            return LocalProof(
                valid, effective_subject_score, planned.relation_score if valid else 0,
                planned.value_score if valid else 0,
                effective_subject_score + (planned.relation_score if valid else 0) + (planned.value_score if valid else 0),
                planned.reason if valid else f"{planned.reason}_subject_not_bound",
            )
        negated = bool(_NEGATION_RE.search(text))
        relation = 3 if not negated and (
            _subject_before_pattern(obligation.subject, _BEHAVIOR_RE, text)
            or (authoritative_identity and bool(_BEHAVIOR_RE.search(text)))
        ) else 0
        valid = subject_score > 0 and relation > 0 and unit.proposition
        return LocalProof(valid, subject_score, relation, 1 if unit.proposition else 0, subject_score + relation + int(unit.proposition), "behavior" if valid else "behavior_missing_or_negated")

    if obligation.kind == "usage":
        planned = planned_usage_proof(obligation, text, source=source)
        if planned is not None:
            effective_subject_score = max(subject_score, planned.subject_score)
            valid = planned.valid and effective_subject_score > 0
            return LocalProof(
                valid, effective_subject_score, planned.relation_score if valid else 0,
                planned.value_score if valid else 0,
                effective_subject_score + (planned.relation_score if valid else 0) + (planned.value_score if valid else 0),
                planned.reason if valid else f"{planned.reason}_subject_not_bound",
            )
        negated = bool(_NEGATION_RE.search(text))
        subject_pattern = re.escape(_normal(obligation.subject)).replace(r"\ ", r"[\s_]+")
        normalized = _normal(text)
        locally_bound = bool(
            re.search(rf"(?<!\w){subject_pattern}(?!\w)(?:\W+\w+){{0,8}}?\W+{_USAGE_RE.pattern}", normalized, _USAGE_RE.flags)
            or re.search(rf"{_USAGE_RE.pattern}(?:\W+\w+){{0,8}}?\W+(?<!\w){subject_pattern}(?!\w)", normalized, _USAGE_RE.flags)
        )
        relation = 3 if not negated and locally_bound else 0
        valid = subject_score > 0 and relation > 0 and unit.proposition
        return LocalProof(valid, subject_score, relation, 1 if unit.proposition else 0, subject_score + relation + int(unit.proposition), "usage" if valid else "usage_missing_or_negated")

    if obligation.kind == "workflow":
        planned = planned_workflow_proof(obligation, text, source=source)
        if planned is not None:
            effective_subject_score = max(subject_score, planned.subject_score)
            valid = planned.valid and effective_subject_score > 0
            return LocalProof(
                valid, effective_subject_score, planned.relation_score if valid else 0,
                planned.value_score if valid else 0,
                effective_subject_score + (planned.relation_score if valid else 0) + (planned.value_score if valid else 0),
                planned.reason if valid else f"{planned.reason}_subject_not_bound",
            )
        negated = bool(_NEGATION_RE.search(text))
        target_score = 3 if not obligation.target or _contains_term(obligation.target, text) else 0
        sequence = bool(_SEQUENCE_RE.search(text)) or text.count("\n-") + len(re.findall(r"^\s*\d+[.)]\s+", text, re.M)) >= 2
        action_count = len(_ACTION_RE.findall(text))
        relation = 3 if (
            not negated
            and target_score > 0
            and action_count >= 2
            and (sequence or unit.kind in {"unit_group", "heading_context", "code_block"})
        ) else 0
        valid = subject_score > 0 and relation > 0 and unit.proposition and unit.kind in {
            "unit_group", "heading_context", "code_block", "bullet", "sentence", "key_value",
        }
        return LocalProof(valid, subject_score, relation, action_count + target_score, subject_score + relation + action_count + target_score, "workflow" if valid else "workflow_subject_target_or_sequence_missing")

    if obligation.kind == "relation":
        planned = planned_relation_proof(obligation, text, source=source)
        if planned is not None:
            effective_subject_score = max(subject_score, planned.subject_score)
            valid = planned.valid and effective_subject_score > 0
            return LocalProof(
                valid, effective_subject_score, planned.relation_score if valid else 0,
                planned.value_score if valid else 0,
                effective_subject_score + (planned.relation_score if valid else 0) + (planned.value_score if valid else 0),
                planned.reason if valid else f"{planned.reason}_subject_not_bound",
            )
        special_valid = _special_relation_valid(obligation.relation, text)
        target = 2 if not obligation.target or _contains_term(obligation.target, text) else 0
        relation = 3 if special_valid else 0
        if not obligation.relation or obligation.relation == "relation":
            relation = 3 if (_BEHAVIOR_RE.search(text) or _SEQUENCE_RE.search(text) or _CONTRAST_RE.search(text)) else 0
        elif obligation.relation not in {
            "recall_mechanism", "authority_invariant", "request_handling",
            "architecture", "responsiveness",
        }:
            relation = 3 if _contains_term(obligation.relation, text) else 0
        valid = subject_score > 0 and target > 0 and relation > 0 and unit.proposition
        return LocalProof(valid, subject_score, relation, target, subject_score + relation + target, "relation" if valid else f"{obligation.relation or 'relation'}_missing")

    if obligation.kind == "exact_fact":
        relation = 2 if (not obligation.attribute or _attribute_present(obligation.attribute, text)) else 0
        value = _value_score(obligation.value_kind, text)
        if obligation.expected_value:
            value = max(value, 3 if _contains_term(obligation.expected_value, text) else 0)
        valid = subject_score > 0 and relation > 0 and value > 0 and unit.proposition
        return LocalProof(valid, subject_score, relation, value, subject_score + relation + value, "exact_fact" if valid else "exact_fact_missing")

    return LocalProof(False, reason="unsupported_obligation")


def best_local_proof(
    obligation: ProofObligation,
    units: Iterable[AnswerUnit],
    *,
    source: Mapping[str, Any] | None = None,
) -> tuple[AnswerUnit, LocalProof] | None:
    matches: list[tuple[AnswerUnit, LocalProof]] = []
    for unit in units:
        proof = local_proof_for_obligation(obligation, unit, source=source)
        if proof.valid:
            matches.append((unit, proof))
    if not matches:
        return None
    matches.sort(key=lambda pair: (
        -pair[1].completeness_score,
        0 if pair[0].proposition else 1,
        len(pair[0].text),
        pair[0].char_start if pair[0].char_start is not None else 10**9,
        pair[0].unit_id,
    ))
    return matches[0]


__all__ = [
    "ANSWER_UNIT_SCHEMA", "AnswerUnit", "LocalProof", "best_local_proof",
    "extract_answer_units", "local_proof_for_obligation",
]
