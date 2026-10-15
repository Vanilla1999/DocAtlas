# Review перед публикацией partial dictionary exit

2026-10-06. **SCOPED APPROVAL**, не full exit/release/quality acceptance.

Два независимых review: технические guards и checkpoint/next-slice contracts.
Обнаруженные блокеры исправлены и независимо воспроизведены после исправления:

- Cached selection теперь учитывает текущие mandatory project/module/version/path
  requirements; несовместимые bindings не расширяют scope.
- Explicit consent/confirmation/nondelivery blocks сохраняются на projector/public
  boundary, не обходятся partial-context recovery и не доставляют sources.
- Fresh и cached paths нормализуют serialized requirements; malformed contracts
  fail closed, а не crash или silently unconstrained retrieval.

Последний независимый прогон: **274 passed** (228 новых + 46 existing technical),
24 scope probes и 16 malformed-contract probes passed. Valid partial context остаётся
без answer/edit authority. Existing tracked tests/eval/workflows не менялись.
Прежний quality report FAIL сохранён; пороги не снижены.

Владелец согласовал исключить из commit gzip raw archive
`archives/p2-real-mcp-alias-ablation-v1.json.gz` (~33 MB). Он остаётся локально,
без удаления. Compact analysis/report публикуются; full raw evidence в fresh clone
отсутствует. Отдельное хранилище не настроено.

Original 416-file manifest сохранён как исторический pre-review snapshot.
Current post-review pins: `archives/dictionary-exit-reviewed-source-manifest.json`.

После commit/push текущего среза следующий bounded slice — default-read reference
binding/ranking и structural answer units. Owners должны согласовать signatures,
не менять common projection/qualification параллельно, сохранить IDs/hashes/spans,
и не делать structural segmentation универсальным доказательством proposition.
