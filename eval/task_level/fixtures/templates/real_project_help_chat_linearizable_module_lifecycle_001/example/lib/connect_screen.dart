Future<void> initializeAfterAuth() async { await HelpRequestModule.init(config: delayedTokenConfig); }
Future<void> logout() async { await HelpRequestModule.reset(); }
