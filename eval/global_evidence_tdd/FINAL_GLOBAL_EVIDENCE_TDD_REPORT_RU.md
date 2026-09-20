# PR #194 — Global Evidence TDD: финальный результат

Дата: 2026-09-20

## Статус

**candidate_rejected**

Цикл T0–T9 выполнен как причинный TDD/validation цикл. Development candidate показал системный прирост на открытых regression-наборах, но независимый source-separated transfer24 обнаружил реальную потерю ранее достаточного ответа. Согласно заранее зафиксированному T9 gate candidate не принимается как общий rollout и production-изменения этого цикла откатываются к `ef39e12ab60fd69f8052079847d9e0ca24a843b4`.

После открытия transfer24 production не донастраивался.

## Что было проверено до независимой validation

### Focused / core parity

Run: `35469202972`  
Artifact: `10592112447`  
Digest: `sha256:0c24fec20ed5d26454e8620de435b5d51e4f7e70e167c2c3343b999ddb95b2e5`

- focused global-evidence gate: **74 passed**;
- full offline core baseline: **22 failed / 4103 passed / 10 skipped / 622 deselected**;
- candidate: **22 failed / 4161 passed / 10 skipped / 622 deselected**;
- failed node IDs: **identical**, candidate-only failures: **0**;
- module-size debt: одинаковый единственный offender, старый `_project_docs_service_part03.py` = 1147 строк.

Это доказывает отсутствие нового core/node-ID регресса в development candidate, но не заменяет переносимость.

### Development question gate

Run: `35469593733`  
Artifact: `10592502225`  
Digest: `sha256:259e2a2fa110bfdd4d9425263a41f1a286029eaf991c51374011332a64143aa1`

- Target30: visible packet changes **0/30**;
- external80 fully-answerable: **31/48 → 34/48**;
- wins: `httpx-01`, `ruff-05`, `starlette-01`;
- losses: **0**;
- safety violations: **0 → 0**;
- Generic30 changed seven visible packets. Manual review of the three previously sufficient changed packets (`G03 lookup`, `G13 lookup`, `G30 lookup`) confirmed preservation of the requested evidence; `G16` gained the intended current-vs-history authority rule.

Development gate therefore satisfied the plan's local three-family criterion. These are exposed regression/development sets and are not independent transfer evidence.

## Независимый transfer24

Frozen before candidate execution:

- 24 root-only tasks;
- 4 new project families: Click, HTTP Core, ItsDangerous, SQLModel;
- 16 fully-answerable / 4 partial / 4 unanswerable;
- pinned upstream commits and blob SHAs are in `source_plan.json`;
- questions/gold/source-plan were committed before the first candidate execution;
- no lookup queries;
- public limits remained 800 admission tokens / 3 sources.

First workflow run `35473691226` failed during **baseline ingest before candidate execution** because pinned `.rst` inputs were passed to a Markdown-only fixture helper. No candidate output was opened. The retry changed transport only: non-Markdown source bytes were materialized under deterministic Markdown fixture aliases; questions, gold, source commits and production candidate were unchanged.

Transfer retry run: `35473791525`  
Artifact: `10593137200`  
Digest: `sha256:c3f8ee2162439fc9a9c64312b6b71fb04e40c7a27dd0c526fb642862295a1b51`

Automatic frozen result:

- baseline supported: **7/16**;
- candidate supported: **7/16**;
- win: `T24-httpcore-03`;
- loss: `T24-click-02`;
- safety: **0 → 0**;
- decision: **rejected**.

### Manual review of the loss

`T24-click-02` asks for the three capabilities listed by Click.

Baseline returns one source with all three literal facts:

- Arbitrary nesting of commands
- Automatic help page generation
- Supports lazy loading of subcommands at runtime

Candidate returns `status="insufficient_evidence"` with **0 sources**.

Therefore this is not scorer strictness or a paraphrase mismatch: it is a real loss of requested evidence on an unseen family.

The transfer win `T24-httpcore-03` is also real: candidate returns the target-extension paragraph containing forward-proxy, CONNECT tunneling, and OPTIONS-* cases. It does not compensate for the Click loss under the predeclared no-loss gate.

## Решение по production

Не делать post-holdout tuning. Не выбирать подмножество fixes после просмотра Click-loss. Не добавлять Click-specific rule, synonym, threshold relaxation, reranker, embeddings or model.

Global-evidence production files are restored byte-for-byte to the pre-cycle `ef39e12...` versions. Candidate-only test/workflow/patch-transport scaffolding is removed. Frozen transfer inputs and this report remain as evidence.

Это означает:

- локальные причинные гипотезы T1–T7 получили полезные RED→GREEN и development evidence;
- combined rollout **не принят**;
- общий перенос на неизвестные проекты **не доказан**;
- следующий цикл, если он будет, должен начинаться с нового design/root-cause анализа Click-loss, но **не использовать transfer24 как holdout для настройки того же candidate**.

## Ограничения

- Independent transfer24 был составлен и оценён тем же исполнителем; независимый второй reviewer не заявляется.
- Literal transfer scorer консервативен, поэтому changed cases требуют manual review. Для единственного loss такой review выполнен и подтвердил фактическую потерю.
- Reader inference не запускался: этот цикл относится к доставке evidence.
- Общий repository CI исторически остаётся красным на старом долге; это не скрывается новым статусом.

## Финальное состояние цикла

`candidate_rejected_transfer_loss_confirmed_production_rolled_back`
