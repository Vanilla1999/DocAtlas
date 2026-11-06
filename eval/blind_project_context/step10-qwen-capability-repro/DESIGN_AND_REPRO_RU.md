# Spent capability: reproduction и proposed minimal lifecycle fix

**Implementation НЕ выполнена.534 frozen files, manifest и policy неизменны.**
Один разрешённый targeted reproduction, не calibration. Validation/T01/Terra/L2,
повтор inference, тесты и изменение threshold не выполнялись.

## Exact public reproduction и граница диагностического assertion

Command:
```sh
HF_HUB_OFFLINE=1 TMPDIR=/tmp/opencode /tmp/opencode/step10-qwen-gpu-py312/bin/python -m eval.blind_project_context.step10-qwen-capability-repro.reproduce
```

Оригинальный immutable output: `/tmp/opencode/step10-qwen-capability-repro-01`.
Byte-exact raw copy `run-01/`; hashes/стоимость/offline interpretation в
`offline-review.json`. Copy не переименовывает runtime root.
Driver `reproduce.py` оставлен в выполненном виде, включая ошибочный assertion.

Sequence:1prepare всех7 TideGauge originals, exact C-T1/project scope → consume
delivered storage.md Retention URI → replay того же URI → exact C-T3.2reads,
first-source read не понадобился. Frozen policy hash
`16fb92b9687d68c30cdc8bfa8656b20d512da2b9b8600497ed78a0f5742d0f11`,
threshold0.8670357465744019; model/recipe/prompt неизменны.

Actual consumed URI: `docatlas://source/v2/838a9a5e37e5e6522849e141`.
Он относится к delivered Retention lines5–8. Его **continuation read** возвращает
следующий полный Capacity section lines9–12, source-exact text и document hash;
это ожидаемый source-read контракт, не повтор Retention body. Replay unavailable.

Raw C-T3 trace:

1. `issue` call для этого URI: `requested_uri_spent=true`.
2. `issue` return: `None`, line95 (выход из `with self._lock`).
3. `_bind_atomic` exception на line312: `ValueError('source_reference_rejected')`.
4. Public C-T3 packet: `status=error`, `hard_stop=true`,
   `reason_code=source_reference_batch_rejected`, `sources=[]`.

Это не один внутренний flag: реальное read/replay, фактический failed issue,
exception вызывающей batch-регистрации и конечный public refusal сохранены.
Frozen issue control flow однозначно связывает их со spent guard98–99:
gateway denial вышел бы на94 до lock; `_expire()` только добавляет tombstones,
а следующий первый условный выход при spent URI —99, до URI-format/existing-cursor
checks. Reader minimal mode подтверждается public v2/одноразовым read path.

Driver завершился exit1 **из-за своего assert `return_event.line==99`**. CPython
при выходе из `with` сообщает return event на95, даже когда return выполнен внутри.
В `trace.json` line events не сохранялись; прямого line99 event не заявляем.
Exact branch установлен actual call/return/exception + frozen control flow.
`failure.json` и operation_error в read-only audit сохранены, не переписаны в PASS.
Отдельное offline conclusion — `OFFLINE_CONFIRMED_PUBLIC_SPENT_REJECTION`.
Inference не повторялся ради исправления assertion.

Стоимость: **1prepare,2queries,2reads,42forwards,19076 model-input tokens**.
Prepare0.126478696s; scorer total6.921350753s; forward0.898097521s.
Peak allocated1,221,184,512 bytes, reserved1,245,708,288 bytes.
Полные per-query latency/runtime/cache receipts в offline-review и raw C-T*.json.
Trace counters внутри calls показывают ранее завершённую работу; final counts
включают обе попытки. Before/after source/catalog/DB/assets совпали несмотря на
driver assertion. Post-run approved manifest и534bound hashes перепроверены.
Небольшое отличие token count от calibration связано с новым native identity/root
в hashed incoming entries, не с изменением исходных документов/вопросов/recipe.

## Текущий issuance/replay flow

- `source_continuation_uri` формирует deterministic locator по root/project/path,
  source+catalog hashes, scope/module, heading/span. Это identity источника/span,
  но сегодня одновременно capability identity, без issuance generation.
