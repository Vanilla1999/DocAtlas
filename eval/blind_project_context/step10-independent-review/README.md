# Independent Step10 review and token accounting

These artifacts preserve an independent review of commit
`9e2c331c45e8f9a86f809a1f4d66c43125250702`. They do not enable an experiment,
replace an installed skill, or change existing benchmark inputs and outcomes.

Start with [`token-ideas/TOKEN_IDEAS_RU.txt`](token-ideas/TOKEN_IDEAS_RU.txt)
for the dictionary-free token analysis and [`REPORT_RU.txt`](REPORT_RU.txt)
for the preceding source-dependency and MCP/direct-file comparison.

## Evidence boundaries

- New measurements are offline text/byte accounting over already-seen Step10
  development sources and saved packets. No new model calls were made to obtain
  these measurements; the original blind-260 holdout was not inspected.
- The user-reported four-question MCP/direct-file comparison is identified as
  such. Its new raw provider requests were not available for independent replay.
- Candidate instructions are analytical `.txt` files, not installed skills.
  The known configured prompt changes from 836 to 725 local text tokens. This
  does not account for all 3,068 system tokens in the separately reported run.
- Source-hash omission is an explicit change to the model-visible metadata
  contract. It is not lossless compression or an implemented host guarantee.
  Initial source text and original public references remain unchanged in the
  ablation; patch-context and source-read hashes are outside its scope.
- Ordinary JSON without visible per-source hashes measured 12,325 tokens
  against the current 14,284 on 16 saved packets, and 46,455 against 49,535 on
  one old large client result. These are result-text sizes, not whole-session
  savings or a new final-answer quality result.
- Six authorized Meridian documents contain 688 source tokens and all 19
  authored facts. Whole-scope delivery still needs its own client/answer
  evaluation; it is not a PASS of the existing minimal-selection gate.
- No new synonym dictionaries, replacement legends, short source aliases or
  positional-column encodings are proposed. Existing table layouts appear only
  as the measured baseline and as explicitly labelled diagnostic ablations.

## Files

| Directory or file | Purpose |
| --- | --- |
| `one_hop.py`, `one-hop-*.json` | Original source-exact one-hop accounting, inputs and receipt |
| `direct-file-comparison.user-reported.json` | User-provided measurements and checked arithmetic |
| `token-ideas/prompt_audit/` | Literal prompt candidates, measurements and manual 78-rule review |
| `token-ideas/transport_audit/` | Format transforms, field/text roundtrips and separate hash ablation |
| `token-ideas/workflow_audit/` | Small-corpus accounting and review of existing client workflow rules |

Historical absolute paths and timestamps in receipts are retained as provenance.
Their presence does not require those paths to exist on another machine.

## Reproduce the measurements

Use a separate clean checkout of the exact reviewed commit. The current PR adds
review artifacts after that commit; do not silently substitute the PR head for
the measured source revision. Write outputs outside that source checkout.

```bash
python3 one_hop.py --repo /absolute/path/to/clean-9e2c331c --out /absolute/path/to/new-one-hop-output
python3 token-ideas/transport_audit/audit_transport.py --repo /absolute/path/to/clean-9e2c331c --out /absolute/path/to/new-transport-output
python3 token-ideas/workflow_audit/measure.py --repo /absolute/path/to/clean-9e2c331c --out /absolute/path/to/new-workflow-output
```

Run these commands from this directory. They need Python 3.12 and `regex`,
but no model, running DocAtlas server or network. The prompt measurement script
additionally uses `tiktoken` with the repository's pinned local vocabulary; copy
both `candidate_*.txt` files into its chosen `--out` directory first. The manual
matrix builder retains its original absolute `ROOT`; adjust that path before
rebuilding it elsewhere. A manual rule matrix is not proof of model behavior.

Hashes and per-case results are stored alongside the corresponding scripts.
New timestamps can change output hashes on replay; compare input hashes, methods
and numerical results. Do not run the assertion-based scripts with Python `-O`.
