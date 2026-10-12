# B — coordinator follow-up and budget receipt

## Ready: later-call ceiling 18

On the coordinator's explicit assignment, `B_host_runner.py` was changed **only** at the persistent later budget check/message: `14 → 18`. Existing model identity, variant, generation/S1/R1 prompts, wrapper, settings, single-attempt behavior and all prior raw receipts are unchanged. No calls were made by B during this assignment.

Reason for extension: coordinator has executed12 approved later calls. Six remaining slots are reserved for **LLML source-span views2, SWE code baseline/pruned2, R1 hard negatives OtherAPI/unrelated2**. These are distinct comparison inputs/method checks, not retries or format repairs. The new ceiling is18 later invocations, not18 remaining; no authority to exceed it or rerun old cases. Coordinator executes serially and retains source-policy/source-span proofs independently. Code results remain separate from documentation question metrics.

Runner SHA-256 after budget-only patch: `c47072e828d0f13c1cd377ab0b83ef2895a43714a9f03f38c9daf0007ddd3152`. Prior receipts preserve their original runner hashes. Frozen common generator and S1/R1 hashes remain those in `B_HOST_RESULTS.json`.

## Actual request ledger at this checkpoint

Read12 existing `B_later_*/receipt.json`; all report EXECUTED. **15 endpoint invocations total**: readiness1 + generation8 (B0 two + later six) + S1 four + R1 two. Later used12/18; six remain unexecuted. There is no new inference/readiness attempt in this assignment.

| Existing later receipts | Count | Observed result |
|---|---:|---|
| B1 Q16/Q46 generation | 2 | both claim complete; Q16 exact citation FAIL, Q46 inspected quotes exact |
| B1 Q16/Q46 S1 | 2 | both sufficient=true/full |
| public-packet R1 Q16/Q46 | 2 | useful IDs returned; ranking on public packets, not proof of full pre-veto candidate-pool ranking |
| R1 Q16/Q46 generation | 2 | both claim complete; Q16 exact citation FAIL, Q46 inspected quotes exact |
| OtherAPI/unrelated generation | 2 | both insufficient; OtherAPI includes an exact DeliveryEngine quote, unrelated has no citation |
| OtherAPI/unrelated S1 | 2 | OtherAPI insufficient/partial; unrelated insufficient/none |

S1 sufficient=true does not override actual citation correctness. These executions are **ADAPTED**, not canonical author-model reproduction. `public` ranking receipt names must not be reported as ranking the whole acquired policy-valid pool. Independent final quality/authority/negative-contract verdicts belong to G; exact quote checks here are a narrow independent raw-text audit.

## Q16: exact-source citation FAIL preserved, no repair

Checked `B_later_B1_Q16_generation/answer.json` and `B_later_R1_Q16_generation/answer.json` against the corresponding **actual submitted source text** in each `messages.json`, not a guessed corpus sentence. Both use source ID `ev-e2fee8fbbe2755c6` and emit:

```text
Поля: `interface`, `operation`, `status`; завершение содержит `duration_ms` и `trace_incomplete`.
```

Actual source substring is:

```text
Поля: `interface`, `operation`, `status`; завершение содержит `duration_ms`
  и `trace_incomplete`.
```

For both, **quote in exact supplied text = false**. Whitespace-normalized comparison is true, explaining the error but **not granting credit**. The frozen criterion is a short verbatim quote: newline/indent normalization is not authorized. Thus both Q16 generations are **FAIL for exact-source citation**, despite valid JSON and substantively present field names. No output, quote, prompt, scoring criterion or receipt was repaired. The existing runner `validation.json: VALID` checks JSON/ID schema only; it is not a citation PASS and remains untouched.

Q46 B1 and R1 quoted strings inspected in submitted packets are exact substrings. This narrow check does not itself certify complete factual coverage. OtherAPI refusal does not excuse irrelevant public-source delivery or establish the owner-specific delivery relation; CURRENT_CONTRACT must remain separate from generation abstention.

## Transport uncertainty unchanged

Requested existing identity remains `openai/gpt-5.6-luna#medium`, OpenCode V2 stateless endpoint. Receipts expose text and measured endpoint/CLI wall time, **not** physical backend revision, provider-wire messages, tokenizer/billed usage, output cap, effective temperature/seed, or provider HTTP retry count. Endpoint request count15 is measured from receipts; provider call count remains unknown. Null token values are unknown, never zero. No model substitution, provider fallback, private corpus transfer, unit tests, repo changes, CI or nested agents by B.

## Coordinator command

Existing `later` command shape remains unchanged; only its total persistent ceiling is now18:

```sh
python3 /tmp/opencode/docatlas-review-evidence/admission-full-20261012/B_host_runner.py later --role generation --input /absolute/path/to/actual_public_only_input.json --run-id distinct_approved_run_id --coordinator-command 'explicit coordinator approval for this distinct comparison'
```

Use `--role ranking` for the two authorized hard negatives. Supply question/sources with stable IDs and full unchanged observed text, without oracle/private diagnostics. Do not execute example placeholders. Six assigned next executions are **NOT RUN at this checkpoint**; the runner is ready for coordinator commands.
