# Strong planner/answerer exploratory control

## Scope

This is an exploratory same-researcher control requested after the weak
`Qwen/Qwen2.5-1.5B-Instruct` pilot. It is **not** an independent acceptance
holdout and is not reproducible as a pinned API model run.

Planner/answerer: **GPT-5.6 Sol**, the interactive model in the research chat.
No Qwen, MPNet, BGE, embeddings, reranker or model is added to DocAtlas.

Nine new questions were prepared over source files not used in the earlier
Typer/HTTPX/M1.5 or Rust/FastAPI/uv pilot: Vue English/Russian documentation,
Django QuerySet documentation and Kotlin coroutines documentation. The source
blobs and questions were frozen before the real handler run.

The real DocAtlas handler ran four retrieval conditions with the normal lexical
path and current packing:

- **O**: original question only;
- **A**: one GPT-5.6 Sol lookup formulated without a language profile;
- **B**: one GPT-5.6 Sol lookup targeted to the source language indicated by the
  profile;
- **E**: one generic bilingual RU+EN lookup without numeric shares.

`answer_supported` and `edit_ready` stayed false in every run. Canonical/budget
audits passed. No experimental neighbor assembly was used.

## Frozen language profiles

The real profiler produced the expected routing hints:

- Vue RU scope: RU 58.1%, unknown 41.9%, query language `ru`;
- Vue EN scope: EN 70.2%, unknown 29.8%, query language `en`;
- Vue mixed scope: EN 41.7%, RU 23.6%, unknown 34.7%, query languages `en, ru`;
- Django scope: EN 78.1%, unknown 21.9%, query language `en`;
- Kotlin scope: EN 75.9%, unknown 24.1%, query language `en`.

These are classified-prose shares, not a universal language census.

## Retrieval result

There are eight answerable questions and one unanswerable control.

The frozen mechanical checker reported complete evidence as:

| Condition | Mechanical complete / 8 |
|---|---:|
| O | 2 |
| A | 3 |
| B | 4 |
| E | 3 |

Manual semantic review found one checker false negative on the Kotlin
`withTimeoutOrNull()` question: the final packet contains the exact sentence
that it returns `null`, but Markdown delimiters break the naive substring
assertion. Without changing the frozen task, semantically sufficient packets are:

| Condition | Semantically sufficient / 8 | Correct abstention / 1 |
|---|---:|---:|
| O | 3 | 1 |
| A | 4 | 1 |
| B | **5** | 1 |
| E | 4 | 1 |

Using only the public final evidence packets, GPT-5.6 Sol can answer every one of
those sufficient cases correctly with evidence IDs and abstains on the single
unanswerable case. This answer review is same-researcher, not blind.

## Where the profile helped

The clearest positive case is deliberately cross-language:

> **English question → Russian-only Vue computed-properties source.**

Original-only and the English lookup both return no usable evidence. A generic
bilingual lookup also fails. With the profile-targeted Russian lookup:

`Vue вычисляемые свойства кэшируются реактивные зависимости вызов метода`

DocAtlas returns the Russian canonical paragraph saying computed properties are
cached based on reactive dependencies. This is a direct A→B gain attributable
to changing the lookup language.

The opposite direction also matters: a Russian Vue question over an English-only
watchers source succeeds in A, B and E. GPT-5.6 Sol already translates the
technical intent well without being told the corpus language, so the profile has
no additional benefit there.

Thus the strong-model result is not “profile always helps”. It is:

- a strong planner can already bridge many RU↔EN queries without a profile;
- a source-language hint can still rescue some cases where the planner would
  otherwise search in the user's language;
- generic bilingual stuffing is not equivalent to a targeted source-language
  query.

## Remaining failures are not planner-language failures

- The mixed Vue caching question retrieves `watchEffect` material instead of the
  Russian computed-caching section in all conditions. This is ranking/scope
  competition after a reasonable query.
- Both Django questions fail in all conditions even with precise English queries.
  The relevant text exists in the source but the final packet is filled by other
  `select_related`/JOIN fragments. This is a retrieval/chunking/packing problem,
  not a translation problem.
- The Kotlin timeout case exposed a flaw in the experiment's string matcher, not
  in DocAtlas retrieval or in the answerer.

## Interpretation

The weak-Qwen pilot and this strong-model control are compatible, not
contradictory. Qwen frequently damaged the query intent, so the language hint
could not show a benefit. With a stronger planner, intent preservation is much
better and a genuine profile-specific cross-language gain appears.

However the observed incremental effect is only one additional answerable task
in this small same-author set (A 4/8 → B 5/8 after semantic review). That is a
useful signal, **not** evidence for product activation.

The next product-relevant work should focus on two things separately:

1. define a robust contract for planner query preservation and source-language
   hint delivery, then evaluate it with the actual target coding-agent;
2. fix/measure retrieval and packing for cases like Django and mixed-source Vue,
   because a perfect translation alone does not solve them.

Keep the profile optional/hint-only until a larger independently reviewed
A/B/E dataset demonstrates a repeatable gain.