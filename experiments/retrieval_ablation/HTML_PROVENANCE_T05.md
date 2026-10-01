# T05 HTML original/canonical provenance

`source_artifact.py` reuses existing production `extraction.extract_content`;
no new extraction algorithm, package installation or lockfile change. Preserve
the immutable original UTF-8 HTML and canonical Markdown separately with hashes
and production converter code identity. Quote spans explicitly belong to
`canonical_utf8_markdown`. No raw HTML offsets or exact original-HTML quote are
invented. Native Markdown remains byte-for-byte identity conversion.

Loading verifies hashes AND repeats conversion from original bytes, refusing
a forged canonical artifact even if its unsigned hashes were recomputed. It
also refuses unsupported formats, symlinks and invalid spans. This is a local
development artifact loader, not an external trust certificate or public MCP
schema change. Extraction output can differ from HTML and may omit information;
provenance does not establish semantic fidelity automatically.

Actual production HTML extraction tests preserve adjacent API declarations,
condition text, code literal spacing and separate original/canonical coordinates.
CommonMark parents over canonical output keep alpha/beta ownership distinct.
Combined harness and adjacent product tests: **176 passed**.

**T05 remains partial:** provenance is now implemented for HTML artifacts, but
the native project arm still receives canonical Markdown, not raw HTML. No
HTML arm quality results or HTML/RST product-scope certification are claimed.
RST parsing remains unsupported: `docutils` is not available in the existing
environment; a regex approximation was deliberately not introduced to pretend
full RST ownership coverage. No environment installation was performed.
General API ownership outside headings and ancestor-declaration binding remain
open. These limits cannot be fixed by the measured soft-heading threshold alone.

## Actual ingestion / packet follow-up

Added `bind_packet_provenance`: first validate the actual public DTO against its
source snapshot, then require its source-content hash to match the canonical
artifact, locate its exact quote only inside the verified source window, and
return private original/canonical locators. Missing artifacts, wrong hashes,
invalid or ambiguous windows fail closed. The public schema/800-token DTO is
unchanged; these locators do not assert HTML offsets or original-HTML quotations.

Replayed six authored HTML mechanism fixtures through production HTML extraction,
native project ingestion and A/B/D_L, two repetitions each: **36 executed,
36 audit-clean**, max **515 tokens**; **36 delivered quotes** successfully bound
to their original/canonical artifacts. All 18 arm/case DTOs match their repeat.
All six A/B DTOs match; all six B/D candidate pools match. Converter-produced
ATX headings already work in A; no structural quality improvement is claimed.
Negative case 6 produces no sources in all arms; no threshold adjustment was
made to force success. Other fixtures cover API references, reordering, renaming,
foreign API prose, a separate condition paragraph and code literals.

Artifacts: `/tmp/opencode/ablation-html-packet-replay/` (raw/canonical provenance,
canonical input corpus, requests, all packets and private citation locators),
driver `/tmp/opencode/ablation-html-packet-replay.py`, log
`/tmp/opencode/ablation-html-packet-replay.log`.

HTML original/canonical provenance deliverable is now integration-tested.
This is the derived-canonical project path, not direct raw-HTML public citations,
not an independent corpus, and not complete T05 ownership/RST acceptance.
