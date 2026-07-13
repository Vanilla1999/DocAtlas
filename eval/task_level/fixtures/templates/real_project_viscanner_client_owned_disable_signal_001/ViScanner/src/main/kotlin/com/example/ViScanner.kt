object ViScanner {
  private var needScan = true
  private val callbacks = mutableListOf<(String) -> Unit>()
  private val scannerListener = object : ScannerListener.Stub() {
    override fun onScan(barcode: String) {
      if (needScan) callbacks.toList().forEach { it(barcode) }
    }
  }
}
