from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def text(rel): return (ROOT/rel).read_text()
def test_aar_listener_and_methods_bridge_to_service():
    client=text("ViScanner/src/main/kotlin/com/example/ViScanner.kt")
    service=text("ViScannerService/src/main/kotlin/com/example/ViScannerService.kt")
    for symbol in ("setDisabledScannerListener", "onDisabledScanAttempt", "enableScanner", "disableScanner"):
        assert symbol in client
    assert "Scanner.enableScanner()" in service and "Scanner.disableScanner()" in service
def test_pause_and_release_restore_vendor_state_first():
    wrapper=text("ViScannerService/src/main/kotlin/com/example/Scanner.kt")
    assert "suspend fun pause() { scanner?.enableScanner(); scanner?.pause() }" in wrapper
    assert "suspend fun release() { scanner?.enableScanner(); scanner?.release() }" in wrapper
def test_only_urovo_overrides_standard_beep_hook():
    abstract=text("ViScannerService/src/main/kotlin/com/example/scanners/AbstractScanner.kt")
    urovo=text("ViScannerService/src/main/kotlin/com/example/scanners/UrovoScanner.kt")
    assert "protected open fun setStandardBeepEnabled" in abstract
    assert "override fun setStandardBeepEnabled" in urovo and "decode_beep" in urovo
