# C: независимый статический patch/workload preflight V3

2026-10-12. Проверены A_IMPLEMENTATION_RU.md, V3_PRODUCT.patch, actual `original_body_discovery.py`/`ordinary_body_context.py`, соответствующие baseline copies, run_v3.py, PROTOCOL_V3_RU.md, EXECUTION_CONFIG.json и EXECUTION_CORPUS.json. Дополнительно прочитаны reused run_public.py/integrity, source admission, selector и fixture/host helpers. Только чтение, текстовый `diff -u` и `sha256sum`. **Никаких runtime/import/compile/AST/tests/models/host**, применения patch или product edits. Holdout labels не раскрываются; case/oracle/FREEZE не менялись.

## Вердикт до runtime

**BLOCKED_PENDING_PRE_INFERENCE_FIXES:** новый source scalar fallback неполно проверяет operator/sign context на краю окна; runner недостаточно строго проверяет false authority. Также конфигурация пока не является execution freeze (`frozen_files={}`). Это конкретные требования до нового runtime, не основание менять inputs или ослаблять oracle. После исправлений требуется обновить implementation/runner identities и статически проверить исправленный delta. B final adapter review остаётся отдельным и не закрыт этим документом.

## 1. Patch identity и baseline comparison

Сравнение обоих actual файлов с `baseline/docmancer/docs/domain/` даёт именно hunks V3_PRODUCT.patch; дополнительных изменений в этих двух файлах вне patch не обнаружено. Нормальные exit=1 текстового diff означают наличие показанного delta, не test FAIL. Patch не применялся повторно.

SHA256 проверенной версии:

| Operand | SHA256 |
|---|---|
| V3_PRODUCT.patch | `6cbf49d65acbdc60b731cb426f85c97d839ac12b0c8d0d9fc4947beff82fcf7c` |
| A_IMPLEMENTATION_RU.md | `c26e62c29f59f7efff702f7b67668c1d3183d352fb92a6c64f863f996e7b3038` |
| actual original_body_discovery.py | `23d8bcb2c45b6007b2bfbe2947ef58a68e107f409761fd16c2fb4df496ecd20c` |
| baseline original_body_discovery.py | `b80209618be43b78bd501abde5e77a04f09e5a26cb4b0e52840ebec8f14ffc14` |
| actual ordinary_body_context.py | `89cc15c2ef2b4dc2a59d8359f1f7e27cb8750ec207eb0b28802b89ae3fb0217f` |
| baseline ordinary_body_context.py | `b069de048f7ae4d3e64b87710a0c709671f0e3e47f4d5e3da12d10dd37c5eedb` |
| run_v3.py | `7b95d47a8a575576d108fd59f6b1255c340112556379a080ee6b764c7c138089` |
| PROTOCOL_V3_RU.md | `a2c0bee43e569626f508ea05c5fa6238ab748391ed4eece14e528ac2036bd821` |
| EXECUTION_CONFIG.json | `9ace0eb899a7ba978ba400b393d66d5e62c44b661aa2ff3f9ab70062bee79e9c` |
| EXECUTION_CORPUS.json | `a7fcf818dfd5580f45e77b17045e541924dbaab323771744756d199865aa2a86` |
| исходный review/FREEZE.json | `bab51b5a6c3953454773b69ee6c791f75e387ca891b875b76029e8366e11b082` |

Это baseline V2 рабочей реализации, не чистый HEAD/default release. Полный repo delta/CI/runtime parity этим сравнением не доказываются.

## 2. Что статически сохранено в A

