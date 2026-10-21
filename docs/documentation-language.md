# Documentation language preflight (declared metadata, not detection)

The public surface still has three tools. This feature adds one opt-in flag to
`docs_status` and one optional argument to `get_docs_context`. It does not enable
MiniLM by default, change access boundaries, translate text in the server, train
models, or implement semantic refusal.

## Ask once for an already selected source

```json
{"action":"project","project_path":"/repo","include_language":true,"details":false}
```

Use `module` with the **exact declared module path** for module language. No
module selector means repository-level documents, not sibling module documents.
For a known registered library use `action=library`, its `canonical_id`, and
`include_language=true`. Do not use status to discover projects/libraries or fetch
missing documents. Omit the flag to retain the existing status response unchanged.
Job actions reject the flag. All reads remain read-only and require existing
access/ownership bindings; an unprepared store is not initialized by this call.

The added `documentation_language` block has `languages`, `status`, `basis`,
`hint_only` and source/scope snapshot bindings. Status is `declared`, `mixed`,
`partial` or `unknown`. A declaration is not independently detected language and
never grants source, answer or edit authority. Do not treat unknown as English.
A mixed/partial declaration must not be silently reduced to a majority language.
Cache only for the same source, exact scope/version and snapshot; invalidate
when the catalog, source snapshot or dependency version changes.

## Declare project languages

Add an optional mapping of **existing literal members** to the ordinary catalog:

```yaml
schema_version: 1
documents:
  - path: README.md
    role: overview
    scope: project
    description: Project usage
    authority: source_of_truth
    status: active
    impact: track
documentation_languages:
  README.md: [en]
```

Multiple documents may declare different languages, e.g. `[ru]`, `[de]`,
`[zh-Hans]`; a single mixed-language document may declare more than one tag.
Only bounded BCP-47-shaped tags are accepted. The mapping cannot add catalog
members. Existing per-entry hashes are unchanged; the whole catalog hash binds
this additional metadata, so normal explicit preparation applies after catalog
changes. No repository files or databases are changed by a status request.

For external documentation, the already confirmed `source_manifest` can contain
`documentation_languages: [en]`. GitHub manifest normalization preserves this
optional metadata; the existing content digest remains a content-identity digest.
Language-profile identity additionally includes the declaration. A stale or
unverified library snapshot yields `unknown`. No English default or automatic
language detector is installed in this first version.

## Search in the declared language, answer in the user's language

```json
{
  "question":"Как Black выбирает целевые версии Python?",
  "search_question":"How does Black determine target Python versions?",
  "project_path":"/repo"
}
```

The host/assistant supplies a **full translation of that same question**; keep
identifiers, version strings, negation, conditions and comparison sides exactly.
The server keeps the original `question` as `query-original`, adds the translation
as one explicit host lookup (within the existing five-lookup total), and passes
the translated question to MiniLM section ranking. It does not infer or certify
equivalence, transfer original-query coverage, or authorize operations.
A sixth lookup fails explicitly; no question/lookup is silently dropped.
This opt-in is documentation-only, not a patch authorization argument.

No translation is inferred from retrieved instructions. Unknown language means
preserve the original question and disclose uncertainty; it is not a reason to
return semantic empty evidence. The answer language remains the user's language.
For mixed catalogs use an explicitly selected scope/source; no scope widening.

Before composing an answer, connect each factual claim to an actual returned
source. Retain supported parts, identify missing parts, and cite the supporting
IDs. Valid source IDs or language hints alone do not prove semantic correctness.
The existing Qwen answer-quality failures are not fixed by this metadata change.
