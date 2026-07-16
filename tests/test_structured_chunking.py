from __future__ import annotations

from docmancer.core.structured_chunking import (
    ChunkingConfig,
    chunk_markdown_parent_child,
    estimate_utf8_tokens,
    parse_markdown_parents,
    stable_sqlite_id,
)


def test_parents_ignore_headings_inside_fences_and_preserve_exact_spans():
    source = "Пролог\n\n# API\n\n```md\n# not a heading\n```\n\n## Calls\nТекст.\n"
    parents = parse_markdown_parents(source, "docs/api.md")

    assert [parent.title for parent in parents] == ["Introduction", "API", "Calls"]
    assert parents[-1].heading_path == ("API", "Calls")
    for parent in parents:
        assert source[parent.char_start:parent.char_end] == parent.display_text
        assert source.encode("utf-8")[parent.byte_start:parent.byte_end].decode("utf-8") == parent.display_text
        assert parent.line_start >= 1
        assert parent.line_end >= parent.line_start


def test_children_are_exact_non_overlapping_source_projection():
    source = (
        "# Rules\n\nLead paragraph.\n\n"
        "- first rule\n- second rule\n\n"
        "| key | value |\n| --- | --- |\n| a | one |\n| b | two |\n\n"
        "```python\nprint('x')\nprint('y')\n```\n"
    )
    parents, children = chunk_markdown_parent_child(
        source, "policy.md", ChunkingConfig(target_tokens=24, hard_max_tokens=48)
    )

    assert len(parents) == 1
    assert len(children) > 1
    assert "".join(child.display_text for child in children) == source
    assert all(source[c.char_start:c.char_end] == c.display_text for c in children)
    assert all(c.display_text in c.retrieval_text for c in children)
    assert all(c.byte_end > c.byte_start for c in children)
    assert all(left.char_end == right.char_start for left, right in zip(children, children[1:]))


def test_short_parent_packs_prose_and_code_without_projection_overhead():
    source = (
        "# API\n\nWidgetClient.fetch_record accepts a timeout.\n\n"
        "```python\nWidgetClient().fetch_record(record_id='r-7', timeout=5)\n```\n"
    )
    _, children = chunk_markdown_parent_child(source, "api.md", ChunkingConfig())

    assert len(children) == 1
    assert children[0].display_text == source
    assert children[0].atom_type == "mixed"
    assert estimate_utf8_tokens(children[0].retrieval_text) <= 160


def test_local_edit_keeps_unaffected_parent_and_child_ids():
    before = "# Alpha\n\nunchanged fact\n\n# Beta\n\nold fact\n"
    after = "# Alpha\n\nunchanged fact\n\n# Beta\n\nnew fact\n"
    parents_before, children_before = chunk_markdown_parent_child(before, "guide.md")
    parents_after, children_after = chunk_markdown_parent_child(after, "guide.md")

    assert parents_before[0].logical_id == parents_after[0].logical_id
    assert parents_before[0].revision_id == parents_after[0].revision_id
    assert children_before[0].stable_id == children_after[0].stable_id
    assert parents_before[1].logical_id == parents_after[1].logical_id
    assert parents_before[1].revision_id != parents_after[1].revision_id
    assert children_before[1].stable_id != children_after[1].stable_id
    assert children_before[0].source_content_hash != children_after[0].source_content_hash


def test_headingless_repeated_and_nested_headings_have_distinct_parents():
    source = "plain\n\n# Same\none\n\n## Nested\ntwo\n\n# Same\nthree\n"
    parents = parse_markdown_parents(source, "repeat.md")

    assert [p.title for p in parents] == ["Introduction", "Same", "Nested", "Same"]
    assert parents[2].heading_levels == (1, 2)
    assert parents[1].logical_id != parents[3].logical_id


def test_unicode_grid_is_deterministic_and_within_hard_limit():
    source = "# Русский\n\n" + "данные значение правило\n" * 180
    for target in (160, 256, 384, 512):
        config = ChunkingConfig(target_tokens=target, hard_max_tokens=max(512, target))
        first = chunk_markdown_parent_child(source, "ru.md", config)[1]
        second = chunk_markdown_parent_child(source, "ru.md", config)[1]
        assert [c.stable_id for c in first] == [c.stable_id for c in second]
        assert "".join(c.display_text for c in first) == source
        prefix_tokens = estimate_utf8_tokens(first[0].retrieval_text) - estimate_utf8_tokens(first[0].display_text)
        assert all(c.token_estimate + prefix_tokens <= config.hard_max_tokens + 1 for c in first)


def test_stable_sqlite_id_is_nonzero_signed_63_bit():
    value = stable_sqlite_id("child-example")
    assert 0 < value < 2**63


def test_split_code_fragments_get_retrieval_only_valid_fences():
    source = "# Code\n\n```python\n" + "\n".join(f"value_{i} = {i}" for i in range(100)) + "\n```\n"
    _, children = chunk_markdown_parent_child(
        source, "code.md", ChunkingConfig(target_tokens=24, hard_max_tokens=48)
    )
    code_children = [child for child in children if "value_" in child.display_text]
    assert len(code_children) > 2
    assert all(child.retrieval_text.count("```") >= 2 for child in code_children)
    assert all(source[child.char_start:child.char_end] == child.display_text for child in code_children)
