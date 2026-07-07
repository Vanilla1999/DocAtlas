from typing import Any, cast

from docmancer.docs.dartdoc import discover_pub_dartdoc_seed_urls


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


def test_async_pub_dartdoc_target_still_discovers_seed_urls(monkeypatch) -> None:
    from docmancer.docs.application.docs_target_service import DocsTargetService
    from docmancer.docs.models import DocsTarget

    root_url = "https://pub.dev/documentation/camera/0.11.2/"

    class Response:
        def __init__(self, status_code: int, text: str) -> None:
            self.status_code = status_code
            self.text = text

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
                return Response(200, '<html><head><base href="./flutter/"></head><body class="dartdoc"><nav><a href="widgets/">widgets</a></nav></body></html>')
            if url == effective_root + "index.json":
                return Response(200, '[{"href":"widgets/FocusNode-class.html"}]')
            return Response(404, "")

    result = discover_urls(root_url, cast(Any, Client()), max_pages=10)

    assert result.diagnostics["discovery_strategy"] == "dartdoc-index"
    assert [item.url for item in result.urls] == [effective_root + "widgets/FocusNode-class.html"]
