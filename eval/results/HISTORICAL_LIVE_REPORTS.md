# Historical live model reports

The committed reports below are historical evidence. They do not establish
current PR acceptance and are not regenerated or resealed by the deterministic
archive test. New current reports must pass the current evaluator fingerprints.

| File | Exact committed byte SHA256 | Provenance |
| --- | --- | --- |
| `eval/results/task21_tool_choice_gate.json` | `78f41a7d92a0d115ee2e525268d1a6468684eb615da539b91bc5d0edbd362bc2` | Recorded in commit `7ec72d6684321407838317a682fb1c26b89ca53e`; no subsequent report change. |
| `eval/agent_developer_v1/results/model-benchmark.json` | `3980c26740edf11feab20c8db669595048732791fb3ab1d95ac9e926b09b2d3b` | Trajectories and usage recorded in `7ec72d6684321407838317a682fb1c26b89ca53e`; one fingerprint field later changed in `5a36a152bf0258997e4b5fbdcde9eb014fc0ee94`. |

The Task 21 report records 20 scenarios × 3 repeats, model `gpt-5.6-luna`,
`medium` reasoning, first-tool accuracy 0.95, and historical schema fingerprint
`sha256:44577591d79a3b2d`. It predates the complete tool-choice contract fingerprint
and cannot be reused as evidence for current schemas, guidance or scenario oracle.

The Agent report records 11 executed tasks, **0/11 passed**, no infrastructure
errors, no false support and no forbidden-source contamination. Its public task
fingerprint is `517853c15d0a234307199ccd4dfdbd8cb8f8dee56f7a1e12bee247a02634a9b8`.
At the original recording commit, its oracle fingerprint was
`e7bba83f624d9f382486275a8b9f8ab50bf63b301a18bc3fd78530626d21854c` and report byte
SHA256 was `16a4ce2c1de5ca6aedea7b248cd98385d44fa5ce4ab8bc60b04da5406927daef`.

Commit `5a36a152bf0258997e4b5fbdcde9eb014fc0ee94` changed only
`oracle_contract_sha256` to
`666318e529a8ea8afcf30b471e2d2744723680c3c697538b9719ec9b70afe306`. This is a
historical fingerprint-only reseal, **not evidence of another model execution**.
The archive retains those exact committed bytes and explicitly checks that the
strict current Agent report validator rejects that stale oracle binding.

The archive exception recognizes only the two exact byte hashes above. Different
report bytes must satisfy current fingerprints and existing model/roster/quality
checks. Live Task 21 reuse now requires the current complete contract: public
schemas, installed guidance, full scenario inputs and expectations, repeats,
thresholds and evaluator source. No provider calls are made by archive auditing.

## Reproducing the historical first-divergence atlas

`eval/agent_developer_v1/results/first-divergence-oracle-5a36a15.json` preserves the
exact oracle file from the historical reseal commit. Its byte SHA256 is
`d7f8b7f2ec9f6484edfaf01865d8b42d8bfc6caad4804530131b6c9f17d6ec7e`; its canonical
JSON fingerprint is the retained `666318e5…afe306` binding above. The historical
atlas builder uses this snapshot by default and rejects a supplied task/oracle
corpus whose fingerprints differ from the supplied report. It does not silently
substitute today's changed expectations into an old run.

The existing first-divergence JSON and generated analysis remain byte-identical.
The atlas describes the already committed historical analysis using the resealed
oracle; the snapshot does not establish a new run on that oracle. Current Agent
gates continue to read `expected_trajectories.json`, independently of this archive.
