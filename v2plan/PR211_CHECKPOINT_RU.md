# PR #211: checkpoint продолжения

Обновлено: 2026-10-10 04:38 UTC.

**PR пока не готов к merge.** Последний завершённый фактический CI:
PR HEAD `d76f6ab85e12f482ad6bec1d43040899f4b0a532` (126),
merge checkout `8120a80bbb0309a3ec0bf4add71f568666c76772`,
общий tree `63bff21aadbfb131082db075ed95ea7e89310e44`.
Reviewed пакет127–129 ниже; его собственный runtime **PENDING**.

## Действующие решения

- Потолки **6144 bytes / 800 tokens / 3 sources** отменены. Сокращаем полный
  полезный output с сохранением фактов, source identity, scope/version/hash и consent.
- Операционные input/read/work/call/time ограничения остаются.
- Retrieval включён в утверждённый план; прежний blanket deferral снят.
- Retirement — после независимого oracle, собственного зелёного baseline,
  intended mutation proof и сохранности helpers/imports/selectors/archive.
- Legacy acceptance по ADR0003: полный frozen fact coverage исходных cases
  с floor **12/15**. Raw original-query coverage — отдельная метрика;
  lookup/parent credit не повышает её.
- Реальные Claude Code/Codex/OpenCode sessions **NOT RUN**. Installed SDK/stdio
  подтверждает CI transport, но не эти клиентские sessions.
- Локальные runtime/import/pytest/AST/install не выполняются. Используются
  существующие авторизованные PR workflows без новых providers/models.
- Обычные commits и fast-forward двух refs разрешены. Merge/release,
  force-push и внешние comments/messages не выполняются.

План: [PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md](PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md).
Решения: [CURRENT_WAVE_DECISIONS_RU.md](CURRENT_WAVE_DECISIONS_RU.md).
Старый local checkout не является актуальной базой.

## Фактический CI: 126

