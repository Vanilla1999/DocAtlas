# PR #211: явный robots member в P1.5 fixture

## Фактическая причина

На SHA `067dd56044fb1fe292af2d17783154c8a4b7c092`
[run 37991321081 / job 114025927641](https://github.com/Vanilla1999/DocAtlas/actions/runs/37991321081/job/114025927641)
текущий P1.5 дал **1/7 cases PASS**, **0/6 complete facts**, **5 runtime errors**.
Во всех пяти реальный job.target_results содержит `explicit_robots_member_required`.
Новый вывод причин подтвердил отсутствие явного protocol URL в fixture grant.
Шесть oracle self-controls, report integrity и syntax прошли.

Полный артефакт: `11645411821`, ZIP SHA256
`e0b94d004f9fd67b19c60947285719d941508924a60da73231d0fe0c82fff90c`.
Здесь прочитан текст job log; ZIP не распаковывался.

## Текущий контракт и узкое исправление

`preflight_target_urls` требует явный exact `/robots.txt` для выбранного origin.
Одного HTTP fixture response недостаточно для разрешения такого запроса.
Действующие prefetch, refresh и staging индексируют весь объявленный finite roster,
включая robots; это поведение закреплено существующими finite caller tests.
Данный slice сохраняет этот production контракт.

Каждый remote fixture target теперь явно объявляет исходный docs URL и его exact
robots URL, прежний host, исходный path плюс `/robots.txt`, `max_pages=2`.
Это количество разрешённых входных members; output ceilings не добавляются.
Если исходный path уже `/`, он сохраняется; новые широкие path/domain grants не вводятся.

Frozen protocol input остаётся ровно:
`User-agent: *\nDisallow:\n`, SHA256
`e5c4b84484ee4216e9373be99380320c25dd94805f99f0a805846f087636553f`.
Он отдельно отражён в migration crosswalk и network observation.
Это инфраструктурный member, аналогично ранее объявленному `FIXTURE_STATE.md`;
он не становится четырнадцатым original question candidate.

Oracle независимо проверяет raw bytes, hashes, диапазоны, parent/source identities
и record library identity обоих фактически сохранённых members.
Требуется наблюдавшийся HTTP read обоих явных URLs только на стадии preparation.
Extra URL, недостающий/изменённый grant, неверный body/hash/library и read-time network
остаются ошибками. Job должен действительно завершиться `succeeded`.

## Сохранённые границы

- Исходные **7 вопросов, 13 candidates, 6 полных фактов и 2 negatives** не изменены.
- `source_errors` и `score_observation` не меняются. Видимая robots citation
  отвергается как `source_outside_frozen_facts`, даже с правильным stored/hash binding.
- Новые контроли находятся в существующем self-test; все шесть имён сохраняются.
  В том числе проверяется, что protocol citation отвергается при сохранённых
  правильных original full facts и успешной preparation.
- Production ingest/retrieval/transport/staging не изменены.
  Отдельное исключение robots из индекса потребовало бы нового product slice.
- P1.5 `document_statement_binds_exact_path` уже отдельно падает по full facts;
  этот retrieval miss данным grant исправлением не объявляется закрытым.

## Статус

Подготовлены reviewable GitHub blobs; локальные imports/runtime/pytest не запускались.
Нужны независимый review и фактический CI на общем SHA. Пять старых preparation
ошибок считаются закрытыми только после нового реального job результата.
