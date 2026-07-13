from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TANDER = ROOT / "android/app/src/tanderStore/AndroidManifest.xml"
SERVICE = ROOT / "lib/app/domain/services/external_browser_intent_service.dart"

def test_production_flavor_does_not_claim_arbitrary_http_links():
    text = TANDER.read_text()
    assert 'android:scheme="http"' not in text
    assert 'android:scheme="https"' not in text
    assert "com.example.enterprise.SDK" in text
    assert "com.example.enterprise.OPEN" in text

def test_cold_and_warm_paths_share_host_aware_http_predicate():
    text = SERVICE.read_text()
    assert text.count("_isValidHttpUri") >= 3
    assert "uri.host.isEmpty" in text
    assert "uri == null" in text
    assert "uri.scheme != 'http'" in text and "uri.scheme != 'https'" in text

def test_dependency_pin_is_unchanged():
    assert 'version: "6.4.1"' in (ROOT / "pubspec.lock").read_text()
