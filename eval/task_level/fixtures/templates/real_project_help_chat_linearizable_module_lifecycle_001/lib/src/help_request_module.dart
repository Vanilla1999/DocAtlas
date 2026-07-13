import 'package:get_it/get_it.dart';

class HelpRequestModule {
  static final _getIt = GetIt.instance;
  static bool _isInitialized = false;

  static Future<void> init({required HelpRequestConfig config, HelpRequestMode mode = HelpRequestMode.live}) async {
    if (isInitialized) return;
    if (_isInitialized) await reset();
    if (mode != HelpRequestMode.mock) {
      final token = await config.getToken?.call();
      if (token == null) throw StateError('token is null');
    }
    HelpRequestUtils.setConfig(config);
    _getIt.registerSingleton<HelpRequestMediaService>(DefaultHelpRequestMediaService());
    initHelpRequestLocator();
    await initializeDateFormatting();
    _isInitialized = true;
  }

  static bool get isInitialized => _isInitialized && HelpRequestUtils.isConfigured;

  static Future<void> reset() async {
    await resetHelpRequestLocator();
    if (_getIt.isRegistered<HelpRequestMediaService>()) {
      await _getIt.unregister<HelpRequestMediaService>();
    }
    HelpRequestUtils.reset();
    _isInitialized = false;
  }
}
