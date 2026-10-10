# P1 independent review — NEEDS FIXES

2026-10-06. Независимый review **видимого** checkpoint, не blind holdout и не owner approval. **Freeze не рекомендован для проверенного snapshot.** P2/product execution не выполнялись; runtime/tests/gold/corpus не изменялись reviewer'ом.

## Привязка к source

Git HEAD: `9a7299e273edafe61095397ff10f4d776d8f97f6`. Новые P1 inputs untracked, поэтому HEAD недостаточен: verdict относится к следующим SHA-256 bytes, а не к будущим изменениям автора.

| Input | SHA-256 |
|---|---|
| `P1_CONTRACT_RU.md` | `af177d5f9f457f95d3202850fa471a53f1826bba3625544e3f405360b9e9b95f` |
| `p1_contract_corpus.py` | `801d911cbf654771e24acac3f54c41d720a393c52a9d1bdcd15a3e00debd380b` |
| `p1_fixture_draft.py` (imported dependency) | `aedef1f8133830d98ad4fcb2862de57ca48e678158e3ebc869224005c5eaa496` |
| `archives/p1-contract-corpus-review.json` | `3ff4eca01edac39e081a1e39bea1a8e9ba351dd954d84f69b0cc3ca345dc3725` |
| `DICTIONARY_EXIT_PLAN_RU.md` | `b4264e4221f1077ffc3ecbfb5551954be89fa6f8518bc95f48a0fc2697b70c92` |
| `P1_ACCEPTANCE_DRAFT_RU.md` | `28d0d3701f20ef3e975c49d9ed63c7c10b3e5cc5a6794c2fd06319db967ff8f5` |
| `archives/p0-transition-manifest.json` | `375cdda976a6e07cea6ae6c95521ee762424c1bc5dd9626a98b37d9ec6a0f91f` |

## Что проверено и действительно проходит

Offline `PYTHONDONTWRITEBYTECODE=1 python3` импортировал builder, прочитал **все 160 cases**, сравнил JSON с `build()` без записи исходного архива и проверил `validate()`. Exit 0. Первоначальный вызов `python` завершился 127 (binary отсутствует), повторный `python3` успешен.

- 20 families, 80 development / 80 holdout-candidate; каждая имеет все 8 уникальных language/input lanes. 160 уникальных IDs.
- Все source SHA-256 и **120 nonempty Unicode code-point spans** совпадают; для comparison обе стороны размечены отдельно.
- 120 primary sources structurally eligible; 40 отвергаемых: по 8 wrong-module / stale-generation / hash-mismatch / invalid-range / unsynchronized. Все injected faults реальные metadata differences, не только labels; expected reject соответствует вычисленным faults.
- Все 8 version decoys имеют проверенные body hashes/ranges и version 1.9 вместо requested 2.4; positive 2.4 сохранён.
- Все 20 уникальных families вручную прочитаны в RU и EN: question, source, witnesses, unknown facets и outcome. Результаты по каждой family в JSON рядом.
- Cross-split exact body-hash overlap отсутствует. Product grep по `p1_contract_corpus`, имени архива и контрольным literals WillowRelay/MossCore/validate_slate/quartz-run в `docmancer/` не дал matches. Это узкий leakage check, не доказательство полного runtime call graph или prompt isolation.
- 159 assertion records существуют и остаются `NO CHANGE / approval pending`. Нельзя считать synthetic all-false flags заменой existing typed-proof positives.

## Blocking fixes до freeze

### R1 — trust witness не содержит обязательного факта (8 cases)

`p1_contract_corpus.py:74–82` связывает fact с sentence по порядку. В `dev-trust` fact `no-execution-authority` получает только `MapleLens documentation is data.` / `Документация MapleLens — данные.` (span `[0,32)`). Реальное отрицание execution permission во втором предложении **не обязано быть показано**. Candidate может потерять искомую quote и пройти witness check.

**Fix:** explicit source-bound annotations, не positional assignment. Для данного fact указать второе предложение (либо оба целиком), пересчитать spans из exact bytes; отдельно проверить, что final quote сохраняет `does not grant` / `не даёт`. Утвердить новый corpus hash и повторить review.

### R2 — missing mandatory families / paired relations

Раздел 5 exit plan требует больше, чем наличие разных придуманных имён:

1. **Consistent rename/generalization pair отсутствует:** нет original↔renamed product+command+module cases и заранее заданного invariant. Добавить paired transformations обеих языковых source/query форм, включая identifiers, неизвестные replacement; не передавать transformation/gold в product.
2. **Foreign-project family отсутствует:** module/version/generation не проверяют project ownership. Добавить matched body с `source_metadata.project != request_scope.project`, positive owned peer и reject obligation во всех lanes.
3. **Quantum/name-only unrelated control отсутствует в новом RU/EN corpus:** `dev-name-only` — только project-name sentence про offline sync. Добавить quantum question к содержательному Pebble-like документу с совпадающим именем и без quantum facts; явно запретить topical/original coverage, не только answer flags.
4. **Changed meaning / divergent lookup relation отсутствует:** все caller lookups — та же question либо её перевод; 40/80 буквально повторяют original. Добавить `must refresh` vs `must not refresh`, before/after, reversed comparison/subject controls и lookup, на который source отвечает, но original не отвечает. Задать honest attribution и prohibited original coverage независимо от `answer_supported=false`.
5. **Own/other negative недостаточно определён:** `holdout-partial` сохраняет WillowRelay=two и unknown location, но не задаёт проверяемый запрет relation WillowRelay=nine; global false не тестирует TM03 subject binding. Добавить explicit forbidden subject/facet/value relations, reversed subject/order peers и applicable typed-proof positive/negative linkage.