- Host env захватывается один раз внутри eligible original synchronous scope; новый режим не включается wire/candidate флагом. Scope eligibility, explicit lookups и teardown/receipt clearing в baseline и actual одинаковы.
- DefaultOff не активирует policy/scalar candidate machinery. B1 policy predicate остаётся true, а scalar predicate false: после отсутствия старого B1 witness новый helper немедленно возвращает None. Ordinary route продолжает прежний numeric subset filter.
- Factor `_source_valid_body_blocks` сохраняет native binding, structural owner и unresolved-name predicates; старый numeric set/blocks/order/witness поля сохранены. Порядок pure numeric-term вычисления относительно source gate изменён, но для действительного string question outputs прежних веток статически эквивалентны. Это не измеренный runtime parity.
- V3 сначала возвращает старый B1 witness, если он есть; новый fallback вызывается только при его отсутствии. Следовательно запрет non-scalar expressions относится к **добавочному fallback**, не глобальной отмене прежних exact routes. Эту ранее отмеченную трактовку необходимо сохранять в результатах.
- `_scalar_label_pairs` берёт maximal `\S+` tokens и требует whole ASCII unsigned decimal; decimal comma не разрезается. Query все digit-bearing tokens по `isdigit()` должны совпасть с целыми accepted scalar spans. Range/identifier/path/exponent/attached sign/декорированный scalar/лишнее numeric occurrence закрывают fallback. Query pairs координатно привязаны к неизменённому whole question, поэтому query window-edge проблемы здесь нет.
- Source scalar+label ищется в masked body block; matched label whole-word/casefold, не словарь единиц. Raw-block pair equality и исходная complete substring equality предотвращают искусственную пару от masking. Проверка предыдущего char и продолжения label предотвращает срез **внутри** composed scalar/слова. Rows/list items/heading masks берутся из прежнего `_body_blocks`; никаких cross-source/cartesian unions не добавлено.
- Witness сохраняет точный raw slice, document coordinates, native receipt и pair spans; `relevance_unassessed`/`numeric_condition_unassessed` не дают authority. Caller `literal_context_admission.py:288–300,368–391` сохраняет canonical qualifier/source gates, missing-hard-exact/body-window, failed original qualification и `coverage_credit=False`. Generic reason/body_witnesses допускают новый kind; закрытого kind-switch в прочитанном пути нет. Final delivery остаётся неподтверждённой до public output.

## 3. Обязательный A defect: source operator/sign context вне slice

**A-SOURCE-EDGE-01 — CONTRACT BLOCKER.** `ordinary_body_context.py:308–310` пересчитывает raw pairs только на `raw[source_offset:end]`. `_scalar_label_pairs:273–275` видит соседние operator/sign tokens только внутри переданной строки. Проверки `:324–331` сверяют непосредственно соседние символы с whitespace и продолжением слова, но не восстанавливают соседние maximal tokens за границей source block/window.

Статическая иллюстрация, **не новый case и не исполненный тест**: raw prose содержит `Значение - 9 часов осталось.`; admitted immutable window начинается с `9 часов осталось.`. Скаляр начинается после настоящего пробела, label имеет корректный конец. Masked/raw-window parsers совпадут и substring bound точен, однако `-` перед окном не виден. Поэтому signed expression может стать unsigned scalar-label candidate вопреки принятому запрету знаковых/операторных конструкций. Аналогичен operator сразу за концом window. Внутри полного raw prose parser его отверг бы.

Это не доказательство, что конкретный frozen public вопрос породит такое окно, и не claim о forged source/hash: defect в заявленной source syntax boundary. Native receipt/owner/hash подтверждают подлинность окна, не отсутствие sign/operator за его краем. Прочитанный `_checked_raw_body_window:227–240` допускает вложенное exact window и не даёт invariant, что оба соседних whitespace tokens исходного документа уже включены. Source pipeline нельзя объявлять автоматически устраняющим этот разрыв.

**Требуемое исправление до runtime:** проверить lexical sign/operator/maximal-token context по оригинальному документу/исходному структурному body operand, сохранив witness строго внутри разрешённого окна; не расширять delivered source и не заимствовать evidence извне него. Если соседний context невозможно подтвердить, fail closed на этом новом fallback. Допустима иная локальная реализация с доказанным original boundary invariant, но одного char-whitespace guard недостаточно. Не менять старый ordinary/B1 parser ради этого исправления. Обновить A_IMPLEMENTATION_RU.md: текущая фраза об original boundaries не закрывает operator tokens за slice.

