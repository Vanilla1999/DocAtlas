# Native evidence sufficiency challenge

This directory supplies an independently authored integration challenge for the
installed public DocAtlas MCP path. The four named systems are fictional. Their
Markdown manuals, rather than prior knowledge of similarly named software,
define the task facts.

## Inventory

- 16 distinct end-to-end questions in one mixed-project installation.
- 16 authored Markdown source files across four project groups.
- 12 fully documented questions, two partial questions, and two unanswerable questions.
- 36 documented required claims and four unsupported requested claims.
- Seven documented claims require a joint witness containing parts from multiple files.
- Eight irrelevant restriction controls are included for optional precision diagnostics.

The questions exercise environment restrictions, negation and exceptions,
prerequisites in another file, exact identifiers, version applicability,
Russian questions over English sources, operational paraphrase, and partial or
missing answers. These are independent scenarios, not a matrix of string
variants or direct tests of selector helpers.

## Installed-project layout

Copy each `sources/<family>/<path>` to `<project>/<family>/<path>`.
All sixteen documents belong to one mixed project. The `source_plan.json`
shape is the same as the V40 source plan: `families` contains an `id` and
a list of relative `paths`.

The query interface is `questions.json["cases"]`. Each case supplies
`id`, `project_group`, `question`, `answerability`, `family`,
`split`, and `source_kind`.

## Independent scoring

Load `gold_spans.json` only after retrieval, selection, delivery, and any
answer generation have completed. Never pass gold, expected statements, span
locations, control labels, or case identifiers as retrieval hints.

For a documented claim, one witness set must be complete: every part in its
`parts` list must be present at its original path and line range. Different
required claims are separate obligations. Paths are relative to that case's
project group. A multi-file witness must not be reduced to an OR over its parts.

An empty `witness_sets` list marks an unsupported requested claim. It is not a
successful proof of absence. Source-span scoring alone cannot establish correct
unknowns, correct final answers, or provider-token savings.

`expected_statement` explains the authored task contract. It is not an exact
answer-string requirement. `irrelevant_negative_controls` identifies
restrictions that do not answer that question; their inclusion can be reported
as a precision diagnostic, but is not automatically a correctness failure.
Preserving a whole source section may legitimately include a control sentence.

Required conditions are question-specific. The oracle does not demand every
restriction in a source document for every question.

## Freeze protocol and limitations

The source bytes, question wording, gold spans, and source plan were authored
before any runtime result for this challenge was observed. Pending product
changes were not read by the fixture author. The fixture author had seen the
older v2 design in the conversation; this is a fresh independently authored
challenge set, not a statistical blind test of production generalization.

The product owner reported freezing the selector before opening these fixtures:
`docmancer/mcp/evidence_selection.py` SHA-256
`81c0e094fb5377923bee595562846f0ef6aa576a23fb6d3708c3d06cc36b4abb`.

`freeze_manifest.json` records the bytes used for this cycle. Do not change
questions, source text, expected claims, or spans to fit runtime outcomes.
If a genuine authoring error is discovered, report it and create a separately
versioned cycle rather than silently editing the frozen acceptance data.

