from docmancer.docs.domain.source_identity import docs_exactness, docs_identity, docs_request
from docmancer.docs.models import LibraryInfo


def test_docs_identity_preserves_registered_source_shape():
    info = LibraryInfo(
        library_id="/pub/riverpod/2.0/api",
        library="riverpod",
        source_id="pub:riverpod:api",
        canonical_id="/pub/riverpod/2.0/api",
        ecosystem="pub",
        version="2.0",
        source_type="api",
        docs_url="https://pub.dev/documentation/riverpod/2.0/",
        docs_snapshot_exact=True,
    )

    assert docs_identity(info, docs_url_source="registry") == {
        "source_id": "pub:riverpod:api",
        "canonical_id": "/pub/riverpod/2.0/api",
        "library": "riverpod",
        "ecosystem": "pub",
        "version": "2.0",
        "docs_url": "https://pub.dev/documentation/riverpod/2.0/",
        "docs_url_source": "registry",
        "selected_by": "registry",
        "docs_snapshot_exact": True,
    }


def test_docs_request_preserves_input_and_effective_args():
    info = LibraryInfo(
        library_id="id",
        library="flutter",
        ecosystem="flutter",
        version="stable",
        source_type="api",
        docs_url="https://api.flutter.dev/",
        docs_url_template="https://api.flutter.dev/{library}/{version}/",
    )
    input_args = {"library": "Flutter", "topic": "widgets"}

    assert docs_request(input_args, info) == {
        "input": input_args,
        "effective": {
            "library": "flutter",
            "topic": "widgets",
            "ecosystem": "flutter",
            "version": "stable",
            "source_type": "api",
            "docs_url": "https://api.flutter.dev/",
            "docs_url_template": "https://api.flutter.dev/{library}/{version}/",
        },
    }


def test_docs_exactness_values():
    assert docs_exactness(True, None, None) == "exact_snapshot"
    assert docs_exactness(False, "https://example.com", None) == "exact_version_url"
    assert docs_exactness(False, None, "https://example.com/{version}/") == "exact_version_url"
    assert docs_exactness(False, None, None) == "no_docs"
