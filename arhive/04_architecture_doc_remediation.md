# Project Docs Onboarding Roadmap: ARCHITECTURE.md Remediation

## Goal

When project-owned docs are missing or incomplete, guide the coding agent to propose a reviewable `ARCHITECTURE.md` file instead of ending with “nothing found” or storing architecture in hidden memory.

## Ownership boundary

Docmancer should:

- detect missing project docs;
- recommend creating `ARCHITECTURE.md`;
- return structured remediation;
- ingest the file after it exists.

The coding agent should:

- ask the user for confirmation;
- inspect the repository;
- create or edit `ARCHITECTURE.md` as a normal repository file;
- avoid unsupported claims;
- run any appropriate checks;
- call `ingest_project_docs` after the file is created.

Docmancer should not silently write official project docs into a hidden database.

## Trigger states

Recommend this remediation when:

- `reason_code = no_project_docs`;
- `reason_code = architecture_doc_creation_recommended`;
- docs exist but none provide a high-level project overview.

## Confirmation prompt

Suggested user prompt:

> I could not find a high-level project architecture document. Do you want me to inspect the repository and create `ARCHITECTURE.md` as a reviewable file?

If declined, continue using available code/docs and clearly state that high-level project documentation is missing.

## Suggested `ARCHITECTURE.md` template

```markdown
# Architecture

## Purpose

Describe what this project does and who/what it serves.

## Main components

- Component/module name — responsibility and key files.

## Data and control flow

Describe important runtime flows and boundaries.

## External dependencies

List important services, packages, APIs, or generated artifacts.

## Development workflow

Describe how to run, test, build, and inspect the project when known.

## Open questions

- TODO: items that could not be confirmed from repository evidence.
```

## Evidence rules

The coding agent should:

- cite repository files when possible;
- mark uncertain claims as TODO/open questions;
- avoid inventing deployment topology, business logic, or ownership;
- prefer concise factual descriptions over broad speculation.

## Post-creation flow

After `ARCHITECTURE.md` is created:

1. Call `inspect_project_docs` to verify discovery.
2. Call `ingest_project_docs` to index it.
3. Use `get_project_context` for the original question.

## Acceptance criteria

- Missing docs returns a direct architecture-doc remediation path.
- The remediation path requires user confirmation.
- No Docmancer tool silently writes official architecture content.
- The generated file is reviewable in git.
- After creation, `ingest_project_docs` includes `ARCHITECTURE.md` in project docs context.
