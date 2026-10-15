# V3 pre-inference protocol

2026-10-12. До inference; окончательные hashes в EXECUTION_CONFIG.json/SOURCE_IDENTITY.json запишутся после product patch и preflight review, до первого runtime вызова.

## Scope и контракт

Исполняется CONTRACT_DECISION_RU.md: узкий `scalar_label_candidates_v3` retrieval-only. Default OFF и старый B1 сохраняются. Scalar-label не даёт relevance/numeric entailment/coverage/answer/edit authority. Безчисловые facets не получают bypass. Full multifacet и universal empty-source не обещаются; прежние ожидания не изменяются.

Arms: DefaultOff (env отсутствует), B1 (`policy_candidates_v1`), V3 (`scalar_label_candidates_v3`). Acquisition/SQLite/ranking/packing/presentation/final validation реальные и одинаковые; selector только read-only observer возвращает None, никакого ranker изменения. Вопросы и документы без изменений. По одному вызову каждого arm на case в той же generation/project; никаких retries и oracle-aware repair.

## Frozen inputs и точный меньший workload

Независимый C freeze: review/FREEZE.json, manifest SHA256 `bab51b5a6c3953454773b69ee6c791f75e387ca891b875b76029e8366e11b082`.

- Calibration V3CAL01–03: print_billing, 2 positives/1 semantic negative; настройки не подбираются по результатам.
- Holdout V3H01–04: directed_routes, 2 positives/2 numeric/relation/owner negatives; labels не передаются implementer/host/selector.
- OLD_PRIORITY7/OLD_PRIORITY7_9: неизменённые controls из старой five-document family.
- OLD_OWNER/OLD_COMPOUND/OLD_SETEXT/OLD_SHORTFACT: прежние исходные вопросы и та же five-document family.
- OLD_UNRELATED: прежний вопрос и исходные bytes, путь docs/store.md (не V2 fixture.md), новая project/generation identity.
- DIAG_HOLD03/05/06: прежние V2 вопросы/документы, известные diagnostics, НЕ независимый holdout и НЕ настройка.
- Q16/Q46: прежний main corpus/questions, known citation diagnostics.

Итого 19 questions ×3 = **57 public contexts**; **7 preparations** (print_billing, directed_routes, legacy_priority, ceramic_firing, tidal_ferry, main, unrelated).

**28 host endpoint attempts**: 7 new ×2 +3 numeric diagnostics ×2 +Q16/Q46 B1 ×1 +OLD_OWNER/OLD_UNRELATED V3 ×1 +4 citation attempts. Все последовательны. No readiness inference.

**0 neural forwards**: Mini/X не запускаются автоматически. Если в новых outputs обнаружится содержательная bounded-selection задача, нужен отдельный pre-inference amendment внутри остатка бюджета; без него Mini NOT_RUN. Этот этап не может подтвердить пользу Mini после исправления pool без такого исполнения.

Потолки владельца 8/80/40/500/7200s/4GiB не расходуются как цель. Failed/interrupted requests учитываются. Ни unit/private-helper/AST/compile checks, downloads/installs/providers/CI/commit/push/default/deployment.

## Два независимых эффекта

1. Все public admission arms исполняются сначала, с неизменным ранжированием и presentation; затем base host B1/V3 использует исходный HOST_PROMPT_RU.txt + тот же V2 public source schema. Host видит только final public snippets/real provenance, не pool/oracle/labels.
2. Citation adaptation отдельно: V3CAL01/V3H01 на parent V3; Q16/Q46 на parent B1. Передаются те же source IDs/text/provenance, плюс точные вспомогательные line offsets. Новый prompt/schema зафиксирован B_CITATION_CONTRACT_RU.md. Raw claims не исправляются, quotes механически извлекаются по выбранным ID/диапазонам; нет fuzzy поиска, восстановления missing facts или перегенерации. Strict source bytes и claim entailment — разные verdicts. Это generator/presentation/extraction adaptation, не ranking gain.

## Runtime и source transport

Переиспользуется runtime-product предыдущего этапа; настоящее in-process public MCP/SQLite. Не installed stdio, реальный клиент или production smoke. Отдельные family projects, finite docs-only catalogs, confirmed public prepare. Private temporary projects/storage под sticky /tmp по существующей production storage policy; artifacts под /tmp/opencode. Никакого обхода ancestor guard.

Все fixed source files записываются UTF-8 bytes без нормализации; hashes/полный raw text/spans/project/catalog/generation/final projection проверяются. Domain version не подставляется в DTO: actual unversioned, requested-version filtering NOT_TESTED. Source-policy status относится к реально проверенным operands, не всему ACL/consent пространству.

Host: существующий `openai/gpt-5.6-luna#medium`, старый single-attempt B_host_runner.py, реальный endpoint и прозрачная conversation JSON wrapper. Timeout 180s/call, runner timeout достаточный; no provider/model substitution. Billing/backend/effective sampling UNKNOWN. Raw и request receipts сохраняются сразу, ledger до каждого вызова.

## Verdicts, costs, stop

Независимо оцениваются final fact delivery, semantic answer sufficiency, soundness/relations/conditions/owner, source/hash/span/scope/state, literal citations, current empty-source contract, host refusal. Semantic entailment может быть доказано альтернативными source spans; frozen exact witness metric остаётся отдельным. Никаких дополнительных unasked требований.

Nonempty negative packet = CURRENT_CONTRACT FAIL даже при отказе хоста. Source-policy defect останавливает ветвь/runner; после двух неудачных patch→public циклов одного дефекта stop. Недоступный host или invalid preparation — blocker, no retry/substitute. При invalid citation coordinates сохранённый REJECTED, без repair.

Считаются acquisition/preparation/host requests и timings, actual submitted prompt chars/UTF-8 bytes, reconstruction artifacts. Нераспределённые process/import/tokenization/serialization/reconstruction расходы UNKNOWN, timing sums — lower bounds. Нет p95/financial advantage claims и вымышленных billing tokens.
