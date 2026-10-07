# Independent initial review — open findings

Reviewed A integration `e69b57b1` and C committed `2abf253d` / `f9513f18`.
B and C's indexed followup were not in scope. Source-derived review; no
hostile filesystem or Windows reproduction executed by R.

| ID | Severity | Finding | Owner | State |
|---|---|---|---|---|
| R1 | High | Path checks do not pin subsequent SQLite DB/journal boundary against parent replacement | A | OPEN |
| R2 | Medium | Input source/catalog/config hardlinks not rejected | A | OPEN |
| R3 | Medium | Aggregate byte/deadline checks happen after excess document read | A | OPEN |
| R4 | Medium | Owned server named `servers` inside V2 mapping is skipped, permitting duplicate registration | C | OPEN |
| R5 | Medium | POSIX descriptor primitives lack deliberate unsupported-platform guard on Windows | A | OPEN |
| R6 | Medium | Host accepts error-marked/malformed/conflicting structured and text evidence channels | B | OPEN |
| R7 | Medium | Host permits forged visible requirement-to-witness syntactic binding | B | OPEN |
| R8 | Medium | Host source line endpoints need not match retained text and are copied into citations | B | OPEN |
| R9 | Medium | Native recovery drops explicit scope/module/version bindings and admits contradictory versions | B | OPEN |

SQLite generation comparison, source ownership and rollback use one
`BEGIN IMMEDIATE` transaction; R found no independent SQL atomicity defect.
Caller confirmation remains intent, not issuer authentication. Cold database
creation/migration is not implemented by the authorized lane. Exact replay after
a changed generation is stale; no-op requests use the explicitly updated
expected generation. These limits must remain visible in acceptance reporting.

No full installed/deployed/release certification was issued. Final closure
requires fixes, targeted tests and independent re-review on the integrated SHA.

## Native consumer followup

R independently ran 39 focused tests plus one targeted recovery case with normal
conftest, and directly reproduced R6–R9 with adversarial probes. No production
edits or historical suite runs. Native retention/copies and absence of invented
read capabilities passed their reviewed checks, but do not close R6–R9.
No new finding in the reviewed coding instructions, projection split, CLI
early-denial/helper extraction or coordinator active assertion migrations.
Those coordinator conclusions were static-only, not full release certification.

## Verified closures on `9863c29b`

- R4 CLOSED narrowly: R independently passed all eight Python/shell ×
  enabled/disabled nested-`servers` registration regressions, including repeat
  registration. Name and disabled state survive without duplication.
- The additional request-triggered project-facade initialization defect is
  CLOSED narrowly by `1e9056d3`: three dispatch tests plus adversarial invalid
  grant and non-sync routing probes passed. Default configured service startup
  still initializes independently; this is not a write-free startup claim.
- Two targeted release-smoke behavioral checks passed. No historical
  self-host/GOLD tests were modified or executed.

R reported 13 focused nodes plus independent rerun probes. R1/R2/R3/R5 and
R6–R9 are not closed by this review. Full installed/release acceptance remains
unestablished.

## Final independent re-review at `5772d372`

157 focused tests passed, plus two reruns with independent attack probes.

- R1: security containment verified, positive persistence OPEN. Valid public
  grant yields nonretryable `blocked` / `unsafe_sqlite_path_mutation`, no disk
  SQLite connection, no mutation; fixture database bytes unchanged.
- R2 CLOSED: FD-pinned input hardlinks/replacement detection.
- R3 CLOSED: selected-document remaining allowance and pre-read deadline checks;
  not a whole-operation deadline certification.
- R4 remains CLOSED narrowly for nested-`servers` duplicate prevention.
- R5 CLOSED: unsupported descriptor-platform denial before I/O; not Windows support.
- R6 CLOSED: conflicting/malformed/error/duplicate channel attacks reject;
  identical canonical dual delivery explicitly supported.
- R7 CLOSED: reported forged visible witness binding rejects using canonical checks.
- R8 CLOSED: reported newline endpoint and assignment containment attacks reject;
  absolute source positions are not authenticated here.
- R9 CLOSED: explicit immutable bindings forwarded, contradictions rejected before
  verifier, missing/non-true verification unresolved; provenance verifier remains
  host-owned.

Compatibility decision OPEN: root-local identity excludes legacy Git-identity
rows with no migration/alias/rebuild; index parity is not certified. Installed
reporting must reflect the final blocked write lane, not earlier positive fixture
commits. No historical evaluations, providers, user-index updates or full release
certification were performed by R.
