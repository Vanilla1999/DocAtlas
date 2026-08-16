# Project answer quality protocol v3

This immutable provider-free protocol covers technical-term and operational
question forms that are intentionally outside frozen protocol v2.  It verifies
CLI flag/command aliases, purpose questions, supported-value inventories,
coordinated delete/preserve facets, relation-local polarity, and environment
variable purpose without changing the v1 or v2 corpora.

Every case uses the public `get_docs_context(question, project_path, mode)`
surface after project-document discovery, SQLite indexing, production
retrieval, evidence selection, and canonical projection.  Positive cases include
adversarial distractors.  Negative cases prove that a related word, a single
scope, one requested facet, a bare variable mention, or a copula-only identity statement cannot authorize `ok`.
