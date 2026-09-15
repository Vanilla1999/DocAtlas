"""Source-local structural alternatives for bounded documentation projection.

This module only enumerates exact spans inside an already authorized retrieval
extent. It performs no retrieval, rendering, source I/O or answer grading.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from docmancer.core.structured_chunking import _atom_spans

MAX_BLOCKS = 4096
MAX_ALTERNATIVES = 4096
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})([^\n]*)")
_ITEM = re.compile(r"^( {0,3})(?:[-+*]|\d+[.)])[ \t]+", re.M)
_TABLE_SEPARATOR = re.compile(
    r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$"
)
_UNSUPPORTED_LINE = re.compile(r"^\s*(?:!!!|\?\?\?|===|<[/!A-Za-z])")


@dataclass(frozen=True, slots=True)
class BlockAlternatives:
    spans: tuple[tuple[int, int], ...]
    limitations: tuple[str, ...] = ()


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _closed_fence(value: str) -> bool:
    lines = value.splitlines()
    if len(lines) < 2:
        return False
    opening = _FENCE.match(lines[0])
    if opening is None:
        return False
    marker = opening[1]
    return bool(re.fullmatch(
        r" {0,3}" + re.escape(marker[0]) + "{" + str(len(marker)) + r",}[ \t]*",
        lines[-1],
    ))


def _supported(value: str, kind: str) -> bool:
    if kind == "code":
        return _closed_fence(value)
    if kind == "table":
        lines = value.splitlines()
        return len(lines) >= 2 and bool(_TABLE_SEPARATOR.fullmatch(lines[1]))
    return not any(_UNSUPPORTED_LINE.match(line) for line in value.splitlines())


def source_block_alternatives(text: str) -> BlockAlternatives:
    """Return complete exact block spans without a per-quote character cap.

    Work caps limit enumeration only. Content size is decided later by the
    existing complete-payload admission counter.
    """
    atoms = _atom_spans(text, 0, len(text))
    if len(atoms) > MAX_BLOCKS:
        return BlockAlternatives((), ("block_work_limited",))

    spans: set[tuple[int, int]] = set()
    roots: list[tuple[int, int, str, int]] = []
    limitations: set[str] = set()
    section = 0

    for atom in atoms:
        start, end = _trim(text, atom.start, atom.end)
        if start >= end:
            continue
        value = text[start:end]
        kind = atom.atom_type
        if kind == "heading":
            section += 1
        if not _supported(value, kind):
            limitations.add("structure_unverified")
            roots.append((start, end, "unsupported", section))
            continue

        roots.append((start, end, kind, section))
        if kind != "heading":
            spans.add((start, end))

        if kind == "list":
            items = list(_ITEM.finditer(value))
            if items:
                outer_indent = min(len(item[1]) for item in items)
                items = [item for item in items if len(item[1]) == outer_indent]
                # If an introduction is merged into the list atom, expose the
                # complete list itself in addition to the intro+list block.
                spans.add((start + items[0].start(), end))
                for index, item in enumerate(items):
                    item_end = (
                        start + items[index + 1].start()
                        if index + 1 < len(items) else end
                    )
                    item_span = _trim(text, start + item.start(), item_end)
                    if item_span[0] < item_span[1]:
                        spans.add(item_span)

        if len(spans) > MAX_ALTERNATIVES:
            return BlockAlternatives((), ("block_work_limited",))

    # A short lead-in can be a dependency of the immediately following
    # structured block. Arbitrary unions of all paragraphs in a section are not
    # semantic blocks: they inflate candidates and join unrelated evidence.
    for left, right in zip(roots, roots[1:]):
        start, intro_end, kind, section = left
        _, end, following_kind, following_section = right
        if (kind == "prose" and section == following_section
                and following_kind in {"code", "list", "table"}
                and text[start:intro_end].rstrip().endswith(":")):
            spans.add((start, end))
        if len(spans) > MAX_ALTERNATIVES:
            return BlockAlternatives((), ("block_work_limited",))

    return BlockAlternatives(
        tuple(sorted(spans, key=lambda span: (span[1] - span[0], span[0]))),
        tuple(sorted(limitations)),
    )


def inline_command_literals(text: str) -> frozenset[str]:
    """Return visible inline invocations/options that re-slicing must retain.

    Ordinary prose and single identifier aliases are not commands. Keeping a
    command does not certify an answer; this only prevents a selected operation
    from silently becoming a different operation with similar topical words.
    """
    return frozenset(
        match.group(0) for match in re.finditer(r"(?<!`)`([^`\n]+)`(?!`)", text)
        if re.match(r"^(?:--[\w-]+(?:[=\s].*)?|[\w./-]+\s+\S.*)$", match.group(1))
    )
