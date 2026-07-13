object Scanner {
  private var scanner: AbstractScanner? = null
  suspend fun prepare() = scanner?.prepare()
  suspend fun pause() = scanner?.pause()
  suspend fun release() = scanner?.release()
}
