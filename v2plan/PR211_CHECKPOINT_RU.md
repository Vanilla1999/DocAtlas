# PR #211: checkpoint продолжения

Обновлено: 2026-10-10 04:06 UTC.

**PR пока не готов к merge.** Последний завершённый фактический CI:
PR HEAD `c2a6682d2438c9217c3bf26938dcd003391dbc75` (121),
merge checkout `642a14289fddd06408400b4ee6cc5480945e7d1a`,
общий tree `89106f59cf181510a25ee8b667a9ff4966a82fd6`.
Reviewed пакет122–125 описан ниже; его собственный runtime **PENDING**.

## Действующие решения

- Потолки **6144 bytes / 800 tokens / 3 sources** отменены. Сокращаем полный
  полезный output с сохранением фактов, source identity, scope/version/hash и consent.
- Операционные input/read/work/call/time ограничения остаются.
- Retrieval включён в утверждённый план; прежний blanket deferral снят.
- Retirement — после независимого oracle, собственного зелёного baseline,
  intended mutation proof и сохранности helpers/imports/selectors/archive.
- Legacy acceptance по ADR0003: полный frozen fact coverage исходных cases
  с floor **12/15**. Raw original-query coverage — отдельная метрика;
  lookup/parent credit не повышает её. Миграция явно версионирована.
- Реальные Claude Code/Codex/OpenCode sessions **NOT RUN**. Installed SDK/stdio
  подтверждает CI transport, но не эти клиентские sessions.
- Локальные runtime/import/pytest/AST/install не выполняются. Используются
  существующие авторизованные PR workflows без новых providers/models.
- Обычные commits и fast-forward двух refs разрешены. Merge/release,
  force-push и внешние comments/messages не выполняются.

План: [PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md](PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md).
Решения: [CURRENT_WAVE_DECISIONS_RU.md](CURRENT_WAVE_DECISIONS_RU.md).
Старый local checkout не является актуальной базой.

## Фактический CI: 121

