"""GitHub finite immutable-manifest adapter; no repository discovery fallback."""
from __future__ import annotations

import fnmatch
import json
import os
import re
from dataclasses import dataclass, field

from docmancer.core.models import Document
from docmancer.docs.github_source_manifest import normalize_resolved_github_manifest

_DOC_EXTENSIONS = (".md", ".mdx", ".txt", ".rst", ".ipynb")


@dataclass(slots=True)
class Context7Config:
    # Parsed configuration is not source membership or version authorization.
    branch: str | None = None
    folders: list[str] = field(default_factory=list)
    exclude_folders: list[str] = field(default_factory=list)
    exclude_files: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    previous_versions: list[str] = field(default_factory=list)
    branch_versions: list[str] = field(default_factory=list)


class GitHubFetcher:
    def __init__(
        self, timeout: float = 30.0, file_patterns: list[str] | None = None,
        token: str | None = None, source_manifest: dict | None = None,
        max_pages: int = 500,
    ):
        self._timeout = timeout
        self._file_patterns = list(file_patterns or [])
        self._token = token or os.environ.get("GITHUB_TOKEN", "")
        self._source_manifest = (
            normalize_resolved_github_manifest(source_manifest)
            if source_manifest is not None else None
        )
        self._max_pages = max_pages

    def fetch(self, url: str) -> list[Document]:
        if self._source_manifest is None:
            raise ValueError("github_source_manifest_required")
        from docmancer.connectors.fetchers.web import WebFetcher

        fetcher = WebFetcher(
            timeout=self._timeout, max_pages=self._max_pages,
            source_manifest=self._source_manifest,
        )
        documents = fetcher.fetch(url)
        self.last_discovery_diagnostics = fetcher.last_discovery_diagnostics
        self.last_page_ledger = fetcher.last_page_ledger
        return documents

    def _select_documentation_files(
        self, all_files: list[str], context_config: Context7Config | None = None,
    ) -> list[str]:
        """Legacy pure syntax utility; never consumed as fetch authorization."""
        config = context_config or Context7Config()
        selected = []
        for path in all_files:
            if config.folders:
                if not path.endswith(_DOC_EXTENSIONS) or not any(
                    path == folder.removeprefix("./").strip("/")
                    or path.startswith(folder.removeprefix("./").strip("/") + "/")
                    for folder in config.folders if folder.removeprefix("./").strip("/")
                ):
                    continue
            elif not self._matches_patterns(path):
                continue
            if not self._is_excluded(path, config):
                selected.append(path)
        return sorted(set(selected), key=lambda path: self._rank_file(path, config))

    def _matches_patterns(self, file_path: str) -> bool:
        for pattern in self._file_patterns:
            if fnmatch.fnmatch(file_path, pattern):
                return True
            if "**/" in pattern:
                prefix, suffix = pattern.split("**/", 1)
                if file_path.startswith(prefix) and fnmatch.fnmatch(file_path.rsplit("/", 1)[-1], suffix):
                    return True
        return False

    def _is_excluded(self, file_path: str, config: Context7Config) -> bool:
        return (file_path.rsplit("/", 1)[-1] in config.exclude_files
                or any(self._path_matches_exclusion(file_path, file_path.split("/")[:-1], pattern)
                       for pattern in config.exclude_folders))

    @staticmethod
    def _path_matches_exclusion(file_path: str, folders: list[str], pattern: str) -> bool:
        clean = pattern.strip()
        if not clean:
            return False
        if clean.startswith("./"):
            root = clean[2:].strip("/")
            return file_path == root or file_path.startswith(root + "/")
        if "/" in clean or "*" in clean:
            return fnmatch.fnmatch(file_path, clean) or any(
                fnmatch.fnmatch("/".join(folders[:i + 1]), clean) for i in range(len(folders)))
        return any(fnmatch.fnmatch(folder, clean) for folder in folders)

    @staticmethod
    def _rank_file(file_path: str, config: Context7Config) -> tuple[int, str]:
        for index, folder in enumerate(config.folders):
            clean = folder.strip("./").strip("/")
            if clean and file_path.startswith(clean + "/"):
                return index, file_path
        return 40, file_path

    @staticmethod
    def _parse_repo_url(url: str) -> tuple[str, str, str, str]:
        """Legacy pure URL syntax parser; missing refs do not authorize lookup."""
        url = url.rstrip("/")
        match = re.match(
            r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/(?:tree|blob)/([^/]+)(?:/(.+))?)?$",
            url,
        )
        if not match:
            raise ValueError(f"URL does not look like a GitHub repository: {url!r}")
        return match.group(1), match.group(2), match.group(3) or "", match.group(4) or ""

    @staticmethod
    def _normalize_file_content(file_path: str, content: str) -> str:
        if not file_path.endswith(".ipynb"):
            return content
        try:
            notebook = json.loads(content)
        except json.JSONDecodeError:
            return ""
        cells = []
        for cell in notebook.get("cells", []):
            source = cell.get("source", "")
            text = "".join(source) if isinstance(source, list) else str(source)
            if text.strip():
                cells.append(f"```python\n{text.strip()}\n```" if cell.get("cell_type") == "code" else text.strip())
        return "\n\n".join(cells)

    def _api_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers
