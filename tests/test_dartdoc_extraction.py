from __future__ import annotations

from docmancer.connectors.fetchers.pipeline.extraction import discover_dartdoc_candidate_links, extract_content


def test_dartdoc_html_extracts_main_documentation_content():
    html = """
    <html><body class="dartdoc"><div class="dartdoc-main-content">
    <h1>Provider class</h1><section class="desc">Riverpod Provider exposes state to widgets.</section>
    </div></body></html>
    """

    content = extract_content(html, url="https://pub.dev/documentation/riverpod/latest/provider/Provider-class.html")

    assert "Provider class" in content
    assert "Riverpod Provider exposes state" in content


def test_dartdoc_shell_page_discovers_candidate_doc_links():
    html = """
    <html><body class="dartdoc"><script src="static-assets/script.js"></script>
    <a href="classes/Provider-class.html">Provider</a>
    <a href="riverpod/riverpod-library.html">riverpod</a>
    </body></html>
    """

    links = discover_dartdoc_candidate_links(html, "https://pub.dev/documentation/riverpod/latest/")

    assert "https://pub.dev/documentation/riverpod/latest/classes/Provider-class.html" in links
    assert "https://pub.dev/documentation/riverpod/latest/riverpod/riverpod-library.html" in links


def test_riverpod_like_dartdoc_page_does_not_raise_no_extractable_content():
    html = """
    <html><body><div id="__content"><div class="documentation markdown">
    <h1>ConsumerWidget</h1><p>Use ConsumerWidget to read providers from the WidgetRef.</p>
    </div></div></body></html>
    """

    content = extract_content(html, url="https://pub.dev/documentation/flutter_riverpod/latest/flutter_riverpod/ConsumerWidget-class.html")

    assert "ConsumerWidget" in content
    assert "WidgetRef" in content
