# 26 - Platform Hardening After the Wedge

## Goal

Improve install reliability, local data safety, backup/restore, and security after the project-aware Context7 replacement wedge is proven.

This is intentionally after `get_project_context`, Trust Contract, exact-version benchmarks, and explainable context.

## Why this is later

A local-first Context7 clone proposal suggested P2P/LAN sync, cloud backup, SQLCipher, GUI, and OS packaging.

These are useful platform features, but they do not directly prove that Docmancer beats Context7 for coding-agent tasks inside a repo.

The first priority is still:

> Which docs should this agent trust for this repo and this dependency version?

## Platform tasks

### Install and update reliability

- Improve install docs for Windows/macOS/Linux.
- Document supported package managers/install targets.
- Add signed release/update checks where applicable.
- Ensure agent integration setup is easy to verify.

### Backup and restore

Document backup/restore for:

- global config;
- registry database;
- per-library SQLite indexes;
- extracted Markdown/JSON;
- Qdrant storage;
- local model cache;
- project-local `docmancer.yaml`.

Acceptance target: a developer can move local Docmancer state to another machine or restore after failure using documented steps.

### Sensitive/private docs posture

Evaluate and document:

- filesystem encryption recommendations;
- OS keychain/credential storage;
- optional SQLCipher for registry/indexes;
- implications of cloud embedding providers;
- safe defaults for private docs.

### Doctor and first-run UX

- Make `doctor` explain local storage and network fetch boundaries.
- Surface stale indexes, failed refreshes, vector drift, missing project docs, and missing dependency docs.
- Provide exact fix commands or MCP next actions.

## Explicitly deferred

Do not lead with:

- P2P/WebRTC/libp2p sync;
- LAN peer discovery;
- cloud backup/sync as a product surface;
- Electron/desktop GUI;
- broad local mirror of hosted public-doc catalogs.

These can be revisited after the replacement benchmark proves that agents get better outcomes from Docmancer's repo-grounded trusted context.

## Acceptance criteria

- Install/setup path is documented and testable.
- Backup/restore path is documented.
- Private-doc users have clear local security guidance.
- Release integrity story is documented.
- None of this blocks the CLI/MCP project-context workflow.
