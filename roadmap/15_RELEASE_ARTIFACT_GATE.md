# Task 15 — test and release the product users actually install

Status: implemented in `feat/task15-release-artifact-gate`.

## Priority

P0 release gate. Do not publish automatically from this implementation PR.

## Problem

The README's one-line installer installs PyPI `doc-atlas`, while the latest package version is `1.1.1` and predates the current three-tool Docs MCP workflow. CI mainly tests editable source, not the wheel users receive. The existing stdio smoke exercises advanced Packs rather than the primary Docs workflow.

## Goal

Make the built wheel/sdist, version metadata, installer, and primary MCP flow one verifiable release unit.

## Required changes

1. Build wheel and sdist once in the release workflow and pass those exact artifacts to every test/publish job. Do not rebuild after tests.
2. Install the wheel outside the repository in clean environments for every Python version declared in package classifiers. Test 3.13 if it remains declared; otherwise remove the classifier in task 08.
3. Verify package assets, `doc-atlas --help`, version output, and project metadata from the installed wheel.
4. Add an offline stdio smoke using the official MCP client and the installed wheel:
   - start the Docs MCP server;
   - assert `tools/list` contains exactly the three public tools;
   - create a deterministic temporary repository with one Markdown source;
   - run `get_docs_context → prepare_docs(sync_project_docs) → get_docs_context`;
   - require cited context from that source.
5. In the implementation PR, test the installer through a local artifact/index override pinned to the candidate version. After publication, repeat it against the exact public version.
6. Before tagging, require candidate package version, changelog release heading, and artifact metadata to agree. After tagging, include the Git tag in the same check.
7. Use one publication trigger. Prevent tag-plus-release double publication.
8. Prefer PyPI Trusted Publishing/OIDC with least workflow permissions; pin third-party actions to immutable commits and generate artifact attestation/provenance where supported.
9. Document the manual approval/release step. The PR may prepare a version but must not publish without explicit maintainer authorization.

## PR merge gate

- Candidate wheel and sdist are built once.
- Wheel passes the declared-Python clean install and Docs MCP smoke outside the repository.
- Sdist metadata/file list is validated, builds the same-version wheel in an isolated environment, and that wheel passes the same smoke on one supported Python version.
- Candidate version, changelog heading, and both artifact metadata records agree.
- Installer local-artifact override installs the candidate and exposes the advertised workflow.
- Workflow trigger/permissions/action pinning changes are validated.

## Post-tag and post-publish promotion gate

- Tag, artifact version/digest, changelog, and release metadata agree.
- Installing the exact public PyPI version through the documented installer passes the three-tool Docs smoke.
- Only after this gate and task 14's live closure artifact may the release be described as Stable.

## CI failure rules

- A source checkout passing while the wheel fails is a release failure.
- Missing package data is a release failure.
- An MCP inventory mismatch is a release failure.
- A README installer that resolves to an older incompatible package is a release failure.

## Non-goals

- Do not publish from a pull request.
- Do not redesign the installer UX; task 21 owns model bootstrap/adoption.
- Do not smoke public network sources.

## Acceptance criteria

- The exact wheel selected for publishing passes the clean-environment matrix and primary Docs stdio smoke.
- Python 3.13 is tested or removed from package classifiers.
- The PR merge gate passes without requiring a tag that does not exist yet.
- The post-tag/publish gate verifies version, tag, changelog, installer target, and public artifact agreement.
- Publication has one explicit trigger and uses least privilege.
- A release checklist names the human authorization step.
- Workflow validation, local artifact smoke, and `git diff --check` pass.
