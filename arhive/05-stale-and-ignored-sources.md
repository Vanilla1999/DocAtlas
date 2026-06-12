# Stale and Ignored Sources

## What already exists

Docmancer already tracks and reports source state.

Existing behavior includes:

- stale-source detection using stored file metadata/content information;
- ignored-source reporting;
- `indexed_source_not_discovered` for indexed docs not selected by the current discovery pass;
- next-action style guidance in inspection/context flows.

This roadmap item is not about adding source-state tracking. It is about making the messages clearer and less likely to be misread.

## What still causes problems

Agents and users may misunderstand source-state labels.

The most important example:

```text
indexed_source_not_discovered
```

This can be misread as “the file is bad, deleted, or irrelevant”. The better interpretation is:

> This source exists in the index, but the current discovery pass did not select it as a project-doc candidate.

That usually means the documentation layout, links, or discovery configuration should be reviewed.

## What to improve

- Improve wording of source-state messages in user-facing responses.
- Add remediation hints for common states:
  - stale source → re-ingest or refresh;
  - indexed but not discovered → link it from a docs index/root doc or adjust discovery;
  - ignored generated/tooling doc → usually no action required;
  - missing expected source → inspect docs map and ingestion scope.
- Add examples to generated agent instructions.
- Make agents explicitly mention source-state caveats when they affect answer confidence.

## UX acceptance criteria

- Users can understand source-state messages without knowing Docmancer internals.
- `indexed_source_not_discovered` is explicitly defined in docs or response guidance.
- Each common source-state warning includes a recommended next action.
- Agents stop treating undiscovered indexed sources as necessarily invalid.
