"""Versioned, span-preserving Markdown parent/child chunking.

Retrieval text may contain deterministic heading context.  Display text is
always an exact slice of the source snapshot and is the only text delivered as
evidence.
"""
from __future__ import annotations

import bisect
import hashlib
import json
import re
import uuid
from dataclasses import dataclass


SCHEMA_VERSION = "parent-child-v1"
TOKEN_ESTIMATOR_VERSION = "utf8-bytes-div4-v1"
_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*\r?\n?$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_LIST = re.compile(r"^[ \t]*(?:[-+*]|\d+[.)])[ \t]+")


def estimate_utf8_tokens(text: str) -> int:
    """Deterministic engineering estimate, never provider token usage."""
    return max(1, (len(text.encode("utf-8")) + 3) // 4)


def _digest(*parts: str) -> str:
    payload = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def stable_sqlite_id(stable_id: str) -> int:
    value = int.from_bytes(hashlib.sha256(stable_id.encode("utf-8")).digest()[:8], "big")
    return (value & ((1 << 63) - 1)) or 1


def stable_vector_id(stable_id: str) -> str:
    """Return the backend-portable deterministic UUID for a child identity."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"docatlas:{SCHEMA_VERSION}:{stable_id}"))


@dataclass(frozen=True, slots=True)
class ChunkingConfig:
    target_tokens: int = 160
    hard_max_tokens: int = 512
    overlap_tokens: int = 0
    schema_version: str = SCHEMA_VERSION
    estimator_version: str = TOKEN_ESTIMATOR_VERSION

    def __post_init__(self) -> None:
        if self.target_tokens < 1:
            raise ValueError("target_tokens must be positive")
        if self.hard_max_tokens < self.target_tokens:
            raise ValueError("hard_max_tokens must be >= target_tokens")
        if self.overlap_tokens != 0:
            raise ValueError("parent-child-v1 supports zero visible overlap only")

    @property
    def config_hash(self) -> str:
        return _digest(
            self.schema_version,
            self.estimator_version,
            str(self.target_tokens),
            str(self.hard_max_tokens),
            str(self.overlap_tokens),
        )


@dataclass(frozen=True, slots=True)
class ParentSection:
    logical_id: str
    revision_id: str
    source_identity: str
    source_content_hash: str
    title: str
    level: int
    heading_path: tuple[str, ...]
    heading_levels: tuple[int, ...]
    occurrence: int
    char_start: int
    char_end: int
    byte_start: int
    byte_end: int
    line_start: int
    line_end: int
    display_text: str


@dataclass(frozen=True, slots=True)
class RetrievalChild:
    stable_id: str
    sqlite_id: int
    vector_id: str
    parent_logical_id: str
    source_identity: str
    source_content_hash: str
    ordinal: int
    duplicate_occurrence: int
    atom_type: str
    atom_id: str
    char_start: int
    char_end: int
    byte_start: int
    byte_end: int
    line_start: int
    line_end: int
    display_text: str
    retrieval_text: str
    token_estimate: int
    retrieval_token_estimate: int
    config_hash: str
    estimator_version: str


def _line_offsets(content: str) -> tuple[list[str], list[int]]:
    lines = content.splitlines(keepends=True)
    if not lines and content:
        lines = [content]
    offsets: list[int] = []
    cursor = 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line)
    offsets.append(cursor)
    return lines, offsets


def _span_values(content: str, line_offsets: list[int], start: int, end: int) -> tuple[int, int, int, int]:
    byte_start = len(content[:start].encode("utf-8"))
    byte_end = byte_start + len(content[start:end].encode("utf-8"))
    line_start = bisect.bisect_right(line_offsets, start)
    line_end = max(line_start, bisect.bisect_left(line_offsets, end))
    return byte_start, byte_end, line_start, line_end


def parse_markdown_parents(content: str, source_identity: str) -> list[ParentSection]:
    """Return heading-scoped authoritative parents with exact source spans."""
    if not content:
        return []
    lines, offsets = _line_offsets(content)
    headings: list[tuple[int, int, str]] = []
    open_fence: tuple[str, int] | None = None
    for index, line in enumerate(lines):
        fence = _FENCE.match(line)
        if fence:
            marker = fence.group(1)
            kind = marker[0]
            if open_fence is None:
                open_fence = (kind, len(marker))
            elif kind == open_fence[0] and len(marker) >= open_fence[1]:
                open_fence = None
            continue
        if open_fence is None:
            match = _HEADING.match(line)
            if match:
                headings.append((index, len(match.group(1)), match.group(2).strip()))

    ranges: list[tuple[int, int, str, int, tuple[str, ...], tuple[int, ...], int]] = []
    stack: list[tuple[int, str]] = []
    occurrences: dict[tuple[tuple[int, str], ...], int] = {}
    if not headings:
        ranges.append((0, len(content), "Document", 0, (), (), 1))
    else:
        if offsets[headings[0][0]] > 0:
            ranges.append((0, offsets[headings[0][0]], "Introduction", 0, (), (), 1))
        for position, (line_index, level, title) in enumerate(headings):
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            key = tuple(stack)
            occurrences[key] = occurrences.get(key, 0) + 1
            end = offsets[headings[position + 1][0]] if position + 1 < len(headings) else len(content)
            ranges.append(
                (
                    offsets[line_index], end, title, level,
                    tuple(item[1] for item in stack), tuple(item[0] for item in stack),
                    occurrences[key],
                )
            )

    source_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    parents: list[ParentSection] = []
    for start, end, title, level, path, levels, occurrence in ranges:
        display = content[start:end]
        if not display:
            continue
        logical_id = "parent-" + _digest(
            SCHEMA_VERSION, source_identity, json.dumps(path, ensure_ascii=False),
            json.dumps(levels), str(occurrence),
        )[:32]
        byte_start, byte_end, line_start, line_end = _span_values(content, offsets, start, end)
        parents.append(
            ParentSection(
                logical_id=logical_id,
                revision_id="parent-rev-" + _digest(logical_id, hashlib.sha256(display.encode("utf-8")).hexdigest())[:32],
                source_identity=source_identity,
                source_content_hash=source_hash,
                title=title,
                level=level,
                heading_path=path,
                heading_levels=levels,
                occurrence=occurrence,
                char_start=start,
                char_end=end,
                byte_start=byte_start,
                byte_end=byte_end,
                line_start=line_start,
                line_end=line_end,
                display_text=display,
            )
        )
    return parents


@dataclass(frozen=True, slots=True)
class _AtomSpan:
    start: int
    end: int
    atom_type: str


def _atom_spans(content: str, start: int, end: int) -> list[_AtomSpan]:
    """Split a parent at Markdown block boundaries without changing text."""
    relative = content[start:end]
    lines, offsets = _line_offsets(relative)
    spans: list[_AtomSpan] = []
    i = 0
    while i < len(lines):
        block_start = i
        fence = _FENCE.match(lines[i])
        if fence:
            atom_type = "code"
            marker = fence.group(1)
            i += 1
            while i < len(lines):
                closing = _FENCE.match(lines[i])
                i += 1
                if closing and closing.group(1)[0] == marker[0] and len(closing.group(1)) >= len(marker):
                    break
        elif lines[i].lstrip().startswith("|"):
            atom_type = "table"
            i += 1
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                i += 1
        elif _LIST.match(lines[i]):
            atom_type = "list"
            i += 1
            while i < len(lines) and (_LIST.match(lines[i]) or lines[i].startswith((" ", "\t"))):
                i += 1
        elif not lines[i].strip():
            atom_type = "whitespace"
            i += 1
        else:
            atom_type = "heading" if _HEADING.match(lines[i]) else "prose"
            i += 1
            while i < len(lines) and lines[i].strip() and not _FENCE.match(lines[i]) and not _LIST.match(lines[i]) and not lines[i].lstrip().startswith("|"):
                i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        atom_start = start + offsets[block_start]
        atom_end = start + offsets[i]
        if atom_end > atom_start:
            spans.append(_AtomSpan(atom_start, atom_end, atom_type))
    return spans


def _bounded_prefix(source_identity: str, heading_path: tuple[str, ...]) -> str:
    source = source_identity[-240:]
    prefix = "Document: " + source
    if heading_path:
        bounded = " > ".join(part[:160] for part in heading_path)
        prefix += "\nHeading: " + bounded[-480:]
    return prefix + "\n\n"


def _retrieval_fragment(content: str, start: int, end: int) -> str:
    """Add retrieval-only Markdown wrappers for split code/table atoms."""
    lines, offsets = _line_offsets(content)
    open_fence: tuple[int, str, str] | None = None
    for index, line in enumerate(lines):
        fence = _FENCE.match(line)
        if fence:
            marker = fence.group(1)
            if open_fence is None:
                open_fence = (index, line, marker)
            elif marker[0] == open_fence[2][0] and len(marker) >= len(open_fence[2]):
                region_start = offsets[open_fence[0]]
                region_end = offsets[index + 1]
                if start < region_end and end > region_start:
                    fragment = content[start:end]
                    if start > region_start:
                        fragment = open_fence[1] + fragment
                    if end < region_end:
                        fragment = fragment.rstrip("\r\n") + "\n" + open_fence[2] + "\n"
                    return fragment
                open_fence = None

    start_line = max(0, bisect.bisect_right(offsets, start) - 1)
    if start_line < len(lines) and lines[start_line].lstrip().startswith("|"):
        table_start = start_line
        while table_start > 0 and lines[table_start - 1].lstrip().startswith("|"):
            table_start -= 1
        if start_line > table_start and table_start + 1 < len(lines):
            header = lines[table_start] + lines[table_start + 1]
            if not content[start:end].startswith(header):
                return header + content[start:end]
    return content[start:end]


def _split_oversized(content: str, span: tuple[int, int], limit_tokens: int) -> list[tuple[int, int]]:
    start, end = span
    if estimate_utf8_tokens(content[start:end]) <= limit_tokens:
        return [span]
    lines, offsets = _line_offsets(content[start:end])
    result: list[tuple[int, int]] = []
    cursor = 0
    while cursor < len(lines):
        group_start = offsets[cursor]
        group_end = offsets[cursor + 1]
        cursor += 1
        while cursor < len(lines):
            candidate_end = offsets[cursor + 1]
            if estimate_utf8_tokens(content[start + group_start:start + candidate_end]) > limit_tokens:
                break
            group_end = candidate_end
            cursor += 1
        # A single pathological line still needs an exact UTF-8-safe split.
        if estimate_utf8_tokens(content[start + group_start:start + group_end]) > limit_tokens:
            absolute = start + group_start
            while absolute < start + group_end:
                boundary = absolute
                byte_count = 0
                while boundary < start + group_end:
                    char_bytes = len(content[boundary].encode("utf-8"))
                    if byte_count and byte_count + char_bytes > limit_tokens * 4:
                        break
                    byte_count += char_bytes
                    boundary += 1
                if boundary < start + group_end:
                    floor = absolute + max(1, (boundary - absolute) // 2)
                    preferred = boundary
                    while preferred > floor and content[preferred - 1] not in " \t.!?;,:\n":
                        preferred -= 1
                    if preferred > floor:
                        boundary = preferred
                result.append((absolute, boundary))
                absolute = boundary
        else:
            result.append((start + group_start, start + group_end))
    return result


def _fit_retrieval_spans(
    content: str,
    span: tuple[int, int],
    prefix: str,
    hard_max_tokens: int,
) -> list[tuple[int, int]]:
    """Split until retrieval-only wrappers also fit the hard ceiling."""
    queue = [span]
    fitted: list[tuple[int, int]] = []
    while queue:
        start, end = queue.pop(0)
        display = content[start:end]
        retrieval = prefix + _retrieval_fragment(content, start, end)
        if estimate_utf8_tokens(retrieval) <= hard_max_tokens:
            fitted.append((start, end))
            continue
        overhead = max(
            0, estimate_utf8_tokens(retrieval) - estimate_utf8_tokens(display)
        )
        body_limit = max(1, hard_max_tokens - overhead - 1)
        pieces = _split_oversized(content, (start, end), body_limit)
        if pieces == [(start, end)]:
            raise ValueError(
                "retrieval-only context exceeds hard_max_tokens even for the "
                f"smallest source span: {estimate_utf8_tokens(retrieval)} > "
                f"{hard_max_tokens}"
            )
        queue[0:0] = pieces
    return fitted


def chunk_markdown_parent_child(
    content: str,
    source_identity: str,
    config: ChunkingConfig | None = None,
) -> tuple[list[ParentSection], list[RetrievalChild]]:
    config = config or ChunkingConfig()
    parents = parse_markdown_parents(content, source_identity)
    _, line_offsets = _line_offsets(content)
    children: list[RetrievalChild] = []
    seen_sql_ids: dict[int, str] = {}
    for parent in parents:
        prefix = _bounded_prefix(source_identity, parent.heading_path)
        prefix_tokens = estimate_utf8_tokens(prefix)
        hard_body = max(1, config.hard_max_tokens - prefix_tokens)
        target_body = max(1, config.target_tokens - prefix_tokens)
        atoms: list[tuple[int, int, str, str]] = []
        atom_occurrences: dict[tuple[str, str], int] = {}
        for atom in _atom_spans(content, parent.char_start, parent.char_end):
            atom_hash = hashlib.sha256(content[atom.start:atom.end].encode("utf-8")).hexdigest()
            occurrence_key = (atom.atom_type, atom_hash)
            atom_occurrences[occurrence_key] = atom_occurrences.get(occurrence_key, 0) + 1
            atom_id = "atom-" + _digest(
                parent.logical_id, atom.atom_type, atom_hash,
                str(atom_occurrences[occurrence_key]),
            )[:32]
            if estimate_utf8_tokens(content[atom.start:atom.end]) > hard_body:
                atoms.extend(
                    (start, end, atom.atom_type, atom_id)
                    for start, end in _split_oversized(
                        content, (atom.start, atom.end), target_body
                    )
                )
            else:
                atoms.append((atom.start, atom.end, atom.atom_type, atom_id))

        packed: list[tuple[int, int, str, str]] = []
        for atom_start, atom_end, atom_type, atom_id in atoms:
            can_merge = (
                packed
                and estimate_utf8_tokens(prefix + content[packed[-1][0]:atom_end])
                    <= config.target_tokens
            )
            if can_merge:
                previous = packed[-1]
                merged_type = previous[2] if previous[2] == atom_type else "mixed"
                merged_atom_id = "atom-" + _digest(previous[3], atom_id)[:32]
                packed[-1] = (previous[0], atom_end, merged_type, merged_atom_id)
            else:
                packed.append((atom_start, atom_end, atom_type, atom_id))

        fitted: list[tuple[int, int, str, str]] = []
        for start, end, atom_type, atom_id in packed:
            fitted.extend(
                (part_start, part_end, atom_type, atom_id)
                for part_start, part_end in _fit_retrieval_spans(
                    content, (start, end), prefix, config.hard_max_tokens
                )
            )
        packed = fitted

        duplicate_counts: dict[str, int] = {}
        for ordinal, (start, end, atom_type, atom_id) in enumerate(packed):
            display = content[start:end]
            display_hash = hashlib.sha256(display.encode("utf-8")).hexdigest()
            duplicate_counts[display_hash] = duplicate_counts.get(display_hash, 0) + 1
            duplicate_occurrence = duplicate_counts[display_hash]
            stable_id = "child-" + _digest(
                parent.logical_id, config.config_hash, display_hash, str(duplicate_occurrence)
            )[:40]
            sqlite_id = stable_sqlite_id(stable_id)
            prior = seen_sql_ids.get(sqlite_id)
            if prior is not None and prior != stable_id:
                raise ValueError(f"stable chunk id collision: {prior} and {stable_id}")
            seen_sql_ids[sqlite_id] = stable_id
            byte_start, byte_end, line_start, line_end = _span_values(content, line_offsets, start, end)
            retrieval = prefix + _retrieval_fragment(content, start, end)
            retrieval_tokens = estimate_utf8_tokens(retrieval)
            if retrieval_tokens > config.hard_max_tokens:
                raise ValueError(
                    "retrieval_text exceeds hard_max_tokens after bounded context: "
                    f"{retrieval_tokens} > {config.hard_max_tokens}"
                )
            children.append(
                RetrievalChild(
                    stable_id=stable_id,
                    sqlite_id=sqlite_id,
                    vector_id=stable_vector_id(stable_id),
                    parent_logical_id=parent.logical_id,
                    source_identity=source_identity,
                    source_content_hash=parent.source_content_hash,
                    ordinal=ordinal,
                    duplicate_occurrence=duplicate_occurrence,
                    atom_type=atom_type,
                    atom_id=atom_id,
                    char_start=start,
                    char_end=end,
                    byte_start=byte_start,
                    byte_end=byte_end,
                    line_start=line_start,
                    line_end=line_end,
                    display_text=display,
                    retrieval_text=retrieval,
                    token_estimate=estimate_utf8_tokens(display),
                    retrieval_token_estimate=retrieval_tokens,
                    config_hash=config.config_hash,
                    estimator_version=config.estimator_version,
                )
            )
    return parents, children
