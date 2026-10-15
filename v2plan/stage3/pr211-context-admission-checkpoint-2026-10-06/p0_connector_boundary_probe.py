"""Pure helper probes for corpus/source-root filters; no fetch/network access."""
from __future__ import annotations

import json

from docmancer.agent import _PARSERS, _import_class
from docmancer.connectors.fetchers.factory import build_fetcher
from docmancer.connectors.fetchers.github import GitHubFetcher, Context7Config
from docmancer.connectors.fetchers.pipeline.filtering import is_docs_url, infer_docset_root, normalize_url


def main() -> None:
    parsers = [{"suffix": suffix, "configured_identity": identity,
                "actual_identity": (cls := _import_class(identity)).__module__ + ":" + cls.__name__}
               for suffix, identity in _PARSERS.items()]
    providers = []
    for provider in ("web", "github", "gitbook", "mintlify", "crawl4ai"):
        fetcher = build_fetcher("https://example.test/docs", provider=provider)
        providers.append({"provider": provider, "actual_class": type(fetcher).__module__ + "." + type(fetcher).__name__})
    github = GitHubFetcher()
    tree = ["README.md", "docs/guide.md", "docs/CHANGELOG.md", "docs/i18n/ru/guide.md", "i18n/ru/guide.md", "docs/legacy/guide.md"]
    defaults = github._select_documentation_files(tree, Context7Config(folders=["docs", "i18n"]))
    override = github._select_documentation_files(tree, Context7Config(folders=["docs", "i18n"], exclude_folders=["never-present-folder"], exclude_files=["never-present-file"]))
    url_cases = [("https://example.test/docs/guide", "https://example.test/docs"),
                 ("https://example.test/ru/docs/guide", "https://example.test"),
                 ("https://example.test/ru/docs/guide", "https://example.test/ru/docs"),
                 ("https://example.test/docs/status", "https://example.test/docs"),
                 ("https://different.test/docs/guide", "https://example.test/docs")]
    print(json.dumps({"schema": "p0-connector-boundaries-v1", "parsers": parsers, "fetcher_factory": providers,
                      "github_default_selection": defaults, "github_explicit_exclusion_override": override,
                      "github_selected_folders": ["docs", "i18n"],
                      "url_filters": [{"url": url, "seed": seed, "admitted": is_docs_url(url, seed)} for url, seed in url_cases],
                      "root_inference": [{"url": url, "inferred": infer_docset_root(url)} for url in
                                         ("https://example.test/docs/alpha/start", "https://example.test/unknown/alpha/start")],
                      "normalization": normalize_url("https://example.test/docs?from=source-owned-value&edition=1"),
                      "limitations": "Pure helpers and constructors only; no HTTP, source freshness, network authorization, or end-to-end library ingestion claimed."}, indent=2))


if __name__ == "__main__":
    main()
