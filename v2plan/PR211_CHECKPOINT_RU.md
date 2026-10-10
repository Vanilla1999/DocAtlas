# PR #211: checkpoint продолжения

Обновлено: 2026-10-10 06:12:54 UTC.

**PR пока не готов к merge.** Последний завершённый CI — PR HEAD
`a9fba17d13ea16ed0dbbb4692ab6029ae6da6a07` (136), merge
`32765e44d2e85d3f638ac9d22a2fa6f4f46f6aee`, общий tree
`7f663bac25aa6e79c48a07301d2e94e5e7352c42`.
Reviewed follow-up137–150 собран на `2c67ba237a53e8cdeeee9cc162bea9533d342c1a`; его собственный
runtime **PENDING**. Старый local checkout не является базой.

## Действующие решения

- Потолки **6144 bytes / 800 tokens / 3 sources** отменены. Сокращаем полезный
  полный output с сохранением фактов, identity/scope/version/hash/consent.
- Действующие operational input/read/work/call/time bounds остаются. Public
  question не имеет ceiling4000; это внутренняя граница legacy compiler.
  Original сохраняется полностью; explicit lookups — максимум5 по500.
- Retrieval входит в порученный план; прежний blanket deferral снят.
- Retirement требует собственного здорового successor, intended mutation proof,
  сохранения исходных inputs и проверки helpers/imports/selectors.
- Legacy по ADR0003 требует полные frozen facts минимум12/15 исходных cases.
  Raw original coverage измеряется отдельно; lookup credit не переносится.
- Installed SDK/stdio не доказывает Claude Code/Codex/OpenCode sessions:
  реальные clients **NOT RUN**.
- Локальные runtime/import/pytest/AST/install не выполняются. Используются
  существующие авторизованные PR workflows без новых providers/models.
- Обычные commits и fast-forward двух refs разрешены. Merge/release,
  force-push и внешние comments/messages не выполняются.

[План](PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md) ·
[решения](CURRENT_WAVE_DECISIONS_RU.md).

## Фактический CI136

