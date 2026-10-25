# Fresh dialogue experiment, 2026-10-25

This is a new controlled experiment requested by the owner, **not** a replay or
repair of the historical Q02. Product code is pinned to main
`d6fc18256ffe91a1d26e03783642e521b056ce12`; the experiment changes only evaluation
inputs, a runner and the existing context-delivery scenario/tokenizer provisioning.

## Boundaries

- Eight new cold questions, with an English synthetic documentation corpus,
  Russian original questions and full meaning-preserving search translations.
- Questions, corpus and independent required facts are frozen before product
  execution. The delivery runner never uses gold to select or rewrite sources.
- Installed, non-editable wheel; real SQLite, CPU MiniLM and public stdio MCP.
  Existing integration preparation and observer mechanisms are reused.
- A: ordinary fixed-five wire text, including the actual preceding tool blocks.
- B: the same fixed-five responses rendered as one managed model-context block.
  A/B do not perform different searches or change the selected source rows.
- C: separate exploratory `adaptive-gap-b1-v1` run on the same frozen requests.
- Two predeclared same-question lookups test a bounded history replay. These
  follow-ups are scripted controls, not autonomous answering-model decisions.

CI measures real delivered content and emits the exact input for subsequent
isolated strong-model answering tasks. Those tasks receive no corpus-wide access
or gold. Generated answers are evaluated separately against independent facts,
their actually delivered evidence and citation bindings.

## What is not claimed

Synthetic data is not broad unseen natural-document acceptance. This controlled
replay is not the user's original deployed client. Token counts of visible
prompts are not provider usage: hidden instructions, reasoning, cache accounting
and total billed model tokens are unavailable in this setup. They must remain
null, not estimated or replaced with snippet counts. Finishing CI is not a pass
on missing facts or final-answer quality. Product defaults and main are unchanged.

Local product runtime/import/install/pytest is not used. Execution reuses the
authorized `.github/workflows/context-delivery.yml` installed-MCP job.
