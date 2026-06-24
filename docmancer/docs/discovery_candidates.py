from __future__ import annotations

from docmancer.docs.resolver import normalize_lookup_key


def _canonical_ecosystem(ecosystem: str | None) -> str | None:
    if ecosystem is None:
        return None
    normalized = normalize_lookup_key(ecosystem)
    if normalized in {"pub", "flutter", "dart"}:
        return "dart"
    return normalized


_KNOWN_DISCOVERY_CANDIDATES = {
    ("python", "mcp"): [
        {
            "library": "mcp",
            "ecosystem": "python",
            "name": "Model Context Protocol Python SDK",
            "docs_url": "https://github.com/modelcontextprotocol/python-sdk",
            "confidence": "medium",
            "why": "candidate matched python ecosystem and mcp query",
        }
    ],
    ("dart", "riverpod"): [
        {
            "library": "riverpod",
            "ecosystem": "dart",
            "name": "Riverpod official guide",
            "docs_url": "https://riverpod.dev/",
            "confidence": "high",
            "why": "Official Riverpod guide documentation (preferred over pub.dev API)",
        },
        {
            "library": "riverpod",
            "ecosystem": "dart",
            "name": "Riverpod pub.dev API reference",
            "docs_url": "https://pub.dev/documentation/riverpod/latest/",
            "confidence": "medium",
            "why": "pub.dev API reference (fallback)",
        }
    ],
    ("dart", "flutter_riverpod"): [
        {
            "library": "flutter_riverpod",
            "ecosystem": "dart",
            "name": "Flutter Riverpod official guide",
            "docs_url": "https://riverpod.dev/",
            "confidence": "high",
            "why": "Official Riverpod guide documentation (preferred over pub.dev API)",
        },
        {
            "library": "flutter_riverpod",
            "ecosystem": "dart",
            "name": "Flutter Riverpod pub.dev API reference",
            "docs_url": "https://pub.dev/documentation/flutter_riverpod/latest/",
            "confidence": "medium",
            "why": "pub.dev API reference (fallback)",
        }
    ],
    ("dart", "flutter_bloc"): [
        {
            "library": "flutter_bloc",
            "ecosystem": "dart",
            "name": "Flutter BLoC official guide",
            "docs_url": "https://bloclibrary.dev/",
            "confidence": "high",
            "why": "Official BLoC library guide documentation (preferred over pub.dev API)",
        },
        {
            "library": "flutter_bloc",
            "ecosystem": "dart",
            "name": "Flutter BLoC pub.dev API reference",
            "docs_url": "https://pub.dev/documentation/flutter_bloc/latest/",
            "confidence": "medium",
            "why": "pub.dev API reference (fallback)",
        }
    ],
    ("dart", "bloc"): [
        {
            "library": "bloc",
            "ecosystem": "dart",
            "name": "BLoC official guide",
            "docs_url": "https://bloclibrary.dev/",
            "confidence": "high",
            "why": "Official BLoC library guide documentation (preferred over pub.dev API)",
        },
        {
            "library": "bloc",
            "ecosystem": "dart",
            "name": "BLoC pub.dev API reference",
            "docs_url": "https://pub.dev/documentation/bloc/latest/",
            "confidence": "medium",
            "why": "pub.dev API reference (fallback)",
        }
    ],
    ("dart", "go_router"): [
        {
            "library": "go_router",
            "ecosystem": "dart",
            "name": "go_router pub.dev API reference",
            "docs_url": "https://pub.dev/documentation/go_router/latest/",
            "confidence": "high",
            "why": "pub.dev API reference with package documentation",
        }
    ],
    ("python", "fastapi"): [
        {"library": "fastapi", "ecosystem": "python", "name": "FastAPI documentation", "docs_url": "https://fastapi.tiangolo.com/", "confidence": "high", "why": "candidate matched python ecosystem and fastapi query"}
    ],
    ("python", "pydantic"): [
        {"library": "pydantic", "ecosystem": "python", "name": "Pydantic documentation", "docs_url": "https://docs.pydantic.dev/latest/", "confidence": "high", "why": "candidate matched python ecosystem and pydantic query"}
    ],
    ("python", "httpx"): [
        {"library": "httpx", "ecosystem": "python", "name": "HTTPX documentation", "docs_url": "https://www.python-httpx.org/", "confidence": "high", "why": "candidate matched python ecosystem and httpx query"}
    ],
}


def discovery_candidates_for(library: str, ecosystem: str | None) -> list[dict]:
    normalized_library = normalize_lookup_key(library)
    normalized_ecosystem = _canonical_ecosystem(ecosystem)
    keys: list[tuple[str, str]] = []
    if normalized_ecosystem:
        keys.append((normalized_ecosystem, normalized_library))
    else:
        keys.extend(key for key in _KNOWN_DISCOVERY_CANDIDATES if key[1] == normalized_library)
    candidates: list[dict] = []
    for key in keys:
        candidates.extend(dict(item) for item in _KNOWN_DISCOVERY_CANDIDATES.get(key, []))
    return candidates