Остальные parser ограничения остаются честно узкими: bare `1.4 label` синтаксически неотличим от semantic version; matching label не доказывает единицу/условие. Это accepted unassessed risk, не самостоятельный source-policy bypass и не повод добавить benchmark dictionaries.

## 4. Обязательный runner authority defect

**RUN-AUTH-01 — SOURCE/AUTHORITY STOP GUARD BLOCKER.** `run_v3.py:88` полагается на reused `run_public.py.integrity`. Последний (`:78–79`) отклоняет только `answer_supported is True` или `edit_ready is True`; не проверяет `answer_available` и не требует строго всех трёх `is False`. Поэтому возможный product authority regression не остановит runner и его packet уйдёт в base host. `integrity_errors=[]` не является доказательством обязательных false-authority flags.

Исправить локальный coordinator guard **до host**: строго `answer_supported is False`, `answer_available is False`, `edit_ready is False`; несоответствие — SOURCE_POLICY_DEFECT/BLOCKED и stop. Это не product edit и не изменение source expectations. B исправляет свой adapter guard отдельно; это не защищает public arms/base host и не заменяет runner fix.

Reused integrity также не проверяет public envelope hash, declared line span, duplicate evidence IDs, `authority=source_of_truth` и pool project identity в полном объёме. Сам public product validator остаётся реальным и не заменён mock; однако название `integrity_errors=[]` нельзя расширять до независимого full-operand PASS. Эти operands необходимо отдельно проверить по сохранённому raw перед quality verdict/при source-policy stop. Усиление saved operand audit допустимо без новых cases/подмены retrieval.

## 5. Runner/workload и execution freeze

Статическое перечисление конфигурации согласовано с protocol:

- 9 frozen independent/control cases + 10 дополнительных = 19 вопросов, 3 public arms = **57 context attempts**.
- Corpus даёт print_billing/directed_routes/legacy_priority; additional docs добавляют ceramic_firing/tidal_ferry/main/unrelated = **7 prepares**.
- 7 synthetic ×2 + 3 known numeric ×2 + Q16/Q46 B1 ×1 + OLD_OWNER/OLD_UNRELATED V3 ×1 = 24 base-host attempts; 4 citation attempts = **28 host**, **0 neural**. Это planned, не observed counts.
- Citation IDs фиксированы до outputs: V3CAL01/V3H01 parent V3; Q16/Q46 parent B1. В прочитанном config mapping Q16/Q46 уже есть, остальные берут default V3. Каждый имеет base-host на том же parent. `generate` использует captured public result, не private pool/oracle; citation packet использует тот же capture.
- `experimental_candidate_selector(observe)` возвращает None и не изменяет candidate objects. Shared selector `:47–49` сохраняет original list, значит selection delta нет. DefaultOff не вызывает observer по `policy_candidate_admission_active=false`, поэтому пустой `pools` для этой ветки — ожидаемое отсутствие наблюдения, не доказательство пустого universe; не требовать одинакового observer count across arms.
- Corpus markdown content соответствует читаемым frozen documents; priority family сохраняет пять документов, old questions и docs/store.md для unrelated сохранены. Дополнительные scope/version metadata diagnostics игнорируются при public request: actual scope project/unversioned; это не requested-version test.
- Fixture write_project пишет UTF-8 bytes; реальные prepare/SQLite/MCP/storage используются. `patch.dict` из unittest.mock меняет лишь host environment, не retrieval/qualification/storage/validation. Generation/project fixture сохраняется для всех arms. Observer проверяет pool bytes и сохраняет original/excluded, но new admitted pools across arms закономерно могут различаться; не требовать V2 common admitted pool equality.
- Consumed RUN_RECEIPT запрещает автоматический replay. Host helper single attempt/exclusive output, raw/messages/request/receipt сохранены; timeout UNKNOWN не восстанавливается и не ретраится. Whole driver stop при UNKNOWN не разрешает inference следующих missing attempts сам по себе.

