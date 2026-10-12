# Independent delta review до inference

Дата: 2026-10-12. Основание: предыдущий `REVIEW_PATCH_RU.md`, новые bytes selector/driver/protocol/transport mapping. Статическое чтение и SHA-256, без product/model/host/test/import/compile runtime. Implementation, frozen corpus/questions/oracle не менялись. Holdout oracle не открывался, labels не раскрываются.

## Решение

**ALLOW: bounded calibration public captures, затем calibration Mini inference и final public confirmation по зафиксированному плану. Конкретного критического source-safety blocker для этого этапа в delta не обнаружено.**

Допуск не означает PASS продукта или всей frozen source-policy. Он относится к доверенному host-only experimental пути и следующей проверке настоящих публичных payloads. До evaluation inference обязательно проверить суммарный меньший primary workload ≤500 forwards; до holdout должен существовать успешный `CALIBRATION_FINAL.json` для Mini и `FROZEN_SELECTION.json`. Любой binding/pool/source defect или calibration confirmation loss — stop без retune, rescue, retry или скрытой подмены inputs.

Family-scope transport adaptation принимается как явно объявленная **pre-inference** адаптация, а не как post-hoc исправление oracle. `requested-version filtering` = **NOT TESTED**; буквальное обязательство transport version `2026.1` = **UNSATISFIED на этом transport**, не PASS. Synthetic source revision `2026.1` подтверждается только frozen bytes/hash. Итоговый review должен сохранить это ограничение независимо от качества ответов.

## Снятие прежних blocker

### 1. Driver/schema/lifetime

`run_public.py:214–324` теперь содержит main, hash-check frozen corpus/cases/calibration export, реальные fixtures/preparations, публичные calls, отдельный scoring process, provisional k, final confirmation, freeze и evaluation dispatch. Полный oracle не читается.

Schema читается правильно: corpus `['documents']`, questions `['cases']`, calibration `['cases']` и `['witnesses']`. Required facts разворачиваются через witness IDs; labels не передаются score model или host. Group documents сохраняют исходные относительные paths/content без answer annotations.

Environment выбирается через `patch.dict` в `public_call:83–85` и per-fixture snapshot:264–265; experiment opt-in не теряется при изоляции. Удерживаются настоящие services/generations в ExitStack, не replay receipt. Existing observer вызывает настоящие retrieval/selection/validator functions; название unittest.mock в import само по себе не является подменой результата.

### 2. Реальные family projects / честная версия

`groupdocs:236–246` разделяет corpus на четыре document_group, ещё три группы — diagnostic fixtures. Каждое семейство получает отдельный физический project, finite catalog и prepare:250–268. Case использует только fixture собственного document_group:269–270/295/307/313. Поэтому project identity теперь является настоящей границей семейства, а не семейным словом в поддельном MCP scope.

Pool проверяется против документов своей группы, raw_document/text/span/content SHA, generation и пустой native version:95–103; публичные sources проверяются по той же allowlist и validation snapshot:60–80. Existing original-body binding дополнительно проверяет request project identity/catalog/member и same-call receipt. Проверки callback не заменяют production guards.

**Path representation проверена статически:** `source_reference_evidence.py:53–59` берёт catalog-relative project_doc_path/source_path и отвергает absolute/parent-traversal path; это значение становится `CatalogSource.canonical_path`, затем metadata:189–195. В данном public project transport driver dictionary с относительными corpus paths и witness source_path совместим с этим code path. Не следует переименовывать эти paths в absolute для host/oracle без реальной необходимости. Абсолютный filesystem source для state/read hash и относительный canonical catalog path — разные поля.

`TRANSPORT_BINDING_RU.md` явно отделяет domain version/owner/access annotations от настоящей provenance. Native catalog действительно не имеет version: фактическое имя константы в `project_docs_catalog.py:26–29` — `DOCUMENT_FIELDS`, а не упомянутое в binding `ENTRY_FIELDS`; это терминологическая неточность, не source-safety blocker. Structural actor/action grounding по тексту остаётся проверяемым. Requested-version denial и произвольные access/consent denial этим срезом не проверяются.

### 3. Полные candidates и доверенный callback

Selector передаёт tuple(original candidates), а exclusions имеют original ordinal. `choose:93–109` сохраняет complete sequence/hash вместе с selectable pool/hash и сравнивает оба across arms. Mutation hash-check:112–113 покрывает исходную последовательность после чтения callback. Это существенно лучше прежней проверки одного pool.

Actual objects/metadata всё ещё mutable; это не immutable sandbox. В представленном callback нет write-back, indices валидируются product selector; доверенная host-only граница принимается. Callback None сохраняет весь original candidates для B1. Budget/Mini используют только существующие admitted pool objects. Downstream source guards не менялись, hook bytes прежние.

Разница B1-vs-budgeted всё ещё явная: B1 допускает исходные extras/duplicate merge через прежний downstream, Budget/Mini используют deduplicated original-admitted pool. Это допустимый original-delivery comparator, но не чистое сравнение ranker на ровно одном selectable pool. Для причинного ranking claim использовать прежде всего Budget↔Mini с одинаковыми pool/k/packing. Поздняя raw review должна отдельно отметить B1 sources вне pool и неодинаковые duplicate windows/metadata; полный capture теперь позволяет это проверить.

### 4. Scores, k и невакуозность

`score:180–202` связывает scoring input hash, case pool hash и ordered candidate row IDs с captured input. Trusted pinned scorer обеспечивает stable descending score order, product selector отвергает недопустимые indices. Не добавлены scalar cutoff или sufficiency judge.