[Main run](https://github.com/Vanilla1999/DocAtlas/actions/runs/38026891736) ·
[Acceptance reader](https://github.com/Vanilla1999/DocAtlas/actions/runs/38026891736/job/114141422568) ·
[Сохранённые records136](pr211-execution/RUNTIME_EVIDENCE_a9fba17d.json).

На каждом Python3.11/3.12/3.13:
**7669 = 6052 PASS / 1607 FAIL / 0 ERROR / 10 SKIP**.
По сравнению с130 — 15 FAIL больше при той же collection. Эти 15 дополнительных сбоев
расследуются отдельно: само число ещё не классифицирует их как product defects. JUnit integrity issues
пусты; три матрицы не складываются в один baseline.

| Python | JUnit SHA-256 |
| --- | --- |
|3.11|`9b3b5b0ca35eb314f59c10ba0d990ec432e286af3472ffb7c0ad46f50152a155`|
|3.12|`e62d11191cde8d6b9e77932a5aa5adcb4a94bf4a1f827dd781f17b63f9386d92`|
|3.13|`d4e572cd644f1414147a18238db14c2ebe0d4d368ac79f801182f66364a0a8a0`|

| Gate | Actual136 | Граница результата |
| --- | --- | --- |
|P1.4|**14/14 cases, 10/10 discovery, 5/5 complete facts**, 0 errors|Собственный run38026891725; oracle5/5.|
|Recovery|**12/12 healthy, 43/43 intended kills**|Все43 case/guard/count outcomes сверены; четыре raw-window faults имеют собственное доказательство136.|
|Critical|**61 entries, 1 observed FAIL**|`critical_project_read_existing_retention_completion`; 39 mutants не выполнялись. Остальные60 entries не объявляются PASS: skip count здесь не раскрыт.|
|Literal comparison|**702/702 historical и82/82 compact**, 51 faults в двух режимах|ProducerPASS,104children найдены; все87 доступных individual receipts проверены,17не выведены. Default уже **compact**; `activated_compact_default=false` означает отсутствие переключения самим comparison runner.|
|read_next|**23 PASS / 8 FAIL** из31case|Все8 прежних continuation scenarios упали на read_next==1; ожидание сохранено, raw/byte coordinates исправлены в146/148.|
|P1.6|Public6/6, full facts1/1, oracle6/6|Общий jobFAIL; adversarial24/28, Agent Developer gaps остаются.|
|Installed MCP|**7/7 selftests, 1/1 scripted task**|reviewed-wheel, deterministic-script; report verificationPASS. Реальные client sessions NOT_RUN.|
|Retrieval evidence / platforms / P1.5|SUCCESS|Ubuntu, macOS Intel/ARM; output ceilings не возвращаются.|
|Legacy / V2 / Agent V1|Соответствующие quality stepsFAIL|Числа текущих quality reports не попали в console. Последние прочитанные числа130 не выдаются за136.|
|Required CI / P1 stack / closure|**FAIL**|Полного acceptance нет.|

Всего18 workflows:11SUCCESS,6FAILURE,1SKIPPED. Advanced adversarial mutation
step17 SKIPPED; literal comparison step16 SUCCESS.

Reader:674211 UTF-8 bytes, SHA-256
`fdf815da3d3a2f0c301b4b36740aac2c29c3de79f0c50fe536281d7aac8bd7f0`.
431 parsed JSON records,0parse errors; JUnit omitted0. Из271 selected artifact
rows134 не напечатаны; priority literal omissions17. Все45 recovery records
(два12-case reports и43 mutants) доступны.

Receipt сохраняет все431 exact parsed records,43 intended recovery outcomes,
87 individual literal audits, exact missing17, source hashes, jobs и short-log
hashes:922428 bytes, SHA-256
`95b63b4c6913166a2acfe526b828b44bb0a7e3e60db1f0631f9fc714d4c66c62`.
Для87 literal receipts отдельно пересчитаны15 exact136 source blobs и
mutation before/after; проверены реальные same-process import receipts.
Независимый полный source/import rehash всех43 recovery faults не заявляется.

### Последние прочитанные quality числа остаются историей130

Legacy8/15 full facts при floor12, raw original0; V2 natural6/15, paraphrase2/5.
Agent V1 target-closed8/11 с4gaps; adversarial24/28.
[Отчёт130](pr211-execution/RUNTIME_EVIDENCE_0065ce62.json) хранит их собственное
доказательство. Новый reader145 отдаёт summaries раньше тяжёлых receipts.

V2 flow136 содержит18 public sources, а private final-ID preview —3.
Core и callback режут preview до3; после core идут joint/query finalizers.
Эти carriers нельзя сравнивать как полный список до/после selection.
Actual first veto недостающего window пока не установлен; source-level
novelty correction не объявляется доказанной причиной именно этого case.

## Reviewed follow-up после136

| Slice | Изменение |
| --- | --- |
|137|Global fixture oracle сравнивает исходные LF/CRLF bytes в заявленных line ranges.|
|138|Exact question-plan consumer/retirement audit; удаления не выполнялись.|
|139|Сохраняются новые qualified source units при уже покрытом lookup; existing24 native windows, duplicate/reverse replays и2directed faults.|
|140|Pending relation/raw mutation recipes привязаны к новому core; прежний runtime credit не переносится.|
|141|Шесть старых retention ожиданий мигрированы к полной fidelity; все26names/37cases и прежние guards сохранены.|
|142|Agent source-quote oracle сохраняет LF/CRLF; существующий self-control проверяет положительные и отрицательные случаи.|
|143|Default surface проверяет validation rejection; explicit advanced surface действительно достигает missing-completion guard.|
|144|Все19 исходных role questions и2resolver collisions воспроизводятся; archives/crosswalk/consumer audit и2faults, без удаления старых19cases.|
|145|Приоритет quality summaries, individual receipts и явные omission counts. Диагностический transport budget не является product ceiling.|
|146|Структурный контекст сохраняет raw[start:end]; восемь read_next native scenarios требуют прежнего continuation и authorization.|
|147|Сохранён independently reviewed receipt136; он не выдаёт новый runtime PASS.|
|148|Char/byte/line координаты структурного окна относятся к одним raw bytes; прежние continuation guards сохранены.|
|149|Полностью разобранный original comparison получает оба буквальных имени из одного проверенного абзаца; без answer/edit authority, с3directed faults.|
|150|Actual validated final sources, core/primary/hint attempts и executed decision events наблюдаются отдельно; нет новых acquisitions или изменения verdict.|


Следующий совместный target: **critical62 healthy / 43 intended kills; recovery12 healthy / 46 intended kills**.
Ноль новых pytest names не означает ноль дополнительных внутренних операций:
они перечислены в owning notes. Исторические PASS не заменяют новый baseline.

## Что осталось

1. Опубликовать reviewed follow-up двумя обычными fast-forward и получить его
   собственный совместный CI; проверить raw/source/retention/read_next corrections.
2. Проверить все104 individual literal receipts на новом SHA и новое critical
   proof. Только затем завершать соответствующие family retirements. Literal
   default уже compact (33+49 вместо historical303+399); повторное переключение
   не требуется и не будет записано как новое сокращение.
3. QP26 retire/2keep, single DQP3/800 case и reference-role19 имеют отдельные
   prerequisite proofs. Remaining relation47 также требует own intended faults.
   Уже завершённое retirement58 подтверждено121; новых удалений после126 нет.
4. Довести реальные frozen source facts до quality floors, проверить Agent
   comparison/module/policy gaps; original-only/paraphrase/full-fact/contamination
   остаются самостоятельными проверками.
5. Завершить required CI/downstream на конечном SHA и нужные installed/client
   проверки. Реальные client sessions пока NOT_RUN. Merge/release не выполнены.
