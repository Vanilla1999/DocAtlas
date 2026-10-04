# Copyright (c) 2025 Andre Rabold
# SPDX-License-Identifier: MIT
# Adapted GreedySplitter at f2938c47bb8937c650f0d5ddb614f867773b29f4.
# Original source spans replace normalized Markdown concatenation. Existing
# DocAtlas Markdown atomization replaces upstream normalized base splitting.
from docmancer.core.structured_chunking import _atom_spans, parse_markdown_parents


def structural_spans(raw, identity):
    parents = parse_markdown_parents(raw, identity)
    if len(raw) > 262144 or len(parents) > 4096:
        return [], [{'reason': 'source_resource_cap'}]
    units = [(atom.start, atom.end, parent.level, parent.heading_path)
        for parent in parents for atom in _atom_spans(raw, parent.char_start, parent.char_end)]
    spans, current = [], None
    size = lambda a, b: len(raw[a:b].encode('utf-16-le')) // 2
    for start, end, level, path in units:
        if current is not None:
            a, b, old_level, old_path = current
            same = old_path == path or old_path == path[:len(old_path)] or path == old_path[:len(path)]
            split = (size(a, end) > 5000 or
                (size(a, b) >= 500 and level in (1, 2) and not same) or
                (size(a, end) > 1500 and size(a, b) >= 500 and size(start, end) >= 500))
            if split:
                spans.append((a, b))
                current = None
            else:
                if old_path == path[:len(old_path)]:
                    merged_path = path
                elif path == old_path[:len(path)]:
                    merged_path = old_path
                else:
                    merged_path = tuple(x for i, x in enumerate(old_path) if i < len(path) and old_path[:i+1] == path[:i+1])
                current = (a, end, min(old_level, level), merged_path)
                continue
        current = (start, end, level, path)
    if current is not None:
        spans.append(current[:2])
    # Preserve whole structural units; an oversized atom is omitted, never cut.
    omissions = [{'span': [a, b], 'reason': 'structural_hard_max'} for a, b in spans if size(a, b) > 5000]
    return [(a, b) for a, b in spans if size(a, b) <= 5000], omissions
