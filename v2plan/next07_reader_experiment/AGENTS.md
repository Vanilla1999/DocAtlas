# External-reader pilot: narrow test-only exception

Read ../NEXT_07_READER_REVIEW_AND_RUN_RU.md before executing this pilot.
The user authorized review and an experiment with an external reader, not a
runtime LLM. Parent restrictions on retrieval, source guards, public MCP schema,
production/main and N10 still apply. These host callbacks are NOT MCP tools.

Use the published next07_reader_experiment package, not the old unpushed
next07_reader_trial ZIP. The current pilot is 10 cases x 2 arms x 1 repeat (20
sessions, <=40 model requests). Do not silently change sample size or provider.
An ordinary push executes technical/native checks only. Live requires explicit
model selection and an authorized provider run. Never print credentials.

The local coding agent is the operator, NOT the model under test. Isolate reader
sessions from repo/fixtures/rubrics/working memory. A separate reviewer assesses
visible-source support, identity, conditions and honest uncertainty. Successful
exact quote binding and green CI do not establish semantic correctness.
