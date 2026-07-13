import 'package:app_links/app_links.dart';

class ExternalBrowserIntentService {
  final AppLinks _appLinks = AppLinks();

  Future<Uri?> getInitialExternalUrl() async {
    final uri = await _appLinks.getInitialLink();
    if (uri == null || !_isHttpUri(uri)) return null;
    return uri;
  }

  Stream<Uri> get externalUrlStream => _appLinks.uriLinkStream.where(_isHttpUri);

  bool _isHttpUri(Uri uri) => uri.scheme == 'http' || uri.scheme == 'https';
}
