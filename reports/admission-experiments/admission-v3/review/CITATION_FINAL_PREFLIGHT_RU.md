# C: citation v3-2 — независимый финальный статический preflight

2026-10-12. Прочитаны исправленные `citation_adaptation.py`, `B_CITATION_CONTRACT_RU.md` и реальные production source-envelope/serializer/validation operands. Использован только source text read/grep и `sha256sum`. **Runtime/import/AST/compile/tests/product/models/host не запускались.** Runner/A окончательный consolidated review не заменяется этим документом. Frozen corpus/cases/oracle/FREEZE не изменялись; holdout labels авторам не раскрываются.

## Решение по B

**STATIC_ACCEPTABLE_WITH_RECORDED_LIMITS:** прежние B1 hash-schema и B2 falseauthority blockers исправлены. Явный null sources обработан без fabrication. Нового обязательного дефекта в исправленной envelope serialization/authority/null-source границе не найдено.

Это не runtime PASS, не подтверждение совместимости каждого будущего public packet с exact-span adapter и не semantic/citation-quality PASS. **Запрашивать runtime сейчас нельзя:** A-SOURCE-EDGE-01 ещё исправляется; runner guards, итоговые identities/config freeze и consolidated review ожидаются отдельно. Этот документ не даёт runtime authorization.

## Проверенная identity

Contract `citation-coordinates-v3-2`; adapter ID `citation-adaptation-v3-2-envelope-authority-empty`. ID входит в prepared/extraction и проверяется extractor. Symbolic ID сам по себе не подпись/code hash.

| Файл | SHA256 фактически прочитанной версии |
|---|---|
| `admission-v3/citation_adaptation.py` | `ff5be53e7358e56f9bee119833bb2014348f1c19740e4068ba291fcedd3915ed` |
| `admission-v3/B_CITATION_CONTRACT_RU.md` | `53083e9e9118a436859ac162a3624ff3fac897ce73efcd94fed0dee88bf33cd5` |
| `docmancer/docs/application/_model_visible_docs_support.py` | `91b603426a36f4cbadc4daacbac7db1bf9170129f9e20011b1b834a9fa1d689f` |
| `docmancer/docs/application/model_visible_projection_helpers.py` | `636128154d92170ac6e9623747cd1117366e64847e3f384a4447ca579884edfd` |
| `docmancer/docs/application/model_visible_projection.py` | `6e822a4db485c4ca4f36ac3d3ae03c4dbec559a8a378e5aa2d005b168f3deb64` |
| исходный `review/FREEZE.json` | `bab51b5a6c3953454773b69ee6c791f75e387ca891b875b76029e8366e11b082` |

Prompt не импортировался/не исполнялся. Его literal source входит в adapter hash; отдельный SHA256 реально отправляемого UTF-8 system prompt и полного model messages фиксирует coordinator до host в окончательных artifacts. При последующем изменении любого operand этот verdict относится только к приведённым identities.

## 1. Production envelope operands и serialization

Статическая сверка выполнена непосредственно с production, не по ошибочному предположению о snippet SHA:

1. `_model_visible_docs_support.py:42–50` формирует пять ключей `path/section/content/snippet/version` и хэширует `canonical_projection_bytes(material)`.
2. `model_visible_projection_helpers.py:197–198` сериализует `json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')`.
3. `model_visible_projection.py:744–750` связывает public hash с canonical projected_source и digest сохранённого bound source.
4. Исправленный adapter `_source_envelope:35–49` использует тот же **порядок Python-or operands**, без trim, str coercion или замены null:
   - `path | source | url | source_url`;
   - `heading_path | title`;
   - `content | display_text`;
   - `snippet | code`;
   - `version_binding | version | requested_version`.
5. Adapter `_digest:30–32` использует те же JSON options и UTF-8 через `_hash`. Пять ключей сохраняются, включая null; sorting делает source insertion order несущественным. Production здесь не использует `default=str`; adapter тоже его не добавляет.
6. `prepare_packet:83–89` требует полное равенство projected_source/public item и сравнивает public `content_sha256` с envelope **из snapshot original source**, не из изменённого projected snippet/path/section.

**Hash operands теперь согласованы статически.** `_docs_source` имеет отдельные display fallback/trim rules, но adapter правильно не использует их вместо `_source_digest`. Full-document SHA по reference source + allowlist, public envelope SHA и client `text_sha256` разделены. Envelope operands/digest сохраняются в sidecar, не отправляются host как новый источник. Production digest не доказывает семантику или соответствие любого другого metadata operand.

## 2. False authority, sources=null и request/source binding

