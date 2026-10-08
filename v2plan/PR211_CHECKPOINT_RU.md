# PR #211: опубликованный checkpoint текущей волны

Дата: 2026-10-08. Это статус изменений, НЕ merge/release approval.

## Включённые результаты

- Reviewed предыдущий checkpoint B/C на edf1ced6 и его 17 commits сверх34fc371e.
- Guard tests acquired qualified retention; upstream retrieval не менялся.
- Пять прежних conflicts мигрированы в fidelity/inert-data controls с сохранением
  параметров и технических/операционных отказов; independent R-AC approval.
- Сняты remaining output caps в joint/query-block/recovery/project packing;
  optional work/acquisition/source/read/security bounds сохранены. CallerNone
  migration завершена, transitional800/3 aliases удалены; R-B approval.
- Schema missing/module_candidates representation caps сняты; byte ceilings
  не менялись; R-D approval.
- Компактный docs-only default MCP surface; patch формат в явно включаемом
  существующем advanced режиме. Default context_format (включая null) отвергается
  до service I/O. Internal patch/source validators сохранены.
- Root/generated skill сокращён; четыре optional guides включены в package,
  installation helpers и Desktop ZIP. Reference writes confined/no-follow,
  symlink/malformed destination controls добавлены; R-SKILL-FIX approval.
- Companion schema/workflow tests мигрированы по явно проверенному structural
  baseline delta; R-COMPANION approval. Отложенный retrieval анализ записан
  в after-merge/RETRIEVAL_DEFERRED_ANALYSIS_RU.md.

## Совместный run

Tested code SHA: `5310e6da83a09daa0938efa9cf68e2c0f7c99851`.
Normal conftest, private fixture app-home/basetemp, pre-import network/descendant
denial, verified worktree imports. **801 collected = executed; 791 PASS /
10 FAIL / 0 ERROR / 0 SKIP**. Exact roster equality, no duplicated concrete nodes.
Counts не суммируют пересекающиеся агентские runs. No full CI/transport certification.

### Остались десять failures

1. Catalog footprint: 7602>6144 bytes. Docs output отдельно860<1000 PASS,
   но combined footprint test останавливается на catalog assertion.
2. Registration resource assertion ожидает старый `mode="library"` в resource,
   текущий unified interface использует library parameter. Не мигрирован в этом checkpoint.
3. Host-scope wording assertion ожидает `repo-level plus modules` вместо компактного
   эквивалентного `repo+modules`; structural/runtime scope controls не отменены.
4. Public documents test ещё ожидает output≤200, actual2466 estimated tokens.
   Этот отменённый cap assertion требует отдельного fidelity successor.
5. Historical resource trust assertion: ожидаемые explicit_agent_policy и
   scoped_agent_policy расходятся с actual scoped_repository_document/untrusted_data;
   base8346 уже содержал actual values. Guard намеренно не ослаблен.
6–10. Пять `test_public_scope_never_implicitly_widens` variants получают
   handler_exception при запрещённом test-runner descendant. Это safety/environment
   blocked scenario evidence, записанное pytest как FAIL, не доказательство
   корректной scope delivery и не скрытый PASS.

## Footprint и текущие границы

Serialized default advertised catalog21409→7602 bytes (примерно64% уменьшение).
Default output12866→860 bytes. Это не фактические model tokens и не гарантированная
client-visible экономия. Advanced catalog остаётся подробным, explicitly enabled.
Нет нового dynamic loader/registry. Обычный docs call не требует skill-first.

Upstream paraphrase/multi-section/long/partial admission fixes отложены владельцем.
Настоящий source/installed stdio, real-client visibility, full CI/downstream gates,
platform acceptance и historical unknown failures НЕ закрыты этим checkpoint.
Не выполнять downloads/provider/user-index/permission workaround ради PASS.

## Provenance

Integration branch перед публикацией: implementation/docatlas-next-pr211.
Один remote PR target: origin/integration/stage3-v2-identity-pr1, PR211, base main.
Обычный fast-forward push, без force-push, merge или release.

Артефакты review/commands/JUnit/origins/точные outcomes:
`/tmp/opencode/docatlas-next-8e38eet1/` — R-AC.md, R-D.md, R-B.md,
R-COMPACT.md, R-SKILL-FIX.md, R-COMPANION.md, FINAL-outcomes.json,
CP-final-collect.log, CP-final-test.log, CP-junit.xml, FINAL-surface-measurements.json.
Эта документация добавлена после tested code SHA; source/tests при этом не менялись.
Локальные DB/cache/raw sessions и полные artifact folders не включены в git.
