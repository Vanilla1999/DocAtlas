# Source Taxonomy

## What already exists

Docmancer already separates several source classes internally.

Existing behavior includes:

- project-owned docs represented separately from dependency docs;
- project context packs that distinguish project-doc and dependency-doc sources;
- dependency metadata such as version, source type, exactness, binding source, and freshness;
- trust-contract style context that reports selected, rejected, and risky sources.

This roadmap item is not about adding source separation from scratch. It is about making that separation obvious to users and agents.

## What still causes problems

Agents can still mix evidence levels in the final answer. Common mistakes:

- using dependency docs as proof of repository-specific behavior;
- using project docs to infer external package API behavior;
- presenting stale docs as current implementation facts;
- forgetting to inspect source code for implementation-sensitive claims.

## What to improve

- Improve user-facing docs that explain the three practical evidence types:
  - project docs for architecture, decisions, runbooks, and workflows;
  - dependency docs for external APIs and framework behavior;
  - source code for current implementation facts.
- Surface source-type labels more clearly in context-pack summaries where they are currently too subtle.
- Add agent-facing wording that says dependency docs are not proof of repository architecture.
- Add guidance for when to move from docs retrieval to code inspection.

## UX acceptance criteria

- A user can tell whether an answer is based on project docs, dependency docs, source code, or a mix.
- Agents are instructed not to use dependency docs as evidence for project-specific claims.
- Context output makes risky source mixing visible enough for the agent to mention it.
- Documentation includes examples of correct and incorrect source use.
