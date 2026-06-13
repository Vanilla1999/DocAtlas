from docmancer.docs.domain.target_security import host_allowed, is_remote_url, path_allowed, url_security_error


def test_url_security_rejects_localhost_private_and_file_urls():
    assert url_security_error("http://localhost:8000/docs") == "localhost URLs are not allowed"
    assert url_security_error("http://127.0.0.1:8000/docs") == "private network URLs are not allowed"
    assert url_security_error("http://192.168.1.1/docs") == "private network URLs are not allowed"
    assert url_security_error("file:///etc/passwd") == "unsupported URL scheme: file"


def test_url_security_allows_public_remote_urls():
    assert url_security_error("https://api.flutter.dev/") is None
    assert is_remote_url("https://api.flutter.dev/") is True
    assert is_remote_url("file:///tmp/docs") is False


def test_host_allowed_preserves_exact_and_subdomain_behavior():
    assert host_allowed("https://api.flutter.dev/widgets", ["api.flutter.dev"]) is True
    assert host_allowed("https://docs.api.flutter.dev/widgets", ["api.flutter.dev"]) is True
    assert host_allowed("https://evilflutter.dev/widgets", ["flutter.dev"]) is False


def test_path_allowed_preserves_prefix_behavior():
    assert path_allowed("https://example.com/docs/index.html", ["/docs/"]) is True
    assert path_allowed("https://example.com/api/index.html", ["/docs/"]) is False
    assert path_allowed("https://example.com/api/index.html", []) is True
