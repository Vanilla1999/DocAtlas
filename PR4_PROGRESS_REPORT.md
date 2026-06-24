# PR4 Progress Report: Dart/Flutter Public Docs Ingestion - Partial Implementation

**Date:** 2026-06-24  
**Branch:** `fix/dartdoc-pub-ingestion`  
**Status:** 🚧 IN PROGRESS (foundation complete, service wiring needed)

## Summary

PR4 foundation work is complete: official docs resolver implemented, config updated, tests added. The core infrastructure for Dart/Flutter docs ingestion is now in place, but full service integration and live validation remain.

## What Was Completed ✅

### 1. Root Cause Analysis
**File:** `PR4_ROOT_CAUSE_ANALYSIS.md`

Identified four primary failure modes:
- **Root-only indexing** — system stops at navigation shell without fetching library/class pages
- **No official docs knowledge** — missing riverpod.dev, bloclibrary.dev as preferred sources
- **Generic failures** — `empty_index` without dartdoc-specific reason codes
- **Missing config** — no Dart packages in docmancer.docs.yaml

### 2. Official Docs Resolver ✅
**File:** `docmancer/docs/dart_official_docs.py` (new, 227 lines)

Implemented comprehensive resolver for Dart/Flutter packages:

```python
@dataclass(frozen=True)
class DartDocsResolution:
    package: str
    official_docs_available: bool
    official_docs_urls: list[str]  # Prioritized: official guides → pub.dev API
    pubdev_docs_url: str
    docs_strategy: str  # 'official_docs' | 'pubdev_only' | 'mixed'
    confidence: str  # 'high' | 'medium'
```

**Supported packages:**
- `riverpod` → riverpod.dev (concepts, providers, modifiers) + pub.dev fallback
- `flutter_riverpod` → riverpod.dev + pub.dev fallback
- `hooks_riverpod` → riverpod.dev + pub.dev fallback
- `flutter_bloc` → bloclibrary.dev (concepts, architecture, tutorials) + pub.dev fallback
- `bloc` → bloclibrary.dev + pub.dev fallback
- `hydrated_bloc` → bloclibrary.dev + pub.dev fallback
- `go_router` → pub.dev + docs.flutter.dev navigation guide
- `provider`, `dio`, `freezed`, `json_serializable` → pub.dev only

**Functions:**
- `resolve_dart_official_docs(package, version)` → DartDocsResolution
- `get_seed_urls_for_package(package, max_urls)` → list[str]
- `has_official_docs(package)` → bool
- `normalize_package_name(package)` → str

### 3. Discovery Candidates Updated ✅
**File:** `docmancer/docs/discovery_candidates.py`

Added official docs to discovery candidates with **high confidence** prioritization:

**Before:**
```python
("dart", "riverpod"): [
    {"docs_url": "https://pub.dev/...", "confidence": "medium"}
]
```

**After:**
```python
("dart", "riverpod"): [
    {"docs_url": "https://riverpod.dev/", "confidence": "high", "why": "Official guide (preferred)"},
    {"docs_url": "https://pub.dev/...", "confidence": "medium", "why": "API reference (fallback)"}
]
```

Added entries for:
- `riverpod`, `flutter_riverpod` → riverpod.dev + pub.dev
- `flutter_bloc`, `bloc` → bloclibrary.dev + pub.dev
- `go_router` → pub.dev

**Ecosystem normalization:**
```python
# Handles ecosystem="flutter" → looks up ("dart", library)
# Handles ecosystem="pub" → looks up ("dart", library)
# Handles ecosystem="dart" → looks up ("flutter", library)
```

### 4. Config Updated ✅
**File:** `docmancer.docs.yaml`

Added 5 Dart/Flutter packages with official docs seed URLs:

```yaml
- id: riverpod
  library: riverpod
  ecosystem: flutter
  docs_url: https://riverpod.dev/
  seed_urls: [riverpod.dev guide pages, pub.dev API]

- id: flutter_riverpod
  ecosystem: flutter
  docs_url: https://riverpod.dev/
  seed_urls: [riverpod.dev guide pages, pub.dev API]

- id: flutter_bloc
  ecosystem: flutter
  docs_url: https://bloclibrary.dev/
  seed_urls: [bloclibrary.dev guide pages, pub.dev API]

- id: bloc
  ecosystem: flutter
  docs_url: https://bloclibrary.dev/
  seed_urls: [bloclibrary.dev guide pages, pub.dev API]

- id: go_router
  ecosystem: flutter
  docs_url: https://pub.dev/documentation/go_router/latest/
  seed_urls: [pub.dev API, docs.flutter.dev navigation]
```

### 5. Tests Added ✅
**File:** `tests/test_dartdoc_pub_ingestion.py` (new, 167 lines, 17 tests)

**Test coverage:**

