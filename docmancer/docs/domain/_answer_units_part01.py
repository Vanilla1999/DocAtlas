"""Implementation shard 1 for answer_units."""
from __future__ import annotations

from ._answer_units_shared import *  # noqa: F401,F403

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

__all__=['_normal', '_bounded_text', 'AnswerUnit', 'materialize_answer_units', 'LocalProof', '_make_unit', '_make_source_field_unit', 'extract_answer_units', '_obligation_technical_term', '_contains_term', '_subject_spans', '_subject_present', '_bounded_clauses', '_word_distance', '_purpose_clause', '_context_score', '_predicate_has_object', '_positive_relation_match', '_positive_relation', '_effect_relation_valid']
