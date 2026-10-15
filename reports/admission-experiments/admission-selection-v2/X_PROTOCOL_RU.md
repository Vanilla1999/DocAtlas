# Conditional XProvence pair — frozen before X inference

Основание перехода: primary Mini reduced Q16 submitted proxy5614→1653, но remaining public snippet911proxy tokens ради коротких диагностических полей; Q46 remains519snippet tokens. Проверка пользы дополнительного pruning оправдана только как два известных diagnostic случая, не holdout/generalization.

Workload: тот же Q16/Q46 captured native pool (10+6windows),16joint FP32 forwards,2real public selection calls на уже существующем main store/generation,4hostrequests. Новых prepares/weights нет. Total bound56context/40host/56forwards/7prepares. Первичный k=2 не меняется.

X-rank: native score top2 → существующий public packing/projection и validators → frozen generator.
X-prune: **тот же X-rank публичный parent packet, те же выбранные native IDs**; отдельный client-side exact-span view, не модификация public DTO. Masks происходят из того же native joint forward. Source validation parent сохраняется. Поэтому это product-integrated ranking + adapted client pruning, НЕ native pruned DTO или deployment proof.

Общее deterministic правило представления pruning:
- только selected native окна участвуют в masks;
- слова не декодируются заново, только original source spans;
- public presentation expansions вне selected native windows сохраняются целиком (их этот forward не оценивал);
- все Markdown heading lines внутри parent snippet сохраняются для structural owner, без oracle rescue;
- внутри selected windows сохраняются author retained sentence spans threshold>.3 + sentence rounding>.3, остальные байты опускаются;
- непрерывные runs объединяются только при overlap/adjacency; раздельные runs получают method-neutral excerpt IDs, исходный path/scope/version/line metadata parent сохраняется, sidecar binds parent/source absolutechar intervals/hash/text;
- никакой полной «цитаты» через omission gap и никакого fabricated public envelope. Mapping unproven =>blocker, не decode fallback.

X-rank model sees обычные public source IDs/text/provenance. X-prune sees exact excerpts/source IDs/provenance, без scores/gold facts. ID framing и closure добавляются в стоимость. Native selection не меняется после host outputs; no retry/repair. Source-policy/semantic facts/owner relations/exact citations and cost judged separately. Это не полное воспроизведение статьи; лицензия прежнего checkpoint не переоценена.
