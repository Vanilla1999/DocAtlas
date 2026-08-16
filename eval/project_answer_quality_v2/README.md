# Project answer quality protocol v2

This immutable provider-free protocol reproduces the real-corpus failure classes
that motivated ProjectAnswerContract v2: branding and troubleshooting
distractors, count-versus-name inventory semantics, witness-scoped fitting,
interrogative subject extraction, source-field locations, contiguous workflows,
and honest abstention.

The 17 cases preserve the original diagnostic questions. They distinguish
project-document answers from facts intentionally outside the Docs lane:
`docmancer.yaml`, dependency declarations, and internal candidate-trace code do
not become answer evidence merely because those files exist in the repository.
Each case uses the public `get_docs_context(question, project_path, mode)` surface
after real project-doc discovery, SQLite indexing, and retrieval.
