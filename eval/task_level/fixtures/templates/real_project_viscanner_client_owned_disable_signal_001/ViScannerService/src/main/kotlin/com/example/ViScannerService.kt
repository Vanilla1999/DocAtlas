class ViScannerService {
  val binder = object : ViScannerAidl.Stub() {
    override fun prepare() { launchMain { Scanner.prepare() } }
    override fun pause() { launchMain { Scanner.pause() } }
    override fun release() { launchMain { Scanner.release() } }
  }
}
