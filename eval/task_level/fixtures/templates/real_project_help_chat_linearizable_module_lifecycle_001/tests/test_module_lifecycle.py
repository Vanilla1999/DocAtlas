from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/"lib/src/help_request_module.dart"
def test_lifecycle_serializes_concurrent_init_and_reset():
    text=MODULE.read_text()
    assert "_operation" in text
    assert "_generation" in text
    assert "await current" in text
    assert "identical(_operation, operation)" in text
def test_failed_init_is_cleaned_and_retryable_without_global_reset():
    text=MODULE.read_text()
    assert "catch" in text and "_resetOwned" in text
    assert ".reset()" not in text.replace("HelpRequestUtils.reset()", "")
def test_pinned_get_it_version_is_preserved():
    assert 'version: "7.2.0"' in (ROOT/"pubspec.lock").read_text()
