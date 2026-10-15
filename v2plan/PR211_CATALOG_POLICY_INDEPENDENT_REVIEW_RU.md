# PR #211: независимый review отмены фиксированного catalog ceiling

Дата: 2026-10-08. База: `df9b682fdd13d8f4d1c5bff6cc4bfc0286e5f8ce`.
Reviewer не является автором policy slice.

**Вердикт: APPROVE** изменения catalog acceptance policy согласно последнему
явному указанию владельца: отказаться от фиксированного лимита и стремиться к
минимуму. Это отдельное согласованное решение, не объявление старого 6144 gate
пройденным и не автоматическое разрешение менять прочие gates.

## Scope и соответствие разрешению

Проверен точный diff трёх файлов:

- `tests/docs/test_mcp_token_footprint.py` — только тело прежнего terminal test;
- `v2plan/CURRENT_WAVE_DECISIONS_RU.md` — уточнение пункта 3 и новое датированное
  решение владельца;
- `roadmap/35_STRUCTURED_TRANSPORT_AND_COMPACT_MCP_SURFACE.md` — catalog budget
  section и связанные measurement/acceptance bullets.

Прочитан также frozen author report `PR211_CATALOG_POLICY_REVIEW_RU.md`;
его границы локальной проверки и pending normal/advanced CI указаны корректно.

Сняты default catalog target 6 KiB/6144 и hard 10 KiB. Нового числового ceiling,
включая ранее предложенные 7168, нет. Измерения и review ненужного объёма остаются;
рост должен объясняться полезным контрактом. В policy явно сохранены input/output
validation, discoverability/guidance, source bindings, consent, отсутствие edit
authority и normal/advanced distinction.

Отдельный output-schema gate **<1000 bytes** остаётся. Retrieval/work/read/acquisition
budgets, gold, остальные CI/downstream/client gates и запрет исправлять deferred
retrieval не отменены. Исторические отчёты не переписываются в fictitious PASS:
новое датированное решение явно задаёт текущую policy.

## Почему новый test не является пустым gate

Прежний node ID сохранён для стабильного diagnostic/acceptance inventory:

`tests/docs/test_mcp_token_footprint.py::test_default_public_catalog_meets_task35_hard_and_target_budgets`.

Его историческое имя пояснено комментарием; оно больше не означает действующий
catalog byte ceiling. Вместо сравнения с новым magic number проверяются:

- Ровно три реальные default tools в прежнем порядке: get_docs_context,
  prepare_docs, docs_status; missing/duplicate measurement rows не допускаются.
- Total tools/list bytes равны actual canonical serialization, per-tool totals,
  description bytes и input/output schema bytes совпадают с их actual encoding.
- Сумма per-tool totals плюс brackets/commas равна whole-list size. Output schema
  уже входит в each-tool total и не прибавляется второй раз.
- Normal input содержит ровно семь текущих public fields; output — object с
  required status без detailed union. В существующем advanced mode доступен
  nullable patch_context и его first output branch совпадает с normal output.
- Detailed advanced output больше normal output; normal output по-прежнему
  меньше **1000 bytes**.
- Остальные default footprint validation rules продолжают выполняться.

Это measurement/surface regression test, а не машинное доказательство абсолютного
минимума возможного schema. Практическая минимизация остаётся engineering review
при сохранении смысла и contract constraints, как и запросил владелец.

## Measurement API и другие limits

Прочитан настоящий `docmancer/docs/mcp_footprint.py`. Он не изменён: optional
`max_tools_list_bytes` в `validate_footprint_report` уже имел default `None`, а CLI
`--max-tools-list-bytes` не задаёт default cap. Сохранение явного caller-selected
local diagnostic limit не восстанавливает default CI/merge requirement.

Неприкосновенны report schema/tool-count validation, bounded report size,
duplicate transport-payload refusal, largest-fields bound и bytes/4 estimate
с пометкой «not provider usage». Отмена catalog ceiling не отменяет эти controls.
Прежний test explicit optional local gates, включая `max_tools_list_bytes=1`,
сохранён AST-exact.

Nullable/schema validation и normal/advanced semantics дополнительно остаются в
неизменённых schema-equivalence, guidance, MCP boundary и installed suites.
Ни новый measurement assertion, ни этот review не заменяют их runtime результат.

## Независимая статическая проверка

- Все **8** исходных test functions, arguments и decorators сохранены.
- Ровно одно test body изменено; все остальные **7** и все прочие module AST nodes
  равны `df9b682f`.
- Module diagnostic hash остаётся
  `34b40986931303bc312678f8e64bb6b3f31129baa6b402508b5181f7e4518833`, совпадает с
  действующей manifest entry. Изменение inventory не требуется.
- Measurement API, `.github/workflows` и deferred retrieval analysis побайтно
  совпадают с базой.
- Четыре source/test files ранее reviewed 6918-byte compaction slice не менялись
  ради этой policy. Canonical размер остаётся измерением, не новым ceiling.
- AST parse и `git diff --check` выполнены; repository imports, pytest,
  subprocess test harnesses, SDK/clients и dependency installations не запускались.

Blocking findings нет. Последующий normal CI должен подтвердить новое тело test
и неизменённые required gates на общем SHA. Согласованная отмена одного числового
catalog требования сама по себе не делает весь PR готовым к merge.

## Frozen hashes

| Файл | SHA256 |
|---|---|
| `tests/docs/test_mcp_token_footprint.py` | `9492eef60963011161b43da2f9c8c06d2d22c8c1aa574fefd05e7a997f6c94a7` |
| `v2plan/CURRENT_WAVE_DECISIONS_RU.md` | `7fa62f6b4aebc6fa922bf4b6ae35ccc94d10627b62bd54cd5aa01a3e07c11411` |
| `roadmap/35_STRUCTURED_TRANSPORT_AND_COMPACT_MCP_SURFACE.md` | `09b619fbfbd38d61720af0fb578b278344f742f556427603b5e6446b9cb2416e` |
| `v2plan/PR211_CATALOG_POLICY_REVIEW_RU.md` | `849407ab83423d8545e7d54ee3145f37d62b884427d30b1f9fa63f58932fde91` |
| Неизменённый `docmancer/docs/mcp_footprint.py` | `c997df98f3088f7adbe3820a6828ab8ad6df00080c685d64f887eb8f7fe1e77c` |