**A. Official Docs Resolver (7 tests, all passing):**
- ✅ `test_normalize_package_name` — lowercase + underscore normalization
- ✅ `test_riverpod_has_official_docs` — riverpod.dev resolution
- ✅ `test_flutter_bloc_has_official_docs` — bloclibrary.dev resolution
- ✅ `test_unknown_package_falls_back_to_pubdev` — pub.dev fallback
- ✅ `test_get_seed_urls_returns_list` — URL list extraction
- ✅ `test_get_seed_urls_respects_max_urls` — max_urls limit
- ✅ `test_has_official_docs_check` — has_official_docs() check

**B. Dartdoc Extraction (4 tests, 3 passing + 1 skipped):**
- ✅ `test_pubdev_dartdoc_root_discovers_library_pages` — library link discovery
- ✅ `test_dartdoc_extraction_handles_empty_root` — empty root doesn't crash
- ✅ `test_dartdoc_class_page_extracts_content` — class page extraction
- ⏭️ `test_pub_package_does_not_return_python_docs` — source isolation (deferred)

**C. Official Docs Prioritization (2 tests, all passing):**
- ✅ `test_flutter_bloc_official_docs_preferred` — bloclibrary.dev before pub.dev
- ✅ `test_riverpod_official_docs_preferred` — riverpod.dev before pub.dev

**D. Diagnostics (2 tests, skipped - not yet implemented):**
- ⏭️ `test_dartdoc_no_extractable_content_reports_reason`
- ⏭️ `test_official_docs_used_diagnostic`

**E. End-to-End (2 tests, skipped - deferred):**
- ⏭️ `test_flutter_bloc_preindex_query_end_to_end_mocked`
- ⏭️ `test_riverpod_preindex_query_end_to_end_mocked`

**Test results:** 12 passed, 5 skipped (as planned)

### 6. Existing Tests Still Pass ✅
**Verification:** 175 tests passed, 5 skipped (15.73s)

Dart-related tests:
- `test_dartdoc_extraction.py` — 3/3 passed
- `test_dartdoc_pub_ingestion.py` — 12/17 passed (5 intentionally skipped)
- `test_docs_service.py` — 175 tests passed (no regressions)

## What Remains 🚧

### Critical (blocking merge):

1. **Service integration** — wire official docs resolver into `LibraryDocsApplicationService`
   - Modify `resolve_library()` to check `has_official_docs()` before returning `needs_docs_url`
   - Auto-populate `seed_urls` from `get_seed_urls_for_package()` when official docs available
   - Ensure `ecosystem="flutter"` queries use Dart resolver

2. **Dartdoc-specific diagnostics**
   - Add `dartdoc` object to `DocsResult.diagnostics`:
     ```python
     {
       "dartdoc": {
         "attempted": true,
         "discovery_strategy": "official_docs|pubdev_dartdoc_json|pubdev_dartdoc_nav",
         "official_docs_url": "https://riverpod.dev/",
         "pubdev_docs_url": "https://pub.dev/...",
         "pages_fetched": 15,
         "pages_indexed": 12,
         "chunks_indexed": 85,
         "reason_code": null | "dartdoc_root_only" | "dartdoc_no_extractable_content",
         "warnings": []
       }
     }
     ```
   - Return precise reason codes instead of generic `empty_index`

3. **Live validation**
   - Run `uv run python eval/live_mcp_context7_benchmark.py --suite public-docs --mode preindexed --quick --skip-context7`
   - Verify flutter_bloc and/or riverpod succeed or return precise unsupported
   - Verify contamination_rate = 0

### Important (pre-merge polish):

4. **Complete skipped tests**
   - Implement `test_pub_package_does_not_return_python_docs` (source isolation)
   - Implement diagnostics tests (2 skipped)
   - Implement end-to-end mocked tests (2 skipped)

5. **Documentation updates**
   - `docs/capabilities.md` — add Dart/Flutter section
   - `docs/mcp-docs-server.md` — document Dart support
   - `eval/results/live/sample_report.md` — add Dart examples

6. **Verify no generated artifacts**
   - `git ls-files eval/results/live` should show only `README.md`, `sample_report.md`

### Optional (nice-to-have):

7. **Enhanced Dartdoc discovery**
   - Parse `index.json`, `categories.json` from pub.dev
   - Discover library/symbol pages beyond root HTML links

8. **Improved extraction**
   - Better handling of Dartdoc navigation shells
   - Extract API signatures from class pages
   - Handle inherited members

## Files Changed

```
+ docmancer/docs/dart_official_docs.py           227 lines (new)
+ tests/test_dartdoc_pub_ingestion.py            167 lines (new)
+ PR4_ROOT_CAUSE_ANALYSIS.md                     (documentation)
± docmancer/docs/discovery_candidates.py         +65 lines (Dart candidates)
± docmancer.docs.yaml                            +68 lines (5 Dart packages)
```

**Total:** +527 additions

## Current Behavior (Partial)

### What Works Now ✅

**Discovery candidates resolution:**
```python
from docmancer.docs.discovery_candidates import discovery_candidates_for

# Returns official docs as first candidate
candidates = discovery_candidates_for("riverpod", "flutter")
assert candidates[0]["docs_url"] == "https://riverpod.dev/"
assert candidates[0]["confidence"] == "high"
assert candidates[1]["docs_url"] == "https://pub.dev/documentation/riverpod/latest/"
assert candidates[1]["confidence"] == "medium"
```

