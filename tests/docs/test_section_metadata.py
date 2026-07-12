from __future__ import annotations

import json

from docmancer.docs.section_metadata import (
    SECTION_METADATA_MAX_JSON_BYTES,
    extract_markdown_section_metadata,
    extract_section_metadata_result,
)


def _extract(text: str) -> list[dict[str, object]]:
    return extract_markdown_section_metadata(text, source_document_path="README.md")


def test_fenced_code_headings_do_not_create_sections() -> None:
    sections = _extract(
        """# Setup

```bash
# not a documentation heading
packages/auth/src/token_service.ts
```
"""
    )

    assert [item["heading_path"] for item in sections] == [["Setup"]]
    assert sections[0]["mentioned_paths"] == ["packages/auth/src/token_service.ts"]


def test_tilde_fence_with_longer_closer_is_respected() -> None:
    sections = _extract("# Setup\n~~~~text\n# fake\n~~~~~\n## Real\n")

    assert [item["heading_path"] for item in sections] == [["Setup"], ["Setup", "Real"]]


def test_paths_are_normalized_and_sentence_punctuation_is_excluded() -> None:
    sections = _extract(
        "# Paths\nUse ./src/auth.py, packages\\auth\\token.ts, and web/session.ts.\n"
    )

    assert sections[0]["mentioned_paths"] == ["src/auth.py", "packages/auth/token.ts", "web/session.ts"]


def test_external_urls_are_not_repository_path_evidence() -> None:
    sections = _extract("# Links\nSee https://github.com/example/project/docs/guide.md.\n")

    assert sections[0]["mentioned_paths"] == []


def test_hyphenated_config_keys_are_explicit_symbols() -> None:
    sections = _extract("# Config\nSet `auth.token-ttl` explicitly.\n")

    assert sections[0]["mentioned_symbols"] == ["auth.token-ttl"]


def test_reference_limit_is_reported_in_metadata() -> None:
    sections = _extract("# API\n" + " ".join(f"`Symbol{i:02}`" for i in range(65)) + "\n")

    assert len(sections[0]["mentioned_symbols"]) == 64
    assert sections[0]["symbols_truncated"] is True
    assert sections[0]["paths_truncated"] is False


def test_section_limit_is_reported_in_metadata() -> None:
    sections = _extract("\n".join(f"# Section {index}\ntext" for index in range(257)) + "\n")

    assert len(sections) == 256
    assert all(section["document_sections_truncated"] is True for section in sections)


def test_oversized_heading_is_bounded_and_reported() -> None:
    sections = _extract("# " + "x" * 1000 + "\ntext\n")

    assert len(sections[0]["heading_path"][0]) == 512
    assert sections[0]["fields_truncated"] is True


def test_headingless_markdown_is_an_intro_section(tmp_path) -> None:
    path = tmp_path / "guide.md"
    path.write_text("Use `issue_token` before continuing.\n", encoding="utf-8")

    result = extract_section_metadata_result(path, source_document_path="guide.md")

    assert result.status == "parsed"
    assert result.sections[0]["heading_path"] == []
    assert result.sections[0]["mentioned_symbols"] == ["issue_token"]


def test_empty_unsupported_and_read_error_are_distinct(tmp_path) -> None:
    empty = tmp_path / "empty.md"
    unsupported = tmp_path / "guide.rst"
    invalid = tmp_path / "invalid.md"
    empty.write_text(" \n", encoding="utf-8")
    unsupported.write_text("Guide", encoding="utf-8")
    invalid.write_bytes(b"# Invalid\n\xff")

    assert extract_section_metadata_result(empty, source_document_path="empty.md").status == "empty"
    assert extract_section_metadata_result(unsupported, source_document_path="guide.rst").status == "unsupported"
    assert extract_section_metadata_result(invalid, source_document_path="invalid.md").status == "read_error"


def test_total_section_metadata_size_is_bounded_and_explicit() -> None:
    parts: list[str] = []
    for section in range(256):
        references = " ".join(
            f"docs/s{section:03}r{reference:02}_{'x' * 180}.md"
            for reference in range(64)
        )
        parts.append(f"# Section {section}\n{references}")

    sections = _extract("\n".join(parts))
    serialized = len(json.dumps(sections, ensure_ascii=False).encode("utf-8"))

    assert serialized <= SECTION_METADATA_MAX_JSON_BYTES
    assert sections
    assert all(section["document_sections_truncated"] is True for section in sections)
