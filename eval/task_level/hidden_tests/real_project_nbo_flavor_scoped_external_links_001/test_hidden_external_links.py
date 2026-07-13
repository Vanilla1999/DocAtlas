from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
def test_flavor_boundaries_and_platform_contract_are_preserved():
    develop = (ROOT / "android/app/src/develop/AndroidManifest.xml").read_text()
    aw = (ROOT / "android/app/src/aw/AndroidManifest.xml").read_text()
    production = (ROOT / "android/app/src/tanderStore/AndroidManifest.xml").read_text()
    assert 'android:scheme="http"' in develop and 'android:scheme="https"' in develop
    assert 'android:scheme="http"' not in aw and 'android:scheme="https"' not in aw
    for required in ('android:launchMode="singleTask"', 'android:exported="true"', 'flutter_deeplinking_enabled'):
        assert required in production
def test_no_parallel_ingress_or_dependency_drift():
    main = (ROOT / "android/app/src/main/kotlin/com/example/MainActivity.kt").read_text()
    service = (ROOT / "lib/app/domain/services/external_browser_intent_service.dart").read_text()
    assert "MethodChannel(" not in main
    assert "getInitialLink" in service and "uriLinkStream" in service
    assert "app_links: 6.4.1" in (ROOT / "pubspec.yaml").read_text()
