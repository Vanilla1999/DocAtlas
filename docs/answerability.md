# Answerability: observation only (experimental)

**Automatic refusal is not accepted and is no longer a supported product mode.**
The independent installed-MCP experiments in #216 and #218 found useful context
being removed by QA null predictions. A host setting is not evidence that a model
passed acceptance. This change protects source delivery; it does NOT solve the
8 strict-empty cases and must not be scored as a semantic-refusal improvement.

## Supported host configuration

- `DOCATLAS_CONTEXT_ABSTENTION=off` (default): unchanged source-native/MiniLM path,
  no QA load or inference.
- `DOCATLAS_CONTEXT_ABSTENTION=observe`: host-only predictions, no filtering or
  changes to the returned context, source bindings, continuation or authority.
- `DOCATLAS_CONTEXT_ABSTENTION=enforce`: explicit operational error
  `answerability_enforcement_not_validated`. Select `off` or `observe` explicitly.
  The error is not a semantic no-answer response and is never counted as one.

Provision diagnostic assets explicitly before serving:

```sh
python -m docmancer.docs.application.answerability_model /private/qa-model
export DOCATLAS_ABSTENTION_MODEL_DIR=/private/qa-model
export DOCATLAS_CONTEXT_ABSTENTION=observe
```

Protect the model directory and manifest as trusted host configuration. The
existing pinned model/decoder are unchanged, still not calibrated for technical
sufficiency, and never download weights or call a remote model during requests.
No semantic approval is implied by successful loading or a non-null span.
Unsupported host-declared languages yield `unknown` diagnostics with no filtering;
this is not Russian semantic support. Missing/corrupt models, excessive queries
and resource limits remain explicit operational failures, not silent fallbacks.

## Safety acceptance is not semantic acceptance

`eval/answerability_safety.py` uses an installed wheel, real SQLite, a real stdio
MCP client, exact response bytes and immutable source text. On V40 it pairs the
existing compact output with the observation-only output and requires equality.
Independent controls cover partial/absent questions, Russian unknown, off without
assets, unsupported enforcement, missing assets, input limits and invalid mode.
The unchanged V40 oracle is loaded only after responses have been captured.
The result reports both `safety_gate_passed` and `semantic_gate_passed` separately.
Observation-only may pass the first while strict-empty remains 0/8 in the second.

`.github/workflows/answerability.yml` now verifies this deliberately changed
public contract. It is named observation safety, not successful semantic refusal.
Old `answerability_integration.py`, `answerability_controls.py`, source questions
and gold are retained unchanged for historical reproduction on their original
commits. Do not run their `enforce` expectations as if enforcement were supported.
No test deletion, oracle weakening, inference threshold fitting or model change
is part of this safety change. Full current MiniLM integration remains separate.

Historical evidence is preserved:
- #216 full reader, `03481c2f`: 19/24 positive, 4/8 partial, 6/8 strict-empty;
  run 38816299289, artifact 12011820607 (FAILED).
- #218 reference reader, `e893460f`: 18/24, 6/8, 6/8; QNLI 24/24, 8/8, 0/8;
  run 39478596895 (both FAILED). Fresh/archived QA drift is unresolved.

## Next product gate

See `docs/answerability-training-contract.md` and issue #217. A technical-context
model needs independently reviewed training examples and project-disjoint
validation, including partial information. It must preserve every useful V40
answer and refuse all eight unsupported questions before deployment is proposed.
No training, new weights, Russian quality claim or enforcement approval is
included in this change. The working MiniLM compression code is unchanged.
