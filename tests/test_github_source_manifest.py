from __future__ import annotations

from contextlib import nullcontext
from copy import deepcopy

import pytest

from docmancer.docs.application.docs_target_service import DocsTargetService
from docmancer.docs.github_source_manifest import (
    GitHubSourceManifestError,
    canonical_manifest_digest,
    normalize_resolved_github_manifest,
    resolve_github_directory_manifest,
)
from docmancer.docs.models import DocsTarget


COMMIT = "1" * 40


def _render(template: str, library: str, version: str) -> str:
    return template.format(library=library, version=version)












class _Response:
    def __init__(self, payload, status_code=200):
        import json
        self._payload = payload
        self.status_code = status_code
        self.content = json.dumps(payload).encode()

    def json(self):
        return self._payload


class _Client:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []
        self.timeouts = []

    def get(self, url, **kwargs):
        self.urls.append(url)
        self.timeouts.append(kwargs.get("timeout"))
        return self.responses.pop(0)











