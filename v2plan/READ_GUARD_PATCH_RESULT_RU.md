# Original-read без proof qualification: первый patch

2026-10-03. Предварительное решение: `ADMISSION_REMOVAL_DECISION_RU.md`.
Все предшествующие изменения, включая существующие crosslingual artifacts,
сохранены snapshot-коммитом `fed1898e` (detached HEAD).

## Изменение

`docmancer/docs/application/read_context_admission.py`: удалены вызов
`qualify_evidence` и whitelist его proof reasons. Вместо этого вызывается
existing `prepare_source_probe`, явно проверяются required literal и subject
в body/verified owner. Existing exact source/request/snapshot/span checks,
native applicability и three-term/adjacent-pair locality сохраняются.

Qualification для claims, typed paths, preferences, prefit/ranking, retrieval,
defaults, budgets и proof/edit flags не изменены. Это изменение существующей
read-функции в рабочем дереве, не только research prototype. Rollout не выполнен.

## Свежая парная проверка полного native pipeline

Runner: `read_guard_pipeline_replay.py`. Baseline function загружена из
`fed1898e`; candidate — текущая. Единственная подстановка — original-read
function. Обе стороны вызывают actual service/handler/projector на одном
native индексе и одном project root. Retrieval configuration и service defaults
не меняются; это полный native call, не experimental renderer с budget 1500.

- 80 frozen cases; **80/80 actual payloads identical**.
- Supported required claims: **49 → 49**, lost 0.
- Claim statuses: supported 49, missing 29, needs_review 10 в обоих arms.
- Negative packets: 0 → 0.
- Answer/edit/support/coverage flags: без изменений.
- Partial claim outcomes сохранены вследствие полной payload parity.

Артефакты первого full calls/traces: `/tmp/opencode/read-guard-pipeline-fed1898e/`.
Runner сохраняет protocol, results и summary; этот output не является
неизменяемым versioned artifact. Baseline всегда pinned через git revision.

Повторный replay в проектном `.venv`: `/tmp/opencode/read-guard-pipeline-final/`,
те же 80/80 identical payloads и 49/49 claims. Summary и code provenance сохранены
в `artifacts/read-guard-pipeline/`. Дополнительные synthetic controls вне frozen
corpus проверяют documented negative fact, echo/heading и wrong preview state;
33 tests passed. Это development controls, не unseen validation.

```bash
PYTHONPATH=. /usr/bin/python3.12 v2plan/read_guard_pipeline_replay.py --baseline fed1898e --output /tmp/opencode/read-guard-pipeline-NEW
```

## Tests и границы приёмки

101 focused tests passed (existing asyncio_mode warning). Research controls
теперь также вызывают actual native read: heading/echo, wrong state, literal vs
owner, source/request mutations, clipping и запрет вызова proof qualification.
Pre-existing expectations не ослаблены.

## Завершение: полный repository regression

Системный Python не собрал suite из-за отсутствующих dependencies. В проектном
`.venv` candidate и clean detached baseline worktree `fed1898e` проверены одним
интерпретатором и командой `python -m pytest -q --junitxml=...`.

Оба runs: **6216 tests, 6076 passed, 130 failed, 10 skipped, 0 collection errors**.
Множества failing test nodes совпадают: новых 0, исчезнувших 0. Assertion outputs
не побайтово равны: есть process addresses, temp paths/order и различающийся
выбранный docs/note path в уже failing ranking test. Node parity не объявляем
полной behavioral equivalence или зелёным regression.

Candidate XML: `/tmp/opencode/read-guard-venv-candidate.xml`;
baseline XML: `/tmp/opencode/read-guard-venv-baseline.xml`, logs рядом.
Последние пять дополнительных parametrized controls добавлены после collection
полного run и отдельно проверены. Итоговый focused inventory: **120 passed**.
Посторонние 130 failures не исправлялись, tests не отключались.

Независимая unseen validation не выполнена.
Synthetic controls не считаем held-out. Equality на exposed corpus не доказывает
универсальной equivalence: удалённый proof refusal мог маскироваться locality.
Поэтому patch реализован, focused/full-pipeline frozen проверки пройдены,
full-suite failing-node parity подтверждена,
но unrestricted production approval не заявляем. Recall gain: **0**.
