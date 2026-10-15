# C: consolidated STATIC execution gate V3

2026-10-12, до первого runtime. Прочитаны actual two domain files, обновлённые A_IMPLEMENTATION_RU.md/V3_PRODUCT.patch, run_v3.py и EXECUTION_CONFIG.json; повторно сверены baseline diffs и previously accepted B identities. Только source reads, текстовый diff, `jq` обработка сохранённых manifest и `sha256sum`. **Runtime/product/adapter imports/tests/compile/AST/models/host не запускались.** Допагенты не создавались; inputs/oracle не менялись и holdout labels implementers не раскрывались.

## Exact gate verdict

**APPROVED_FOR_FIXED_NARROW_PRE_INFERENCE_EXPERIMENT — NO_MANDATORY_STATIC_BLOCKERS_FOUND.**

Ранее перечисленные обязательные A-SOURCE-EDGE-01, RUN-AUTH-01 и RUN-FREEZE-01 закрыты по текущему source/identity comparison. B v3-2 static acceptance сохранён. Reviewer допускает только уже разрешённый координатору frozen workload: **7 preparations / 57 public context attempts / 28 host endpoint attempts / 0 neural forwards**, при сохранении stop/no-retry/no-substitute правил. Это **ограниченный pre-inference gate**, не product PASS, не обещание завершения всех planned calls, не отдельное расширение runtime authorization, не default/release/full multifacet approval.

Если required guard/prepare/host/citation binding блокирует выполнение, записывать фактические attempts и BLOCKED/UNKNOWN/NOT_RUN, не добирать план заменами cases/retries. После outputs — отдельный независимый quality/source/semantic review по исходному oracle.

## Точные проверенные identities

| Operand | SHA256 |
|---|---|
| EXECUTION_CONFIG.json | `8284ba02cc3a175657296a06a89115fa3621931bc6261f5d0b9d54e1af0a9f36` |
| run_v3.py | `c87b599bc7547c093b0182e0efea82723fa87fdd5d92b797b9caa61c99d3c995` |
| V3_PRODUCT.patch | `6bf646832abfa7e9ae225504565a0377c6235322a5818f6684f054dc642d2d54` |
| A_IMPLEMENTATION_RU.md | `d23fd42cd9d02da11d411934d96887fb3733c3f922468c5bc4c4e1d2a0fe5a2d` |
| actual original_body_discovery.py | `23d8bcb2c45b6007b2bfbe2947ef58a68e107f409761fd16c2fb4df496ecd20c` |
| actual ordinary_body_context.py | `a5523cf48dfa280960eb05f8d64e2af330923022a54862ee42e242e0d9a3eb3b` |
| citation_adaptation.py | `ff5be53e7358e56f9bee119833bb2014348f1c19740e4068ba291fcedd3915ed` |
| B_CITATION_CONTRACT_RU.md | `53083e9e9118a436859ac162a3624ff3fac897ce73efcd94fed0dee88bf33cd5` |
| PROTOCOL_V3_RU.md | `a2c0bee43e569626f508ea05c5fa6238ab748391ed4eece14e528ac2036bd821` |
| EXECUTION_CORPUS.json | `a7fcf818dfd5580f45e77b17045e541924dbaab323771744756d199865aa2a86` |
| review/inputs/cases.json | `d5fa6155f0c41af71222145278a635c79122cf5761f2d705524850626b15a0bb` |
| исходный review/FREEZE.json | `bab51b5a6c3953454773b69ee6c791f75e387ca891b875b76029e8366e11b082` |

**Все 40 execution frozen_files hashes сверены с actual bytes: совпадают. Все 17 hashes исходного C FREEZE сверены: совпадают**, включая private oracle files без публикации их содержимого. Новый review не добавлялся в исходный corpus/oracle freeze и не подменяет его. Config SHA независимо совпадает с указанным координатором; self-reference в frozen_files отсутствует.

Production serializer `model_visible_projection_helpers.py` дополнительно повторно проверен: SHA256 `636128154d92170ac6e9623747cd1117366e64847e3f384a4447ca579884edfd`, совпадает с accepted B review. Он не отдельная строка текущего 40-file manifest; это recorded identity limitation, а не обнаруженный drift. Gate не утверждает transitive hash pinning всех Python dependencies/модулей/host backend. Без последующих edits текущие прочитанные operands согласованы; изменение source/helper/config до исполнения требует нового identity checkpoint.

## Закрытие A-SOURCE-EDGE-01

В `ordinary_body_context.py:304–311` source pair index теперь строится по **полному immutable raw document**. Соседние maximal sign/operator tokens с обеих сторон больше не исчезают за acquired window edge. В `:320–330` local masked pair переводится в absolute document coordinates, полностью содержится в existing body block, должна совпасть по всем fields с full-raw pair и exact raw substring.

Следовательно прежняя статическая signed-scalar иллюстрация теряет full-raw match и новый fallback закрывается. Full raw scan используется только для syntax veto/context: пару вне разрешённого блока нельзя превратить в witness; delivered block/window/native binding не расширены. Никаких новых source reads/expansion/project-wide contribution grants не добавлено. Возможный консервативный false negative из neighboring structural block и стоимость полного raw scan честно указаны A; runtime perf не доказана.

