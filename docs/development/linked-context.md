# Bounded linked context after Qwen selection

`DOCATLAS_CONTEXT_LINKS=one-hop-v1` is an opt-in post-selection extension of
`qwen3-contextual-own-body-evidence-v1`. The default is `off`. It neither enables
a model automatically nor changes the frozen Qwen scoring inputs, scores or
threshold. It is not enabled in the ordinary algorithmic retrieval path, MiniLM
recipes or the separate historical reference-closure-v3 experiment.

## Behavior

After Qwen selects sections, inspect links in their **own bodies**. A unique
local Markdown section target already present in the checked, authorized
same-call documents can be added with its ancestor introductions. Added text is
an exact source span, not a generated summary. Every additional row passes the
existing source/snapshot/hash/scope validation and terminal recheck.

- A section added through a link does not become another expansion frontier.
- Ancestor introductions remain available, but their links are not a frontier.
- Explicit HTML navigation and syntactically link-only Markdown blocks/lists
  are not automatically expanded. No heading vocabulary or synonym dictionary
  decides relevance. A link-only block can contain a real condition; when not
  otherwise delivered its reference therefore remains explicitly pending.
- Source-defined Markdown reference links and footnotes are resolved without
  inventing names or introducing citation aliases.
- A document URL without a section does not trigger full-document expansion.
  Missing/ambiguous anchors, unavailable targets, unsupported assets, omitted
  descendants and references beyond the one-hop boundary are reported.
- A reference is **not authorization**: no new network fetch, no read outside
  the checked scope, and no access to unprepared or private documents.

The server distinguishes `selected_body`, `ancestor` and `linked_body` origins.
Host diagnostics retain the full reference trace. Model-facing metadata retains
counts and literal unresolved addresses with source paths, character spans and
reasons, without repeating the successful-edge trace or introducing a decoding
dictionary. It is included in actual rendered response sizing. The existing
50,000-token emergency stop applies to the complete response; there is no silent
trimming of added conditions.

`coverage` remains `unverified`, including when no pending reference was found.
Links do not enumerate all requirements: a condition can lack a link, occur two
hops away, or live in an unselected rule. Threshold calibration applies to the
original selected units, not to the usefulness of all added material. The mode
and its contract digest are bound into continuation identity; `off` leaves the
historical fingerprint unchanged.

## Explicit host configuration

Use the existing prepared **pinned Qwen model** and compatible frozen v1 policy:

```json
{
  "DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT": "1",
  "DOCATLAS_MINIMAL_CONTEXT_RECIPE": "qwen3-contextual-own-body-evidence-v1",
  "DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH": "/absolute/prepared-qwen-model",
  "DOCATLAS_MINIMAL_CONTEXT_POLICY": "/absolute/frozen-qwen-v1-policy.json",
  "DOCATLAS_CONTEXT_COMPRESSION": "off",
  "DOCATLAS_CONTEXT_LINKS": "one-hop-v1"
}
```

These are placeholders for real host-owned paths, not downloadable assets or
permission to use an arbitrary model. Existing asset hashes and pinned GPU
runtime requirements remain enforced. Without a policy, the existing diagnostic
keep-all mode still runs Qwen and is labelled uncalibrated; it is not a fallback
for a missing model. Wrong flag values or incompatible recipes fail explicitly.

For the optional [OpenCode documentation profile](../../integrations/opencode-v2-compact/DOCUMENTATION_PROFILE.md),
pass this map using `--server-env-json` when generating a new dedicated location.
The profile does not enable it by default. Restart the server to adopt host
configuration changes. No index-format migration or reindex is introduced by
this feature; links are interpreted on checked source text after selection.

## Verification boundary

See [the Step12 checkpoint](../../v2plan/STEP12_LINKED_CONTEXT_CHECKPOINT_RU.md)
for the predeclared tests, actual results and unavailable runtime. Structural
replay using saved real Qwen choices is not fresh Qwen inference and is not an
end-to-end final-answer quality test. The profile's separate source-to-draft
instruction likewise does not certify complete answers.