- `prepare_packet:65–67` требует `answer_supported is False`, `answer_available is False`, `edit_ready is False`. True/None/0/пропущенное поле не проходят: прежняя недостающая `answer_available` проверка закрыта.
- `:76–79` принимает только list либо explicit null; null превращается в пустой list **только для model packet**, не мутируя исходный public_result. Fragments остаются пустыми, источники не придумываются. Empty list также поддержан.
- Missing `sources` вызывает KeyError и блокирует prepare, а не трактуется как успешный empty packet. Это fail-closed, но ниже отмечена неточность универсального ValueError обещания.
- Unique nonempty evidence ID, exact projected_source equality, full document hash/allowlist, canonical path, actual project/generation/unversioned scope и исходный request/question связываются до подготовки. Project identity следует existing local SHA256 абсолютного project-path string.
- Exact schema требует `snippet == ref.text == raw_document[a:b]`, offsets только type=int и валидный range. Это deliberately narrow: не ищется подстрока и не выравнивается trimmed/merged source автоматически. Невалидный span/allowlist/hash нельзя исправлять изменением source bytes.
- Full document/envelope сохраняются лишь в sidecar. Model получает question, public text/IDs/provenance и helper line coordinates, без oracle, scores, native pool или hidden document remainder.

Проверка EXECUTED/integrity_errors/state equality остаётся чтением saved producer assertions. Adapter не переисполняет production validators/SQLite и не доказывает fresh ACL/consent/version denial. Планируемые coordinator stop-checks envelope/parent lines/duplicate/source authority/pool identity важны и проверяются отдельно в consolidated runner review, не объявляются уже принятыми здесь.

## 3. Extraction и неизменность claims

Статически сохранены необходимые fail-closed свойства:

- Raw bytes принимаются как bytes, хэшируются без repair; strict JSON object, duplicate keys и invalid constants отвергаются.
- Status/claims/missing и source ID/offset shape проверяются. Bool/float не могут быть offsets; диапазон непустой, snippet-relative code points.
- Extractor выбирает `snippet[start:end]`, сверяет абсолютную raw-document substring и document SHA. Нет fuzzy quote поиска, newline/Markdown normalization, concatenation rescue, новых фактов или повторной генерации.
- Quotes/UTF-8 hash, document char ranges, snapshot-encoding byte ranges и LF line ranges вычисляются из неизменного текста. Последние не гарантируют original file byte offsets при prior decoding/BOM/newline conversion; contract это честно оговаривает.
- Original claim text и parsed generator output сохраняются; все citations проходят либо весь extraction REJECTED. `semantic_entailment=INDEPENDENT_REVIEW_REQUIRED` остаётся обязательным.
- При пустых fragments affirmative complete/partial claim не сможет указать допустимый source ID. Insufficient с пустыми claims и непустыми missing может быть EXTRACTED; это лишь валидная форма, не доказательство честного отказа или решения positive.
- `save_artifacts` использует exclusive paths и сохраняет raw отдельно от extraction. Partial artifact write не разрешает новый host attempt. Coordinator дополнительно сохраняет транспортный response/request/receipt и packet/messages до host.

## 4. Остаточные ограничения, не скрытые как PASS

1. **Exact-span compatibility NOT_TESTED.** Production projection может выдавать exact subspan/trimmed/merged packet, не равный reference whole text. Такой packet данный adapter отклонит. Это PREPARE_BLOCKED/NOT_RUN по заранее фиксированному workload, не исправление bindings после outputs и не повод заменить выбранные citation IDs. Generic client adapter не объявляется совместимым со всеми product sources.
2. **Exception taxonomy неточна:** B contract §Reusable API обещает ValueError для любого invalid packet, но отсутствующий required key даёт KeyError, malformed item может дать TypeError. Все такие ошибки блокируют подготовку, source rescue не возникает. Для текущего coordinator driver общий Exception stop достаточен; потребителям нельзя обещать единый ValueError API без отдельного исправления/уточнения. Это не новый mandatory evidence-boundary blocker.
3. **Parent metadata не вся проверяется самим adapter.** Public `authority`, line_start/end, source class/catalog operands не становятся валидными от того, что попали в provenance. Полный before-host stop audit coordinator/reviewer обязателен. `integrity_errors=[]` и prepared hash — не trusted signature.
4. **Новый prompt/schema вмешивается в generator behavior.** Base vs coordinate pair на одном public parent измеряет generator+client contract, не quote repair прежнего raw ответа, не ranking/admission gain. Source hashes/байты должны совпасть across pair; auxiliary offsets не новые evidence.
5. **EXTRACTED ≠ semantic PASS.** Точная citation может не поддерживать claim, скрывать условие/отрицание, перепутать owner или покрывать лишь numeric facet. Independent final review проверяет исходный question и весь frozen oracle, отдельно от witness/citation адресации. Citation-free refusal не засчитывается positive completeness.

## Итог

Предыдущие B hash/authority blockers закрыты **по статическому source comparison**, explicit null handling добавлен корректно. Исправленную B identity можно включить в окончательный pre-inference freeze. Из этого не следует разрешение общего runtime: A source-edge и итоговый runner/consolidated review ещё pending. Новых cases/labels/oracle amendments не требуется и не выполнено.
