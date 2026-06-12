# Agent MCP Workflow

## What already exists

Docmancer already provides repository-aware MCP tools and generated agent guidance.

Existing behavior includes:

- project-doc inspection before repository-specific answers;
- project-doc and project-context retrieval tools;
- generated instructions that tell agents not to skip project-doc discovery;
- next-action guidance when docs are missing, stale, or need ingestion;
- warnings not to use generic web fetches before retrying through Docmancer when Docmancer provides candidates or arguments patches.

This roadmap item is not about inventing a new workflow. It is about making the existing workflow more visible, testable, and harder to misuse.

## What still causes problems

Weaker agents can still:

- produce broad market-style summaries instead of repository-grounded answers;
- mention Docmancer capabilities without checking the current project state;
- ignore stale/ignored source warnings;
- treat project questions and dependency questions as the same type of task;
- skip source-code verification for implementation-sensitive claims.

## What to improve

- Tighten generated agent instructions around repository-specific questions.
- Add a short “golden path” example:
  1. inspect project docs;
  2. retrieve project context;
  3. review trust/stale/ignored source information;
  4. answer with source-grounded caveats;
  5. inspect code only when implementation facts are required.
- Add a “bad path” example showing an ungrounded generic summary.
- Add tests that check generated instructions still include the inspect-first rule.
- Make confidence guidance more explicit when project docs are missing or stale.

## UX acceptance criteria

- A user reading generated agent instructions understands when project-doc inspection is required.
- A weaker agent has an explicit step-by-step path for project-specific questions.
- The instructions distinguish project architecture questions from external dependency API questions.
- When project docs are stale or incomplete, the agent is told to disclose that limitation instead of presenting a confident answer.
