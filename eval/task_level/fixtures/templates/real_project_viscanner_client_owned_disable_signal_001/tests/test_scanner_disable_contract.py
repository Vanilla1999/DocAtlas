from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def text(rel): return (ROOT/rel).read_text()
def test_aidl_exposes_state_and_disabled_attempt_callback():
    api=text("ViScannerAIDL/src/main/aidl/com/example/ViScannerAidl.aidl")
    listener=text("ViScannerAIDL/src/main/aidl/com/example/ScannerListener.aidl")
    assert "void enableScanner();" in api and "void disableScanner();" in api
    assert "void onDisabledScanAttempt();" in listener
def test_service_abstract_state_suppresses_barcode_and_notifies():
    source=text("ViScannerService/src/main/kotlin/com/example/scanners/AbstractScanner.kt")
    assert "ScannerWorkState.DISABLED" in source
    assert "onDisabledScanAttempt()" in source
    disabled=source[source.index("open suspend fun disableScanner"):]
    assert "needScan = false" in disabled and "setStandardBeepEnabled(false)" in disabled
def test_custom_audio_and_block_scanner_are_out_of_scope():
    all_source="\n".join(p.read_text() for p in ROOT.rglob("*.kt"))
    assert "MediaPlayer" not in all_source and "audioPath" not in all_source
    assert "blockScanner" not in all_source
