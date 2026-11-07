# Capability repair — implementation и scoped public regression

## Revision, не перезапись freeze

Exact BEFORE bytes трёх production files и SHA map сохранены до правок в
`history/capability-before-fix/`. Actual correction-only diff: `production.patch`.
Изменены только:

- `docmancer/docs/application/_source_continuation_core.py`;
- `docmancer/docs/application/source_continuation.py`;
- `docmancer/docs/interfaces/mcp/context_tools.py`.

Старый approved manifest `87585ea10a1c0a4e6673020368ad51ee0e64bdd9ca3d6de4ca8ddce86a34046a`
и policy `16fb92b9687d68c30cdc8bfa8656b20d512da2b9b8600497ed78a0f5742d0f11`
не переписаны. Остальные531 bound files неизменны. Новый **неутверждённый**
repair manifest: `repair-manifest.json`; старый frozen manifest теперь закономерно
не валидирует три исправленных production файла. Никакого fitter/calibration/
validation не запускалось. Threshold0.8670357465744019 неизменён.

## Реализованный контракт

Handler передаёт host-only `binding_intent=fresh_query` только для текущей
реально acquired portion1 без continuation_token. Default binding — rebind.
Earlier portions используют registration snapshot и rebind; snapshot читателя
дополнительно маркируется registration-only и не принимает fresh intent в binder.
Legacy nonminimal registration code path не изменён.

Reader сохраняет session nonce и canonical→(ordinal,latest URI) map без source
text. Registration snapshot копирует map и tombstones; tuples immutable. Fresh
resolver вызывается только на staged reader. Active alias reuse не меняет TTL
или read budget. Consumed/expired latest capability получает новый nonce-bound
opaque URI с проверкой collision против cursors/spent. Strict issue/issue_range/
read spent branches не ослаблены; old URI не следует alias и не оживает.

Atomic binder проверяет canonical locator против native checked source, remap
public source/bound.projected_source/bound.source_uri на staged DTO bindings.
Read-next target имеет отдельную canonical range проверку/remap (minimal v2
обычно не выдаёт read_next). Native source objects сохранены, не deep-copied:
same-call lineage не подменяется serialized copies. Projection validation,
refresh estimate и full rendered-token pricing выполняются после actual URI
bytes; затем live authorize/hash reread/authorize/expiry и commit maps+packet+
snapshot под lock. Fingerprint preselection/semantic recipe не изменены.

Expiry/atomic-fault code-review границы, НЕ runtime injected proof:

- staged `_expire` добавляет tombstones; renewal не удаляет их и не refresh-ит
  существующий cursor. Consumed/expired URI rebind остаётся unavailable.
- Registration snapshot независим по cursors/spent/issuance map. До завершения
  проверки body/hash/expiry live reader не получает ни ordinal, ни alias/cursor.
- Remap/validation/budget/authorization failure возвращает body-free refusal;
  staged DTO/maps не публикуются. Post-remap overflow также не commits issuance.
- Snapshot-only fresh intent отвергается; rebind не вызывает fresh resolver.
- Не имитировались gateway faults/clock/expiry; эти ветки требуют отдельного
  разрешения для runtime. Existing legacy test ниже подтверждает public replay,
  но не atomic injected failure/expiry или renewed aliases across restart.

## Один Qwen public regression — PASS с первой попытки

```sh
HF_HUB_OFFLINE=1 TMPDIR=/tmp/opencode /tmp/opencode/step10-qwen-gpu-py312/bin/python -m eval.blind_project_context.step10-qwen-capability-repair.regression
```

Raw output `/tmp/opencode/step10-qwen-capability-repair-01`; byte-exact copy
`run-01/`, SHA map `raw-sha256.json`. Новый driver `regression.py`; старый
failing reproduce.py/raw не изменялись.

Sequence выполнен полностью: C-T1 → consume Retention U → replay U unavailable
→ fresh C-T3 с V!=U → identical fresh C-T3 до read V, **literal packet equality**
→ consume V → U remains unavailable → replay V unavailable.
Read U/V вернули exact following Capacity lines9–12 с original document hash,
не Retention snippet. C-T3 required units/facts реально доставлены в обоих packets;
per-query проверки complete spans/hash/scope/version/project identity, facts,
hard negatives и actual rendering budget находятся в `*-checks.json`.
Readonly before/after source+catalog/logical DB/assets совпадают, полные значения
сохранены в `readonly.json`. Policy не переделывалась ради результата.

**1prepare,3queries,5reads,63forwards,28536 model-input tokens.**
Sum query wall6.000701277s; scorer5.415954459s; forwards1.092691899s.
Peak allocated1,221,214,208 bytes; reserved1,245,708,288 bytes.
1model load,2runtime cache hits,0score cache hits. Полные receipts, prepare/read
latencies и queries в raw; aggregate `costs.json`. Это lifecycle regression на
новом root/generation, не semantic split acceptance и не exact calibration replay.

## Один разрешённый legacy public test

`tests/test_context_portions_integration.py::test_context_portion_replay_keeps_spent_reads_spent_and_issues_new_sources`
— **1 passed in0.90s**. Existing test не переписывался.1prepare/3queries/6reads
по выполненному сценарию; отдельно от Qwen counters выше.
Две setup attempts не исполняли test: GPU env без pytest; системный pytest без
jsonschema. Они сохранены в `TEST_RECEIPTS.json`. Offline установка pytest и
pytest-asyncio добавила только5 test packages в GPU env; core model pins не менялись.
Затем выполнен только этот test, без suite и без runtime regression rerun.

Final static checks — `static-checks.json`. Новый repair manifest включает
post-install package provenance. No commit/push/delegation; parent v2plan untouched.

## Provenance предел следующего этапа (parent discovery учтён)

Исторические prepared SQLite были TemporaryDirectory и удалены после exit.
Native source_identity содержит random generation UUID, входящий в incoming
context hash. Повторный public prepare даже на прежнем absolute root не
воспроизводит exact inputs. Ручное восстановление generation/binding запрещено.

После parent review/refreeze следующий этап следует назвать **fresh-prepared
recovery acceptance**: прежние threshold/originals/labels/prompt/recipe,8final
queries, без8diagnostic queries и без нового fit. Model-input hashes могут
отличаться; старые offline unit predictions тогда только diagnostics. Gate —
независимые unchanged required facts/units/no-answer/hard-negatives/50% reduction.
Потеря facts означает FAIL, не tuning. Такой runner сейчас НЕ реализован и НЕ запущен.
