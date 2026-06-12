# Maintained Documentation Index

## What already exists

Docmancer already discovers many project documentation locations, including root docs and common documentation directories such as `docs/`, wiki/ADR/roadmap/runbook-style folders.

It also reports indexed sources that are no longer selected by the current discovery pass.

## What still causes problems

Projects often scatter important docs across nested modules, packages, and investigation notes. Even when Docmancer has good discovery, users and agents may not know which docs are official or maintained.

This can lead to:

- important nested docs not being linked from root docs;
- stale indexed docs being misunderstood as invalid;
- generated or tooling docs being confused with maintained project docs;
- agents missing the intended documentation map.

## What to improve

- Document a recommended canonical documentation index file:

  ```text
  docs/INDEX.md
  ```

- Provide a template that lists:
  - root project docs;
  - architecture docs;
  - module/package docs;
  - runbooks;
  - investigation notes;
  - generated/tooling docs to ignore.
- Explain how explicit links from root docs or `docs/INDEX.md` help humans and agents treat nested docs as intentional.
- Consider prioritizing an explicit docs index in project-doc discovery or at least mentioning it prominently in inspection output when present.

## UX acceptance criteria

- Docmancer documentation includes a copy-pasteable `docs/INDEX.md` template.
- Users understand how to make nested docs discoverable and trustworthy.
- Agents are instructed to treat a maintained docs index as the canonical map of project docs.
- Inspection output or documentation explains what to do when an indexed source is no longer discovered.