[Main run](https://github.com/Vanilla1999/DocAtlas/actions/runs/38023053227).
[Acceptance reader](https://github.com/Vanilla1999/DocAtlas/actions/runs/38023053227/job/114129755653).
[Selected runtime records126](pr211-execution/RUNTIME_EVIDENCE_d76f6ab8.json).

На **каждом** Python3.11/3.12/3.13:
**7669 = 6062 PASS /1597 FAIL /0 ERROR /10 SKIP**.
Матрица не складывается в один baseline; JUnit integrity issues пусты.

| Python | SHA-256 JUnit |
| --- | --- |
|3.11|`12808a98f9ef5984147f608dbaba49797e2da3783c2e4b6d2f718a1b43cd6a01`|
|3.12|`572802584bf65241d32bcaea66ddab45d9f8124c11282c923fc2a52d1aa0ab9a`|
|3.13|`44843fefc212d45ec252da461bc67a4b601a21709fcc3eb66910bad0891bf0b4`|

Collection уменьшился ровно на58 после retirement123: DQP70→37,
relation72→47. Их PASS counts сохранились25 и23. Относительно121 появились
ещё три FAIL: native24-window fixture и два retention cases. Имена двух новых
retention failures в старом compact reader не напечатаны; они не объявлены
миграциями ожиданий без traceback. Slice127 расширяет только диагностику.

| Gate | Actual126 | Граница доказательства |
| --- | --- | --- |
|Critical baseline|59 entries,58P/1F|Native fixture: `critical_project_read_acquired_qualified`. Guard повторяется на нескольких operands; точный первый operand в126 console отсутствует.|
|Critical mutations|**не выполнены**|Baseline блокирует цикл; нового35-kill proof нет.|
|Recovery|**12P и33 intended kills**|Все33 per-mutant outcomes сверены с собственными case/guard:0P/1F/0E; priority omissions0.|
|Literal historical/compact comparison|SUCCESS|Existing step16. Individual51-fault receipts ещё не доступны в console; aggregate не разрешает новое retirement.|
|Lossless core projection|**32/32** на каждом Python|Все4 cap killer cases PASS; их4 новые faults не выполнены из-за critical baseline.|
|Legacy live|Source-fact acceptance **8/15**, raw original coverage0|Floor12/15 не достигнут; reportFAIL.|
|V2 live|Natural facts6/15; paraphrase1/5|REPORT_ONLY; production runnerFAIL. Request flow2/4facts; есть precision/contamination failure.|
|Agent Developer|v1:8target-closed/11,4gaps; adversarial24/28|false_supported0, contamination0 в этих agent fixtures; baseline не target-green.|
|P1.4|12/14cases,8/10discovery,5/5complete facts; execution errors0|Два ordinary original-only cases FAIL;5/5oracle selftests.|
|P1.5|SUCCESS|Отдельный текущий run38023053171.|
|P1.6|Public delivery6/6,complete facts1/1,oracle6/6|Общий jobFAIL: Agent Developer gaps и adversarial baseline.|
|Installed MCP / retrieval evidence / platforms|SUCCESS|Installed selftests7/7,deterministic scripted task1/1; реальные client sessions NOT RUN.|
|Required CI / P1-stack exact / closure|**FAIL**|Core, advanced и quality остаются красными.|

Hermetic16/16 проверяет literal query identity без retrieval. P1.6 public delivery
и installed transport не подменяют полное quality acceptance.

Reader:592758 UTF-8 bytes, SHA-256
`5ba00eacb3e432d650c6ef6d5f396db286397487189436fbdeec90940e5042a1`.
Разобраны357 JSON records без ошибок. JUnit console omitted0.
Recovery priority35 records (два baseline reports и33 mutants), пропущено0.
Critical baseline доступен; individual critical mutant records отсутствуют.
Остальных artifact rows не напечатано55 из133 selected.
Новый receipt содержит59 selected records, все33 intended outcomes, jobs и short-log hashes:
122030 bytes, SHA-256 `02105cf8680d81e65be9ed073e6ee3fd0e68ca50a3ea2dea00c35448b96a6990`.

Полная независимая пересверка всех source/import operands33 recovery mutants
этим receipt не заявляется: console сохраняет все outcomes, но только часть
подробных module records. Проверки самого CI writer и read-only review receipt
различаются. Separate import probe не является same-pytest-process attestation.

## Применённый reviewed пакет127–129

| Slice | Commit | Изменение |
| --- | --- | --- |
|127|`e6babced683c005303af597a79878ecd13e54c90`|Два source-proven fixture hash-domain fixes: public project hash и snapshot hash имеют prefix `sha256:`, SQL/display hashes — raw. Добавлены failure traces и два focused modules в existing reader.|
|128|`23af9fc5b5934bc651e40f510ec90c88e1642dcc`|Original-only project partial-body context с current native receipt, без answer/original-coverage grant. Independent native controls и6 directed recovery faults.|
|129|`e8929ae6d3bf0bc571aafffa52d29366d4c00da8`|Четыре frozen relation source-context reads внутри existing privacy test;+1existing critical selector/+2faults. Оставшиеся47 witness cases не удалены.|

Joint targets: **critical60healthy/37intended kills; recovery12healthy/39intended kills**.
Это targets следующего запуска, не фактический PASS.
Новых pytest test names пакет127–129 не добавляет; внутренние native calls
учтены в соответствующих notes и не выдаются за бесплатную проверку.

- [Hash domains и диагностика](pr211-execution/PROJECT_READ_HASH_DOMAINS_RU.md).
- [Ordinary body contract](PR211_ORDINARY_PARTIAL_BODY_ADMISSION_RU.md).
- [Relation source-context precheck](pr211-execution/RELATION_SOURCE_CONTEXT_PRECHECK_RU.md).
- [Retirement58 с собственным121 proof](pr211-execution/COMPILER_RETIREMENT_58_RU.md).
- [Четыре cap faults](pr211-execution/OUTPUT_CAP_MUTATION_PRECHECK_RU.md).

## Оставшиеся причины

### Качество и объём выдачи

В126 V2 natural выдаёт41source суммарно,max18; max16744public UTF-8bytes,
max4186estimated tokens. Это наблюдения, не ceilings. Full facts остаются6/15.
Request-flow теперь доставляет MCP/gateway facts, но application/selection facts
не доставлены; verdict2/4. Production runner также сообщает
`no_packs_contamination` и `only_allowed_sources` failures.
Результат нельзя считать безрегрессионным по качеству только потому, что он
сохраняет больше admitted windows. Нужны current source/body/ownership причины
и исправление полезности/precision; caps и weakened oracle не возвращаются.

Legacy8/15, V2 architecture/cache-reset и четыре Agent Developer target gaps
остаются открытыми. В source обнаружено возможное несовпадение span domains:
reference probe использует `evidence_text.strip()`, а closed-literal admission
сравнивает span с длиной raw native chunk. Завершающий LF может блокировать
полезный body; ведущие whitespace требуют правильного raw offset.
Это source-level finding, не доказанный runtime first operand и не готовый fix.
Comparison task требует отдельного анализа.

### Ordinary partial-body admission

Slice128 разрешает только ordinary original project read, полученный этим
синхронным MCP handler из подготовленного current member store. В одной
substantive source clause нужен contiguous span исходного вопроса с двумя
различными content words; нельзя перескакивать через другие content words
или соединять независимые clauses. Полный acquired window сохраняется.
Технические/literal/path/numeric/operator вопросы остаются в строгих lanes.
Private request context связывает root/member/generation/source/hash/window
и закрывается при нормальном и аварийном выходе.
Весь original остаётся missing; answer/edit false. Modifier вне span не доказан.
Scoped, replay, metadata, split-clause, single-hit и hostile controls не снимаются.
Нужны собственные P1.4 и12/39 runtime results.

### Сокращение тестов

DQP16definitions/37cases, relation4definitions/47cases.
Один старый DQP default3/800 test остаётся collected до четырёх собственных cap kills.
Оставшиеся47 relation нельзя удалить по этому precheck: source-policy15,
condition3/native5 и исторические negative obligations требуют точного crosswalk.
Question-plan v4: рассматривается reuse существующих literal/span/dictionary
successors для26 obsolete semantic cases; два literal/code-span cases сохраняются.
Own evidence, archive обоих файлов и import/selector audit ещё нужны.
Причина FAIL сама по себе не разрешает удаление.

## Следующие действия

1. Fast-forward обоих refs с reviewed127–129 и этим checkpoint; проверить
   merge SHA/tree нового existing PR CI.
2. Проверить60/37critical,12/39recovery,P1.4,retention traces и required/downstream;
   сохранить individual receipts. Исправить действительные first failures.
3. После четырёх cap kills отдельным узким slice убрать default3/800 test,
   обновить precise AST preservation, crosswalk и owning node hash.
4. Довести raw source-span correction и Agent/V2 gaps на неизменных questions/facts;
   не добавлять implicit queries, source-policy исключения или output ceilings.
5. Продолжить retirement remaining relation/question-plan через reused own proof;
   завершить quality,required CI и необходимые installed/client acceptance.

Исторические121/118/113 receipts сохраняются. Static APPROVE, прошлый SHA,
aggregate SUCCESS и целевой roster не заменяют собственного runtime.
