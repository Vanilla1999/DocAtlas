# Decision: defer public-release execution and permit P1.1 harness work

- Date: 2026-08-22
- Status: accepted maintainer sequencing exception
- Scope: DocAtlas `1.3.1` publication and P1.1 harness construction

## Decision

Public publication of `doc-atlas==1.3.1` and the post-public artifact/install checks are deferred. The reviewed release request remains in the repository but is changed to `execute_on_merge=false` so ordinary merges cannot publish it.

Work may proceed on the P1.1 installed-MCP harness before P0 public-artifact closure, subject to the restrictions below.

## What remains open

Deferral does not convert missing public evidence into an accepted proof. Until the release is actually published and independently verified, all of the following remain pending:

- successful Trusted Publisher execution for the intended release;
- exact public wheel/sdist identity;
- no-cache installation of the exact public package;
- public Linux/macOS/Windows MCP verification;
- P0.6 closure.

An existing source version or tag is not a substitute for those facts.

## Exception boundary

The sequencing exception permits only measurement infrastructure that does not depend on a public release claim:

- build one wheel from an exact reviewed commit;
- install it into a fresh virtual environment;
- launch the installed Docs MCP process;
- expose the real installed schemas to a bounded driver;
- retain sanitized package/schema/tool-trajectory evidence;
- add provider-free positive controls and verifier mutations.

The resulting mode must be labelled `built_wheel`. It cannot close public-release rows and cannot be described as testing the public package.

## Explicitly not authorized

This decision does not authorize:

- a new public MCP tool;
- loosening `insufficient_evidence` or support adjudication;
- retrieval/reranking expansion;
- `working_path`, server-owned inference, or continuation-token API changes;
- a Stable, Context7-parity, correct-patch-improvement, or Agent Truth claim;
- a long-lived PyPI token fallback;
- silent publication from a pull request or ordinary push.

Those changes require later evidence and their own reviewed decisions.

## Completion and resumption

P1.1 harness construction is complete only when the installed-wheel boundary, report verifier, bounded driver protocol, and privacy checks are reproducible in CI. P1.1 Agent Truth remains open until a real model is run with provider/model/request provenance.

When public release work resumes, it must be explicitly re-enabled in a separate reviewed change and then execute the existing OIDC-only publication and public verification gates. This decision must not be rewritten retroactively as proof that those gates ran.
