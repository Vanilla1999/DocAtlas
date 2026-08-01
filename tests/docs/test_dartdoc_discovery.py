from typing import Any, cast

from docmancer.docs.dartdoc import discover_pub_dartdoc_seed_urls, rank_dartdoc_seed_urls


def test_discover_pub_dartdoc_seed_urls_reads_index_json() -> None:
    root_url = "https://pub.dev/documentation/camera/0.11.2/"
    root_html = "<html><body><h1>camera</h1></body></html>"

    def fetch_url(url: str) -> str | None:
        if url == root_url + "index.json":
            return """
            [
              {"name":"CameraController","href":"camera/CameraController-class.html","type":"class"},
              {"name":"CameraController","href":"camera/CameraController/CameraController.html","type":"constructor"},
              {"name":"startVideoRecording","href":"camera/CameraController/startVideoRecording.html","type":"method"}
            ]
            """
        return None

    seeds = discover_pub_dartdoc_seed_urls(
        "camera",
        "0.11.2",
        root_html,
        root_url,
        max_seed_urls=20,
        fetch_url=fetch_url,
    )

    assert root_url + "camera/CameraController-class.html" in seeds
    assert root_url + "camera/CameraController/CameraController.html" in seeds
    assert root_url + "camera/CameraController/startVideoRecording.html" in seeds
    ranked = rank_dartdoc_seed_urls(seeds, "How does startVideoRecording work?", limit=2)
    assert ranked[0] == root_url + "camera/CameraController/startVideoRecording.html"


def test_async_pub_dartdoc_target_still_discovers_seed_urls(monkeypatch) -> None:
    import ipaddress

    monkeypatch.setattr(
        "docmancer.docs.fetch_policy.resolve_host",
        lambda _host: (ipaddress.ip_address("93.184.216.34"),),
    )
    from docmancer.docs.application.docs_target_service import DocsTargetService
    from docmancer.docs.models import DocsTarget

    root_url = "https://pub.dev/documentation/camera/0.11.2/"

    class Response:
        def __init__(self, status_code: int, text: str) -> None:
            self.status_code = status_code
            self.text = text
            self.headers = {
                "content-type": "application/json" if text.startswith("[") else "text/html"
            }

    class Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def get(self, url: str) -> Response:
            if url == root_url:
                return Response(200, "<html><body>camera</body></html>")
            if url == root_url + "index.json":
                return Response(200, '[{"href":"camera/CameraController-class.html"}]')
            return Response(404, "")

    monkeypatch.setattr("docmancer.docs.application.docs_target_service.httpx.Client", Client)
    service = DocsTargetService(lambda library, version, source_type: root_url)

    target = service.discover_pub_dartdoc_target(
        DocsTarget(library="camera", ecosystem="pub", version="0.11.2", source_type="api"),
        [],
        job_id="job-1",
        canonical_id="pub:camera@0.11.2:api",
    )

    assert target.docs_url is None
    assert target.seed_urls == [root_url + "camera/CameraController-class.html"]


def test_flutter_dartdoc_discovery_honors_html_base_href() -> None:
    from docmancer.connectors.fetchers.pipeline.discovery import _try_dartdoc_index

    root_url = "https://api.flutter.dev/"
    effective_root = "https://api.flutter.dev/flutter/"

    class Response:
        def __init__(self, status_code: int, text: str) -> None:
            self.status_code = status_code
            self.text = text

    class Client:
        def get(self, url: str) -> Response:
            if url == root_url:
                return Response(200, '<html><head><base href="./flutter/"></head><body class="dartdoc"></body></html>')
            if url == effective_root + "index.json":
                return Response(200, '[{"href":"widgets/FocusNode-class.html"}]')
            return Response(404, "")

    discovered = _try_dartdoc_index(root_url, cast(Any, Client()), max_pages=10)

    assert discovered is not None
    assert [item.url for item in discovered] == [effective_root + "widgets/FocusNode-class.html"]