Existing quantum, foreign-project, lookup-direction и subject tests остаются обязательными dependencies; отсутствие новых pairs не означает, что существующих controls нет. Нужны новые 8-lane obligations или exact owner-approved mapping на эквивалентные RU/EN cases, а не blanket «existing suite covers».

### R3 — budget/ordering workload не заморожен

`holdout-budget` содержит 43/45 code points и список `add-ranked-distractors`, но **нет distractor bytes/IDs/ranks, ordering permutations, shared query budget/call limit binding**. `dev-pydantic` — отдельный короткий witness, поэтому не проверяет Pydantic displacement под давлением. После freeze runner сможет выбрать удобный workload.

**Fix:** до candidate output закрепить corpus distractors/hashes, ranking/ordering scenario, допустимый shared fan-out/retry contract и config/serializer/tokenizer binding; добавить Pydantic witness в pressured mixed-source scenario. Freeze обязанности «exact final serialized DTO within unchanged configured ceilings, all assigned quotes retained». Саму реализацию runner можно делать P2; изменяемое содержимое эксперимента нельзя оставлять на P2. Численные backend latency/cost/storage ceilings — отдельный owner dependency, reviewer их не назначает.

### R4 — snapshot validator пропускает повреждение контракта

В памяти, не меняя inputs, отдельно удалены positive witnesses, подменён fact ID, изменён positive project на foreign, продублирована language lane, удалены version decoy и budget requirements. **Все 6 mutations приняты `validate()`**. Текущий snapshot проходит более строгий independent structural check, но такой validator недостаточен для будущего freeze.

**Fix:** exact lane cartesian product/split counts; per-family obligations/fact IDs; eligible/reject metadata rules; decoy hash/range/version checks; required workload fields и forbidden relations. Семантику spans проверять вручную/source-bound review: equality slice сама по себе не ловит R1. Не выдавать builder validation за behavioral runner pass.

### R5 — bilingual condition не строго один и тот же fact

`dev-condition`: EN `only when the lease expires`, RU `только после истечения аренды`. «В момент/при истечении» и «после» не гарантируют одинаковую temporal relation. Exit plan требует одинаковые source facts и preservation of conditions.

**Fix:** согласовать одинаковую relation (например `only after the lease expires` / `только после истечения аренды`) и добавить противоположный before-expiry control; reviewer проверяет обновлённые bytes, не исправляет corpus сам.

## Scope/freshness/offline: что не является новым defect

Metadata поля действительно заданы, faults воспроизводимы, но это **synthetic fixture metadata**, не уже проверенный actual SQLite/catalog snapshot. P2 обязан материализовать источники, показать actual ownership/version/generation/synchronization и citation-to-body range/hash binding; нельзя доверять `expected_observable`, `fault`, split/family ID или gold как product eligibility input. Для decoy сейчас source_id совпадает с positive; runner обязан закрепить distinct identities либо точный composite version key, исключить index overwrite, доказать одновременное присутствие обоих источников.

Offline имеет разумный contract `index-source-before-fault`, `disable-optional-backend-and-network`, `retain-eligible-local-witness`. Это не выполненный backend failure test. При freeze уточнить named optional stage, fault timing и counters/spies на network/model calls/retries; проверять local partial preservation и честный degraded status. Отсутствие P2 runner само по себе не блокирует P1; отсутствие заранее определённой процедуры делает последующий claim недоказанным.

Hostile fixture действительно содержит разрешённую command quote и network/permission injection. Его data не должны назначать действия/permissions; caller/action/network tracing остаётся обязательным control, не выводится из `edit_ready=false`.

## TD/TM loophole review и approvals

- TD01/02/04/05 ограничены explicit typed identity/syntax, не NL intent/ranking/proof. TD03 правильно **не разрешает новые number tables**, но existing normalization остаётся только временной pending dependency, не разрешением P5 DONE. TD06 должен получить explicit DTO/catalog contract **до** удаления inference. Blanket technical exemptions в новом тексте нет.
- TM01–TM06 не утверждены, asserts не мигрированы. Для будущего diff нужен **каждый assertion**, old guarantee, incompatible detail, replacement positive+negative evidence и final SHA/owner/reviewer. TM05 не разрешает fake coverage/floor lowering; TM06 не разрешает opportunistic README rehash. Global-false workaround прямо запрещён.
- Недостающие R2/R3 controls должны появиться до demonstrated fact delivery, иначе TM01/TM03/TM04 можно формально связать с слишком слабыми synthetic tests. 159 records покрывают четыре исходных alias-specific файла, не blanket approval для остальных tests.
- `P1_ACCEPTANCE_DRAFT_RU.md:76` требует P0 DONE, новый contract допускает owner-authorized P1 preparation при P0 archival ACTIVE. Указанное user authorization позволяет review/development, но не автоматически меняет freeze prerequisites: записать точное owner waiver/remaining gate и supersession draft, не объявлять P0 green. Resource ceilings должны согласовываться до model choice/download/run, как требует draft, не только перед финальным запуском.

## Итог

**Independent status: NEEDS FIXES (R1–R5), не approved freeze.** Exact bytes/spans проверены, но semantically sufficient witnesses и mandatory matrix пока неполны. После исправлений нужен новый hashed snapshot и повторный review. Existing real Pebble/Pydantic/three trust controls, core/advanced/adversarial/required CI/release, P0 provenance, owner TD/TM/behavior/resource decisions остаются отдельными dependencies; их red/pending статус этим review не изменён. Весь holdout виден reviewer'у и авторам; family-disjoint ≠ независимый blind unseen benchmark.
