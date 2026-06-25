from __future__ import annotations

from docmancer.docs.domain.snippets import (
    build_snippet_presentation,
    clean_snippet_title,
    clean_surrounding_context,
    extract_snippet_candidates,
    normalize_code_for_dedupe,
)
from docmancer.docs.models import DocsChunk


def chunk(title, content, metadata=None, source="https://example.com/docs"):
    return DocsChunk(title=title, content=content, source=source, url=source, metadata=metadata or {})


def test_extracts_metadata_code_snippets():
    item = chunk("Depends", "prose", {"code_snippets": [{"language": "python", "code": "from fastapi import Depends\nDepends()"}]})
    candidates = extract_snippet_candidates(item, origin_lane="library", question="FastAPI Depends example")
    assert candidates[0].language == "python"
    assert "Depends" in candidates[0].code


def test_falls_back_to_fenced_code_block():
    item = chunk("Click", "```python\n@click.group()\ndef cli():\n    pass\n```")
    presentation = build_snippet_presentation([item], question="Click command group example", response_style="snippet-first")
    assert presentation.primary_snippet["language"] == "python"
    assert "@click.group" in presentation.primary_snippet["code"]


def test_does_not_treat_prose_as_code():
    item = chunk("Prose", "This section explains architecture without an example.")
    assert extract_snippet_candidates(item, origin_lane="project", question="architecture") == []


def test_preserves_code_indentation_comments_and_decorators():
    code = "# keep comment\n@app.get('/')\ndef read():\n    return {'ok': True}"
    item = chunk("FastAPI", "prose", {"code_snippets": [{"language": "python", "code": code}]})
    primary = build_snippet_presentation([item], question="FastAPI decorator example", response_style="snippet-first").primary_snippet
    assert primary["code"] == code


def test_depends_query_selects_depends_snippet_not_unrelated_async_example():
    unrelated = chunk("Async", "```python\nasync def lifespan(app):\n    yield\n```", source="https://fastapi.tiangolo.com/advanced/events/")
    depends = chunk("Dependencies", "```python\nfrom fastapi import Depends\n\ndef read(item = Depends(get_item)):\n    return item\n```", source="https://fastapi.tiangolo.com/tutorial/dependencies/")
    primary = build_snippet_presentation([unrelated, depends], question="How do I use FastAPI Depends?", response_style="auto").primary_snippet
    assert "Depends" in primary["code"]
    assert "dependencies" in primary["source"]


def test_click_group_query_selects_click_group_snippet():
    item = chunk("Groups", "```python\nimport click\n\n@click.group()\ndef cli():\n    pass\n```")
    primary = build_snippet_presentation([item], question="Show a Click command group example", response_style="auto").primary_snippet
    assert "@click.group" in primary["code"]


def test_riverpod_autodispose_selects_relevant_dart_snippet():
    item = chunk("autoDispose", "```dart\nfinal userProvider = FutureProvider.autoDispose((ref) async {\n  ref.keepAlive();\n});\n```")
    primary = build_snippet_presentation([item], question="Riverpod autoDispose example", response_style="auto").primary_snippet
    assert primary["language"] == "dart"
    assert "autoDispose" in primary["code"]


def test_flutter_bloc_selects_blocprovider_snippet():
    item = chunk("BlocProvider", "```dart\nBlocProvider(create: (_) => CounterCubit(), child: CounterView())\n```")
    primary = build_snippet_presentation([item], question="flutter_bloc BlocProvider example", response_style="auto").primary_snippet
    assert "BlocProvider" in primary["code"]


def test_anyhow_context_selects_context_snippet():
    item = chunk("Context", "```rust\nuse anyhow::{Context, Result};\nlet value = read().with_context(|| \"read failed\")?;\n```")
    primary = build_snippet_presentation([item], question="How do I wrap an error with anyhow Context?", response_style="auto").primary_snippet
    assert primary["language"] == "rust"
    assert "with_context" in primary["code"]


def test_exact_version_snippet_outranks_latest_fallback():
    latest = chunk("Context latest", "```rust\nuse anyhow::Result;\n```", {"version": "latest", "requested_version": "1.0.86", "exact_version_match": False})
    exact = chunk("Context exact", "```rust\nuse anyhow::{Context, Result};\nread().context(\"failed\")?;\n```", {"version": "1.0.86", "requested_version": "1.0.86", "exact_version_match": True})
    primary = build_snippet_presentation([latest, exact], question="anyhow Context", response_style="snippet-first").primary_snippet
    assert primary["version"] == "1.0.86"
    assert primary["exact_version_match"] is True


def test_identical_snippets_are_deduplicated():
    code = "```python\nprint('x')\n```"
    first = chunk("A", code, source="https://example.com/a")
    second = chunk("B", code, source="https://example.com/b")
    presentation = build_snippet_presentation([first, second], question="python print example", response_style="snippet-first")
    assert presentation.metrics["duplicates_dropped"] == 1


def test_max_one_supporting_snippet_per_source():
    first = chunk("One", "```python\nprint('one')\n```")
    second = chunk("Two", "```python\nprint('two')\n```")
    presentation = build_snippet_presentation([first, second], question="python print example", response_style="snippet-first")
    assert presentation.metrics["supporting_selected"] == 0


def test_cleaning_does_not_change_code_symbols():
    assert clean_snippet_title("Usage [¶] Copy") == "Usage"
    assert "Copy" not in clean_surrounding_context("Intro\nCopy\nBody")
    code = "# comment\n@decorator\nprint('✅')"
    assert normalize_code_for_dedupe(code) == code
