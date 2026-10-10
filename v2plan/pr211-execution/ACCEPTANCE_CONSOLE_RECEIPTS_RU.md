# PR211: полный диагностический вывод acceptance receipts

## Наблюдаемая нехватка вывода

CI136: HEAD `a9fba17d13ea16ed0dbbb4692ab6029ae6da6a07`, run `38026891736`,
reader job `114141422568`. Log имеет 674211 UTF-8 bytes и SHA-256
`fdf815da3d3a2f0c301b4b36740aac2c29c3de79f0c50fe536281d7aac8bd7f0`.

Comparison summary сообщает 104 найденных literal children (два baseline,
51 fault в двух режимах), отсутствующих или лишних children нет. В console
дошли 87 individual `LITERAL_CHILD_OPERANDS`, 17 явно отмечены omitted.
Все QUALITY_ARTIFACT, CONTRACT_ARTIFACT и Legacy case summaries также остались
за этой очередью. Полный selected ledger сохранён в существующем artifact;
его отсутствие в доступном console не превращается в успешное review.

На этом же log проверены 12 healthy recovery cases и все 43 правильных пары
case/guard. Critical baseline имеет 61 entry и один failure; этот reader slice
не меняет оценку результатов и не объявляет mutation kills для critical.

## Изменение

1. Уже прочитанные небольшие QUALITY_ARTIFACT, CONTRACT_ARTIFACT и
   LEGACY_ARTIFACT_CASE records идут после critical/recovery outcomes перед
   большими V2/literal ledgers. Из прежнего хвоста они исключаются, поэтому
   каждая такая запись сохраняется один раз.
2. Для этих трёх типов добавлены отдельные omission counters. Прежние counters
   critical/recovery/literal/V2 сохраняются.
3. Диагностический console budget увеличен с 384000 до 768000 UTF-8 bytes,
   чтобы разместить individual literal receipts вместе с новым healthy
   critical evidence. Budget и фактически напечатанные record bytes указаны
   в финальном console receipt. Прежний резерв 512 bytes для receipt остаётся.

Это ограничение **диагностического транспорта**, не token/source/schema gate
продукта. Оно не ограничивает ответы get_docs_context, source facts, размеры
retrieval outputs или acceptance quality. Прежние 6144-byte/800-token/3-source
product ceilings не возвращаются.

Никакой источник не читается дополнительно: меняются только порядок
имеющихся records и размер console представления. Individual source receipts,
hashes, current child outcomes и исходные bounded envelopes не пересчитываются
и не заменяются aggregate PASS. Все первоначальные reports и complete selected
ledger сохраняются. Per-record bounds, failure trace limits, omission
semantics, issue detection, return code и gate commands не меняются.

Появление всех необходимых records на следующем SHA ещё нужно проверить:
дополнительный объём сам по себе не является доказательством полноты вывода
или correctness результата. Непоместившиеся записи будут честно отмечены.

## Manifest и проверка

- Path `scripts/summarize_acceptance_artifacts.py`; mode `100644`.
- Base blob `5b4f0388f5f828f8f7c259ff8b3deb755323d636`; proposed `2ddc2fc70476ef522bb8225c504e2b7fb64ef9bc`.
- Proposed source SHA-256 `23c63ab0ab80dba4a4737cb86f78a34fa7a2d09619d36bff78fea1230b128322`; 845 physical lines.
- Шесть обратных замен восстанавливают base побайтно.
- Новых CI workflows, artifact downloads, pytest/runtime/provider calls,
  source acquisitions или зависимостей нет.
- Static review и exact readback отдельно; own next-runtime result pending.