def test_dartdoc_index_ignores_out_of_scope_links_before_page_limit() -> None:
    from docmancer.connectors.fetchers.pipeline.discovery import _try_dartdoc_index

    root_url = "https://api.flutter.dev/flutter/"

    class Response:
        def __init__(self, text: str) -> None:
            self.status_code = 200
            self.text = text

    class Client:
        def get(self, url: str) -> Response:
            if url == root_url:
                return Response('<html><body class="dartdoc"></body></html>')
            return Response(
                '[{"href":"https://evil.example/Fake-class.html"},'
                '{"href":"widgets/FocusNode-class.html"}]'
            )

    discovered = _try_dartdoc_index(root_url, cast(Any, Client()), max_pages=1)

    assert discovered is not None
    assert [item.url for item in discovered] == [root_url + "widgets/FocusNode-class.html"]


def test_dartdoc_discovery_prefers_base_aware_index_over_root_nav_shell() -> None:
    from docmancer.connectors.fetchers.pipeline.discovery import discover_urls

    root_url = "https://api.flutter.dev/"
    effective_root = "https://api.flutter.dev/flutter/"

    class Response:
        def __init__(self, status_code: int, text: str) -> None:
            self.status_code = status_code
            self.text = text

    class Client:
        def get(self, url: str) -> Response:
            if url == root_url:
                raise AssertionError("already fetched Dartdoc root must not be requested again")
            if url == effective_root + "index.json":
                return Response(200, '[{"href":"widgets/FocusNode-class.html"}]')
            return Response(404, "")

    root_html = '<html><head><base href="./flutter/"></head><body class="dartdoc"><nav><a href="widgets/">widgets</a></nav></body></html>'
    result = discover_urls(root_url, cast(Any, Client()), max_pages=10, root_html=root_html)

    assert result.diagnostics["discovery_strategy"] == "dartdoc-index"
    assert [item.url for item in result.urls] == [effective_root + "widgets/FocusNode-class.html"]


def test_flutter_dartdoc_oversized_index_uses_bounded_library_fallback() -> None:
    from docmancer.connectors.fetchers.pipeline.discovery import discover_urls
    from docmancer.docs.fetch_policy import DocsFetchSecurityError

    root_url = "https://api.flutter.dev/"
    effective_root = "https://api.flutter.dev/flutter/"
    library_url = effective_root + "widgets"

    class Response:
        def __init__(self, status_code: int, text: str) -> None:
            self.status_code = status_code
            self.text = text

    class Client:
        def get(self, url: str) -> Response:
            if url == root_url:
                return Response(
                    200,
                    '<html><head><base href="./flutter/"></head><body class="dartdoc">'
                    '<a href="widgets/">widgets</a>'
                    '<a href="https://evil.example/library/">external</a></body></html>',
                )
            if url == effective_root + "index.json":
                raise DocsFetchSecurityError("response_too_large", url, phase="fetch")
            if url == library_url:
                return Response(
                    200,
                    '<html class="dartdoc"><a href="https://api.flutter.dev/flutter/widgets/FocusNode-class.html">'
                    'FocusNode</a></html>',
                )
            return Response(404, "")

    result = discover_urls(root_url, cast(Any, Client()), max_pages=10)

    assert [item.url for item in result.urls] == [
        effective_root + "widgets/FocusNode-class.html",
        library_url,
    ]
    assert result.diagnostics["complete"] is False
    assert result.diagnostics["reason_code"] == "discovery_manifest_too_large"


def test_flutter_dartdoc_oversized_index_without_links_is_not_retried() -> None:
    from docmancer.connectors.fetchers.pipeline.discovery import discover_urls
    from docmancer.docs.fetch_policy import DocsFetchSecurityError

    root_url = "https://api.flutter.dev/"
    effective_root = "https://api.flutter.dev/flutter/"

    class Response:
        status_code = 200
        text = '<html><head><base href="./flutter/"></head><body class="dartdoc"></body></html>'
        headers = {"content-type": "text/html"}

    class Client:
        def __init__(self) -> None:
            self.index_requests = 0

        def get(self, url: str) -> Response:
            if url == effective_root + "index.json":
                self.index_requests += 1
                raise DocsFetchSecurityError("response_too_large", url, phase="fetch")
            return Response()

    client = Client()
    result = discover_urls(root_url, cast(Any, client), max_pages=10)

    assert client.index_requests == 1
    assert result.urls == []
    assert result.diagnostics["reason_code"] == "discovery_manifest_too_large"
