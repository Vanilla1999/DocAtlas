from __future__ import annotations

from docmancer.docs.section_metadata import extract_markdown_section_metadata


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
