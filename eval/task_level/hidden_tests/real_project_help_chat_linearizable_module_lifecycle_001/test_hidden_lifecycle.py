from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
MODULE=ROOT/"lib/src/help_request_module.dart"
def test_reset_wins_over_inflight_init_and_waits_failures():
    text=MODULE.read_text()
    reset=text[text.index("static Future<void> reset()"):]
    assert "_generation++" in reset
    assert "try { await current; } catch" in reset
    assert "await _resetOwned()" in reset
def test_owned_cleanup_preserves_host_registrations_and_public_modes():
    text=MODULE.read_text()
    assert "_getIt.reset" not in text
    assert "allowReassignment" not in text
    assert "HelpRequestMode.mock" in text and "token == null" in text
    assert "resetHelpRequestLocator" in text and "unregister<HelpRequestMediaService>" in text
def test_no_dependency_or_example_drift():
    assert "get_it: ^7.2.0" in (ROOT/"pubspec.yaml").read_text()
    assert "await HelpRequestModule.reset()" in (ROOT/"example/lib/connect_screen.dart").read_text()