**RUN-FREEZE-01 — обязательный незавершённый checkpoint:** config пока содержит `frozen_files={}`. Runner `:131–134` не проверит ни один hash. До первого runtime нужен непустой exact freeze с source/patch/runner/reused helper/adapter+prompt/corpus/cases/contract identities и исходным C manifest. Включить реальные operand files, а не только сохранённый SOURCE_IDENTITY как утверждение об этих files. Hash конфига сохранять во внешнем SOURCE_IDENTITY/manifest без self-reference; RUN_RECEIPT сохраняет неизменный config. Проверенные здесь hashes — ещё не окончательные после обязательных исправлений A/runner/B.

Сейчас modules `v2`/`host` загружаются на top level runner **до** `main()` hash check. Прочитанные imports не запускают public/models/host inference, но для строгого code freeze предпочтительно проверять identities до загрузки reused code. Не объявлять пустой/поздний hash check pre-runtime защитой от любой модификации imported helper.

### Дополнительные runner robustness ограничения

- `sources(result):123` использует `.get('sources', [])`, а не `... or []`; explicit `sources=null` допустим в frozen empty-source нормализации и вызовет TypeError до соответствующего host. При planned base host для negatives/empty positives нужно поддержать null как empty без fabrication. Это устранение schema handling, не evidence rescue. Отсутствующее поле уже обрабатывается.
- `planned_workload` не сверяется с config lists, ceiling 8/80/40 шире exact 7/57/28; runner должен записать observed counts и не использовать оставшийся ceiling как разрешение дополнительных cases/attempts. В текущем прочитанном config арифметика совпадает.
- Не проводится independent expected/indexed paths equality check перед первым public call: `index_project` возвращает эти поля. Partial preparation нельзя назвать полной seven-project подготовкой. До calls проверять finite indexed set/catalog/document hashes или явно останавливать malformed preparation, а не объявлять отсутствующий source semantic empty success.
- Citation prepare не завершается на пустом/неподдерживаемом exact packet автоматически: B будет reviewed отдельно. Не заменять frozen citation case другим успешным ID после outputs. Если PREPARE_BLOCKED, attempt NOT_RUN с честным accounting; нельзя объявить план 28 фактическим результатом.
- Base schema validation/independent semantic review не выполнены driver-ом: host receipt EXECUTED лишь endpoint completion, не корректный JSON/answer. Final reviewer оценивает raw отдельно.

## 6. Oracle preservation и итоговые границы

Ни scalar-label witness, ни restored pool не переписывают frozen positive/negative ожидания. Все 7 synthetic cases сохраняют исходный question/corpus и independent criteria; strict empty-source FAIL остаётся FAIL даже при честном отказе host. Exact-witness доставка, alternative semantic entailment и host sufficiency/refusal считаются отдельно. Здесь per-holdout labels/ожидаемые ответы не публикуются.

Full multifacet recall с contributing nonnumeric blocks A не реализует и заранее не обещает; частичную восстановленную numeric delivery нельзя назвать complete. Known V2 diagnostics не становятся новым independent holdout. Default parity по этим public arms — ограниченный fresh slice, не full40/50/installed-stdio/client/production PASS. Не доказаны arbitrary ACL/consent/version denial или универсальная numeric/relation safety. Mini/X отсутствуют обоснованно; bounded-selection research требует отдельного checkpoint.

**До исполнения:** закрыть A-SOURCE-EDGE-01 и RUN-AUTH-01, финализировать RUN-FREEZE-01 и B final review; исправить empty-source schema handling/prepare-set guard либо явно зафиксировать blockers до расходования host. После этого допустимо только разрешённое узкое public experiment, без обещаний default/full multifacet. Этот документ не даёт собственного runtime authorization.
