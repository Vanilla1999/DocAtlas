"""Split tests from test_docs_service.py; shared helpers remain in the façade module."""
from tests import _shared_test_docs_service as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

from tests._async_job_wait import wait_for_docs_job_status


def test_same_library_version_can_have_api_and_guides_targets(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    api = service.resolve_library(
        "riverpod",
        ecosystem="web",
        version="latest",
        source_type="api",
        docs_url="https://pub.dev/documentation/riverpod/latest/",
    )
    guides = service.resolve_library(
        "riverpod",
        ecosystem="web",
        version="latest",
        source_type="guides",
        docs_url="https://riverpod.dev/docs/",
    )

    assert api.library_id == "web:riverpod@latest:api"
    assert guides.library_id == "web:riverpod@latest:guides"
    assert service.registry.get("riverpod", "web", "latest", "api").docs_url == "https://pub.dev/documentation/riverpod/latest/"
    assert service.registry.get("riverpod", "web", "latest", "guides").docs_url == "https://riverpod.dev/docs/"