[Main run](https://github.com/Vanilla1999/DocAtlas/actions/runs/38021212993).
[P1-stack](https://github.com/Vanilla1999/DocAtlas/actions/runs/38021213074).
[Acceptance reader](https://github.com/Vanilla1999/DocAtlas/actions/runs/38021212993/job/114124354950).
[Точные selected runtime records121](pr211-execution/RUNTIME_EVIDENCE_c2a6682d.json).

На **каждом** Python3.11/3.12/3.13:
**7727 = 6065 PASS /1652 FAIL /0 ERROR /10 SKIP**.
Матрица не складывается в один baseline; JUnit integrity issues пусты.
Это те же counts, что на118. Удаление58 cases выполнено позже, в123.

| Python | SHA-256 JUnit |
| --- | --- |
|3.11|`184cd15117d6f42b743c4c56d32ac9111bc949ac5e9560ee6fdc0b855d47d93d`|
|3.12|`db291c4e5eecd8828995ff6a192a1e0039769eea18c0464c0a65112455237663`|
|3.13|`4c026aee08d93073b0df18c87f76b5b60fcd1f40b93ace99e139cdf0324474bd`|

| Gate | Actual121 | Граница доказательства |
| --- | --- | --- |
|Critical|**54P/0F/0E/0S;30 intended kills**|Все individual priority records доступны; нужные DQP4+relation1 guards/source/import hashes независимо проверены.|
|Recovery baseline|**12P/0F/0E**|Свой baseline здоров.|
|Recovery mutations|**FAIL**|filename-collision-first-winner пойман другим guard; полного33-kill summary на121 нет.|
|Literal historical/compact comparison|SUCCESS|Собственный existing producer step16 на том же checkout.|
|Lossless core projection|**32/32** на каждом Python|Все четыре будущих cap killer cases отдельно напечатаны как PASS; новые cap faults ещё не выполнялись.|
|Legacy live|Source-fact acceptance **8/15**, raw original coverage0|Floor12/15 не достигнут; report FAIL.|
|V2 live|Natural facts6/15; paraphrase1/5|REPORT_ONLY; production runner FAIL.|
|Agent Developer|v1:8target-closed/11;4target gaps. Adversarial24/28|false_supported0, contamination0; полезный context для части исходных задач отсутствует.|
|Installed MCP / retrieval evidence / platforms|SUCCESS|Завершённые jobs121; это не реальные Claude/Codex/OpenCode sessions.|
|Build / exact wheel / sdist installer|SUCCESS в P1-stack|Это отдельные packaging/installed jobs.|
|P1.4 / P1.6 / closure|FAIL|P1.5 SUCCESS. Подробные numbers предыдущего118 не выдаются за новые individual121 receipts.|
|Required CI / P1-stack exact|**FAIL**|Core и advanced остаются красными.|

Hermetic16/16 проверяет literal query identity без retrieval.
Legacy raw report8/16 и positive7/15 отличаются от принятого source-fact oracle8/15.
Agent Developer v1 полностью исполнил11tasks; проблемы setup не подменяются текущими quality gaps.

Reader:591931 UTF-8 bytes, SHA-256
`f2a9ab819aab5498f858d85f3525d3fbd9912e2b7ef090f2f28ca92a89e6b397`.
Разобраны407 JSON records без ошибок. JUnit console omitted0.
Critical priority31 records (baseline+30), recovery priority27, пропущено0.
Остальных artifact rows не напечатано41 из170 selected.
Все три V2 compact headers получены.

Receipt сохраняет все31 critical records,27 recovery,3 JUnit counts и provenance/omissions.
SHA-256 `d672705adec2e132a91dc894af261a688405addf9cbc06e7fc0051fd33a52d57`;
144504 UTF-8 bytes. Это selected parsed records, не полный diagnostic ledger.
Все42 baseline import rows получены отдельным probe subprocess, **не same-pytest-process attestation**.

## Применённый reviewed пакет122–125

| Slice | Commit | Изменение и состояние |
| --- | --- | --- |
|122|`85fdb5166e24e071b8a9b616895043819ac526ea`|Сохранение admitted acquired project windows после bounded control; native24-window control и1fault. Own runtime pending.|
|123|`4bc25f9b543ef8ac6c0f508aaf339c9ddad8cf54`|Удалены58 superseded compiler cases после собственного54/30 proof: DQP33 и relation25; архивы/helpers/guards сохранены. Post-removal runtime pending.|
|124|`d5811c8fc703073b21c2a2dd623c36f5f3b5307f`|Детерминированный filename collision guard по actual full naming plan, без смены expected guard/production/33mutants. Runtime pending.|
|125|`8552d125be7eef93c880592f71106b810c96dc48`|4направленных cap faults и2existing selectors (1+3cases);0new ordinary cases. Joint target59healthy/35kills pending.|

Каждый code slice имеет root и независимый peer review; локальных запусков нет.

- [Project window delivery](pr211-execution/PROJECT_READ_PRESENTATION_RU.md).
- [Retirement58 и audit118 файлов](pr211-execution/COMPILER_RETIREMENT_58_RU.md).
- [Filename guard](pr211-execution/FILENAME_COLLISION_PLAN_GUARD_RU.md).
- [Output cap precheck](pr211-execution/OUTPUT_CAP_MUTATION_PRECHECK_RU.md).

DQP теперь16definitions/37cases; relation4definitions/47cases.
Все5 DQP negative rows, relation helpers `CASES/probe/qualify`, source-policy15,
conditional3/native5 и safety26 сохраняются.
Ожидаемое новое core collection:7727−58=7669; фактического post-removal результата ещё нет.
Статическое уменьшение roster не является измерением ускорения.

## Оставшиеся причины и границы

### Request flow

Actual118: member31 windows/15qualified → Project и Unified20/9.
Control stage27items/18457bytes →20/12016, budget_exceeded=True.
Этот post-acquisition view overflow блокировал delivery при status=success и отсутствии consent.
Slice122 сохраняет отдельный admitted presentation pack, оставляя bounded control,
source hashes/catalog membership, consent/stale/dependency и реальные work bounds.
Нативный fixture требует24→control20→Project/Unified24 и полные байты каждого
реально выбранного public source. **24 публичных источника не обещаются**:
отдельное downstream правило no_new_direction ещё может сокращать presentation.

### Cache reset / architecture и original-only P1.4

[Аудит exact113](pr211-execution/V2_QUALIFIED_WINDOW_AUDIT_113_RU.md):
все3/1 qualified windows дошли до public. Нужные cleanup/infrastructure paragraphs
были найдены, но не qualified. Их нельзя объявить исправленными retention patch.

Разрабатывается отдельный versioned ordinary partial-body admission для двух
original-only P1.4 случаев: order drafts before upload и project network retries.
Дизайн требует actual same-call native discovery, finite current catalog/source,
exact body/hash/span/scope и двух последовательных content words исходного вопроса
в одной substantive source clause. Generated queries, synonyms, stemming и
original/answer/edit grants не добавляются. Весь исходный вопрос остаётся missing.
Технические/literal/path вопросы сохраняют старые строгие lanes.
Этот draft ещё не входит в reviewed122–125 и требует native controls/ADR/review.
Обычный modifier вне доказанного span не получает answer credit; frozen literal/lunar
negative controls и single-hit/metadata/split-clause запреты сохраняются.

### Recovery

В121 first-winner mutant встретил `recovery_filename_path_selection_not_naming_scope`
вместо `recovery_filename_catalog_ambiguity`. По source сортировка opaque source IDs
и удаление одинаковых title/body могли выбрать разных members; actual winner неизвестен.
Slice124 проверяет уже вычисленный полный naming plan до public no-source assertion.
Все12case names,33mutants и их intended guards сохранены. Нужен собственный новый12/33 PASS.

## Следующие действия

1. Опубликовать reviewed122–125 и этот checkpoint обычным fast-forward обоих
   implementation/pr211-merge-readiness и integration/stage3-v2-identity-pr1.
   Проверить новый CI merge SHA/tree и фактические required/downstream jobs.
2. Проверить own59healthy/35intended critical kills, recovery12/33, lossless
   controls, exact58 removal и native24-window delivery; сохранить individual receipts.
3. Только после четырёх новых cap kills отдельным slice удалить старый
   `test_context_budget_is_a_product_invariant`, обновив precise AST state,
   crosswalk и owning node hash. Этот один старый3/800 test пока collected.
4. Довести ordinary partial-body slice с независимыми native positives/negatives
   и scoped receipt; не менять frozen questions/facts/host lookups.
5. Продолжить remaining relation47 и другие failing families через независимые
   original-task/source controls, не удалять их только из-за красного CI.
   Завершить quality/required/downstream и необходимые installed/client acceptance.

Исторические actual118 и113 сохранены в соответствующих receipts. Статический
APPROVE, старый SHA или aggregate SUCCESS не заменяют отсутствующий собственный runtime.
