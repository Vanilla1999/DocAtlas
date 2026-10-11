"""Tests for the content extraction pipeline."""

from __future__ import annotations

from docmancer.connectors.fetchers.pipeline.extraction import (
    DocsMarkdownConverter,
    extract_content,
    extract_dartdoc_content,
    extract_metadata,
    extract_section_path,
)


# ---------------------------------------------------------------------------
# Sample HTML fixtures
# ---------------------------------------------------------------------------

SIMPLE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head><title>Getting Started</title>
<meta name="description" content="Learn how to get started">
<link rel="canonical" href="https://example.com/docs/getting-started">
</head>
<body>
<nav><a href="/">Home</a><a href="/docs">Docs</a></nav>
<main>
<h1>Getting Started</h1>
<p>Welcome to the documentation. This guide will help you get started
with our platform quickly and easily.</p>
<h2>Installation</h2>
<p>Install using pip:</p>
<pre><code class="language-bash">pip install example-lib</code></pre>
<h2>Quick Start</h2>
<p>Here is a quick example:</p>
<pre><code class="language-python">from example import Client
client = Client()
result = client.run()
print(result)</code></pre>
</main>
<footer>Copyright 2024</footer>
</body>
</html>
"""

HTML_WITH_ADMONITIONS = """
<html><body>
<main>
<h1>Configuration</h1>
<p>Configure the following settings.</p>
<div class="warning">
<p>Do not use this in production without proper testing.</p>
</div>
<div class="note">
<p>This feature requires version 2.0 or later.</p>
</div>
<div class="tip">
<p>Use environment variables for sensitive values.</p>
</div>
</main>
</body></html>
"""

HTML_WITH_TABLE = """
<html><body>
<main>
<h1>API Reference</h1>
<p>The following endpoints are available:</p>
<table>
<tr><th>Method</th><th>Path</th><th>Description</th></tr>
<tr><td>GET</td><td>/users</td><td>List all users</td></tr>
<tr><td>POST</td><td>/users</td><td>Create a user</td></tr>
</table>
</main>
</body></html>
"""

HTML_WITH_NOISE = """
<html><body>
<nav class="sidebar">
<a href="/page1">Page 1</a>
<a href="/page2">Page 2</a>
</nav>
<main>
<h1>Real Content</h1>
<p>This is the actual documentation content that should be preserved
in the extraction output. It contains useful information.</p>
</main>
<footer><p>Built with DocsFramework</p></footer>
<script>console.log("tracking")</script>
</body></html>
"""

HTML_WITH_BREADCRUMBS = """
<html><body>
<nav aria-label="breadcrumb">
<a href="/docs">Docs</a>
<span>›</span>
<a href="/docs/guides">Guides</a>
<span>›</span>
<a href="/docs/guides/auth">Authentication</a>
</nav>
<main><h1>Authentication</h1><p>Content here.</p></main>
</body></html>
"""

EMPTY_HTML = """
<html><body></body></html>
"""

PLAIN_MARKDOWN = """# Hello World

This is already markdown content, not HTML.

```python
print("hello")
```
"""

DARTDOC_SIZED_BOX_HTML = """
<html><body>
<nav><a>Classes</a><a>Widget</a></nav>
<main id="dartdoc-main-content" class="main-content">
<h1>SizedBox class</h1>
<section class="desc markdown"><p>A box with a specified size.</p></section>
<section class="constructors"><h2>Constructors</h2>
<dl><dt><code>SizedBox({double? width, double? height, Widget? child})</code></dt>
<dd>Creates a fixed size box.</dd></dl></section>
<section class="properties"><h2>Properties</h2><dl><dt><code>width</code></dt><dd>The requested width.</dd></dl></section>
</main>
<footer>Flutter footer</footer>
</body></html>
"""

DARTDOC_SHELL_ROUTE_HTML = """
<html><body><aside>Navigation</aside>
<main class="content">
<h1>ShellRoute class</h1>
<p>A route that displays a UI shell around matching child routes.</p>
<h2>Example</h2>
<pre><code class="language-dart">ShellRoute(
  builder: (context, state, child) => Scaffold(body: child),
)</code></pre>
</main></body></html>
"""

DARTDOC_PROVIDER_HTML = """
<html><body>
<div id="dartdoc-main-content">
<h1>Provider class</h1>
<p>A provider that synchronously creates a value.</p>
<h2>Methods</h2><dl><dt><code>select</code></dt><dd>Filters rebuilds.</dd></dl>
</div>
</body></html>
"""


# ---------------------------------------------------------------------------
# extract_content tests
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# extract_metadata tests
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# extract_section_path tests
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# DocsMarkdownConverter tests
# ---------------------------------------------------------------------------
