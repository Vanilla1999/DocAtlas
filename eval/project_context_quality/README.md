# Project context quality protocol

This protocol freezes natural newcomer questions that must traverse the public
project-documentation path.  The primary success is useful bounded
`docs_context`; project reads never become `docs_answer`.

The corpus contains Russian questions, English semantic pairs, and a nonexistent
premise.  Contract tests verify that broad queries receive retrieval-only
aliases, generic CLI commands are not rewritten as the Docs MCP tool inventory,
and an unknown premise receives no canonical alias.

Run the provider-free contract gate with:

```bash
python -m eval.project_context_quality_protocol
```

Run the heavier self-hosted public-path gate explicitly with:

```bash
python -m eval.project_context_quality_protocol --live
```
