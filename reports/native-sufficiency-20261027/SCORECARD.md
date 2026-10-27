# Native evidence selection experiment

**Infrastructure checks passed. Candidate source-witness results below are separate; final answers and correct unknowns were not tested.**

All token counts are complete first MCP replies, not full dialogue usage. No answering model was called.

## v40 — 40 questions, 15 documents

| Policy | Required claims delivered | Complete documented cases | First-page tokens | Source witness gate | Losses vs controls |
|---|---:|---:|---:|---|---:|
| `preserve` | 29/32 | 29/32 | 117692 | **FAIL** | 3 |
| `guarded-cover-v2` | 32/32 | 32/32 | 51450 | **PASS** | 0 |
| `guarded-obligation-v1` | 32/32 | 32/32 | 59088 | **PASS** | 0 |
| `guarded-constraint-v1` | 32/32 | 32/32 | 99938 | **PASS** | 0 |
| `guarded-combined-v1` | 32/32 | 32/32 | 100128 | **PASS** | 0 |

### Missing required source claims

- `preserve`: V40-P03/required (admitted_not_on_first_page); V40-P06/documented_part (admitted_not_on_first_page); V40-E01/required (admitted_not_on_first_page)
- `guarded-cover-v2`: none
- `guarded-obligation-v1`: none
- `guarded-constraint-v1`: none
- `guarded-combined-v1`: none

Calls: 332 Python MCP + 200 real OpenCode MCP. Elapsed: not recorded; fully persisted delivery replayed for scoring. Unsupported claims are explicitly ungraded.

## new — 16 questions, 16 documents

| Policy | Required claims delivered | Complete documented cases | First-page tokens | Source witness gate | Losses vs controls |
|---|---:|---:|---:|---|---:|
| `preserve` | 36/36 | 14/14 | 44682 | **PASS** | 0 |
| `guarded-cover-v2` | 27/36 | 10/14 | 29633 | **FAIL** | 9 |
| `guarded-obligation-v1` | 27/36 | 10/14 | 30005 | **FAIL** | 9 |
| `guarded-constraint-v1` | 28/36 | 11/14 | 30491 | **FAIL** | 8 |
| `guarded-combined-v1` | 28/36 | 11/14 | 30672 | **FAIL** | 8 |

### Missing required source claims

- `preserve`: none
- `guarded-cover-v2`: NS16-L03/pause_ingress (admitted_not_on_first_page); NS16-L03/journal_watermark (admitted_not_on_first_page); NS16-L03/restore_command (admitted_not_on_first_page); NS16-L03/post_restore_sequence (admitted_not_on_first_page); NS16-C01/hold_overrides_expired_retention (admitted_not_on_first_page); NS16-V01/remote_endpoint (admitted_not_on_first_page); NS16-V01/namespace_credential (admitted_not_on_first_page); NS16-V03/precedence_order (admitted_not_on_first_page); NS16-V03/file_permission_no_exception (admitted_not_on_first_page)
- `guarded-obligation-v1`: NS16-L03/pause_ingress (admitted_not_on_first_page); NS16-L03/journal_watermark (admitted_not_on_first_page); NS16-L03/restore_command (admitted_not_on_first_page); NS16-L03/post_restore_sequence (admitted_not_on_first_page); NS16-C01/hold_overrides_expired_retention (admitted_not_on_first_page); NS16-V01/remote_endpoint (admitted_not_on_first_page); NS16-V01/namespace_credential (admitted_not_on_first_page); NS16-V03/precedence_order (admitted_not_on_first_page); NS16-V03/file_permission_no_exception (admitted_not_on_first_page)
- `guarded-constraint-v1`: NS16-L03/pause_ingress (admitted_not_on_first_page); NS16-L03/journal_watermark (admitted_not_on_first_page); NS16-L03/restore_command (admitted_not_on_first_page); NS16-L03/post_restore_sequence (admitted_not_on_first_page); NS16-V01/remote_endpoint (admitted_not_on_first_page); NS16-V01/namespace_credential (admitted_not_on_first_page); NS16-V03/precedence_order (admitted_not_on_first_page); NS16-V03/file_permission_no_exception (admitted_not_on_first_page)
- `guarded-combined-v1`: NS16-L03/pause_ingress (admitted_not_on_first_page); NS16-L03/journal_watermark (admitted_not_on_first_page); NS16-L03/restore_command (admitted_not_on_first_page); NS16-L03/post_restore_sequence (admitted_not_on_first_page); NS16-V01/remote_endpoint (admitted_not_on_first_page); NS16-V01/namespace_credential (admitted_not_on_first_page); NS16-V03/precedence_order (admitted_not_on_first_page); NS16-V03/file_permission_no_exception (admitted_not_on_first_page)

Calls: 96 Python MCP + 80 real OpenCode MCP. Elapsed: 237.691 seconds. Unsupported claims are explicitly ungraded.

## Evidence boundary

- Gold contains independently authored source spans; no selector accesses gold.
- The observed pool is legacy public docs_context after admission/upstream projection, before the native selector/page renderer.
- Missing-before-native-selection and admitted-but-not-on-first-page are reported separately; the latter includes selection and transport budget effects.
- A pre-native miss does not isolate upstream retrieval, admission or projection as its cause.
- All original text, coordinates, scope/version provenance, signed continuation and state invariants are checked.
- A PASS source-witness result is not proof of semantic sufficiency, global absence or lower provider cost.
- Detailed JSON contains every case, claim, raw reply, failure and call latency.
