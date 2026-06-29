# Docmancer task-level fallback fixture

This sanitized Docmancer-derived fixture models benchmark accounting for project-context injection when vector indexing or retrieval times out. It is intentionally self-referential to the Docmancer benchmark and can only be used as workflow/regression evidence, not as independent proof that DocAtlas improves external projects.

The issue belongs in `src/docmancer_benchmark/context_accounting.py`. Do not solve it by changing tests or by assuming fallback context is the same thing as successful vector retrieval.
