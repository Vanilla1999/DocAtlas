# Pinned Kotlin documentation smoke

Task 14 provides a bounded opt-in smoke for the exact reported query. It uses the official
`Kotlin/kotlinx.coroutines` repository pinned to tag `1.8.1`; it never follows rolling `master`.

Run the orchestration and artifact validation offline first:

```bash
DOCMANCER_HOME="$(mktemp -d)" python scripts/kotlin_live_smoke.py \
  --mode fixture --timeout 180 --output /tmp/kotlin-smoke-fixture.json
```

With outbound access, run the real three-tool workflow in an isolated home:

```bash
DOCMANCER_HOME="$(mktemp -d)" python scripts/kotlin_live_smoke.py \
  --mode live --timeout 180 --output /tmp/kotlin-smoke-live.json
```

The script requires `prepare_docs` to return a job id within one second, polls responsive
`docs_status`, and repeats `coroutines launch async example with code` through
`get_docs_context`. The output is a small sanitized artifact: it contains identity, timing,
terminal status, and citations, but no downloaded page content or credentials.

The machine schema is `eval/kotlin_smoke/artifact.schema.json`; the committed
`eval/kotlin_smoke/task14_fixture.json` proves the offline artifact contract only.

A live network failure is diagnostic evidence, not Task 09 closure. After a successful pinned
run, commit only the sanitized JSON artifact in a separate evidence-only PR.