Обновлённый actual-vs-baseline diff обоих файлов соответствует обновлённому V3_PRODUCT.patch. Default/B1 numeric/ordinary branches и source/native/owner/unresolved eligibility остаются статически прежними. Новый helper всё ещё V3-only fallback после старого B1 candidate отсутствия. Query maximal-token coverage/unsigned decimal/comma правила не изменены. Witness остаётся unassessed; caller coverage_credit=False и source-policy qualification gates сохранены. Это закрытие конкретного статического дефекта, не новый исполненный negative PASS.

## Закрытие coordinator guards/freeze

- **RUN-AUTH-01:** run_v3.py:124–129 требует все три `answer_supported/answer_available/edit_ready is False`, затем SOURCE_POLICY_DEFECT stop. Старый reused integrity больше не единственный authority guard.
- **Null sources:** `sources():156–160` нормализует null/отсутствующее поле в empty для base-host packet без fabrication. Исправленный B отдельно принимает explicit null/list согласно своему контракту.
- **Envelope/source authority/duplicates/lines:** `extra_integrity:48–78` сверяет production-shaped envelope operands, source_of_truth, missing/duplicate evidence IDs и допустимый declared snippet line range внутри parent reference. Вместе с reused integrity проверяются raw equality/hash/path/project/generation/unversioned/snapshot projection. Не объявлять это полным ACL/consent proof.
- **Pool project identity:** observer :100–105 добавляет actual local project ID к source/raw/hash/generation/span checks; возвращает None, не меняя selector membership/ranking.
- **Preparation guard:** :206–212 проверяет finite expected/indexed path equality, отсутствие excluded/failed/unexpected, content hashes и реальный catalog hash до public captures. Partial/mismatched preparation останавливается; не маскируется под semantic empty-source.
- **RUN-FREEZE-01:** :168–173 отвергает пустой freeze и проверяет 40 actual files до загрузки reused v2/host (:176–177), а также до preparations/public/host. Top-level driver имеет только stdlib setup; product imports перенесены за identity gate. Adapter import происходит позже и его bytes уже проверены в общем gate.
- **Receipts:** consumed run запрещает повтор; ledger сохраняется до product/host attempts. Source/state defect и UNKNOWN host completion останавливают driver без retry/substitution. Transport raw/model messages/request receipts сохраняются existing single-attempt helper; schema/semantics не выводятся из EXECUTED.

Line/envelope guard на необычной projection может быть консервативным и остановить корректный, но несовместимый packet: при этом нужен recorded blocker и отдельный checkpoint, не inline repair. Guard freeze покрывает выбранные operands, не защищает от произвольного Python-кода/изменения файлов после проверки.

## Workload и сохранение независимых ожиданий

Config/protocol по-прежнему задают 19 questions ×3 DefaultOff/B1/V3 =57 contexts, семь isolated projects. Base host: 7 synthetic ×2 +3 known V2 numeric ×2 +Q16/Q46 B1 ×1 +OLD_OWNER/OLD_UNRELATED V3 ×1 =24; citation=4; total28, neural0. Ceilings8/80/40 не являются разрешением дополнительных calls. Planned counts не заменяют observed ledger.

Citation fixed IDs и parents сохранены **до outputs**: V3CAL01/V3H01 parentV3; Q16/Q46 parentB1. Base и coordinate contract используют один captured parent public source packet, не новый public read, gold spans или oracle-fed source rescue. B byte identities ровно previously accepted v3-2; остаются exact-whole-span compatibility и exception taxonomy ограничения из CITATION_FINAL_PREFLIGHT_RU.md. Citation REJECTED/insufficient не считается positive completeness PASS.

Все frozen вопросы/bytes/negative empty-source expectations сохранены. Known V2 HOLD03/05/06 — diagnostics, не новый holdout/калибровка. Nonempty negative остаётся CURRENT_CONTRACT FAIL даже при правильном host refusal. Semantic sufficiency, exact-witness delivery, literal citations и source-policy/state — разные оси; raw full-document metadata не даёт missing-text credit. Scalar-label не доказывает единицу/условие/actor relation; nonnumeric facets всё ещё могут отсутствовать. Нельзя расширять gates или менять oracle после outputs ради PASS.

Default OFF/old B1 branch preservation пока статическое; fresh limited public parity ещё предстоит, не full regression. Experiment не доказывает full multifacet, universal relevance/empty-source, arbitrary numerical reasoning, requested-version filtering, consent/ACL или installed-stdio/client/production quality. Mini/X отсутствуют; model-selection amendment требует отдельного основания и freeze.

## Передача координатору

**Обязательных pre-inference blockers по текущим identities не осталось.** Можно выполнять только уже зафиксированный и разрешённый узкий 7/57/28/0 experiment. При изменении patch/config/runner/adapter — этот gate не переносится автоматически. По завершении или interruption передать raw/ledger/receipts/bindings для отдельного final review; никакие результаты здесь заранее не обозначены PASS.
