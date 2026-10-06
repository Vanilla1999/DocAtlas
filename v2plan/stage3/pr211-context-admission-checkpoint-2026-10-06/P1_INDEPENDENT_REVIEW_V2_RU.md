# P1 independent review V2 — REVIEW PASSED / REFERENCE PIN ELIGIBLE

2026-10-06. **Проверенный artifact snapshot можно закрепить как independently reviewed immutable reference по hashes ниже.** Это не owner-approved freeze, не P1 DONE, не разрешение P2/model download и не оценка качества replacement. True blocking defects для такого reference pin не обнаружены. R1–R5 предыдущего review закрыты на уровне артефактов; execution/control dependencies остаются.

Reviewer прочитал все 224 cases вычислительно и все 28 уникальных families вручную в RU/EN, включая все восемь новых. Старые review files сохранены. Изменены reviewer'ом только этот документ и `archives/p1-independent-review-v2.json`.

## Exact snapshot

Git HEAD: `9a7299e273edafe61095397ff10f4d776d8f97f6`. P1 inputs untracked: reference определяется **file bytes + SHA-256**, не одним HEAD и не изменяемым результатом будущего `build()`.

| Input | SHA-256 |
|---|---|
| `P1_CONTRACT_RU.md` | `e999802fbf420f3db66b6e03f4f7bfcde1242a803c5a4bb139793cd7da902fc1` |
| `p1_contract_corpus.py` | `4486f54c81e736e9179f738b2630befd61730fbf70a3953742597db36f50c891` |
| `p1_fixture_draft.py` | `aedef1f8133830d98ad4fcb2862de57ca48e678158e3ebc869224005c5eaa496` |
| `archives/p1-contract-corpus-review.json` | `fb704db29324346c6e94df5a30ecd89670f66a79e44a7a6c51cc51a3d7cd1f38` |
| `DICTIONARY_EXIT_PLAN_RU.md` | `b4264e4221f1077ffc3ecbfb5551954be89fa6f8518bc95f48a0fc2697b70c92` |
| `P1_ACCEPTANCE_DRAFT_RU.md` | `28d0d3701f20ef3e975c49d9ed63c7c10b3e5cc5a6794c2fd06319db967ff8f5` |
| `archives/p0-transition-manifest.json` | `375cdda976a6e07cea6ae6c95521ee762424c1bc5dd9626a98b37d9ec6a0f91f` |

V1 review retained hashes: `P1_INDEPENDENT_REVIEW_RU.md` = `b6c4e7e5eca18b226bf05565641d22e4cf7f5a6360143b65a770c673588f2c02`; `archives/p1-independent-review.json` = `a56707147bfd9f503a2cb6e28f5277769b60e1ea38da8278e6523d1740a3148c`.

## Offline checks / фактические изменения

`PYTHONDONTWRITEBYTECODE=1 python3` импортировал builder **без запуска его write-main**, прочитал actual JSON, сравнил с `build()`, проверил metadata/spans/peers/workloads и mutation probes. Exit 0.

- **224 unique cases / 28 families / 88 development + 136 holdout-candidate**, exact 8-lane cartesian product в каждой family.
- **176 primary required spans**: nonempty, in bounds, exact source slice, все primary source hashes совпадают. Дополнительно 8 Pydantic companion ranges/hashes проверены.
- 176 primary sources structurally eligible; 48 rejects: по 8 project/module/generation/hash/range/unsynchronized faults. Ни одного fault/outcome mismatch. Это реальные **synthetic metadata** различия, не доказательство actual indexed snapshot.
- 8 version decoys: exact hash/range, version 1.9 против 2.4, distinct source identity.
- 8 budget cases: каждый имеет 12 distinct IDs/ranks 0–11 и фиксированные body hashes, Pydantic companion, 3 named ordering scenarios, zero additional calls/retries.
- 9 independent in-memory mutations отвергнуты: missing positive witness, wrong fact ID, foreign positive metadata, duplicate language lane, missing decoy, budget requirements, forbidden relation, Pydantic companion, offline fault protocol. Inputs при probes не изменялись.

