# PR #211: checkpoint продолжения

Обновлено 2026-10-09, 21:33 UTC. Код и diagnostics этой публикации — до
`0369fd397ab6a6294da51e2cb07504f555cc2bba`; commit самого checkpoint добавляет только этот файл и точный архив предыдущего.

**PR пока не готов к merge.** Следующий CI ещё должен проверить новые slices на общем SHA.

## Действующие решения

- Потолки **6144 bytes / 800 tokens / 3 sources** отменены. Измеряем и сокращаем
  объём, сохраняя полные факты, source identity, scope/version/hash и consent guards.
- Операционные input/read/work/call/time ограничения сохраняются.
- Retrieval включён в позднее утверждённый план. Исходный blanket deferral больше
  не блокирует исправление подтверждённых потерь.
- Сокращение tests требует собственного зелёного baseline и доказанного обнаружения
  дефектов. Не считать все оставшиеся FAIL устаревшими и не заменять quality facts
  фактическим пустым результатом.
- Реальные Claude Code/Codex/OpenCode sessions **NOT RUN**. Installed SDK/stdio
  harness не является доказательством таких sessions.

План: [PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md](PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md).
Решения: [CURRENT_WAVE_DECISIONS_RU.md](CURRENT_WAVE_DECISIONS_RU.md).
Предыдущий checkpoint сохранён **побайтно**:
[CHECKPOINT_067dd560_RU.md](pr211-execution/CHECKPOINT_067dd560_RU.md),
git blob `7659d17450bcb4dff2260cd2481be61d1153f5ff`.
В архиве остаются вся предшествующая история, ссылки и ограничения.

## Последний полностью проверенный CI: 067dd560

