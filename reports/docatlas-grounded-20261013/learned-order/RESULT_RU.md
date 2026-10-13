# Пилот learned reranker: обе задачи всё ещё FAIL, эксперимент остановлен

Один готовый `cross-encoder/ms-marco-MiniLM-L6-v2`, pinned local nonquantized
ONNX graph, без новых semantic heuristics. Только изменение order всех
source-admitted полных окон, не top-k, cutoff, crop, adjacency rule или новый
retrieval. Existing provenance checks и full public DTO cap12000 сохранены.

| Case | Native | Learned | Существенное наблюдение |
| --- | --- | --- | --- |
| P03 | FAIL | FAIL | Rule в начале; example rank74→106, отсутствует |
| E01 | FAIL | FAIL | Все6 filenames rank137→1, доставлены; continuation rank46 отсутствует |

Старый oracle не переписывался. Для E01 это **частичное улучшение фактической
доставки списка**, не PASS полного witness. Для P03 основное правило доставлено
в обеих arms; обязательный code example остаётся отсутствующим.
Не объявлять model answer quality: generation0.

## Исполнение и независимые gates

-2 prepares,4 public get_docs_context (2x2), installed wheel Python -I, real
  isolated member SQLite. Shared generation/root каждого pair; alternating order.
- Одинаковые ordered admitted pools для обоих pair:2/2. Default None — native.
- Sources/hash/spans/scope/version/authority integrity4/4, read-only4/4.
- Full public DTO budget4/4, расходы по native/learned:
  P03=11805/11962, E01=11916/11942, cap12000.
- Модель видела167+256=423 полных question/window pairs;53 ONNX batches.
  Max pair lengths275/269 при max512; truncated0, fallback0, ошибок0.
- Cold load0.380s, model execution P03=1.439s/E01=2.349s;
  total workload30.410s. Это pilot timings, не production latency.
- Context times P03 native4.978s/learned6.245s,
  E01 native7.754s/learned9.974s, including trace and optional copied receipts.
-470 frozen inputs проверены без изменений. Corpus/questions/oracle/evaluator
  не менялись; gold только offline. Установленные product files соответствуют wheel.
- Один pilot run,0 runtime retries,0 answer generator calls,0 второй модели.

**Pilot gate FAIL**, поэтому conditional full40x2 **НЕ ЗАПУСКАЛСЯ**.
В generic unchanged assessor unrun38 вопросов на arm записаны NOT_RETURNED;
это76 unrun rows, не76 ошибочных calls. `PILOT_RESULT.json` учитывает только4
запланированных returned rows. Никакого нового результата24/8/8 здесь нет.

## Что изменено в коде

`docmancer/docs/application/experimental_candidate_selection.py` — opt-in host
callback использует immutable question/passages и только complete integer
permutation pool. None сохраняет native order. Callback не подключён к MCP wire,
не используется по умолчанию и не добавляет ordinary model dependency/download.
При ошибке callback нет silent fallback. Order invalid guards добавлены, но
malicious/invalid-callback public scenarios этим пилотом отдельно не проверены.

`eval/heuristic_removal/learned_order.py` — paired installed runner, pinned local
ONNX, no oracle runtime input; independent state/source/cap/equal-pool checks.
`docs/experimental-learned-order.md` — experimental контракт без claims улучшения.
Learned sorter **не внедрён как default**. Никаких изменений вопросов/gold или
подгонки model inputs после результатов. Commit/push/deploy не выполнялись.
Предыдущие uncommitted diagnostic файлы E01/P03 сохранены.

Default native source order проверен как baseline внутри4 public calls, не как
полная regression suite; SDK/stdout/client/production smoke здесь не заявляются.
Это development на открытых двух вопросах, не новое blind доказательство.

## Исследования после FAIL

Выполнено требование владельца «если не получится — ищи исследования».
Подробный разбор primary papers, механизмов, ограничений и воспроизводимости:
[`RESEARCH_RU.md`](RESEARCH_RU.md).

Основной следующий принцип — learned **выбор взаимодополняющего набора**, а не
ещё одна независимая оценка каждого окна. SetR(ACL2025) и ParaSet/SetCE(preprint
2026) исследуют collective usefulness; Late Chunking — contextual chunk
representation; Sufficient Context(ICLR2025) — отдельную sufficiency/abstention
задачу. Эти результаты не устанавливают PASS для DocAtlas.

Готовый pinned deployable SetR checkpoint в прочитанном official README не
подтверждён; evaluation section=TBD. ParaSet использует approximate beam search
и training, поэтому нельзя выдавать его за полностью безэвристический drop-in.
Не добавлены manual-neighbor boosts, thresholds/MMR и не повысили budget.
Второй эксперимент/собственное обучение автоматически не запускались.

## Артефакты и воспроизведение

- `PROTOCOL_RU.md`, `FROZEN_PILOT.json`, conditional `FROZEN_V40.json`: frozen
  design/artifacts/gates до product/model calls, full V40 manifest NOT EXECUTED.
- `PILOT_RESULT.json`: gate, original native/packed scoring, target window raw
  hashes/bindings/logits/ranks/delivery, model receipts, fairness, budgets/state.
- `pilot/` raw native/learned public DTO, selection universe/exclusions, model
  input hashes/lengths/raw scores/order, source checks, trace, snapshots/ledger.
- `pilot-assessment/`: unchanged independent original evaluator results.
- Raw receipts losslessly archived in `receipts.tar.xz`, verified against every
  per-file SHA in `RECEIPTS_ARCHIVE.json`; local unpacked copies retained.
  В архив также включены первичные research HTML и official SetR README с URLs/hash.
- Model weights outside repository; revision/hash identity pinned in manifest.

Executed once:

```sh
timeout 600 /tmp/opencode/docatlas-learned-reranker-runtime-20261013/bin/python -I eval/heuristic_removal/learned_order.py --manifest reports/docatlas-grounded-20261013/learned-order/FROZEN_PILOT.json --output reports/docatlas-grounded-20261013/learned-order/pilot --work /tmp/opencode/docatlas-learned-order-pilot-20261013
```

Offline, no product/model calls:

```sh
/tmp/opencode/docatlas-learned-reranker-runtime-20261013/bin/python -I eval/heuristic_removal/assess.py --manifest reports/docatlas-grounded-20261013/learned-order/FROZEN_PILOT.json --run-dir reports/docatlas-grounded-20261013/learned-order/pilot --output reports/docatlas-grounded-20261013/learned-order/pilot-assessment
/tmp/opencode/docatlas-learned-reranker-runtime-20261013/bin/python -I reports/docatlas-grounded-20261013/learned-order/summarize_pilot.py
```

Freeze абсолютных paths относится к текущей машине; перенос requires новый freeze,
не изменение saved receipts. Воспроизводить product только в свежих output/work.
