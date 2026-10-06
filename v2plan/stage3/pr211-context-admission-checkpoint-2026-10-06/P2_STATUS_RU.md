# P2: отдельный replacement prototype

**Исторический P2 report. Current implementation/next task:**
[CONTINUE_HERE_RU.md](CONTINUE_HERE_RU.md). Partial dictionary exit уже реализован;
replacement-first ordering ниже superseded owner decision.

**P2 ACTIVE / NOT DONE. P3–P7 NOT STARTED.**
Последующее owner decision: [dictionary-exit execution](DICTIONARY_EXIT_EXECUTION_RU.md).
Сначала удаление смысловых правил, затем улучшение полноты. Replacement acceptance
больше не prerequisite удаления; tests/gold/thresholds не ослабляются.
Ниже сохранён исторический статус прежнего P2 experiment, не текущий порядок работ.
Owner scope update: [same-language contract](P1_SAME_LANGUAGE_AMENDMENT_RU.md).
Обязательны RU→RU/EN→EN; cross-language результаты ниже — diagnostics.
Latest result: [real MCP paired ablation](P2_REAL_MCP_ABLATION_RU.md).
15 EN same-language cases: baseline 11/15 all facts, no-alias 9/15.
One retrieval loss; three witness-candidate relevance-qualification losses.
Candidate третья arm ещё не выполнена; это diagnosis, не готовая replacement.
P1 owner approval/freeze проверен; корпус не менялся. Product и существующие
tests/gold не менялись; прежний локальный trust-trigger diff сохранён отдельно.

## Первый experiment

- `p2_retrieval_prototype.py`: два dictionary-independent scorer — word TF-IDF
  (lexical reference) и character-trigram TF-IDF (experimental candidate).
  Никаких aliases, topic triggers, translations, product-name tables.
  Scorer получает только queries/source bytes/explicit scope; gold остаётся evaluator.
- `p2_development_probe.py`: 88 development cases, один общий multilingual pool
  из 22 источников, одинаковые exploratory top-k=5 / serialized byte cap=8192.
  Source hashes, scope, generation, synchronization, ranges проверяются отдельно;
  final quote передаётся целиком либо пропускается, а не обрезается с fake proof.
- `archives/p2-development-probe-v1.json`: source-pool/source/runner/freeze hashes,
  actual original+explicit queries, stage witnesses, first-loss и per-lane results.
- `p2_prototype_checks.py`: **5 passed** — boundaries, integrity faults, local
  degraded fallback, byte projection и Unicode extraction. Это unit controls
  прототипа, не product/release acceptance.

| Lane (для обоих scorer одинаково) | Final assigned witnesses |
|---|---:|
| EN→EN / RU→RU, original-only и with-lookups | 10/10 на каждую lane |
| EN→RU / RU→EN, original-only | 8/10 на каждую lane |
| EN→RU / RU→EN, with-lookups | 10/10 на каждую lane |

Первые потери: `dev-trust-scope` и `dev-trust-network` в обеих cross-language
original-only lanes. **First-loss = retrieved**, не qualification/prefit/final.
Char TF-IDF не восстанавливает эти witnesses. Caller lookups на языке источника
спасают их, но обязательность таких lookups нарушила бы исходный cross-language
P1 contract. После owner scope amendment эти failures не блокируют same-language
milestone; они не считаются исправленными.

## Что этот эксперимент НЕ доказывает

- Lexical reference этого первого prototype — не product baseline/alias ablation.
  Позже выполнена actual same-index baseline/no-alias пара (см. latest result);
  полная триада с candidate ещё не выполнена.
- Большинство synthetic positives имеют одинаковое literal имя в обеих языковых
  формах. Их доставка не доказывает semantic bilingual retrieval.
- TF-IDF orthographic candidate отклонён как достаточный bilingual replacement.
  Same-language replacement ещё не принят: product/negative/guard проверки впереди.
- Experimental byte/top-k caps не объявляются production token/DTO budgets.
- Fixture eligibility не равна actual SQLite/catalog/source qualification.
- Prototype не реализует topical/proof/original coverage. Name-only/hostile
  negative controls и typed-proof positives не объявлены пройденными по факту
  отсутствия authority flags. No global-false product workaround.
- Cold/warm paired p95, actual resource delta, budget-pressure workload, actual
  optional-stage failure и required real controls ещё не проверены.
- Holdout не запускался; model downloads/network/lockfile changes отсутствуют.

## Следующий bounded шаг

1. Следовать owner same-language scope: сравнить actual product baseline,
   no-alias ablation и independent candidate на одном snapshot, отдельно для
   RU→RU/EN→EN и original-only/with-lookups. Не выбирать модель автоматически.
2. Проверить same-language first-loss, paraphrases, negatives и guard behavior;
   выбирать дальнейший scorer по реальным потерям. Prototype positives сами
   по себе не являются разрешением удалить product aliases.
3. До acceptance выполнить same-snapshot actual product baseline/no-alias/
   candidate, bind production budgets/serializer/tokenizer и guard controls;
   затем frozen holdout и ≥3 model-dependent final repetitions.

P2 здесь начат, не закрыт. Existing red release gates и wheel portability defect
остаются отдельными задачами. Ни commit, ни push, ни merge не выполнялись.
