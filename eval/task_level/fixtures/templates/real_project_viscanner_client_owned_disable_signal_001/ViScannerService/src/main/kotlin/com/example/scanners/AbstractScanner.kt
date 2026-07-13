abstract class AbstractScanner {
  protected var needScan = true
  protected var listeners: List<ScannerListener> = emptyList()
  fun sendBarcodeToClients(barcode: String) {
    if (needScan) listeners.forEach { it.onScan(barcode) }
  }
  open suspend fun pause() { needScan = false }
  open suspend fun release() { needScan = false }
}
