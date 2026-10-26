# Native evidence selection: measured results, 2026-10-26

Tested product commit: `a957b0b3213321bf8c740f78e7ceb3a79da7cd7f`.
Dedicated installed integration: https://github.com/Vanilla1999/DocAtlas/actions/runs/40342412148 (success).
This report-only commit does not change the tested product.

## What changed

The default native `opencode-v1` path now uses `guarded-cover-v1` before rendering. The selector covers literal query clauses and exact identifiers, favors additional coverage per source cost, removes redundant lexical witnesses, preserves acquired owner/parent conditions, and falls back to original ordering when matching is ambiguous. This is a fallible lexical/structural heuristic, NOT certified semantic sufficiency or a globally minimum set.

The renderer stops when the selected prefix ends even if space remains. The transport ceilings are UNCHANGED: 3,000 o200k tokens, 24,000 UTF-8 bytes and 900 lines, including the signed continuation. No lowered ceiling or mandatory fixed fragment count explains the reduction. Source text is never paraphrased. The rest of the authorized pool stays accessible via authenticated continuation.

An actually applied MiniLM selector is preserved instead of applying a second lexical veto. These experiments intentionally exercise normal native installation without provisioned MiniLM assets. Other-client wire contracts remain unchanged. `DOCATLAS_NATIVE_SELECTION=preserve` restores delivery-only behavior.

## Same-run comparison

Forty unchanged V40 questions; all fifteen original documents in ONE mixed project. Thirty-two questions have committed documented witness groups; eight no-answer questions are not counted as successful final answers merely because their expected witness list is empty.

| Policy | Complete documented groups | First-page tokens | Delivered source rows | Newly lost groups vs delivery-only |
|---|---:|---:|---:|---:|
| delivery-only / preserve | 29/32 | 117,421 | 759 | baseline |
| query-cover-v1 | 16/32 | 20,493 | 52 | 13 |
| owner-cover-v1 | 29/32 | 31,976 | 134 | 2 |
| guarded-cover-v1 (selected) | 30/32 | 59,930 | 343 | 0 |

Guarded saves 57,491 first-page tokens, 48.96%. Owner-cover has the same aggregate completeness as preserve but loses T07/E04 while gaining P03/P06; that is why it was not selected. Guarded restores P06 and does not lose any originally delivered required group. P03 and E01 remain incomplete on the first page. These are grouped source-span checks, not the user's separate 23-fact or 11-fact grading of generated answers.

In 26/40 requests, guarded stops after selected evidence, before the transport ceiling. Fourteen uncertain requests retain the original paged order. Median delivered rows is 5.5 vs 19; the range is 0–21, not a fixed top-k. B02 still retains four same-owner rows and is not claimed minimal.

## Five user-audited questions, tool inputs only

| Case | Preserve blocks | Guarded blocks | Preserve tokens | Guarded tokens |
|---|---:|---:|---:|---:|
| B01 | 19 | 1 | 2,979 | 433 |
| B02 | 18 | 4 | 2,885 | 964 |
| B05 | 19 | 1 | 2,953 | 455 |
| B06 | 17 | 7 | 2,883 | 1,306 |
| B08 | 20 | 0 | 2,953 | 345 |
| Total | 93 | 13 | 14,653 | 3,503 |

This is 76.09% less first-page text on these five questions, NOT 76.09% lower provider usage. Both arms above ran on the same current product/data. Counts can differ from historical e13fdef2 agent sessions. Small nonce/signature token variation is not itself an algorithmic saving.

B08 reports that no direct lexical witness was selected, NOT that no guarantee exists in the entire corpus. B06 handles the documented configuration-search clause separately from the unsupported port clause. Correct final unknowns and any remaining file fallback require another full answering-model test. Of eight no-answer cases, four have no source rows; three still trigger conservative full-page fallback and one retains a candidate. We do not count any of these as verified semantic absence.

## Actual delivery and integrity

- Real installed CLI registration, SQLite, authorized public stdio MCP; no retrieval/model mocks and no oracle access by the selector.
- Actual pinned OpenCode v2.1.2 (`a517687fde98a7329ada3ae644a01a9fc6c4e99e`) McpClient and ToolOutput, 40 requests per arm: zero truncations and zero temporary-output-file spills in BOTH preserve and guarded.
- Post-client required-span coverage agrees with Python delivery: 29/32 vs 30/32, no new losses. Guarded first ten documented cases all preserve their committed witnesses.
- All 343 guarded first-page source spans match original source text and coordinates. Full enumeration for one query recovers all 256 snippets byte-for-byte over 15 pages. This is a security/completeness control, not a proposed agent workflow to read all pages.
- Forged cursor, changed question, changed scope and changed source rejected. Source files and SQLite logical state unchanged.
- 219 Python stdio requests including pagination/security controls; 80 actual OpenCode adapter requests; zero answering-model calls; provider_usage=null.

Downloaded artifact 12662615951: `native-opencode-40342412148`, 5,872,733 bytes.
SHA-256: `9014834527a6bc9bb3910281ffa2a38f063ec17d1cb50cdb57973d66a4845560`.
Recounting recorded texts with the pinned codec reproduces all token/byte/row totals. Independent source-span comparison also agrees after real OpenCode normalization. No additional model or retrieval calls were made for that recount.

## Acceptance boundaries

The dedicated integration is green; broad repository CI remains partly red. This is a known development/regression set, not a new blind test. It is not a full autonomous OpenCode answering run, and does not establish total token savings, final-answer non-regression, correct unknowns or fewer file reads. A lexical coverage heuristic can miss synonyms, implicit prerequisites and exceptions; ambiguity fallback intentionally trades some extra text for lower regression risk. Continue measuring the same strong model and complete histories before claiming the original end-to-end objective is met. Main is not modified by this draft PR update.