По сравнению с V1 прочитанными bytes изменены contract и builder/archive; imported draft, acceptance draft, exit plan и assertion manifest сохранили hashes. У untracked P1 нет Git patch к V1: сравнение основано на сохранённом V1 review и непосредственно прочитанных V1/V2 annotations, а не на выдуманном tracked diff. `git diff -- tests eval` пуст. В product tree остаётся **ранее существовавший** 12-line trust-block deletion в `docmancer/docs/domain/project_retrieval_intent.py`; этот review его не меняет и не утверждает. Нельзя сообщать, что весь working tree product-clean.

## R1–R5 re-review

| ID | Actual correction / verdict |
|---|---|
| R1 | `p1_contract_corpus.py:105–109`: trust sentence 2. EN `[33,86)` содержит `does not grant execution permission`; RU `[33,90)` содержит `не даёт разрешения на выполнение`. Fact obligation теперь семантически верна. **CLOSED.** |
| R2 | Added rename/module peer; foreign/owned pair; quantum unrelated; divergent negation + actual lookup-only unresolved storage; reversed subject/comparison и explicit forbidden relations (`:119–143`). Все новые families вручную проверены ниже. **CLOSED для reference.** |
| R3 | Fixed 12 distractor bodies/hashes/ranks + 3 ordering scenarios + Pydantic companion + shared-budget binding/no extra calls (`:148–159`, contract `:67–69`). Workload больше не выбирается по candidate output. **CLOSED для artifact obligations**, runner mapping pending. |
| R4 | Exact lanes и canonical equality (`:172–191`), все прежние шесть плюс три новых mutations rejected. **CLOSED для pinned builder+archive**; canonical equality не заменяет внешний byte hash/manual semantic review. |
| R5 | EN теперь `only after the lease expires` (`:66–68`), RU `только после истечения аренды`: одинаковое условие. Existing `holdout-negation` и новый divergent control сохраняют before-expiry denial. **CLOSED.** |

## Все новые families: manual RU/EN semantics

| Family | Проверка |
|---|---|
| `dev-rename` | LumenBox→VioletBox, lumen-start→violet-start, requested-module→renamed-module согласованы в source/query/request и peer IDs для всех lanes. Exact command quote; transformation/gold не должны поступать product. |
| `holdout-project` | LakeHub port 5092 релевантен, но metadata project foreign: reject. `owned_peer` существует с теми же question/body и разрешённым project. |
| `holdout-owned-project` | Та же port 5092 quote source-backed и разрешена: positive предотвращает безусловный reject по имени/body. |
| `holdout-quantum` | Pebble retention sentence ничего не говорит о quantum entanglement. Нет required witness; явно запрещены topical и original-fact coverage. Совпавшее имя не даёт authority. |
| `holdout-divergent-lookup` | Original спрашивает affirmative obligation; source и distinct caller lookup содержат `must not` / `не должен`. Quote отвечает original **отрицательно**, а не делает весь вопрос unsupported. Forbidden affirmative relation проверяется отдельно от all-false authority flags. |
| `holdout-subject-reversed` | Чужой CypressRelay=nine идёт первым; свой SpruceRelay=two — вторым, правильно размеченным. Запрещено SpruceRelay=nine. |
| `holdout-lookup-only` | Original storage не разрешён source ни в одном arm; caller lookup — command. AmberNode=amber-run quote может быть context, но `storage-location` unresolved и `original-storage-coverage` forbidden. Required command delivery в original-only — отдельная retrieval-only obligation, **не** storage/topical proof. |
| `holdout-comparison-reversed` | Source order ValleyIndex=server, затем SummitIndex=local; question order обратный. Обе exact quotes required, обе перестановки субъект→storage явно forbidden. |

Остальные 20 families также повторно прочитаны: command/condition/trust, name-only, partial+comparison, module/stale, Pebble, scope/network trust, Pydantic, hostile/offline, negation/version/budget/hash/range/unsynced. Их exact quotes, сохранение неизвестной location, hash/range rejects и injection-as-data согласованы с contract. Полный per-family checklist — в JSON.

