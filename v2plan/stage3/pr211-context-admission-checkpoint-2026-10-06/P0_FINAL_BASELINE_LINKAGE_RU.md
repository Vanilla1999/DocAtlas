# P0: финальная привязка baseline evidence

**Вердикт: baseline audit gate PARTIAL, не green и не missing frozen failure log.**
Проверка read-only; baseline/tests не запускались, network/fetch/merge не выполнялись.
Изменены только этот отчёт и `archives/p0-final-baseline-linkage.json`.

## Что именно pinned

P0 HEAD — `8d2381d8c9d18498483feaaab918d93dfee47969`, Git tree —
`e583d59af4512d0d832fbdb9ed93ce95808ed866`. Это **не чистый worktree baseline**:
`project_retrieval_intent.py` уже изменён пользователем. Diagnostic runners восстанавливают
published producer через `git show 8d2381d8:…` в памяти; они не снимают весь local diff.
383 product-file pins и два lock/config pins из `p0-dictionary-static-audit.json.gz`
совпали с текущими bytes. Static manifest Python **3.14.3** нельзя подменять runtime
Python **3.12.3** из `p0-transition-manifest.json` (editable doc-atlas 1.3.2).
Исходный static `product_diff_sha256` и текущий `git diff -- docmancer` имеют разный
scope/serialization; равенство этих двух digests не заявляется.

## Official frozen: красный запуск действительно сохранён

Точный адрес: `archives/retrieval-alias-ablation-2026-10-06.tar.gz::pr211-alias-published-direct15-test.log`.
SHA256 member: `7a42b835eb1d9d336cf26550937535f87803b1868fe059921b22b0aba3133e69`.
Archive SHA256: `14be204be49c4a6e98999114fb99260b50c5ce16e9bf06091cc3318cae424fd0`.
Вложенный `MANIFEST.json` связывает member с P0 HEAD и `acceptance=false`.

Лог содержит **1 failed in 0.51s**: `test_direct_docatlas_questions_15_visible_context_covers_all_required_facts`
→ `_assert_direct_15_sidecar` → README blob mismatch **до retrieval**.
Expected Git blob SHA1 `1a1975b2ffaf587f3b752c1966acdb20e7a88468`, actual
`9678dd4d10ca77856e33393ffa8e0db1c7539772`; actual подтверждён локальным HEAD.
`cases.json` SHA256 `48ddd7030c886cfe3df2959df65e092298823b7c308f240a8644fd03a4571d7e`,
sidecar baseline commit `e179471527e009c88f77acbdaeeeeb8ad1c8d316` — это другой pin,
не P0 HEAD. Frozen contract: scope all, lookups absent, 3 sources / 800 tokens.
Проверка source в `tests/docs/test_direct_docatlas_questions_15.py:19–45` подтверждает,
что это Git blob SHA1, а не SHA256 артефакта. Gold/sidecar не обновлялись.

**Остаток provenance:** этот member не содержит команду, environment или exit-code
record; вложенный manifest также их не содержит. Команду
`.venv/bin/python -m pytest -q tests/docs/test_direct_docatlas_questions_15.py`
можно восстановить из test identity, но нельзя выдать за archived executed command.
Python/config соседнего diagnostic replay не доказывают environment этого pytest.
Новый запуск не нужен для подтверждения существующего failure; предпочтительно
добавить уже существующий execution record, если он есть вне обследованного checkpoint.

## Diagnostic replay и controls: что доказано, а что нет

Четыре `p0-stages-{ru-original,ru-lookups,en-direct15,trust}.json.gz` связаны с
runner `p0_stage_baseline.py` и `p0-stage-wheel-evidence-hashes.json`; все pins совпали.
Runner CLI: `.venv/bin/python <checkpoint>/p0_stage_baseline.py <arm> <output>`
(**reconstructed recipe**, не shell transcript). Каждый JSON содержит HEAD,
published producer SHA256, tracked source snapshot, actual SQLite/config identities,
same-call projections и text blobs. `with_vectors=false`, model calls 0, socket attempts 0.
`p0-trace-integrity.json` сохраняет exact-row/blob/citation validation, не acceptance.
RU useful counts 8/15 и 12/15, EN 11/15; EN verdict **FAIL**, positive 2/15,
17 errors. Trust без gold не даёт acceptance. Replay обходит frozen precondition и
**не заменяет official frozen**.

Existing subsets имеют точные archived logs: config **18 PASS**, connectors **67 PASS**,
policy **81 PASS**, neighbor **76 PASS** (SHA256 в JSON). Это не full required CI.
`EXECUTION_STATUS_RU.md:19–34` записывает red core/advanced/adversarial/required-ci/P1
и green required-release, но не содержит их полного P0 execution bundle.
В обследованных семи parallel/simplification tar archives baseline controls относятся
к `37bfd0668f819935dd9e027bd9d8bf767fcd185a`, а не к `8d2381d8…`;
`parallel-strict-attribute::environment.json` явно задаёт Python 3.13.12.
Candidate/ablation logs нельзя переименовать в original P0 controls.

## Итог по gap `P0_PARALLEL_CLOSURE_ASSESSMENT_RU.md:156–175`

1. **Frozen failure linkage закрыт:** конкретный log, hash, HEAD, test/config/sidecar
   и failure branch найдены; red допустим как recorded baseline.
2. **Строгая command/environment linkage PARTIAL:** нет archived executed command,
   process environment/exit record, привязанного именно к frozen pytest member.
3. **Required-control scope PARTIAL:** не найден same-P0 pinned execution bundle
   для official core matrix, advanced lineage floor, adversarial, required-ci/release
   и применимых P1 jobs. Исторические reports перечисляют состояния, а старые
   archives/diagnostic subsets не дают такой замены. Это граница обследованного
   checkpoint, не утверждение, что записи отсутствуют на всех дисках/CI.

Проверены **213 manifest artifact/member comparisons**, mismatch **0**, плюс
**383 product и 2 lock/config pins**, mismatch **0**. Hash consistency — не принятие
качества и не доказательство полного execution provenance. Baseline не повторять
ради green: сначала найти/привязать конкретные недостающие execution records.
Общий P0/P1 gate, workflows, thresholds и gold не изменены; merge approval отсутствует.