- `attach_source_continuation_locators` синхронизирует public row `source_uri`,
  `bound['projected_source']['source_uri']` и `bound['source_uri']`.
- `continuation_fingerprint` включает весь canonical checked pool/rows, source
  и reference bindings, query/settings. Поэтому нельзя просто рандомизировать
  pool locators до fingerprint: это сломает continuation/replay consistency.
- `context_tools.py:498`: ранний bind только вне experimental budget path.
  В experimental/minimal режиме finalizer590–603 регистрирует выбранный packet;
  для пересчитываемых earlier portions599 создаёт `registration_snapshot`.
  Requested current portion использует live reader.629 — отдельный compressed path.
- `registration_snapshot` копирует cursors, lock и spent set, не меняя clock,
  gateway, limits. `_bind_atomic` ещё раз staging-copy под live lock, затем
  issue, live gateway authorization, hash reread, expiry check и atomic commit.
- `read` удаляет cursor и добавляет spent tombstone. `issue` при явном spent URI
  возвращает None. Такой запрет необходим для stale-packet rebinding, но fresh
  authorized C-T3 сейчас не отличён от replay и получает тот же deterministic URI.
- `test_context_portion_replay_keeps_spent_reads_spent_and_issues_new_sources`
  сохраняет old unavailable и выдаёт другой source на следующем portion; это
  полезный existing public replay regression, не доказательство same-source renewal.
  `_semantic_packet` в prepared-retrieval tests уже исключает session URI/estimate
  из semantic parity, сохраняя остальные поля и отдельную actual-budget проверку.

## Предлагаемый контракт (на review, не применён)

Разделить **canonical source locator** и **session issuance capability** только
на minimal v2 binding boundary. Не менять semantic selection/scorer/fitted policy.
Fresh authorization нельзя выводить из самого packet или из отсутствия URI в cache.

### Fresh против replay

Добавить host-only параметр binding intent с default `rebind` (без renewal).
`fresh_query` допускается из public handler только для новой portion1 без
continuation_token, после настоящего retrieval/qualification этой же попытки.
Повтор того же пользовательского вопроса без token — новая авторизованная query;
присланный старый token/continuation, cached/stale packet и earlier-portion replay
— `rebind`, никогда `fresh_query`. Wire JSON не может задать этот параметр.
Для compressed path629 intent должен определяться так же; legacy path498 не
менять renewal-семантику (новый механизм только reader.minimal).

На fresh path перед remap сверить исходный locator с canonical locator,
вычисленным из native checked snapshot. Нельзя использовать произвольный URI
из serialized packet как ключ для renewal. Native qualification/lineage не
заменять gateway authorize: нужны обе существующие границы.

### Session-local renewal, только когда старый capability spent/expired

Минимальные дополнительные reader state: session nonce (создаётся один раз) и
map canonical locator → latest issued URI + monotonic issuance ordinal. В map
нет исходного текста. Nonce нужен лишь для renewed opaque identifiers, не для
первых deterministic locators/всех queries. Одинаковое session state/OFF-ON
использует тот же active URI и expiry, без refresh бюджета/TTL.

Fresh query resolution на **staged reader** под lock:

1. Канонический URI ещё valid active — reuse без изменения expiry/read budget.
2. Для canonical locator есть active latest renewal с теми же reference/range
   bindings — reuse его, без renewal TTL.
3. Canonical/latest capability spent или expired — reauthorization + новая
   issuance ordinal, URI=`prefix+SHA256(session_nonce,canonical,ordinal)[:24]`.
   Проверить отсутствие collision в cursors/spent; не удалять tombstones.
4. `rebind` не следует alias map и не mint-ит: старый spent URI остаётся отказом.
   Это правило сохраняется и на registration_snapshot для earlier portions.

Map/ordinal/nonce копируются в registration_snapshot; commit вместе с cursors/
spent только после успешного полного batch. Replay snapshots не commit в live.
Не сбрасывать reader/session, не очищать spent, не вызывать issue(uri=None)
как скрытый unconditional обход stale packet. Renewal не grants authority.
State живёт ровно в reader/session, не model cache и не persistent source store.
Session restart не восстанавливает renewed capabilities; nonce исключает их
случайное повторение в новом session. Исторический deterministic first-issuance
контракт сам по себе этим scoped исправлением не расширяется.

