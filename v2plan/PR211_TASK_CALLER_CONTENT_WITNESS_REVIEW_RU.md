# PR #211: явные content witnesses для семи v4 caller tests

Дата: 2026-10-08. Авторский follow-up rationale после первого runtime прогона.

## Наблюдение CI и граница исправления

Advanced CI run [37805723255](https://github.com/Vanilla1999/DocAtlas/actions/runs/37805723255)
для head `5bf3b00493577f68c816c90bb667f5ca84eabf75` исполнял merge checkout
`2f2252616deb2cd64b2a4bcce48f64e894b2bb2d`: 517 PASS, 105 FAIL, 0 errors,
0 skipped. JUnit artifact `11562223158`, SHA-256
`a29ff5a950998ff3627270a449eeeb83af427135c7f8b58325acf1a46434feba`;
XML SHA-256 `19be911398ca359ee31ccbb48745280db2d492f5222ea95c80814977676dc00c`.

Все семь caller nodes из предыдущего slice дошли до нового положительного
assertion и остановились на `completeness=partial`, где fixture ожидал
`complete`. Это не runtime PASS предыдущих миграций. Старые авторский и
независимый reports сохранены без изменений; настоящий документ фиксирует
обнаруженную неполноту fixture и следующий ограниченный diff.

JUnit показывает фактический `partial`, но не печатает поле `missing` этих
пакетов. Причина ниже установлена чтением producer; новые tests проверят точный
machine reason в подготовленной CI-среде. Локальный runtime результат здесь
не заявляется.

Изменены только прежние nodes в четырёх test modules: GitHub wrong-objective
metadata, Codex required-once normalization, explicit exploratory delivery и
общий `_packet` для четырёх isolated broker cases. Новых test nodes нет.
Objective, исходные source bytes, source/target requirements, production,
evaluator implementations, golds и ceilings не изменены.

## Почему сохранённый текст ещё не давал complete

[`build_action_packet`](../docmancer/docs/application/_action_packet_part03.py)
строит требования через `build_requirements(..., profile="generic")`, затем
возвращает `partial`, если у отобранных sources остаются machine reasons.
[`evidence_requirements.py`](../docmancer/docs/application/evidence_requirements.py)
не выводит behavioral facts из обычной формулировки objective. Переданные
`required_evidence_paths` и `required_target_paths` создают identity obligations.

В [`_evidence_selection_part03.py`](../docmancer/docs/application/_evidence_selection_part03.py)
непустой patch selection без assignment с `unit_id` получает
`visible_content_assignment_required`. Поэтому первых двух metadata fixtures
и общего isolated fixture без content requirement недостаточно. Exploratory
fixture уже имел оба path requirements, но identity assignments не заменяли
отдельный witness видимого содержимого.

[`_legacy_requirement_matches_unit`](../docmancer/docs/application/_evidence_selection_part02.py)
принимает `required_fact` только при точном равенстве `unit.text` переданной
цитате. Это механическая проверка видимых bytes. Validator в
[`_action_packet_part04.py`](../docmancer/docs/application/_action_packet_part04.py)
повторно извлекает units, проверяет assignment binding и требует content
assignment для `complete`. Никакой policy или edit authority цитата не даёт.

Оба required-once consumers —
[`_github_models_part01.py`](../eval/task_level/_github_models_part01.py) и
[`runners/codex.py`](../eval/task_level/runners/codex.py) — требуют валидный flat
patch payload, совпадающий original objective, `result=data` и
`completeness=complete`. Codex также требует explicit patch format. Менять
положительное ожидание на `partial` означало бы потерять проверку успешного
required-once metadata.

## Исправленные fixtures и сохранённые отрицательные контроли

| Fixture | Явное content requirement и положительная проверка | Отрицательные контроли |
|---|---|---|
| GitHub metadata | `public_requirements=(source_text,)` задаёт уже существующее единственное предложение fixture. Проверяются mandatory/public provenance, настоящий unit ID, source identity, path, unit hash и полный span | Второй настоящий builder/projector без content requirement сохраняет те же полные sources, возвращает valid `data/partial` с точным `visible_content_assignment_required`, а matching-objective consumer отказывает в retrieval success. Wrong objective, error, malformed, legacy wrapper и edit grant сохранены |
| Codex JSONL | Такое же явное предложение; complete positive по-прежнему проходит started/completed normalization, один logical call и clean policy audit | Valid partial с полным source передаётся через настоящий structured-content lane; objective и explicit format верны, metadata сообщает data/partial, но `retrieval_succeeded=False`. Четыре прежних negative variants сохранены |
| Isolated `_packet` | Обе заранее написанные строки исходного fixture передаются как отдельные literal requirements, полный source window остаётся одним. Каждая строка получает assignment с проверяемыми unit hash/span и source binding | Поддельный source fixture остаётся валидным относительно собственных bytes, затем отвергается broker против оригинального host snapshot. Capability, timeout, consumed-attempt, count/revision/query/objective/usage, forged scaffold, mutated host evidence и failure-projection guards сохраняются |
| Exploratory delivery | Явная исходная docs-цитата дополняет существующие evidence/target identity requirements. После добавления настоящего target window проверяются complete, quote witness и прежний target assignment | Без target window остаётся `partial` с точным `target_path:0:lib/modules/permission/service.dart`; broker по-прежнему отклоняет missing target. Citation filename не заменяет target evidence. Tier и usage остаются exploratory/unverified, без causal claim |

`complete` в этих fixtures означает покрытие явно перечисленных literal и path
obligations. Это не утверждение о смысловой полноте ответа, правильности
выполненного изменения или разрешении редактировать. Во всех положительных
fixtures сохраняются `edit_ready=False`, `instruction_trust=untrusted_data`,
полные исходные тексты и SHA-256. Source estimates пересчитывает production;
`<=1500`, `envelope.token_budget`, замороженные 2000/800 и остальные ceilings
не повышены и не отменены.

## Проверка и необходимые следующие шаги

- `git diff --check` для четырёх modules: PASS.
- Stdlib AST parse: PASS. Все 53 test interfaces (11/19/16/7), их имена,
  arguments и decorators совпадают с `21fe472d`; новых nodes/markers нет.
- Изменённые function bodies ограничены согласованным slice; остальные tests,
  `tests/diagnostic_labels.json` и старые reports не редактировались.
- Actionability и frozen semantic-density conflicts остаются открытыми;
  соответствующие files сохранены. Retrieval и one-call edit loop не менялись.
- Actual pytest, builder/projector/validator execution, workers, Git/server
  subprocesses, installed/client acceptance здесь **NOT RUN**. Зависимости не
  скачивались; никакой обход локальных ограничений не использован.

Перед publication требуется независимый review этого follow-up. После него
нужен повтор тех же семи nodes и общий CI inventory на опубликованном SHA.
Команда targeted pytest с их неизменными node IDs сохранена в
`PR211_TASK_CALLER_MIGRATION_REVIEW_RU.md`. Ни этот diff, ни статические проверки
не являются acceptance verdict для всего PR #211.