## Leakage и границы выводов

**В V2 есть cross-split source overlap:** `dev-pebble` и `holdout-quantum` используют одинаковые EN и RU bodies. SHA-256: `09f4e4042f515ded9ac78d75e893c9ecba4f67912ba14ca547e04a679e26d294`, `ada564acc8b4cd942dfcec038527c2c1fed4a74e993f3d1a2768e7b422ce7caa`.

Family IDs disjoint, **source content не disjoint**. Это допустимая явно видимая positive/negative topical pair для контрольного reference, не blind/generalization holdout. Rename peers оба development; owned/foreign peers оба holdout. Авторы/reviewer видели fixtures. Даже остальные holdout families нельзя называть independent unseen benchmark; aggregate обязан отдельно показывать эти ограничения.

Grep в `docmancer/` по corpus import/archive names и sampled fixture identifiers (включая новые VioletBox/AmberNode/JuniperHub/SpruceRelay/SummitIndex) — 0 matches. Это narrow textual leakage check, не доказательство всех runtime imports/config/prompts. Product не должен получать family/fault/gold/forbidden annotations как inference input. Evaluation-only branch по family ID допустим только в runner.

## Не blockers reference pin, но обязательные dependencies formal freeze/run

1. **Budget runner mapping:** материализовать pinned distractors/companion как eligible sources; Pydantic companion — обязательный visible witness, не optional adornment. Зафиксировать конкретные списки IDs для `distractors-first`, `witnesses-first`, `interleaved`, место primary/companion, ranks/stage injection, current config/serializer/tokenizer и counters до candidate output. Если quotes не помещаются — preflight fail, не lowering/ceiling increase. Named permutations здесь фиксируют сценарии, ещё не полностью определённый execution trace.
2. **Offline:** protocol теперь named `optional-query-enrichment`, fault after local indexing/before enrichment, zero network/model/retries + explicit degraded status (`:160–164`). Это **описание counters**, не измеренные нули. Runner обязан сопоставить actual stage, fault injection и spies; local context не потерять. Не выдавать degraded route за successful bilingual model run.
3. **Metadata:** catalog/index ownership, version/generation/synchronized state и final citations подтверждать actual bytes/ranges. Distinct version source identities не должны схлопываться index ingestion. Hostile permissions/network/action effects наблюдать, не выводить из flags.
4. **Real controls/TD/TM:** synthetic suite дополняет реальные Pebble, Pydantic, три trust controls и typed-proof positives. Все 159 assertions/TD01–06/TM01–06 pending; нет blanket technical exemptions, fake original coverage, floor lowering, opportunistic README rehash или all-false workaround. Existing full core/advanced/adversarial/required CI/release не пройдены этим review и не сняты.
5. **P0/owner:** preparation/re-review прямо разрешены пользователем. `P1_ACCEPTANCE_DRAFT_RU.md:76` P0-DONE prerequisite остаётся вопросом owner waiver/reconciliation **для formal freeze**, не блокером текущего preparation/reference pin. P0 archival ACTIVE не становится green. Owner TD/TM/behavior/resource decisions всё ещё нужны. Новый contract `:87–89` правильно требует ceilings до **model choice/download/run**.

## Reference pin protocol / итог

Можно архивировать exact bytes с указанными hashes и обоими review generations как **REVIEWED_REFERENCE_NOT_OWNER_APPROVED**. Сверять hashes перед каждым run; изменение builder/dependency/archive требует новой версии и review. `validate()==build()` без сверки этих hashes не защищает от совместного редактирования gold и builder. Этот документ подтверждает review пригодности snapshot, а не физическую read-only защиту файлов.

**Independent review: PASSED for immutable artifact reference; blocking findings: none.** Formal owner-approved freeze/P1 DONE/P2 entry остаются pending. Ни owner approval, ни blind holdout, ни runtime/CI success не заявлены.