**Official docs resolver:**
```python
from docmancer.docs.dart_official_docs import resolve_dart_official_docs

resolution = resolve_dart_official_docs("flutter_bloc")
assert resolution.official_docs_available is True
assert resolution.docs_strategy == "official_docs"
assert "bloclibrary.dev" in resolution.official_docs_urls[0]
```

**Config-based ingestion:**
```python
# docmancer.docs.yaml now includes flutter_bloc with bloclibrary.dev seed URLs
# Manual refresh would now fetch official docs instead of only pub.dev API
```

### What Doesn't Work Yet ❌

**Automatic official docs use:**
```python
# This still returns needs_docs_url instead of auto-using riverpod.dev
service.get_docs(library="riverpod", ecosystem="flutter")
# Expected: use riverpod.dev automatically
# Actual: returns needs_docs_url (no service integration yet)
```

**Precise diagnostics:**
```python
# This still returns generic empty_index
service.get_docs(library="flutter_bloc", ecosystem="flutter", docs_url="...")
# Expected: dartdoc diagnostics with reason_code
# Actual: generic empty_index without dartdoc-specific context
```

## Next Session Tasks

**Priority 1: Service Integration (30-60 min)**
1. Modify `LibraryDocsApplicationService.resolve_library()`:
   - Check `has_official_docs(library)` before returning `needs_docs_url`
   - Auto-populate `seed_urls` from `get_seed_urls_for_package(library)`
   - Set `docs_url` to first official URL if available
2. Test that `get_docs(library="riverpod", ecosystem="flutter")` now works without explicit `docs_url`

**Priority 2: Diagnostics (30-45 min)**
1. Add `dartdoc` diagnostics object to `DocsResult`
2. Add reason codes: `dartdoc_root_only`, `dartdoc_no_extractable_content`, `official_docs_used`
3. Update extraction pipeline to populate diagnostics

**Priority 3: Live Validation (15-30 min)**
1. Run live benchmark: `--suite public-docs --mode preindexed --quick --skip-context7`
2. Verify flutter_bloc or riverpod succeeds
3. Check contamination_rate = 0

**Priority 4: Complete Tests & Docs (30 min)**
1. Implement 5 skipped tests
2. Update capabilities.md, mcp-docs-server.md, sample_report.md

**Total estimated time to PR4 completion:** 2-3 hours

## Acceptance Criteria Status

**Minimum acceptance:**

| Criterion | Status |
|-----------|--------|
| flutter_bloc: preindex → pages > 0, chunks > 0 | 🚧 Pending live validation |
| flutter_bloc: query returns bloclibrary.dev or pub.dev | 🚧 Pending service integration |
| flutter_bloc: contamination_rate = 0 | 🚧 Pending live validation |
| riverpod: preindex → pages > 0, chunks > 0 | 🚧 Pending live validation |
| riverpod: query returns riverpod.dev or pub.dev | 🚧 Pending service integration |
| riverpod: contamination_rate = 0 | 🚧 Pending live validation |
| Dartdoc root pages report precise reason (not generic empty_index) | ❌ Not implemented |
| Official docs fallback works | ✅ Infrastructure ready (not wired) |
| Diagnostics include reason codes | ❌ Not implemented |
| Tests pass | ✅ 12/12 implemented tests pass |
| No generated artifacts tracked | ✅ Verified |

**Preferred acceptance:**

| Criterion | Status |
|-----------|--------|
| Both flutter_bloc AND riverpod succeed | 🚧 Pending |
| Dartdoc discovery discovers library/symbol pages | ✅ Already works (discover_dartdoc_candidate_links) |
| pub.dev JSON metadata discovery | 🔄 Partially (discover_pub_dartdoc_seed_urls supports JSON) |

## Commands Run

```bash
# Investigation
find . -name "*.py" | grep -E "(pub|dart)"
grep -rn "ecosystem.*pub" docmancer/docs/ --include="*.py"

# Tests
uv run pytest tests/test_dartdoc_extraction.py -v
  → 3 passed

uv run pytest tests/test_dartdoc_pub_ingestion.py -v
  → 12 passed, 5 skipped

uv run pytest tests/test_dartdoc*.py tests/test_docs_service.py -v
  → 175 passed, 5 skipped (15.73s)

# Verification
git ls-files eval/results/live
  → README.md, sample_report.md (no timestamp dirs)
```

## Conclusion

**PR4 foundation is complete and tested.** The official docs resolver infrastructure is in place, config is updated, and discovery candidates prioritize official docs over pub.dev API. However, **service integration, diagnostics, and live validation remain** before PR4 is merge-ready.

**Current state:** ⚠️ Infrastructure complete, service wiring needed (2-3 hours estimated)

**Next step:** Wire `dart_official_docs.resolve_dart_official_docs()` into `LibraryDocsApplicationService.resolve_library()` to auto-use official docs when available.

---

**✅ Foundation complete. 🚧 Service integration next.**