SHA: `067dd56044fb1fe292af2d17783154c8a4b7c092`.
[Main run 37991321138](https://github.com/Vanilla1999/DocAtlas/actions/runs/37991321138).

Каждая Python lane **3.11 / 3.12 / 3.13**:
**7847 = 6000 PASS / 1837 FAIL / 0 ERROR / 10 SKIP**.
Не суммировать матричные повторы.
[JUnit reader 114029489614](https://github.com/Vanilla1999/DocAtlas/actions/runs/37991321138/job/114029489614)
проверил XML counts, concrete node uniqueness и hashes; integrity issues пусты,
console omissions — 0.

| Python | SHA256 JUnit |
|---|---|
|3.11|`932742113e4cbad9a395a0ec4945558af33a93659504f4035f467b0b113a2cd3`|
|3.12|`b090b55b76bd328273add6f078da1b071348b55951a8c829646e0f2c8e21d044`|
|3.13|`400fc3e00820b0a350856915072e22f653a033ae4505a5d42763ebbe895441cb`|

Сравнение с 10277: удалены 49 прежних alias cases после доказанного replacement,
добавлены 7 reader invalid-storage cases; SourceMap больше не в failing modules.
Другие per-module failure counts совпали. Новый reader отдельно выведет concrete
outcomes reader/generated/contract nodes, чтобы не выводить PASS только из отсутствия
модуля в списке ошибок.

Всего обнаружено **18 workflows: 8 SUCCESS / 9 FAILURE / 1 SKIPPED**.
Static, docs contract, retrieval evidence, installer, installed MCP и три platform
smokes прошли. Core, advanced, required-ci, P1 stack/closure/P1.4/P1.5/P1.6,
Task33 и language investigations остаются красными; Direct question validation
пропущен условиями workflow и не считается PASS.

### Что действительно подтверждено

- [Advanced 114025929400](https://github.com/Vanilla1999/DocAtlas/actions/runs/37991321138/job/114025929400):
  recovery **11 baseline PASS / 14 intended guard kills**; question surface —
  **100 original inputs PASS** с реальными member-backed positive, absent-fact
  negative и source-removal transformation.
- Critical gate: **29 baseline PASS / 7 intended mutants killed**. Alias mutant
  падает ровно на `critical_alias_no_generated_queries`, без errors/skips.
- Literal reduction: historical **702** и compact **82** проходят; все **51**
  directed mutations обнаружены обоими наборами. Это не доказательство других API.
- [P1.4 114025928063](https://github.com/Vanilla1999/DocAtlas/actions/runs/37991321105/job/114025928063):
  **14/14 read-only checks PASS**, **7/14 total**, discovery **3/10**, full facts
  **2/5**, runtime errors **0**. Пять independent oracle controls PASS.
  Семь оставшихся failures относятся только к discovery/full facts.
- [P1.5 114025927641](https://github.com/Vanilla1999/DocAtlas/actions/runs/37991321081/job/114025927641):
  **1/7 total**, full facts **0/6**, **5 runtime errors**.
  Причина всех пяти observed target failures — `explicit_robots_member_required`.
  Все **6 oracle controls**, report integrity и syntax PASS.
- [Task33 114025928664](https://github.com/Vanilla1999/DocAtlas/actions/runs/37991321112/job/114025928664):
  **61 PASS / 3 FAIL**. Четыре adapter cases предыдущего slice прошли.
  Source-choice producer и 32 consent negatives выполнены до более позднего assertion.
- V2 завершает реальный отчёт: full semantic facts **6/15** natural и **1/5**
  exposed paraphrases. Legacy original coverage **0 < 12**.
  Agent Developer target closure **8/11**; adversarial **24/28**.
  Эти quality gaps не закрыты.
- [P1.6 114025927870](https://github.com/Vanilla1999/DocAtlas/actions/runs/37991321109/job/114025927870)
  останавливается на `support mismatch for legitimate_fact_survives_hostile_tail`.
  Это следующая исследуемая contract/quality граница, а не разрешение снять full fact.

## Reviewed slices этой публикации

| Slice | Commit | Изменение |
|---|---|---|
|41|`2913d626`|P1.4 runner выводит сохранённые stages/requests/preparation и read-state всех 14 случаев.|
|42|`40062871`|P1.5 явно разрешает original docs URL и exact robots member; независимый oracle проверяет оба stored members.|
|43|`16113656`|Intent precheck: один current contract и directed mutant; прежние 32 cases пока collected.|
|44|`71973165`|Task33 fixtures используют настоящий retention completion, полные v4 окна и корректные retrieval-only citations; completion cost вместо ceiling.|
|45|`33e41cd7`|Private trace копирует уже наблюдаемые BM25/qualification/reference fields и hash окна; нет нового engine вызова.|
|46|`5f60400b`|JUnit reader показывает collected/counts/concrete outcomes активных controls по каждой Python lane.|
|47|`0369fd39`|Восемь ActionPacket part02 tests мигрированы на v4 whole-window, exact-version, rejection и literal-witness contracts.|

Все slices прошли независимое source review и exact parent/tree/blob verification.
Это **не runtime PASS** новых изменений. Новые Python imports/tests выполнит обычный CI.

P1.5 frozen **7 questions / 13 candidates / 6 full facts / 2 negatives** сохранены.
Robots — отдельно объявленная инфраструктура, не question evidence; даже корректно
bound robots citation отвергается. Production ingest/retrieval/staging не менялись.

Intent precheck только добавляет проверку. Возможное следующее сокращение —
**31 classifier-only cases → 1**, с отдельным сохранением mixed ranking guard.
Оно допускается после actual **30 baseline / 8 named mutant** evidence.
Сокращение ordinary collection не выдаётся за уменьшение числа всех внутренних
property checks или всех CI executions.

Три Task33 причины разобраны по producer/selector контрактам: реальные retention
completion, недостающий hash stable child fixture, допустимые generic citations.
Source texts и вопросы сохранены; `ok/context_available` не означает answer/edit grant.
Второй completion test про полный `mkdocs-05` priority fact оставлен побайтно прежним.

## Следующие действия

1. Прочитать actual Task33/P1.4/P1.5/critical/JUNIT_TRACKED на общем опубликованном SHA.
   Не переносить старые PASS на изменённый код автоматически.
2. По P1.4 trace локализовать original `What does OrdersDraftStore do?`:
   acquisition → canonical qualification → admission → projection.
   Не вводить blanket CamelCase admission: frozen quantum/absent negatives остаются.
3. После устранения robots preparation разобрать реальные P1.5 fact/source guards.
   Partial job не принимается за succeeded, инфраструктура не получает fact credit.
4. Продолжать подтверждённые миграции и precheck следующего classifier-only семейства.
   Live finite/source-binding/ranking и quality cases сохраняются отдельно.
5. Закрыть remaining original-query/full-fact/contamination, P1.6, closure/stack и
   required gates. Итоговый acceptance — на конечном SHA с полным составом tests.
6. Указать конкретный недоступный обязательный client run, если он останется;
   scripted MCP не называть настоящим client. Сам merge — отдельное действие.

## Рабочая среда

Refs: `implementation/pr211-merge-readiness` и `integration/stage3-v2-identity-pr1`.
Только ordinary fast-forward. Force, merge, release и внешние комментарии не выполнялись.

Local checkout устарел после `0049c6d`; exec transport недоступен с 18:09 UTC.
После outage local AST/import/compile/runtime **NOT RUN**.
Изменения готовятся exact-file GitHub API и проверяются разрешённым PR CI.
Не запускать пользовательские индексы, загрузки моделей, providers или реальные clients
без соответствующего уже имеющегося разрешения.