Calibration:272–300 выбирает минимальный k из {1,2,4} только для **Mini**, по всем отдельным обязательным witnesses, уже доставленным B1. Это preservation baseline, не доказательство полноты всех исходных задач, если B1 сам неполон. Budget использует тот же k и его loss допускается как результат comparator. Оба final public payloads сохраняются; любой loss Mini останавливает этап без повышения k. Отсутствие всех B1 targets блокирует вакуозный выбор. Проверка невакуозности выполняется после calibration scoring, поэтому возможные forwards на такой неуспешной calibration всё равно входят в стоимость.

Freeze:301–304 выполняется до первых holdout captures:305–308 и фиксирует k/prompt/presentation/no citation adapter. Holdout sources могли быть подготовлены ранее, но labels не читаются и k по holdout не выбирается. No suitable k/final confirmation fail прекращает execution, а не скрыто перезапускает выбор.

Ни индивидуальные B1-delivered witnesses, ни количество выбранных документов нельзя назвать complete-answer accuracy: полнота фактов/отношений и конечные semantic answers остаются задачей raw independent review.

## Workload и условия после calibration capture

- **7 preparations**: четыре family + три diagnostic; допустимо при общем потолке8. Это заменяет прежнее уточнение5 явно и до inference.
- Main driver:54 public calls (18×3),36 host requests; calibration confirmation12 включена в54. После failure не повторять consumed run автоматически.
- `score_mini.py` ограничивает **каждый** scoring input pool до500 forwards; driver делает два scoring stages. Таким образом code не обеспечивает самостоятельно объявленные ≤500 **primary aggregate** forwards. Перед calibration inference записать точный calibration pool count, а перед evaluation inference проверить `already consumed + evaluation pool count ≤500`. Не объявлять 500+500 primary законным только потому, что это укладывается в общий потолок1000: оставшаяся квота предназначена отдельному обоснованному conditional stage. При превышении меньшего плана stop до model call, не обрезать pool.
- Provisional budget options рассчитываются на единственном scoring pass, не создают скрытых forwards/public calls. No truncation >512 сохранён; overflow — blocker, не разрешение оставить только удобные окна.
- Driver контролирует elapsed/artifact budget между операциями; subprocess имеет timeout1800, host вызовы ограничены. Это не OS memory/time sandbox: RSS проверяется scorer после forward. Консервативно остановиться, если оставшегося runtime/artifact/headroom недостаточно для очередного bounded operation.
- `score()` не перехватывает `TimeoutExpired` для чтения частичного scorer receipt; при timeout/crash ledger может не включить уже выполненные forwards. В таком случае не выдавать ledger0 за zero cost: сохранить частичный receipt/log и отметить точное число UNKNOWN с conservative upper bound размера submitted pool, если окончательный счёт восстановить нельзя. Execution и так прекращается; это ограничение failure accounting, а не разрешение продолжать с недостоверным остатком бюджета.
- Pipeline input/prompt/protocol/transport hashes должны сохраняться в evidence; run receipt уже фиксирует frozen corpus hashes и product bytes, FROZEN_SELECTION — generator prompt hash. Этот review ниже дополнительно привязывает driver/protocol/binding/scorer bytes. Изменённые после review bytes требуют delta review.

Эти условия не требуют дополнительных tests или новой модели. Calibration public captures можно выполнить теперь; model inference допускается после проверки успешных binding receipts и точного меньшего workload. Если существующий driver запускается целиком без ручной паузы, executor обязан обеспечить те же budget checks до каждого scoring stage; простое доверие per-stage500 недостаточно для aggregate claim.

## Что направить этой же роли после исполнения

Independent raw review получает все original/pool/excluded/selected receipts, group prepare+binding/state data, score inputs/receipts, calibration provisional/final/frozen selection, final public payload+validation snapshot, реально отправленные host prompts/raw outputs, ledger/errors/timings/RSS. Не только сводную таблицу или пересказ executor.

Раздельные verdicts: B1 obligation preservation, semantic completeness, actor/condition/negation relations, exact-source quotes, unsupported claims/refusals, CURRENT_CONTRACT empty-source negatives, actual project/generation/hash/access policy. Version axis и неисполненные ACL/consent checks остаются NOT TESTED/UNSATISFIED, не озеленяются правильным ответом. Никаких исправлений labels/questions после raw.

## Reviewed hashes

| Файл | SHA-256 |
|---|---|
| `docmancer/docs/application/experimental_candidate_selection.py` | `f6961f3f8df68e4fcdf0944fadbeda20e5fc118bc7081002331d68f02e89c2f6` |
| `docmancer/docs/application/_project_docs_service_part03.py` | `5e158284d8516796a977fddf56fb5afaf08c2d2bc8618ca3ba9178f9310e84bb` |
| `admission-selection-v2/run_public.py` | `2f09f375c358ef6ce6b951c24bea670d4fd3aacc77d0eb3370410f4c46de7bef` |
| `admission-selection-v2/PROTOCOL_V2_RU.md` | `4d13ca03439da16eaf599316442b0201951921786fc090f0faf5ec9451c3862f` |
| `admission-selection-v2/TRANSPORT_BINDING_RU.md` | `15d3eb02664dd7731c96a12844163b13a78f1fe31331af1d840878b2049883fb` |
| `admission-selection-v2/score_mini.py` | `c645cc7622333709f5eac9ea46a4eaae253a23ecb47cda324e92c10898560dd9` |
