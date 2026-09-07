# DocAtlas module documentation

Module documents are maintained source-of-truth contracts for architectural boundaries. They are registered in `docatlas.project-docs.yaml` with `scope: module` and a real `module_path`, allowing `get_docs_context` and project-doc retrieval to filter evidence to one module without losing cross-module project questions.

Current documented boundaries:

- [Project context retrieval](./project-context-retrieval.md) - retrieves bounded project context without certifying an answer.
- [Question planning](./question-planning.md) - protects certification lanes with explicit proof obligations.
- [Evidence selection](./evidence-selection.md) - certifies library and dependency answers from bounded visible evidence.
- [Storage mutation coordination](./storage-mutation-coordination.md) - coordinates refresh/publication/removal/cleanup over shared storage.

When adding a new module contract, add the Markdown file and the matching manifest entry in the same change. Tests should verify both manifest validity and at least one real retrieval question against the registered module.

## Index and query workflow

After adding or changing module documentation, synchronize project docs through the normal public preparation surface:

```text
prepare_docs(
  action="sync_project_docs",
  project_path="/absolute/path/to/project",
)
```

For a module-scoped question, bind the same `module_path` that the manifest entry declares:

```text
get_docs_context(
  question="What does OrionRouter do?",
  project_path="/absolute/path/to/project",
  scope="module",
  module_path="modules/orion",
)
```

Omit the module filter for a cross-module contract question such as `What is ModuleEvidenceContract?`; the returned context may then cite source-of-truth documents from both registered modules.

Prefer a stable, code-shaped identity for an important architecture concept (`QuestionPlan`, `ModuleEvidenceContract`, `StorageMutationCoordination`) and state its definition or behavior in one local proposition. That gives the proof layer a precise subject while keeping the surrounding prose readable.
