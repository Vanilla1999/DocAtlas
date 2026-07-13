class HelpRequestUtils { static Object? _config; static bool get isConfigured => _config != null; static void setConfig(Object value) { _config = value; } static void reset() { _config = null; } }