### Atomic packet/snapshot/pricing

В `_bind_atomic` работать с staged packet + staged snapshot и staged reader,
не мутировать исходный packet частично. Обновить в одном месте public row,
projected_source и bound.source_uri, а также read_next/range bindings если они
есть. Native content/hash/span/authority/version не меняются. Любые связанные
DTO renderings вычислять заново из updated packet, не оставлять cached text.

Существующий initial budget check может остаться cheap rejection, но НЕ authority
для commit: после фактических URI bytes заново render/price complete packet,
проверить projection/snapshot consistency, reauthorize/read hashes/expiry, затем
atomic commit всех maps+packet+snapshot. Даже fixed-width hex меняет BPE pricing.
Failure — body-free refusal и никакого частичного renewal/live registration.

Canonical preselection pool locators остаются неизменными; continuation
fingerprint вычисляется по ним ДО issuance remap. Нельзя fingerprint actual fresh
session URI. Replay token связывает query/source/settings, не разрешает renewal.
Minimal v2 не имеет productive second portion (exhausted); существующий generic
paging replay contract не менять этим scoped fix. В дальнейшем его versioning
обсуждать отдельно, а не добавлять alias-map authority к cached packets.

## Smallest proposed diff surface

1. `_source_continuation_core.py`: session issuance state и его snapshot copy;
   небольшой explicit fresh-resolution method. `issue/read` strict spent contract
   оставить; renewal отдельный вызов, не ослабление issue.
2. `source_continuation.py`: optional host-only intent; staged resolution/remap,
   binding consistency, post-remap pricing, all-or-none commit/reauthorization.
3. `interfaces/mcp/context_tools.py`: явный intent только для fresh portion1;
   earlier/rebound portions всегда rebind, compression entry согласован.
4. Один existing public integration scenario расширить для same-source fresh
   renewal (предпочтительно рядом с context-portions replay), без unit helpers.

Не предполагаются изменения scorer/recipe/policy/questions/labels/source texts,
evaluator resource-read sequence, continuation token semantics или threshold.
`context_continuation.py` не должен требовать diff при сохранении canonical pool.
Если implementation покажет необходимость менять fingerprint format, остановиться
и согласовать отдельный контракт, а не молча invalidate исторические tokens.

## Один необходимый public regression после approval

Reuse real prepared structural fixture и existing public source-read assertions.
Одна preparation; queryA → получить relevant complete body и URI U → consume U
(проверить full following source section, independent hash/span/scope) → replay U
unavailable → fresh queryB (реальная qualification, source содержит тот же body)
→ successful packet с V!=U → read V source-exact → read U unavailable.
Итого2queries/4reads; policy/semantic expected facts не менять. Сравнить required
source facts/hash/scope/version, projection consistency и actual rendered budget;
DB/source/catalog readonly и старые URI never revived. Нельзя добиться PASS
удалением read между queries, resetting service или private ._spent injection.

Existing portion replay сценарий оставить контрольной границей: old tokens/
earlier portion не получают новую issuance, новые источники следующего portion
доступны. Atomic-refusal/expiry сценарии из `probe_source_references.py` полезны
как design reference, но они используют hand-built private packets: не объявлять
их новым public integration proof и не добавлять private-helper тесты.
После approval reuse публичных source-change/expiry cases должен проверять:
изменённые bytes/catalog/version ⇒ body-free refusal/no new usable URI;
expired capability ⇒ unavailable, rebind не продлевает expiry; fresh rechecked
query может выдать новый URI. Time boundary допустимо задавать host-configured
коротким TTL и реальным public read после expiry, без подмены gateway/scorer.
Atomic mid-batch failure без искусственной подмены требует отдельно согласованного
public reproduction; до него all-or-none rollback остаётся control-flow review,
не runtime-injected proof. Не расширять это разрешение до broad-suite.

Следующий этап — parent approval lifecycle design/implementation. Полный
calibration replay только после implementation review/refreeze, с прежним
numeric threshold и без поиска другого cutoff.
